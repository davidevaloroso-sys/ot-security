import importlib.util
import sys

import pytest
from conftest import ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('postdeploy_check', ROOT / 'scripts/postdeploy_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def frame(times, values):
    return {'schema': {'fields': [{'type': 'time'}, {'type': 'number'}]},
            'data': {'values': [times, values]}}


@pytest.mark.parametrize('frames', [[], [frame([], [])], [frame([1], [25])],
                                  [frame([999_999], [None])], [frame([1_100_000], [25])],
                                  [frame([999_999], [])], [frame([999_999], [float('nan')])],
                                  [frame([999_999], [float('inf')])]])
def test_empty_stale_invalid_and_future_data_do_not_pass(frames):
    assert not check.has_recent_reading(frames, 1_000_000)


def test_current_numeric_reading_passes():
    assert check.has_recent_reading([frame([999_999], [0])], 1_000_000)


@pytest.mark.parametrize('response', [{}, {'results': {'A': {'error': 'secret-like-body'}}},
                                    {'results': {'A': {'status': 403}}}])
def test_query_errors_are_not_accepted_or_logged(monkeypatch, response):
    monkeypatch.setattr(check, 'request', lambda *args: response)
    with pytest.raises(RuntimeError, match='response body withheld') as exc:
        check.query('http://127.0.0.1', 'test-only', 'test')
    assert 'secret-like-body' not in str(exc.value)
