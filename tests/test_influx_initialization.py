import importlib.util
from unittest.mock import Mock

import pytest

from conftest import ROOT


@pytest.fixture
def helper(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('initialize_influx', ROOT / 'scripts/initialize_influx.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('allowed', [True, False])
def test_setup_only_initializes_an_empty_database(helper, monkeypatch, allowed):
    responses = [{'allowed': allowed}]
    if allowed:
        responses.append({})
    responses += [{'orgs': [{'id': 'org-id'}]}, {'buckets': [{'id': 'bucket-id'}]}]
    api = Mock(side_effect=responses)
    monkeypatch.setattr(helper, 'api', api)
    assert helper.initialize('http://127.0.0.1:8086', 'admin', 'password', 'test-token', 'lab', 'ot') is allowed
    writes = [call for call in api.call_args_list if len(call.args) == 4]
    assert len(writes) == int(allowed)
    if allowed:
        assert writes[0].args[2] == '/api/v2/setup'
        assert writes[0].args[3]['token'] == 'test-token'


def test_initialized_database_with_different_org_fails_without_writing(helper, monkeypatch):
    api = Mock(side_effect=[{'allowed': False}, {'orgs': []}])
    monkeypatch.setattr(helper, 'api', api)
    with pytest.raises(ValueError, match='organization'):
        helper.initialize('http://127.0.0.1:8086', 'admin', 'password', 'test-token', 'lab', 'ot')
    assert all(len(call.args) == 3 for call in api.call_args_list)


@pytest.mark.parametrize('state', [{}, {'allowed': 'true'}, {'allowed': 1}])
def test_invalid_setup_state_fails_closed(helper, monkeypatch, state):
    api = Mock(return_value=state)
    monkeypatch.setattr(helper, 'api', api)
    with pytest.raises(ValueError, match='setup response'):
        helper.initialize('http://127.0.0.1:8086', 'admin', 'password', 'test-token', 'lab', 'ot')
    assert api.call_count == 1
