

def test_rules_reference_returns_six_rules(client):
    response = client.get('/compliance/rules')
    assert response.status_code == 200, response.text[:300]
    rules = response.json()
    assert len(rules) == 6
    assert {rule['id'] for rule in rules} == {'mrp','net_quantity','manufacturer_details','date_mfg','consumer_care','font_size_pdp'}
    assert all(rule['mandatory'] is True for rule in rules)
