import importlib.util
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from conftest import ROOT


@pytest.fixture
def integration(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('integration_test', ROOT / 'scripts/integration_test.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_persistence_check_follows_changed_host_port(integration, monkeypatch):
    stack = SimpleNamespace(endpoint=Mock(side_effect=['127.0.0.1:40000', '127.0.0.1:40001']))
    calls = []
    def request(url, token, data):
        calls.append(url)
        if ':40000/' in url:
            return 200, b',result,table,device,_value\n,_result,0,other,26\n'
        return 200, b'#datatype,string,long,string,double\n,result,table,device,_value\n,_result,0,recovery,26\n'
    monkeypatch.setattr(integration, 'request', request)
    assert not integration.reading_persisted(stack, 'test-only', 'query', 'recovery')
    assert integration.reading_persisted(stack, 'test-only', 'query', 'recovery')
    assert ':40000/' in calls[0] and ':40001/' in calls[1]


def test_query_error_is_not_misreported_as_persisted(integration, monkeypatch):
    stack = SimpleNamespace(endpoint=lambda *args: '127.0.0.1:40000')
    monkeypatch.setattr(integration, 'request', lambda *args: (401, b'recovery unauthorized'))
    with pytest.raises(RuntimeError, match='HTTP 401'):
        integration.reading_persisted(stack, 'test-only', 'query', 'recovery')


def test_database_startup_is_retryable(integration, monkeypatch):
    stack = SimpleNamespace(endpoint=lambda *args: '127.0.0.1:40000')
    monkeypatch.setattr(integration, 'request', lambda *args: (503, b'starting'))
    assert not integration.reading_persisted(stack, 'test-only', 'query', 'recovery')


def test_unacknowledged_test_publication_fails_explicitly(integration):
    client = Mock()
    client.publish.return_value = Mock(rc=0)
    client.publish.return_value.is_published.return_value = False
    with pytest.raises(TimeoutError, match='acknowledge'):
        integration.publish_checked(client, 'lab/raspi1/temperature', {'value': 25})
