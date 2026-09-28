import pytest


@pytest.fixture(autouse=True)
def _no_gmst_env(monkeypatch):
    """A developer's exported GMST_* variables must not leak into tests (R7: GMST_MODEL=tiny
    turned test_defaults_when_no_file red). Tests that want one set it themselves."""
    import os

    for key in [k for k in os.environ if k.startswith("GMST_")]:
        monkeypatch.delenv(key)
