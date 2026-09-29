import importlib.util
import shutil

import pytest
from conftest import ROOT

spec = importlib.util.spec_from_file_location('verify_platform_sbom', ROOT/'scripts/verify_platform_sbom.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_verified_inventory_matches_pinned_base():
    assert helper.verify().is_file()


@pytest.mark.parametrize('damage', ['base', 'inventory'])
def test_base_updates_and_inventory_tampering_require_review(tmp_path, damage):
    target = tmp_path/'platform/grafana'
    shutil.copytree(ROOT/'platform/grafana', target)
    if damage == 'base':
        path = target/'Dockerfile'
        path.write_text(path.read_text().replace('dhi.io/grafana:13.2.2', 'dhi.io/grafana:13.2.3'))
    else:
        path = target/'security/base-sbom.spdx.json'
        path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError):
        helper.verify(tmp_path)
