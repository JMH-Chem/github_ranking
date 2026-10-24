import pytest

from pipeline import config


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point the pipeline at an empty data/ and work/ directory."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "WORK_DIR", tmp_path / "work")
    return tmp_path / "data"
