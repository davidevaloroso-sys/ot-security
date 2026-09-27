import importlib.util
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ia():
    return load('inference', 'IA-integration/ia-consumer/mqtt_anomaly_consumer.py')


@pytest.fixture
def training():
    return load('training', 'IA-integration/ia-consumer/train_model.py')


@pytest.fixture
def simulator():
    return load('simulator', 'IA-integration/raspi-simulator/main.py')


@pytest.fixture(autouse=True)
def health_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('HEALTH_DIR', str(tmp_path))


@pytest.fixture
def payload():
    return {'device': 'raspi1', 'ts': 1, 'value': 25.0, 'unit': 'C'}
