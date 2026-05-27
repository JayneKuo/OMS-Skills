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
