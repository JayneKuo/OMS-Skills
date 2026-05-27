# Product Diagnosis Skill Capability Status

Last updated: 2026-05-20

## Purpose

`product-diagnosis` analyzes product/channel failures from factual data produced by `product-query`. It should not query or mutate OMS data directly. It consumes structured facts such as `channel_summary`, `channel_products`, `publish_history`, `resolution`, `product`, and `skus`, then explains causes and next actions.

## Current Implemented Capabilities

### Rule-based OMS/channel diagnosis

Implemented in `scripts/product_diagnosis_engine/engine.py` and covered by `tests/test_product_diagnosis_engine.py`:

- Missing required fields from `missing_fields`.
- Listing failure from `publish_history` failures or error messages.
- Audit failure from rejected/failed channel product status.
- Sync/listing/audit failures from explicit error arrays and `channel_product_snapshot.last_error`.
- Low-confidence insufficient-context response when no usable evidence is provided.

### Shopify platform readiness MVP

Implemented for `intent="platform_readiness"` with `filters.channel_code` starting with `SHOPIFY`.

Rules live in `scripts/product_diagnosis_engine/platform_requirements/shopify.py`; `engine.py` calls `evaluate_shopify_readiness()` so Shopify-specific API requirements stay isolated from generic diagnosis flow.

The module uses Shopify Admin GraphQL API requirements as readiness rules, not live Shopify API calls. It checks OMS facts before real publishing:

- Product title must exist.
- At least one SKU/variant should exist.
- Variant SKU should exist for traceability.
- Variant price should exist.
- Variant currency should exist in OMS before mapping to Shopify pricing.
- Multi-variant products need options/sales attributes for Shopify `productSet` / `productVariantsBulkCreate`.
- Product media/image is treated as a blocking readiness issue for operational publishing quality.
- `ShopifyV3` unsupported OMS publish errors are surfaced as connector/channel-type issues when present in `channel_summary.errors`.
- Outputs `details.readiness_checklist` for Shopify release readiness display.
- Uses a ShopifyV3-specific recommendation when `channel_summary.errors` includes unsupported connector/channel-type evidence.

Rule sources are recorded per issue:

- `shopify_admin_graphql_api` for Shopify official Admin API-derived requirements.
- `oms_publish_error` for errors observed from OMS publishing attempts.

## Current Output Shape for Shopify Readiness

```json
{
  "details": {
    "issue_type": "platform_readiness_failed",
    "platform": "SHOPIFY",
    "failed_stage": "pre_publish_validation",
    "ready_to_publish": false,
    "blocking_issues": [
      {
        "code": "missing_variant_options",
        "message": "...",
        "source": "shopify_admin_graphql_api",
        "field": "options"
      }
    ],
    "readiness_checklist": [
      {
        "item": "Variant Options",
        "status": "blocked",
        "evidence": "缺少多 variant options",
        "issue_code": "missing_variant_options"
      }
    ],
    "retryable": true,
    "requires_manual_fix": true
  },
  "metrics": {
    "blocking_issue_count": 1
  }
}
```

## Verified Test Coverage

Run command:

```bash
python -m pytest ".kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py"
```

Current tests cover:

- Missing required fields.
- Listing failure from publish history.
- Audit failure from channel product status.
- Sync failure from sync errors.
- Shopify readiness missing title/SKU/price/currency/media.
- Shopify readiness multi-variant missing options and ShopifyV3 unsupported OMS connector error.
- Shopify readiness pass-case for complete single-variant products.
- Shopify readiness pass-case for complete multi-variant products with options.
- Shopify readiness checklist for blocked product data.
- Shopify readiness checklist for complete single-variant product data.
- Multi-variant option values matching Shopify product options.
- ShopifyV3-specific remediation recommendation for the real `0324fan` fixture.
- Fixture-based regression for real `0324fan` product-query output and ShopifyV3 readiness diagnosis.

## Important Boundaries

- This skill does not call Shopify, SHEIN, Amazon, or TikTok directly.
- This skill does not publish, retry publish, edit product data, or change channel state.
- This skill depends on `product-query` for current OMS facts.
- Shopify readiness is a pre-publish validation layer; final publish still needs a dedicated publish skill and real Shopify credentials.
- First release scope is Shopify only; SHEIN/Amazon/TikTok readiness rules are intentionally deferred.

## Verified End-to-End Smoke Check

Real staging `product-query` output for `0324fan` was passed into `product-diagnosis` with `intent="platform_readiness"` and `channel_code="ShopifyV3"`. A reduced fixture is stored at `tests/fixtures/product_query_0324fan.json` so this case can be regression-tested without calling staging.

Observed result:

- Query found 5 channel products across 2 channels and 8 publish history entries.
- Diagnosis returned `ready_to_publish=false`.
- Blocking issue: `unsupported_oms_shopify_channel_type` from `oms_publish_error` because `channel_summary.errors` reports `ShopifyV3` is unsupported by the current publish service.

## Next Recommended Work

1. Expand Shopify readiness rules for publish scope/channel publication once the publish skill starts calling Shopify Admin GraphQL.
2. Add SHEIN readiness rules from observed OMS errors and later official SHEIN API documentation.
3. Add `product-listing-planner` after diagnosis can produce stable platform readiness outputs.
