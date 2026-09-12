# Rule Engine Input Contract

This is the data shape the rule engine (`rule_engine.py`) expects per product.
Share this with Shreyansh (OCR/AI) early — it's the seam between his pipeline
and Garvit's rule engine, and it should be agreed before either side builds
much further.

## Required fields (no compliance check runs correctly without these)

| Field | Type | Example | Notes |
|---|---|---|---|
| `manufacturer_address` | str | `"ABC Foods Pvt Ltd, Sector 5, Noida, UP"` | Full extracted text block |
| `commodity_name` | str | `"Wheat Flour"` | |
| `net_quantity` | str | `"500 g"` | Raw text as printed |
| `net_quantity_value_g_ml` | float | `500` | Parsed numeric value, normalized to g or ml |
| `quantity_type` | str | `"weight_or_volume"` or `"length_area_or_number"` | Determines whether Table-I or Table-II applies |
| `mrp` | str | `"Rs.55 (incl. of all taxes)"` | Raw text as printed |
| `mfg_date` | str | `"08/2026"` | MM/YYYY, MMM YYYY, or MM-YYYY |
| `consumer_care` | str | `"care@abcfoods.com, 1800-XXX-XXXX"` | |
| `is_imported` | bool | `false` | |
| `buyer_type` | str | `"retail"` \| `"institutional"` \| `"industrial"` | Determines Rule 3 scope |
| `category` | str | see category list below | Drives exemption logic |
| `font_heights_mm` | dict | `{"mrp": 2.5, "net_quantity": 1.8, "commodity_name": 1.2}` | **mm, not pixels** — see conversion note |
| `is_embossed` | bool | `false` | Whether text is blown/molded/embossed/perforated |
| `letter_width_height_ratios` | dict | `{"mrp": 0.4}` | width/height per field |
| `detected_language` | str | `"en"` or `"hi"` | ISO-ish code |

## Optional fields (enable extra checks when present; checks pass through as N/A when absent — they will NOT fail a product for missing geometry)

| Field | Type | Purpose |
|---|---|---|
| `country_of_origin` | str | Required only if `is_imported: true` |
| `pdp_area_cm2` | float | Needed for Table-II lookup |
| `pdp_box` | `{x0,y0,x1,y1}` | Principal Display Panel bounding box |
| `declaration_boxes` | `{field_name: {x0,y0,x1,y1}, ...}` | Bounding box per declaration, same coordinate space as `pdp_box` |
| `nearest_other_text_distance_mm` | `{"top","bottom","left","right"}` | Clear-space check around net quantity |
| `body_text_height_mm` | float | For MRP/net-qty prominence check |
| `contrast_ok` | `{field_name: bool}` | From a contrast-ratio calculation against background |

## `category` values currently recognized by the exemption logic
`packaged_food`, `restaurant_fast_food`, `drugs_price_control_order`,
`agricultural_produce`, `bidi_or_incense`, `bidi`, `domestic_lpg_cylinder_psu`,
`domestic_lpg_cylinder_apm`, `dimension_relevant_textile`,
`cement_or_fertilizer`. Extend this list together as new product categories
come up — it's a plain string match in the config, not a hardcoded enum.

## Critical conversion note: pixels → mm

Font height checks are legally defined in **millimetres on the physical
package**, not pixels in the photo. Shreyansh's pipeline needs one of:
- a known reference object/marker in the frame (e.g. a ruler or ArUco marker) to compute px→mm scale, or
- user-provided package dimensions (e.g. "this is a 500ml bottle, 20cm tall") to estimate scale, or
- a calibrated camera setup (fixed distance, fixed focal length) for a controlled scanning station.

Flag this explicitly in your pitch as a known limitation/assumption — judges
respect an accurate scoping statement far more than a hand-wave.

## Testing the contract

Run `python3 rule_engine.py` for a working example, and
`pytest test_rule_engine.py -v` to see the full behavior spec as executable
tests. Any change to this schema should come with an updated test case.
