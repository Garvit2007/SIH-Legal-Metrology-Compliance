import base64
import uuid


def test_scan_create_and_review(client):
    scan_id = None
    png = base64.b64encode(b"not-a-real-png-but-base64").decode()
    response = client.post('/compliance/scans', json={
        'product_name': f'tscheck-scan-{uuid.uuid4().hex[:8]}',
        'category': 'Food & Grocery', 'region': 'Delhi NCR', 'inspector': 'TS Inspector',
        'image_base64': png, 'mime_type': 'image/png'
    })
    assert response.status_code == 200, response.text[:300]
    record = response.json(); scan_id = record['id']
    assert len(record['declarations']) == 6
    updated = client.patch(f'/compliance/scans/{scan_id}', json={'remarks':'tscheck remark','review_status':'verified'})
    assert updated.status_code == 200, updated.text[:300]
    assert updated.json()['remarks'] == 'tscheck remark'
    assert updated.json()['review_status'] == 'verified'
