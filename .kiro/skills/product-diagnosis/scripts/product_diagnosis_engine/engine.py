from __future__ import annotations


class ProductDiagnosisEngine:
    def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
        filters = filters or {}
        context = context or {}
        missing_fields = context.get("missing_fields") or context.get("product_snapshot", {}).get("missing_fields") or []
        required_missing = [field for field in missing_fields if field.get("required", True)]

        if required_missing:
            return {
                "success": True,
                "summary": f"{identifier} 缺少 {len(required_missing)} 个必填字段。",
                "reason": "输入上下文包含必填字段缺失信息。",
                "evidences": [
                    {
                        "source": "missing_fields",
                        "description": f"缺少必填字段 {field.get('field')}",
                        "data": field,
                    }
                    for field in required_missing
                ],
                "confidence": "high",
                "data_completeness": "partial",
                "severity": "major",
                "recommendations": [
                    {
                        "action": "complete_required_attribute",
                        "precondition": "确认缺失字段的准确值",
                        "risk": "字段不准确可能导致再次审核或同步失败",
                        "priority": "high",
                        "expected_effect": "补齐必填字段后可继续同步或提交审核",
                    }
                ],
                "metrics": {"missing_required_field_count": len(required_missing)},
                "details": {
                    "issue_type": "missing_required_fields",
                    "failed_stage": "field_validation",
                    "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                    "retryable": True,
                    "requires_manual_fix": True,
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        publish_history = context.get("publish_history") or []
        failed_publish_history = [
            item for item in publish_history
            if item.get("error_message") or str(item.get("status") or "").lower() in {"failed", "fail", "rejected"}
        ]
        if intent in ("listing_failed", "audit_failed", None) and failed_publish_history:
            issue_type = "audit_failed" if any(str(item.get("audit_status") or "").lower() in {"rejected", "failed"} for item in failed_publish_history) else "listing_failed"
            failed_stage = "audit" if issue_type == "audit_failed" else "listing"
            return {
                "success": True,
                "summary": f"{identifier} {self._intent_label(issue_type)}，发现 {len(failed_publish_history)} 条发布历史错误证据。",
                "reason": "输入上下文包含发布历史失败或错误信息。",
                "evidences": [
                    {"source": "publish_history", "description": item.get("error_message") or str(item), "data": item}
                    for item in failed_publish_history
                ],
                "confidence": "high",
                "data_completeness": "partial",
                "severity": "major",
                "recommendations": [
                    {
                        "action": "review_publish_history_and_fix_source_data",
                        "precondition": "确认发布历史错误信息对应的商品字段或渠道规则",
                        "risk": "未修正源数据前重新发布可能继续失败",
                        "priority": "high",
                        "expected_effect": "修正源数据后可重新发布或提交审核",
                    }
                ],
                "metrics": {"publish_history_error_count": len(failed_publish_history)},
                "details": {
                    "issue_type": issue_type,
                    "failed_stage": failed_stage,
                    "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                    "retryable": True,
                    "requires_manual_fix": True,
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        error_sources = {
            "sync_failed": ("sync_errors", "sync"),
            "audit_failed": ("audit_errors", "audit"),
            "listing_failed": ("listing_errors", "listing"),
        }
        if intent in error_sources:
            error_key, failed_stage = error_sources[intent]
            errors = context.get(error_key) or []
            last_error = context.get("channel_product_snapshot", {}).get("last_error")
            if last_error and not errors:
                errors = [{"message": last_error}]
            if errors:
                return {
                    "success": True,
                    "summary": f"{identifier} {self._intent_label(intent)}，发现 {len(errors)} 条错误证据。",
                    "reason": "输入上下文包含渠道商品错误信息。",
                    "evidences": [
                        {"source": error_key, "description": error.get("message") or str(error), "data": error}
                        for error in errors
                    ],
                    "confidence": "high",
                    "data_completeness": "partial",
                    "severity": "major",
                    "recommendations": [
                        {
                            "action": "review_channel_error_and_fix_source_data",
                            "precondition": "确认渠道错误信息对应的商品字段或渠道规则",
                            "risk": "未修正源数据前重试可能继续失败",
                            "priority": "high",
                            "expected_effect": "修正源数据后可重新同步或提交审核",
                        }
                    ],
                    "metrics": {"error_count": len(errors)},
                    "details": {
                        "issue_type": intent,
                        "failed_stage": failed_stage,
                        "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                        "retryable": True,
                        "requires_manual_fix": True,
                    },
                    "charts": [],
                    "visual_blocks": [],
                    "links": [],
                    "errors": [],
                }

        channel_products = context.get("channel_products") or []
        rejected_channel_products = [
            item for item in channel_products
            if str(item.get("audit_status") or "").lower() in {"rejected", "failed"}
        ]
        if intent in ("audit_failed", None) and rejected_channel_products:
            return self._status_result(identifier, "audit_failed", "audit", "channel_products", rejected_channel_products, "渠道商品状态")

        return {
            "success": True,
            "summary": "现有上下文不足以确认商品异常原因。",
            "reason": "未提供 missing_fields、sync_errors、audit_errors 或 last_error。",
            "evidences": [],
            "confidence": "low",
            "data_completeness": "insufficient",
            "severity": None,
            "recommendations": [
                {
                    "action": "provide_product_query_context",
                    "precondition": "先获取商品快照、渠道状态或错误信息",
                    "risk": "缺少证据时无法确认根因",
                    "priority": "high",
                    "expected_effect": "补充证据后可输出可信诊断",
                }
            ],
            "metrics": {},
            "details": {"issue_type": intent or "unknown", "retryable": None, "requires_manual_fix": None},
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": ["缺少可诊断的商品上下文"],
        }

    def _status_result(self, identifier, issue_type, failed_stage, source, rows, source_label):
        return {
            "success": True,
            "summary": f"{identifier} {self._intent_label(issue_type)}，发现 {len(rows)} 条{source_label}证据。",
            "reason": f"输入上下文包含{source_label}。",
            "evidences": [
                {"source": source, "description": row.get("error_message") or row.get("listing_status") or row.get("audit_status") or str(row), "data": row}
                for row in rows
            ],
            "confidence": "high",
            "data_completeness": "partial",
            "severity": "major",
            "recommendations": [
                {
                    "action": "review_channel_status_and_fix_source_data",
                    "precondition": "确认渠道商品状态对应的商品字段或渠道规则",
                    "risk": "未修正源数据前重试可能继续失败",
                    "priority": "high",
                    "expected_effect": "修正源数据后可重新提交审核或发布",
                }
            ],
            "metrics": {"evidence_count": len(rows)},
            "details": {
                "issue_type": issue_type,
                "failed_stage": failed_stage,
                "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                "retryable": True,
                "requires_manual_fix": True,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": [],
        }

    @staticmethod
    def _intent_label(intent: str) -> str:
        return {
            "sync_failed": "同步失败",
            "audit_failed": "审核失败",
            "listing_failed": "上架失败",
        }.get(intent, "存在异常")
