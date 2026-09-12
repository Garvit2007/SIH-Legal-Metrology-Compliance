import uuid


def test_scan_uses_supplied_rule_engine_as_authoritative_verdict(client):
    response = client.post('/compliance/scans', json={
        'product_name': f'tscheck-ruleeng-{uuid.uuid4().hex[:8]}',
        'category': 'Food & Grocery', 'region': 'Delhi NCR', 'inspector': 'TS Inspector'
    })
    assert response.status_code == 200, response.text[:300]
    record = response.json()

    report = record['rule_engine_report']
    assert report is not None
    assert report['rule_version'] == '2017-amendment'

    declarations = {d['key']: d for d in record['declarations']}
    assert len(declarations) == 6

    # font-height declaration must be a violation citing the Table-I threshold via the rule engine
    font_decl = declarations['font_size_pdp']
    assert font_decl['status'] == 'non_compliant'
    assert font_decl['reason'].startswith('Rule engine')
    assert 'Table-I' in font_decl['rule_code'] or 'TABLE_I' in report['violations'][0]['rule_id']

    violation_ids = [v['rule_id'] for v in report['violations']]
    assert any('HEIGHT_TABLE_I' in v for v in violation_ids)

    # compliant declarations should cite passed rule-engine checks, not raw Gemini verdicts
    compliant_decl = declarations['mrp']
    assert compliant_decl['status'] == 'compliant'
    assert compliant_decl['reason'].startswith('Rule engine passed')
