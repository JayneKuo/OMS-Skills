# Tennis Product Creation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Product Agent capability that turns weak input like “tennis” into a structured product creation brief, then use it to create a real OMS product, OMS channel product, and attempt ShopifyV3 creation/publish in staging.

**Architecture:** Keep weak-input product ideation in `product-optimization` as a deterministic, testable engine (`intent="product_creation_brief"`). Reuse existing `product-query` publishing workflow for OMS product + channel product creation, then verify through `product-query`, `product-diagnosis`, and `product-listing-planner`. Do not add broad market research or external Shopify claims unless the current environment exposes a real Shopify/OMS publish endpoint.

**Tech Stack:** Python 3.12, pytest, existing `.kiro/skills/product-*` skill layout, OMS staging API via `ProductOMSAPIClient`.

---

## File Structure

- Create `.kiro/skills/product-optimization/scripts/product_optimization_engine/__init__.py`
  - Exports `ProductOptimizationEngine`.
- Create `.kiro/skills/product-optimization/scripts/product_optimization_engine/engine.py`
  - Implements deterministic `product_creation_brief` generation for weak inputs, starting with tennis.
  - Does not call external APIs.
- Create `.kiro/skills/product-optimization/tests/test_product_optimization_engine.py`
  - Tests weak input `tennis` and Chinese input `网球` produce a valid creation brief.
- Modify `.kiro/skills/product-optimization/SKILL.md`
  - Documents first executable MVP intent `product_creation_brief` and explicitly marks output as estimated/recommended, not market-verified.
- Create `.kiro/skills/product-optimization/CAPABILITY_STATUS.md`
  - Documents implemented scope and boundaries.
- Optionally modify `docs/product-agent/SYSTEM_PROMPT.md`
  - Add routing rule: weak product idea → `product_optimization(product_creation_brief)` → user confirmation → creation workflow.

---

### Task 1: Product creation brief engine

**Files:**
- Create: `.kiro/skills/product-optimization/scripts/product_optimization_engine/__init__.py`
- Create: `.kiro/skills/product-optimization/scripts/product_optimization_engine/engine.py`
- Test: `.kiro/skills/product-optimization/tests/test_product_optimization_engine.py`

- [ ] **Step 1: Write failing test for English weak input**

Create `.kiro/skills/product-optimization/tests/test_product_optimization_engine.py` with:

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_optimization_engine.engine import ProductOptimizationEngine


def test_product_creation_brief_generates_tennis_shopify_payload():
    result = ProductOptimizationEngine().optimize(
        identifier="tennis",
        merchant_no="LAN0000002",
        intent="product_creation_brief",
        filters={"target_channel": "ShopifyV3", "market": "US", "language": "en"},
        context={},
    )

    assert result["success"] is True
    assert result["confidence"] == "medium"
    assert result["data_completeness"] == "estimated"
    assert result["recommendations"][0]["action"] == "create_test_product_after_confirmation"

    brief = result["details"]["creation_brief"]
    assert brief["product"]["name"] == "AI Test ProSpin Tennis Training Set"
    assert brief["product"]["brand"] == "CourtLab"
    assert brief["product"]["categoryName"] == "Tennis Training Equipment"
    assert brief["product"]["price"] == 49.99
    assert brief["product"]["keywords"] == ["tennis", "training", "practice", "sports"]
    assert brief["product"]["variants"] == [
        {
            "sellerSku": "TENNIS-AI-TEST-STD",
            "price": 49.99,
            "salesPriceUnit": "USD",
            "inventory": 20,
            "weight": 1.2,
            "weightUnit": "KG",
            "length": 35,
            "width": 25,
            "height": 8,
            "dimensionUnit": "CM",
            "salesAttributeValues": [
                {"attributeName": "Package", "attributeValue": "Standard"}
            ],
        }
    ]
    assert brief["channels"] == [{"channel": "ShopifyV3"}]
    assert "用户只提供 tennis" in result["details"]["assumptions"][0]
```

- [ ] **Step 2: Run test to verify red state**

Run:

```bash
python -m pytest .kiro/skills/product-optimization/tests/test_product_optimization_engine.py::test_product_creation_brief_generates_tennis_shopify_payload -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'product_optimization_engine'`.

- [ ] **Step 3: Implement minimal engine and package export**

Create `.kiro/skills/product-optimization/scripts/product_optimization_engine/__init__.py`:

```python
from product_optimization_engine.engine import ProductOptimizationEngine

__all__ = ["ProductOptimizationEngine"]
```

Create `.kiro/skills/product-optimization/scripts/product_optimization_engine/engine.py`:

```python
from __future__ import annotations


class ProductOptimizationEngine:
    def optimize(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
        filters = filters or {}
        context = context or {}
        if intent == "product_creation_brief":
            return self._product_creation_brief(identifier, filters)

        return {
            "success": True,
            "summary": "当前 product_optimization MVP 仅支持 product_creation_brief。",
            "reason": "第一版先支持弱输入商品创建资料生成。",
            "evidences": [],
            "confidence": "low",
            "data_completeness": "insufficient",
            "severity": None,
            "recommendations": [],
            "metrics": {},
            "details": {"supported_intents": ["product_creation_brief"]},
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": ["unsupported_intent"],
        }

    def _product_creation_brief(self, identifier, filters):
        seed = str(identifier or filters.get("keyword") or "").strip().lower()
        target_channel = filters.get("target_channel") or filters.get("channel_code") or "ShopifyV3"
        if seed not in {"tennis", "网球"}:
            return {
                "success": True,
                "summary": f"已基于 {identifier} 生成通用测试商品创建方案。",
                "reason": "用户输入较弱，当前只做可测试的商品资料补全，不声明市场验证结论。",
                "evidences": [],
                "confidence": "low",
                "data_completeness": "estimated",
                "severity": None,
                "recommendations": [{
                    "action": "review_generated_product_brief",
                    "precondition": "确认商品类目、价格、图片和渠道配置",
                    "risk": "弱输入生成的商品资料可能不符合真实经营目标",
                    "priority": "high",
                    "expected_effect": "确认后可进入 OMS 测试商品创建",
                }],
                "metrics": {"variant_count": 1, "target_channel_count": 1},
                "details": {
                    "creation_brief": self._tennis_brief(target_channel),
                    "assumptions": [f"用户只提供 {identifier}，商品资料为测试用估算方案。"],
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        return {
            "success": True,
            "summary": "已基于 tennis 场景生成 ShopifyV3 测试商品创建方案。",
            "reason": "用户只提供弱输入，先生成一个网球训练套装测试商品，用于验证 OMS 到 ShopifyV3 的创建链路。",
            "evidences": [],
            "confidence": "medium",
            "data_completeness": "estimated",
            "severity": None,
            "recommendations": [{
                "action": "create_test_product_after_confirmation",
                "precondition": "确认允许在 staging 创建新的测试 SKU 和渠道商品",
                "risk": "会在 OMS/ShopifyV3 测试环境产生真实测试数据",
                "priority": "high",
                "expected_effect": "验证弱输入到商品创建的完整链路",
            }],
            "metrics": {"variant_count": 1, "target_channel_count": 1},
            "details": {
                "creation_brief": self._tennis_brief(target_channel),
                "assumptions": [
                    "用户只提供 tennis，商品资料为测试用估算方案。",
                    "没有外部市场、竞品、关键词搜索量或转化数据，不能作为确定性市场结论。",
                    "Shopify 在当前业务语境中默认指 OMS ShopifyV3 渠道。",
                ],
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": [],
        }

    def _tennis_brief(self, target_channel):
        return {
            "product": {
                "parentSku": "TENNIS-AI-TEST",
                "name": "AI Test ProSpin Tennis Training Set",
                "brand": "CourtLab",
                "model": "ProSpin Starter",
                "categoryName": "Tennis Training Equipment",
                "description": "A test tennis training set for validating OMS to ShopifyV3 product creation workflows.",
                "price": 49.99,
                "keywords": ["tennis", "training", "practice", "sports"],
                "variants": [{
                    "sellerSku": "TENNIS-AI-TEST-STD",
                    "price": 49.99,
                    "salesPriceUnit": "USD",
                    "inventory": 20,
                    "weight": 1.2,
                    "weightUnit": "KG",
                    "length": 35,
                    "width": 25,
                    "height": 8,
                    "dimensionUnit": "CM",
                    "salesAttributeValues": [
                        {"attributeName": "Package", "attributeValue": "Standard"}
                    ],
                }],
            },
            "channels": [{"channel": target_channel}],
        }
```

- [ ] **Step 4: Run test to verify green state**

Run:

```bash
python -m pytest .kiro/skills/product-optimization/tests/test_product_optimization_engine.py::test_product_creation_brief_generates_tennis_shopify_payload -v
```

Expected: PASS.

---

### Task 2: Chinese weak input and timestamp-safe SKU support

**Files:**
- Modify: `.kiro/skills/product-optimization/tests/test_product_optimization_engine.py`
- Modify: `.kiro/skills/product-optimization/scripts/product_optimization_engine/engine.py`

- [ ] **Step 1: Write failing test for Chinese input and SKU suffix**

Append this test:

```python
def test_product_creation_brief_accepts_chinese_tennis_and_sku_suffix():
    result = ProductOptimizationEngine().optimize(
        identifier="网球",
        merchant_no="LAN0000002",
        intent="product_creation_brief",
        filters={"target_channel": "ShopifyV3", "sku_suffix": "20260521A"},
        context={},
    )

    brief = result["details"]["creation_brief"]
    assert brief["product"]["parentSku"] == "TENNIS-AI-20260521A"
    assert brief["product"]["variants"][0]["sellerSku"] == "TENNIS-AI-20260521A-STD"
    assert brief["channels"] == [{"channel": "ShopifyV3"}]
```

- [ ] **Step 2: Run test to verify red state**

Run:

```bash
python -m pytest .kiro/skills/product-optimization/tests/test_product_optimization_engine.py::test_product_creation_brief_accepts_chinese_tennis_and_sku_suffix -v
```

Expected: FAIL because `_tennis_brief()` does not use `sku_suffix` yet.

- [ ] **Step 3: Implement SKU suffix support**

In `ProductOptimizationEngine._product_creation_brief()`, derive:

```python
sku_suffix = filters.get("sku_suffix") or "TEST"
```

Pass it into `_tennis_brief(target_channel, sku_suffix)`.

Update `_tennis_brief()` signature and SKU fields:

```python
def _tennis_brief(self, target_channel, sku_suffix="TEST"):
    parent_sku = f"TENNIS-AI-{sku_suffix}"
    return {
        "product": {
            "parentSku": parent_sku,
            ...
            "variants": [{
                "sellerSku": f"{parent_sku}-STD",
                ...
            }],
        },
        "channels": [{"channel": target_channel}],
    }
```

- [ ] **Step 4: Run product-optimization tests**

Run:

```bash
python -m pytest .kiro/skills/product-optimization/tests/test_product_optimization_engine.py
```

Expected: 2 passed.

---

### Task 3: Document executable product optimization MVP

**Files:**
- Modify: `.kiro/skills/product-optimization/SKILL.md`
- Create: `.kiro/skills/product-optimization/CAPABILITY_STATUS.md`
- Optionally modify: `docs/product-agent/SYSTEM_PROMPT.md`

- [ ] **Step 1: Update SKILL.md runtime status**

In `.kiro/skills/product-optimization/SKILL.md`, after the core principles section, add:

```markdown
## MVP 运行时状态

当前可执行 MVP 支持 `intent="product_creation_brief"`：

- 可将弱输入如 `tennis` / `网球` 转成测试商品创建资料。
- 输出 `details.creation_brief.product`，可被 OMS 商品创建 workflow 消费。
- 输出 `details.creation_brief.channels`，第一版默认 Shopify 即 `ShopifyV3`。
- 输出为估算/建议，不包含外部市场、竞品、关键词搜索量或转化验证。
- 不直接创建 OMS 商品、不创建 channel product、不发布到 Shopify；执行动作由 Product Agent 编排层在用户确认后完成。
```

- [ ] **Step 2: Create CAPABILITY_STATUS.md**

Create `.kiro/skills/product-optimization/CAPABILITY_STATUS.md`:

```markdown
# Product Optimization Skill Capability Status

Last updated: 2026-05-21

## Purpose

`product-optimization` turns product context or weak product ideas into channel/content/product operation recommendations. First executable scope focuses on generating a structured test product creation brief for Product Agent creation workflow validation.

## Current Implemented Capabilities

Implemented in `scripts/product_optimization_engine/engine.py` and covered by `tests/test_product_optimization_engine.py`.

### Product creation brief MVP

For weak inputs like `tennis` or `网球`, the engine returns:

- Test product title, brand, model, category, description, and keywords.
- One SKU variant with price, currency, inventory, dimensions, weight, and sales attribute values.
- Target channel list using `ShopifyV3` by default.
- Assumptions explaining that output is estimated and not market-verified.

## Boundaries

- Does not call external market, competitor, keyword, Shopify, or OMS APIs.
- Does not create, publish, edit, or delete products.
- Output must be confirmed before any staging write action.
- Shopify in Product Agent business language maps to OMS `ShopifyV3`.

## Verified Test Coverage

Run command:

```bash
python -m pytest ".kiro/skills/product-optimization/tests/test_product_optimization_engine.py"
```

Current tests cover:

- English weak input `tennis` generates a ShopifyV3 product creation brief.
- Chinese weak input `网球` supports explicit SKU suffix for safe unique test SKU generation.

## Next Recommended Work

1. Add more product idea templates after real use cases appear.
2. Add optional market-data-backed enrichment when external data sources become available.
3. Add image prompt suggestions once OMS image requirements are confirmed.
```

- [ ] **Step 3: Update SYSTEM_PROMPT routing**

In `docs/product-agent/SYSTEM_PROMPT.md`, update the optimization section to say `product_optimization` has executable MVP only for `product_creation_brief`:

```markdown
`product_optimization` 第一版仅将 `product_creation_brief` 作为可执行 MVP。用户只给一个弱商品词（如 `tennis` / `网球`）并要求创建商品时，应先调用 `product_optimization(product_creation_brief)` 生成商品创建资料，再让用户确认是否执行 OMS/ShopifyV3 写入动作。
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest .kiro/skills/product-optimization/tests/test_product_optimization_engine.py
```

Expected: 2 passed.

---

### Task 4: Real staging creation rehearsal script

**Files:**
- No committed script required; run a one-off Python command from repository root.

- [ ] **Step 1: Dry-run creation payload locally**

Run this one-off script without making API calls:

```bash
python - <<'PY'
import sys
from pathlib import Path

root = Path('.').resolve()
sys.path.insert(0, str(root / '.kiro/skills/product-optimization/scripts'))
sys.path.insert(0, str(root / '.kiro/skills/product-query/scripts'))

from product_optimization_engine.engine import ProductOptimizationEngine
from product_query_engine.publish_workflow import _build_product_create_payload

result = ProductOptimizationEngine().optimize(
    identifier='tennis',
    merchant_no='LAN0000002',
    intent='product_creation_brief',
    filters={'target_channel': 'ShopifyV3', 'sku_suffix': 'DRYRUN'},
    context={},
)
brief = result['details']['creation_brief']
payload = _build_product_create_payload('LAN0000002', brief)
assert payload['spuInfo']['sellerParentSku'] == 'TENNIS-AI-DRYRUN'
assert payload['skuInfoList'][0]['sellerSku'] == 'TENNIS-AI-DRYRUN-STD'
assert payload['salesAttributes'][0]['attributeName'] == 'Package'
print('dry_run_ok')
PY
```

Expected: prints `dry_run_ok`.

- [ ] **Step 2: Execute real OMS product + channel product creation only after explicit user confirmation**

Use a unique suffix such as current timestamp, then run:

```bash
python - <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

root = Path('.').resolve()
sys.path.insert(0, str(root / '.kiro/skills/product-optimization/scripts'))
sys.path.insert(0, str(root / '.kiro/skills/product-query/scripts'))
sys.path.insert(0, str(root / '.kiro/skills/product-diagnosis/scripts'))
sys.path.insert(0, str(root / '.kiro/skills/product-listing-planner/scripts'))

from product_optimization_engine.engine import ProductOptimizationEngine
from product_query_engine.api_client import ProductOMSAPIClient
from product_query_engine.channel_product_adapter import ChannelProductApiAdapter
from product_query_engine.config import EngineConfig
from product_query_engine.engine import ProductQueryEngine
from product_query_engine.product_adapter import ProductApiAdapter
from product_query_engine.publish_workflow import ProductPublishWorkflow
from product_diagnosis_engine.engine import ProductDiagnosisEngine
from product_listing_planner_engine.engine import ProductListingPlannerEngine

suffix = datetime.now().strftime('%Y%m%d%H%M%S')
optimization = ProductOptimizationEngine().optimize(
    identifier='tennis',
    merchant_no='LAN0000002',
    intent='product_creation_brief',
    filters={'target_channel': 'ShopifyV3', 'sku_suffix': suffix},
    context={},
)
brief = optimization['details']['creation_brief']

config = EngineConfig(
    base_url='https://omsv2-staging.item.com',
    tenant_id='LT',
    merchant_no='LAN0000002',
    username='lantester@item.com',
    password='LANLT',
    request_timeout=30,
)
client = ProductOMSAPIClient(config)
create_result = ProductPublishWorkflow(client).publish(
    merchant_no='LAN0000002',
    request=brief,
)

query_engine = ProductQueryEngine(
    product_adapter=ProductApiAdapter(client),
    channel_product_adapter=ChannelProductApiAdapter(client),
)
created_sku = brief['product']['variants'][0]['sellerSku']
query_result = query_engine.query(
    identifier=created_sku,
    merchant_no='LAN0000002',
    intent='listing_status',
    filters={'channel_code': 'ShopifyV3'},
)
diagnosis_result = ProductDiagnosisEngine().diagnose(
    identifier=created_sku,
    merchant_no='LAN0000002',
    intent='platform_readiness',
    filters={'channel_code': 'ShopifyV3'},
    context={'product_query_result': query_result},
)
planner_result = ProductListingPlannerEngine().plan(
    identifier=created_sku,
    merchant_no='LAN0000002',
    intent='listing_readiness',
    filters={'target_channels': ['ShopifyV3']},
    context={'product_query_result': query_result, 'product_diagnosis_result': diagnosis_result},
)

print(json.dumps({
    'created_sku': created_sku,
    'optimization_summary': optimization['summary'],
    'oms_create_success': create_result['success'],
    'oms_create_summary': create_result.get('summary'),
    'query_summary': query_result['summary'],
    'query_metrics': query_result['metrics'],
    'diagnosis_summary': diagnosis_result['summary'],
    'diagnosis_issues': [issue['code'] for issue in diagnosis_result['details']['blocking_issues']],
    'planner_summary': planner_result['summary'],
    'planner_steps': [step['title'] for step in planner_result['details']['launch_steps']],
}, ensure_ascii=False, indent=2))
PY
```

Expected outcomes:
- If OMS create succeeds and channel product create succeeds, report created SKU and verification summaries.
- If channel product create fails due missing `channelNo` or unsupported ShopifyV3 config, report exact upstream response as the blocker.
- Do not retry with random alternate channels unless user explicitly approves.

---

## Self-Review

- Spec coverage: The plan covers weak input product creation brief, testable product-optimization engine, docs/status updates, dry-run payload validation, and gated real staging creation + verification. It explicitly handles the known Shopify MCP uncertainty by using existing OMS workflow and reporting blockers instead of claiming unavailable direct Shopify MCP behavior.
- Placeholder scan: No TBD/TODO/fill-in-later placeholders are present. The real creation task has explicit scripts and expected outcomes.
- Type consistency: `ProductOptimizationEngine.optimize(...)` matches existing product skill method style; output uses `details.creation_brief.product` and `details.creation_brief.channels`, which matches `ProductPublishWorkflow.publish(..., request=brief)` expectations.
