import uuid


def test_scan_record_lookup_and_not_found(client):
    product = f'tscheck-repository-{uuid.uuid4().hex[:8]}'
    created = client.post('/compliance/scans', json={'product_name':product,'category':'Test','region':'Maharashtra','inspector':'TS Inspector'})
    assert created.status_code == 200, created.text[:300]
    scan_id = created.json()['id']
    listed = client.get('/compliance/scans')
    assert listed.status_code == 200
    assert any(row['id'] == scan_id and row['product_name'] == product for row in listed.json())
    opened = client.get(f'/compliance/scans/{scan_id}')
    assert opened.status_code == 200
    assert opened.json()['id'] == scan_id
    missing = client.get('/compliance/scans/tscheck-missing-record')
    assert missing.status_code == 404
