# Product Query MVP API Mapping Design

## Goal

Make Product Agent first-version behavior usable and explicit by documenting the `product_query` MVP data sources, supported scenarios, limits, and acceptance cases.

The output is `docs/product-agent/02-product-query-api-mapping.md`. It should help Product Agent, product skills, and frontend integration answer one question consistently: what product data can the first version rely on today, and what must still be treated as missing or unsupported?

## Scope

This design covers documentation only. It does not add new API integrations or expand `product_query` runtime behavior.

The mapping document will cover first-version usable capabilities:

- Product identity resolution: SKU, SPU, productId, channel product id when available.
- Product master data: SPU list/detail through the confirmed product SPU APIs.
- Channel product status: channel product list/detail through the confirmed channel product APIs.
- Publish, audit, and listing evidence: publish history page API.
- Inventory and price summary: existing inventory adapter behavior.
- Sales performance bridge: `performance_query` for `oms_analysis` and `product_performance`.

Out of scope for MVP:

- Full sync log root-cause tracing.
- Deep product-to-channel mapping lineage.
- Channel required-field completeness by category.
- Image sync detail and image quality inspection.
- Independent SKU master API if not already confirmed.
- Market, competitor, keyword volume, trend, review, or ads data.

## Mapping Document Structure

`docs/product-agent/02-product-query-api-mapping.md` will use this structure:

1. MVP positioning
   - State that the first version is evidence-based and partial.
   - Explain that missing data must be surfaced through `errors`, `data_completeness`, or explicit answer caveats.

2. Runtime inputs
   - `identifier`
   - `merchant_no`
   - `intent`
   - `filters`
   - `context`
   - runtime variables such as base URL, tenant id, and access token.

3. API mapping table
   - Capability
   - Current API / runtime source
   - Input fields
   - Output fields
   - Evidence source
   - Current limitations

4. Supported MVP intents
   - `overview`
   - `sku_detail`
   - `spu_detail`
   - `channel_listing`
   - `sync_status`
   - `audit_status`
   - `listing_status`
   - `inventory_price`
   - `identity_for_performance`

5. First-version answerable questions
   - What is this product's current OMS/channel status?
   - Which channels have channel products for this SKU/SPU/product?
   - What publish/audit/listing evidence exists?
   - What inventory and price summary is available?
   - What sales query should be passed to `oms_analysis`?

6. First-version non-commitments
   - Questions that must be answered as unsupported, partially supported, or requiring additional APIs.

7. Acceptance cases
   - Overview query.
   - Channel listing query.
   - Listing/audit status query.
   - Inventory and price query.
   - Performance identity query.
   - Missing evidence degradation query.

## Data Flow

For a Product Agent query, the expected first-version flow is:

1. Product Agent calls `product_query` with the user's identifier, merchant number, intent, filters, and runtime context.
2. `product_query` resolves the most reliable available product identity.
3. It collects evidence from the confirmed product, channel product, publish history, and inventory/price sources.
4. It returns a unified result containing summary, reason, evidences, confidence, data completeness, metrics, details, visual blocks, links, and errors.
5. For sales-performance questions, Product Agent or `product_performance` uses `identity_for_performance` to produce `performance_query`, then calls `oms_analysis`.

## Error and Degradation Rules

The mapping document should require these behaviors:

- If an API is not connected, do not synthesize data.
- If evidence is partial, mark `data_completeness` as partial or insufficient.
- If a status exists but the root cause does not, say that the status is visible but the root cause requires sync log or channel error details.
- If market or competitor data is requested, say it is outside MVP unless the user provides data or a future market data skill is connected.
- If identity cannot be resolved, ask for SKU, SPU, product id, or channel product id.

## Testing and Review

Because this step is documentation-only, verification is a review pass rather than automated tests:

- Confirm the document only references capabilities already present in the current Product Agent plan and skills.
- Confirm unsupported areas are clearly marked and not phrased as current behavior.
- Confirm each acceptance case has a clear expected result shape.
- Confirm the document can serve as the implementation guide for a later `product_query` second version.

## Success Criteria

The work is complete when:

- `docs/product-agent/02-product-query-api-mapping.md` exists.
- It documents MVP APIs and runtime sources without overclaiming unsupported integrations.
- It lists answerable and non-answerable Product Agent questions.
- It includes acceptance cases for first-version usability.
- It can be used directly to guide follow-up implementation or frontend integration.
