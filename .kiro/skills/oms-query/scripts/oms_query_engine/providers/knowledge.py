"""KnowledgeProvider - OMS 本体知识检索

从 OMS本体知识文件.json 加载业务本体图谱，支持：
1. 按名称/别名模糊搜索节点
2. 按类型（label）列举节点
3. 按关系遍历（给定节点，找关联节点）
4. 按 API 路径查找 APIEndpoint
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.query_plan import QueryContext


# 知识文件默认路径（相对于项目根目录）
_DEFAULT_KNOWLEDGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..",
    "docs", "OMS本体知识文件.json",
)

# 有效节点类型
VALID_LABELS = {
    "System", "Project", "Module", "BusinessObject", "BusinessProcess",
    "Rule", "State", "APIEndpoint", "SourceArtifact",
}

# 关系类型
VALID_RELATION_TYPES = {
    "composition", "dependency", "flow", "action", "mapping",
    "constraint", "ownership", "query", "mutate",
}


class KnowledgeIndex:
    """本体知识内存索引（单例懒加载）。"""

    _instance: KnowledgeIndex | None = None

    def __new__(cls, knowledge_path: str | None = None):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._loaded = False
            cls._instance = inst
        return cls._instance

    def __init__(self, knowledge_path: str | None = None):
        if self._loaded:
            return
        self._path = knowledge_path or os.path.normpath(_DEFAULT_KNOWLEDGE_PATH)
        self._nodes: dict[str, dict] = {}          # id -> node
        self._by_label: dict[str, list[str]] = {}   # label -> [id]
        self._name_index: dict[str, list[str]] = {}  # lowercase token -> [id]
        self._api_path_index: dict[str, str] = {}    # path -> id
        self._relations: list[dict] = []
        self._outgoing: dict[str, list[int]] = {}    # node_id -> [rel_index]
        self._incoming: dict[str, list[int]] = {}    # node_id -> [rel_index]
        self._load()
        self._loaded = True

    def _load(self):
        """加载并构建索引。"""
        with open(self._path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        ontology = raw.get("ontology", {})
        business = ontology.get("business", {})
        nodes = business.get("nodes", [])
        rels = business.get("relationships", [])

        # 索引节点
        for node in nodes:
            nid = node.get("id", "")
            if not nid:
                continue
            self._nodes[nid] = node

            # 按 label 分桶
            for label in node.get("labels", []):
                self._by_label.setdefault(label, []).append(nid)

            # 名称/别名倒排索引
            props = node.get("properties", {})
            tokens = set()
            for field in ("name", "aliases", "summary"):
                val = props.get(field, "")
                if val:
                    tokens.update(self._tokenize(val))
            for token in tokens:
                self._name_index.setdefault(token, []).append(nid)

            # API 路径索引
            if "APIEndpoint" in node.get("labels", []):
                path = props.get("path", "")
                if path:
                    self._api_path_index[path] = nid

        # 索引关系
        for i, rel in enumerate(rels):
            self._relations.append(rel)
            start_id = rel.get("start", {}).get("id", "")
            end_id = rel.get("end", {}).get("id", "")
            if start_id:
                self._outgoing.setdefault(start_id, []).append(i)
            if end_id:
                self._incoming.setdefault(end_id, []).append(i)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """将文本拆分为检索 token（小写）。"""
        text = text.lower()
        # 按逗号、空格、斜杠等分割
        parts = re.split(r"[,，\s/\-_|]+", text)
        return {p.strip() for p in parts if len(p.strip()) >= 1}

    # ── 查询方法 ──

    def search_by_name(
        self, query: str, node_type: str | None = None, limit: int = 20,
    ) -> list[dict]:
        """按名称/别名模糊搜索。"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 计算每个节点的匹配分数
        scores: dict[str, float] = {}
        for token in query_tokens:
            # 精确 token 匹配
            for nid in self._name_index.get(token, []):
                scores[nid] = scores.get(nid, 0) + 2.0
            # 前缀匹配
            for idx_token, nids in self._name_index.items():
                if idx_token != token and (idx_token.startswith(token) or token.startswith(idx_token)):
                    for nid in nids:
                        scores[nid] = scores.get(nid, 0) + 0.5

        # 给 name 字段完全包含查询词的节点额外加分
        query_lower = query.lower()
        for nid, score in list(scores.items()):
            node = self._nodes.get(nid)
            if node:
                name = node.get("properties", {}).get("name", "").lower()
                if query_lower in name or name in query_lower:
                    scores[nid] = score + 10.0

        # SourceArtifact 降权（数量多但通常不是用户想要的主要结果）
        for nid in list(scores.keys()):
            node = self._nodes.get(nid)
            if node and "SourceArtifact" in node.get("labels", []):
                scores[nid] = scores[nid] * 0.3

        # 过滤 node_type
        if node_type:
            label = self._normalize_label(node_type)
            valid_ids = set(self._by_label.get(label, []))
            scores = {k: v for k, v in scores.items() if k in valid_ids}

        # 排序取 top
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
        return [self._format_node(self._nodes[nid]) for nid, _ in ranked]

    def list_by_type(
        self, node_type: str, limit: int = 50,
    ) -> list[dict]:
        """按类型列举节点。"""
        label = self._normalize_label(node_type)
        ids = self._by_label.get(label, [])[:limit]
        return [self._format_node(self._nodes[nid]) for nid in ids]

    def search_by_api_path(
        self, path_keyword: str, limit: int = 20,
    ) -> list[dict]:
        """按 API 路径关键词搜索。"""
        results = []
        kw = path_keyword.lower()
        for path, nid in self._api_path_index.items():
            if kw in path.lower():
                results.append(self._format_node(self._nodes[nid]))
                if len(results) >= limit:
                    break
        return results

    def get_related(
        self,
        node_name: str,
        direction: str = "both",
        relation_type: str | None = None,
        target_label: str | None = None,
        limit: int = 30,
    ) -> dict:
        """按关系遍历：给定节点名称，找关联节点。"""
        # 先找到节点（优先非 SourceArtifact）
        candidates = self.search_by_name(node_name, limit=10)
        if not candidates:
            return {"source": node_name, "found": False, "related": []}
        # 优先选择非 SourceArtifact 的节点作为源
        preferred = [c for c in candidates if c.get("type") != "SourceArtifact"]
        candidates = preferred if preferred else candidates

        source = candidates[0]
        nid = source.get("_id", "")
        related = []

        if direction in ("out", "both"):
            for ri in self._outgoing.get(nid, []):
                rel = self._relations[ri]
                if relation_type and rel.get("type") != relation_type:
                    continue
                end_id = rel.get("end", {}).get("id", "")
                end_node = self._nodes.get(end_id)
                if not end_node:
                    continue
                if target_label and target_label not in end_node.get("labels", []):
                    continue
                related.append({
                    "direction": "outgoing",
                    "relation_type": rel.get("type"),
                    "relation_name": rel.get("relation_name", ""),
                    "node": self._format_node(end_node),
                })

        if direction in ("in", "both"):
            for ri in self._incoming.get(nid, []):
                rel = self._relations[ri]
                if relation_type and rel.get("type") != relation_type:
                    continue
                start_id = rel.get("start", {}).get("id", "")
                start_node = self._nodes.get(start_id)
                if not start_node:
                    continue
                if target_label and target_label not in start_node.get("labels", []):
                    continue
                related.append({
                    "direction": "incoming",
                    "relation_type": rel.get("type"),
                    "relation_name": rel.get("relation_name", ""),
                    "node": self._format_node(start_node),
                })

        return {
            "source": source,
            "found": True,
            "total_related": len(related),
            "related": related[:limit],
        }

    def get_stats(self) -> dict:
        """返回知识库统计信息。"""
        return {
            "total_nodes": len(self._nodes),
            "total_relationships": len(self._relations),
            "nodes_by_type": {k: len(v) for k, v in self._by_label.items()},
            "total_api_endpoints": len(self._api_path_index),
        }

    # ── 内部辅助 ──

    def _normalize_label(self, user_input: str) -> str:
        """将用户输入的类型名归一化为标准 label。"""
        mapping = {
            "system": "System",
            "project": "Project",
            "module": "Module",
            "businessobject": "BusinessObject",
            "business_object": "BusinessObject",
            "object": "BusinessObject",
            "对象": "BusinessObject",
            "业务对象": "BusinessObject",
            "businessprocess": "BusinessProcess",
            "business_process": "BusinessProcess",
            "process": "BusinessProcess",
            "流程": "BusinessProcess",
            "业务流程": "BusinessProcess",
            "rule": "Rule",
            "规则": "Rule",
            "state": "State",
            "状态": "State",
            "apiendpoint": "APIEndpoint",
            "api_endpoint": "APIEndpoint",
            "api": "APIEndpoint",
            "endpoint": "APIEndpoint",
            "接口": "APIEndpoint",
            "sourceartifact": "SourceArtifact",
            "source_artifact": "SourceArtifact",
            "artifact": "SourceArtifact",
            "源码": "SourceArtifact",
        }
        return mapping.get(user_input.lower().strip(), user_input)

    @staticmethod
    def _format_node(node: dict) -> dict:
        """格式化节点输出（精简，不暴露内部 id）。"""
        props = node.get("properties", {})
        labels = node.get("labels", [])
        result: dict[str, Any] = {
            "_id": node.get("id", ""),
            "type": labels[0] if labels else "Unknown",
            "name": props.get("name", ""),
        }
        if props.get("description"):
            result["description"] = props["description"]
        if props.get("content"):
            # content 可能很长，截断到 500 字符
            content = props["content"]
            result["content"] = content[:500] + "..." if len(content) > 500 else content
        if props.get("aliases"):
            result["aliases"] = props["aliases"]
        # APIEndpoint 特有字段
        if "APIEndpoint" in labels:
            for key in ("path", "method", "summary", "api_level", "api_audience"):
                if props.get(key):
                    result[key] = props[key]
        return result


class KnowledgeProvider:
    """知识查询 Provider — 不继承 BaseProvider（不需要 API client）。"""

    name = "knowledge"

    def __init__(self, knowledge_path: str | None = None):
        self._index = KnowledgeIndex(knowledge_path)

    def search(
        self,
        query: str,
        node_type: str | None = None,
        search_mode: str = "name",
        relation_type: str | None = None,
        limit: int = 20,
    ) -> dict:
        """统一搜索入口。

        Args:
            query: 搜索关键词
            node_type: 节点类型过滤（可选）
            search_mode: 搜索模式
                - name: 按名称/别名搜索
                - type: 按类型列举
                - api_path: 按 API 路径搜索
                - related: 按关系遍历
                - stats: 返回知识库统计
            relation_type: 关系类型过滤（仅 related 模式）
            limit: 返回数量上限
        """
        if search_mode == "stats":
            return {"mode": "stats", "result": self._index.get_stats()}

        if search_mode == "type":
            target = node_type or query
            nodes = self._index.list_by_type(target, limit=limit)
            return {
                "mode": "type",
                "node_type": target,
                "total": len(nodes),
                "nodes": nodes,
            }

        if search_mode == "api_path":
            nodes = self._index.search_by_api_path(query, limit=limit)
            return {
                "mode": "api_path",
                "query": query,
                "total": len(nodes),
                "nodes": nodes,
            }

        if search_mode == "related":
            target_label = self._index._normalize_label(node_type) if node_type else None
            result = self._index.get_related(
                query,
                relation_type=relation_type,
                target_label=target_label,
                limit=limit,
            )
            return {"mode": "related", **result}

        # 默认: name 搜索
        nodes = self._index.search_by_name(query, node_type=node_type, limit=limit)
        return {
            "mode": "name",
            "query": query,
            "node_type": node_type,
            "total": len(nodes),
            "nodes": nodes,
        }
