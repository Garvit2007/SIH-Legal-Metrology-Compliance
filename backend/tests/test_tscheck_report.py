

def test_report_update_rejects_unknown_scan(client):
    response = client.patch('/compliance/scans/tscheck-unknown', json={'remarks':'x','review_status':'verified'})
    assert response.status_code == 404
