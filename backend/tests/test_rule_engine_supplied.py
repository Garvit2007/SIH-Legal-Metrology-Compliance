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


def test_condition_simple_eq_true():
    assert eval_condition("category == 'restaurant_fast_food'", {"category": "restaurant_fast_food"}) is True


def test_condition_simple_eq_false():
    assert eval_condition("category == 'restaurant_fast_food'", {"category": "packaged_food"}) is False


def test_condition_numeric_gt():
    assert eval_condition("net_quantity_value_g_ml > 25000", {"net_quantity_value_g_ml": 30000}) is True
    assert eval_condition("net_quantity_value_g_ml > 25000", {"net_quantity_value_g_ml": 100}) is False


def test_condition_and():
    data = {"category": "agricultural_produce", "net_quantity_value_g_ml": 60000}
    assert eval_condition("category == 'agricultural_produce' and net_quantity_value_g_ml > 50000", data) is True
    data["net_quantity_value_g_ml"] = 1000
    assert eval_condition("category == 'agricultural_produce' and net_quantity_value_g_ml > 50000", data) is False


def test_condition_or():
    assert eval_condition("buyer_type == 'institutional' or buyer_type == 'industrial'", {"buyer_type": "industrial"}) is True


def test_fully_compliant_product_has_no_violations(engine):
    report = engine.evaluate("SKU-OK", base_compliant_product())
    assert report.is_compliant, report.to_dict()
    assert not report.exempt
    assert not report.out_of_scope


def test_bulk_package_out_of_scope(engine):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = 30000
    data["category"] = "packaged_food"
    report = engine.evaluate("SKU-BULK", data)
    assert report.out_of_scope
    assert "Rule 3(a)" in report.scope_reason


def test_institutional_buyer_out_of_scope(engine):
    data = base_compliant_product()
    data["buyer_type"] = "institutional"
    assert engine.evaluate("SKU-INST", data).out_of_scope


def test_tiny_package_fully_exempt(engine):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = 8
    report = engine.evaluate("SKU-TINY", data)
    assert report.exempt
    assert "Rule 26(a)" in report.exempt_reason


def test_fast_food_exempt(engine):
    data = base_compliant_product()
    data["category"] = "restaurant_fast_food"
    assert engine.evaluate("SKU-FASTFOOD", data).exempt


def test_bidi_exempt_from_mrp_only_not_full_product(engine):
    data = base_compliant_product()
    data["category"] = "bidi"
    data["mrp"] = ""
    report = engine.evaluate("SKU-BIDI", data)
    assert [v for v in report.violations if v.rule_id == "MRP"] == []


def test_missing_manufacturer_address_flagged(engine):
    data = base_compliant_product()
    data["manufacturer_address"] = ""
    report = engine.evaluate("SKU-NOADDR", data)
    assert "MFR_ADDRESS" in [v.rule_id for v in report.violations]
    assert report.critical_count >= 1


def test_vague_net_quantity_wording_flagged(engine):
    data = base_compliant_product()
    data["net_quantity"] = "approximately 500 g"
    ids = [v.rule_id for v in engine.evaluate("SKU-VAGUE", data).violations]
    assert "NET_QUANTITY_NO_VAGUE_WORDS" in ids or "NET_QUANTITY" in ids


def test_invalid_mfg_date_flagged(engine):
    data = base_compliant_product()
    data["mfg_date"] = "2026"
    assert "MFG_DATE" in [v.rule_id for v in engine.evaluate("SKU-BADDATE", data).violations]


def test_imported_product_requires_country_of_origin(engine):
    data = base_compliant_product()
    data["is_imported"] = True
    data["country_of_origin"] = ""
    assert "COUNTRY_OF_ORIGIN" in [v.rule_id for v in engine.evaluate("SKU-IMPORT", data).violations]


def test_domestic_product_does_not_require_country_of_origin(engine):
    data = base_compliant_product()
    data["is_imported"] = False
    assert "COUNTRY_OF_ORIGIN" not in [v.rule_id for v in engine.evaluate("SKU-DOMESTIC", data).violations]


@pytest.mark.parametrize("qty,height,should_pass", [
    (150, 1.0, True),
    (150, 0.8, False),
    (300, 2.0, True),
    (300, 1.5, False),
    (1000, 4.0, True),
    (1000, 3.0, False),
])
def test_table_i_boundaries(engine, qty, height, should_pass):
    data = base_compliant_product()
    data["net_quantity_value_g_ml"] = qty
    data["font_heights_mm"] = {"mrp": height, "net_quantity": height, "commodity_name": 1.2}
    ids = [v.rule_id for v in engine.evaluate("SKU-TABLE1", data).violations]
    if should_pass:
        assert "NUMERAL_HEIGHT_TABLE_I_WEIGHT_VOLUME" not in ids
    else:
        assert "NUMERAL_HEIGHT_TABLE_I_WEIGHT_VOLUME" in ids


def test_table_ii_not_triggered_for_weight_products(engine):
    data = base_compliant_product()
    data["quantity_type"] = "weight_or_volume"
    ids = [v.rule_id for v in engine.evaluate("SKU-NOTABLE2", data).violations]
    assert "NUMERAL_HEIGHT_TABLE_II_LENGTH_AREA_NUMBER" not in ids


def test_region_membership_skips_when_no_geometry(engine):
    report = engine.evaluate("SKU-NOGEO", base_compliant_product())
    assert "PDP_PLACEMENT" not in [v.rule_id for v in report.violations]


def test_region_membership_flags_declaration_outside_pdp(engine):
    data = base_compliant_product()
    data["pdp_box"] = {"x0": 0, "y0": 0, "x1": 100, "y1": 100}
    data["declaration_boxes"] = {
        "mrp": {"x0": 10, "y0": 10, "x1": 30, "y1": 20},
        "consumer_care": {"x0": 90, "y0": 90, "x1": 120, "y1": 110},
    }
    ids = [v.rule_id for v in engine.evaluate("SKU-OUTSIDE", data).violations]
    assert "PDP_PLACEMENT" in ids