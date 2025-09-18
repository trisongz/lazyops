from pathlib import Path

from lzl.io.persistence import PersistentDict


def test_persistent_dict_local_backend(tmp_path: Path) -> None:
    cache = PersistentDict(
        name="test",
        backend_type="local",
        base_key="test",
        file_path=tmp_path / "cache.json",
        serializer="json",
    )

    cache["alpha"] = {"value": 1}
    stored_key = cache.get_key("alpha")
    assert cache.get("alpha") == {"value": 1}
    assert cache.base.contains(stored_key)

    cache.set_batch({"beta": 2, "gamma": 3})
    assert cache.get_values(["beta", "gamma"]) == [2, 3]

    cache.delete("beta")
    assert not cache.contains("beta")

    cache.clear()
    assert list(cache) == []
