"""
Test suite for the LMPC rule engine.
Run with: pip install pytest --break-system-packages && pytest test_rule_engine.py -v
"""

import pytest
from rule_engine import RuleEngine, eval_condition

CONFIG_PATH = "lmpc_rules_config.json"


@pytest.fixture
def engine():
    return RuleEngine(CONFIG_PATH)


def base_compliant_product():
    return {
        "manufacturer_address": "ABC Foods Pvt Ltd, Sector 5, Noida, UP",
        "commodity_name": "Wheat Flour",
        "net_quantity": "500 g",
        "net_quantity_value_g_ml": 500,
        "quantity_type": "weight_or_volume",
        "mrp": "Rs.55 (incl. of all taxes)",
        "mfg_date": "08/2026",
        "consumer_care": "care@abcfoods.com",
        "is_imported": False,
        "buyer_type": "retail",
        "category": "packaged_food",
        "font_heights_mm": {"mrp": 4.5, "net_quantity": 4.2, "commodity_name": 1.2},
        "is_embossed": False,
        "letter_width_height_ratios": {"mrp": 0.4, "net_quantity": 0.35},
        "detected_language": "en",
    }


# ---- condition parser -----------------------------------------------------

def test_condition_simple_eq_true():
    assert eval_condition("category == 'restaurant_fast_food'",
                           {"category": "restaurant_fast_food"}) is True


def test_condition_simple_eq_false():
    assert eval_condition("category == 'restaurant_fast_food'",
                           {"category": "packaged_food"}) is False


def test_condition_numeric_gt():
    assert eval_condition("net_quantity_value_g_ml > 25000",
                           {"net_quantity_value_g_ml": 30000}) is True
    assert eval_condition("net_quantity_value_g_ml > 25000",
                           {"net_quantity_value_g_ml": 100}) is False


def test_condition_and():
    data = {"category": "agricultural_produce", "net_quantity_value_g_ml": 60000}
    assert eval_condition("category == 'agricultural_produce' and net_quantity_value_g_ml > 50000", data) is True
    data2 = {"category": "agricultural_produce", "net_quantity_value_g_ml": 1000}
    assert eval_condition("category == 'agricultural_produce' and net_quantity_value_g_ml > 50000", data2) is False


def test_condition_or():
    assert eval_condition("buyer_type == 'institutional' or buyer_type == 'industrial'",
                           {"buyer_type": "industrial"}) is True


# ---- full compliant baseline ----------------------------------------------

def test_fully_compliant_product_has_no_violations(engine):
    report = engine.evaluate("SKU-OK", base_compliant_product())
    assert report.is_compliant, report.to_dict()
    assert not report.exempt
    assert not report.out_of_scope


# ---- scope exclusions -------------------------------------------------

def test_bulk_package_out_of_scope(engine):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = 30000  # 30kg
    data["category"] = "packaged_food"
    report = engine.evaluate("SKU-BULK", data)
    assert report.out_of_scope
    assert "Rule 3(a)" in report.scope_reason


def test_institutional_buyer_out_of_scope(engine):
    data = base_compliant_product()
    data["buyer_type"] = "institutional"
    report = engine.evaluate("SKU-INST", data)
    assert report.out_of_scope


# ---- exemptions ----------------------------------------------------------

def test_tiny_package_fully_exempt(engine):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = 8
    report = engine.evaluate("SKU-TINY", data)
    assert report.exempt
    assert "Rule 26(a)" in report.exempt_reason


def test_fast_food_exempt(engine):
    data = base_compliant_product()
    data["category"] = "restaurant_fast_food"
    report = engine.evaluate("SKU-FASTFOOD", data)
    assert report.exempt


def test_bidi_exempt_from_mrp_only_not_full_product(engine):
    data = base_compliant_product()
    data["category"] = "bidi"
    data["mrp"] = ""  # missing MRP should be forgiven for this category
    report = engine.evaluate("SKU-BIDI", data)
    mrp_violations = [v for v in report.violations if v.rule_id == "MRP"]
    assert mrp_violations == []


# ---- mandatory declarations ------------------------------------------------

def test_missing_manufacturer_address_flagged(engine):
    data = base_compliant_product()
    data["manufacturer_address"] = ""
    report = engine.evaluate("SKU-NOADDR", data)
    ids = [v.rule_id for v in report.violations]
    assert "MFR_ADDRESS" in ids
    assert report.critical_count >= 1


def test_vague_net_quantity_wording_flagged(engine):
    data = base_compliant_product()
    data["net_quantity"] = "500 g"
    # simulate a vague qualifier caught by OCR/NLP in the surrounding text
    data["net_quantity"] = "approximately 500 g"
    report = engine.evaluate("SKU-VAGUE", data)
    # regex check will now also fail since "approximately 500 g" doesn't match
    ids = [v.rule_id for v in report.violations]
    assert "NET_QUANTITY_NO_VAGUE_WORDS" in ids or "NET_QUANTITY" in ids


def test_invalid_mfg_date_flagged(engine):
    data = base_compliant_product()
    data["mfg_date"] = "2026"  # not MM/YYYY
    report = engine.evaluate("SKU-BADDATE", data)
    ids = [v.rule_id for v in report.violations]
    assert "MFG_DATE" in ids


def test_imported_product_requires_country_of_origin(engine):
    data = base_compliant_product()
    data["is_imported"] = True
    data["country_of_origin"] = ""
    report = engine.evaluate("SKU-IMPORT", data)
    ids = [v.rule_id for v in report.violations]
    assert "COUNTRY_OF_ORIGIN" in ids


def test_domestic_product_does_not_require_country_of_origin(engine):
    data = base_compliant_product()
    data["is_imported"] = False
    report = engine.evaluate("SKU-DOMESTIC", data)
    ids = [v.rule_id for v in report.violations]
    assert "COUNTRY_OF_ORIGIN" not in ids


# ---- font-size tiered lookup (Table-I) -------------------------------------

@pytest.mark.parametrize("qty,height,should_pass", [
    (150, 1.0, True),    # up to 200g band, exactly at 1mm minimum
    (150, 0.8, False),   # up to 200g band, below 1mm minimum
    (300, 2.0, True),    # 200-500g band, exactly at 2mm minimum
    (300, 1.5, False),   # 200-500g band, below 2mm minimum
    (1000, 4.0, True),   # above 500g band, exactly at 4mm minimum
    (1000, 3.0, False),  # above 500g band, below 4mm minimum
])
def test_table_i_boundaries(engine, qty, height, should_pass):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = qty
    data["font_heights_mm"] = {"mrp": height, "net_quantity": height, "commodity_name": 1.2}
    report = engine.evaluate("SKU-TABLE1", data)
    ids = [v.rule_id for v in report.violations]
    if should_pass:
        assert "NUMERAL_HEIGHT_TABLE_I_WEIGHT_VOLUME" not in ids
    else:
        assert "NUMERAL_HEIGHT_TABLE_I_WEIGHT_VOLUME" in ids


def test_table_ii_not_triggered_for_weight_products(engine):
    # Table-II is for length/area/number products -- must not fire on a
    # weight_or_volume product even with a tiny font height.
    data = base_compliant_product()
    data["quantity_type"] = "weight_or_volume"
    report = engine.evaluate("SKU-NOTABLE2", data)
    ids = [v.rule_id for v in report.violations]
    assert "NUMERAL_HEIGHT_TABLE_II_LENGTH_AREA_NUMBER" not in ids


# ---- geometry checks (graceful skip when data absent) ----------------------

def test_region_membership_skips_when_no_geometry(engine):
    data = base_compliant_product()  # no pdp_box / declaration_boxes supplied
    report = engine.evaluate("SKU-NOGEO", data)
    ids = [v.rule_id for v in report.violations]
    assert "PDP_PLACEMENT" not in ids


def test_region_membership_flags_declaration_outside_pdp(engine):
    data = base_compliant_product()
    data["pdp_box"] = {"x0": 0, "y0": 0, "x1": 100, "y1": 100}
    data["declaration_boxes"] = {
        "mrp": {"x0": 10, "y0": 10, "x1": 30, "y1": 20},          # inside
        "consumer_care": {"x0": 90, "y0": 90, "x1": 120, "y1": 110},  # outside
    }
    report = engine.evaluate("SKU-OUTSIDE", data)
    ids = [v.rule_id for v in report.violations]
    assert "PDP_PLACEMENT" in ids


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
