# Rule Engine Input Contract

The OCR/vision layer supplies one product object to `rule_engine.py`. The rule engine is the authoritative source for scope, exemptions, declaration violations, font/placement checks, language checks, and the final compliance verdict.

## Required fields

| Field | Type | Notes |
|---|---|---|
| `manufacturer_address` | string | Full extracted manufacturer/packer/importer block |
| `commodity_name` | string | Common or generic product name |
| `net_quantity` | string | Raw printed value, for example `500 g` |
| `net_quantity_value_g_ml` | number | Normalized grams or millilitres |
| `quantity_type` | string | `weight_or_volume` or `length_area_or_number` |
| `mrp` | string | Raw printed price and inclusive-tax wording |
| `mfg_date` | string | MM/YYYY, MMM YYYY, or MM-YYYY |
| `consumer_care` | string | Consumer complaint contact block |
| `is_imported` | boolean | Enables country-of-origin requirement |
| `buyer_type` | string | `retail`, `institutional`, or `industrial` |
| `category` | string | One of the category identifiers in the supplied config |
| `font_heights_mm` | object | Millimetres, never uncalibrated pixels |
| `is_embossed` | boolean | Molded/embossed declaration flag |
| `letter_width_height_ratios` | object | Width/height ratio by field |
| `detected_language` | string | `en` or `hi` |

## Optional geometry fields

`country_of_origin`, `pdp_area_cm2`, `pdp_box`, `declaration_boxes`, `nearest_other_text_distance_mm`, `body_text_height_mm`, `contrast_ok`, and `dimensions` enable conditional rules when available.

Physical font checks require a known scale, calibrated capture setup, package dimensions, or a reference marker. The vision prompt leaves millimetre values empty rather than inventing them when no reliable scale is visible.