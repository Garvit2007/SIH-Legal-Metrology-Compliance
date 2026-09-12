import uuid


def test_dashboard_has_analytics_shapes(client):
    created = client.post('/compliance/scans', json={'product_name':f'tscheck-analytics-{uuid.uuid4().hex[:8]}','category':'Test','region':'Karnataka','inspector':'TS Inspector'})
    assert created.status_code == 200, created.text[:300]
    response = client.get('/compliance/dashboard')
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert set(body) == {'stats','violation_types','regions','trend'}
    assert {'total_scanned','violation_rate','pending_reviews','reports_issued'} <= set(body['stats'])
    assert len(body['trend']) >= 6
    assert body['regions']
