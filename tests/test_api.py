from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

KEY = 'test-key-only'
HEADERS = {'X-API-Key': KEY}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / 'test.db'), KEY)) as c:
        yield c


def event(**changes):
    return {'event_id': 'evt-1', 'camera_id': 'cam-1', 'kind': 'intrusion',
            'confidence': 0.95, 'zone': 'restricted',
            'occurred_at': '2026-01-01T10:00:00+00:00', **changes}


def post(client, **changes):
    return client.post('/api/events', json=event(**changes), headers=HEADERS)


def test_health_and_auth(client):
    assert client.get('/health').json()['status'] == 'ok'
    assert client.get('/').status_code == 200
    assert client.get('/api/events').status_code == 401
    assert client.get('/api/summary', headers={'X-API-Key': 'wrong'}).status_code == 401
    assert client.post('/api/events/evt-1/ack').status_code == 401
    assert client.get('/api/events/evt-1/audit').status_code == 401


@pytest.mark.parametrize(('changes', 'level'), [
    ({}, 'critical'), ({'confidence': 0.8}, 'critical'),
    ({'confidence': 0.799}, 'info'), ({'zone': 'lobby'}, 'info'),
    ({'kind': 'motion'}, 'info'), ({'kind': 'camera_offline'}, 'warning'),
])
def test_rule_boundaries(client, changes, level):
    response = post(client, **changes)
    assert response.status_code == 201
    assert response.json()['event']['severity'] == level


@pytest.mark.parametrize('changes', [
    {'confidence': -0.1}, {'confidence': 1.1}, {'kind': 'unknown'},
    {'camera_id': '<script>'}, {'occurred_at': '2026-01-01T10:00:00'},
    {'zone': ''}, {'extra_field': 'unexpected'},
])
def test_validation(client, changes):
    assert post(client, **changes).status_code == 422


def test_idempotency_and_conflict(client):
    assert post(client).status_code == 201
    retry = post(client)
    assert retry.status_code == 200 and retry.json()['duplicate']
    assert post(client, confidence=0.5).status_code == 409
    assert client.get('/api/summary', headers=HEADERS).json()['total'] == 1


def test_acknowledgement_and_audit(client):
    post(client)
    path = '/api/events/evt-1/ack'
    first = client.post(path, headers=HEADERS)
    second = client.post(path, headers=HEADERS)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()['status'] == 'acknowledged'
    audit = client.get('/api/events/evt-1/audit', headers=HEADERS).json()['items']
    assert [r['action'] for r in audit] == ['ingested', 'acknowledged']
    assert client.get('/api/summary', headers=HEADERS).json()['critical_open'] == 0
    assert client.post('/api/events/missing/ack', headers=HEADERS).status_code == 404


def test_filter_and_pagination(client):
    post(client)
    post(client, event_id='evt-2', kind='motion')
    page = client.get('/api/events?severity=critical&status=open&limit=1', headers=HEADERS).json()
    assert page['total'] == 1 and page['items'][0]['event_id'] == 'evt-1'
    page = client.get('/api/events?limit=1&offset=1', headers=HEADERS).json()
    assert page['total'] == 2 and len(page['items']) == 1
    assert client.get('/api/events?limit=101', headers=HEADERS).status_code == 422
    assert client.get('/api/events?severity=invalid', headers=HEADERS).status_code == 422


def test_concurrent_retries(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: post(client).status_code, range(16)))
    assert statuses.count(201) == 1
    assert statuses.count(200) == 15
    assert client.get('/api/summary', headers=HEADERS).json()['total'] == 1


def test_persistence_across_app_restart(tmp_path):
    path = str(tmp_path / 'persistent.db')
    with TestClient(create_app(path, KEY)) as first:
        post(first)
    with TestClient(create_app(path, KEY)) as second:
        assert second.get('/api/summary', headers=HEADERS).json()['total'] == 1


def test_missing_server_key_fails_closed(tmp_path):
    with TestClient(create_app(str(tmp_path / 'closed.db'), '')) as c:
        assert c.get('/api/events', headers=HEADERS).status_code == 503


def test_request_ids(client):
    a, b = client.get('/health'), client.get('/health')
    assert a.headers['x-request-id'] != b.headers['x-request-id']
