from pathlib import Path

from lzl.io.persistence import TemporaryData


def test_temporary_data_roundtrip(tmp_path: Path) -> None:
    store = TemporaryData(filedir=tmp_path)
    store["alpha"] = 1
    assert store.get("alpha") == 1
    assert "alpha" in store

    with store.ctx() as data:
        data["alpha"] = 2
    assert store["alpha"] == 2

    store.setdefault("beta", [])
    is_duplicate = store.append("beta", "value")
    assert is_duplicate is False
    is_duplicate = store.append("beta", "value")
    assert is_duplicate is True

    store.cleanup_on_exit()
    assert not store.filepath.exists()
    assert not store.filelock_path.exists()
