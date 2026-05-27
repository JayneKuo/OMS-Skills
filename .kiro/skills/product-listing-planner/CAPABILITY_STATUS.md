# Product Listing Planner Skill Capability Status

Last updated: 2026-05-20

## Purpose

`product-listing-planner` converts factual product/channel data and diagnosis results into an actionable multi-channel listing plan. It can also run the confirmed submit execution loop for existing channel products after explicit user confirmation. It expects upstream `product-query` and optionally `product-diagnosis` results.

## Current Implemented Capabilities

Implemented in `scripts/product_listing_planner_engine/engine.py` and covered by `tests/test_product_listing_planner_engine.py`.

### Degraded planning

When `product_query_result` is missing, the planner returns a low-confidence plan that blocks progress and instructs the caller to run `product-query` first.

### Channel plan + launch steps MVP

For fixture-backed `0324fan` data, the planner can:

- Read `product_query_result.details.channel_summary`.
- Read `product_diagnosis_result.details.blocking_issues`.
- Mark `ShopifyV3` as blocked when diagnosis reports `unsupported_oms_shopify_channel_type`.
- Mark `SHEIN` as blocked when channel summary includes attribute/SKC/product attribute publish errors.
- Produce deterministic channel priorities:
  - `P0` for blocked ShopifyV3 verification when diagnosis reports unsupported OMS Shopify channel type.
  - `P1` for SHEIN attribute completion.
  - `P2` for channels with no observed blockers.
- Produce deterministic launch steps:
  1. Verify publishing-service support/config for the observed ShopifyV3 channel type before retrying publish.
  2. Complete SHEIN product attributes.
  3. Re-run product-query and product-diagnosis.

### Confirmed submit execution loop

For existing channel products, the planner can:

- Build a confirmation form from `product_query_result.details.channel_products`.
- Require explicit confirmation before any submit action.
- Submit through `POST /rpc-api/channel-product/submit`.
- Re-read the channel product detail and publish history after execution.
- Return only one of the three final conclusions:
  - `Executed successfully`
  - `Submitted successfully but business result did not take effect`
  - `Execution failed`

Boundary: this capability does not create new channel products yet. A future create-from-SPU phase is still required for new channel product creation.

Current tests now cover submit safety gates and no-effect verification.

## Current Boundaries

- API calls are limited to the confirmed submit execution loop for existing channel products.
- No unconfirmed publish/retry/mutation behavior.
- No market, sales, SEO, or content optimization decisions.
- Channel priority is readiness-based only; it is not a market opportunity ranking.
- Rules are currently focused on the known `0324fan` ShopifyV3 + SHEIN failure pattern.

## Verified Test Coverage

Run command:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py"
```

Current tests cover:

- Degraded plan when `product_query_result` is missing.
- Fixture-based `0324fan` plan using `product_query_0324fan.json` and `product_diagnosis_0324fan_shopifyv3.json`.
- Stable channel priority and launch step ordering.
- Confirmed submit execution loop safety gates.
- No-effect verification when submit succeeds but live OMS state does not change.

## Next Recommended Work

1. Add pass-case fixture for a Shopify-ready product.
2. Add SHEIN diagnosis integration after `product-diagnosis` implements SHEIN readiness.
3. Add readiness checklist items for product title, SKU, price, image, channel type, and channel attributes.
4. Add visual block output for frontend rendering.
