"""Tests for the instance config layer (single env fallback + multi-instance YAML)."""

import pytest

from ipsymcon_mcp.client import IPSConfigError
from ipsymcon_mcp.config import make_client

_ENV = ["IPS_INSTANCES_FILE", "IPS_URL", "IPS_USER", "IPS_PASSWORD", "IPS_DEFAULT_INSTANCE"]


def _clear(monkeypatch):
    for v in _ENV:
        monkeypatch.delenv(v, raising=False)


def test_single_env_url_is_the_default_instance(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IPS_URL", "http://10.0.0.1:3777/api/")
    assert "10.0.0.1" in make_client().url


def test_yaml_file_defines_named_instances(monkeypatch, tmp_path):
    _clear(monkeypatch)
    f = tmp_path / "instances.yaml"
    f.write_text(
        "default: home\n"
        "instances:\n"
        "  home:\n"
        "    url: http://10.0.0.1:3777/api/\n"
        "  linux:\n"
        "    url: http://10.0.0.2:3777/api/\n"
    )
    monkeypatch.setenv("IPS_INSTANCES_FILE", str(f))
    assert "10.0.0.1" in make_client().url          # falls back to 'default'
    assert "10.0.0.1" in make_client("home").url
    assert "10.0.0.2" in make_client("linux").url


def test_unknown_instance_raises(monkeypatch, tmp_path):
    _clear(monkeypatch)
    f = tmp_path / "instances.yaml"
    f.write_text("default: home\ninstances:\n  home:\n    url: http://10.0.0.1:3777/api/\n")
    monkeypatch.setenv("IPS_INSTANCES_FILE", str(f))
    with pytest.raises(IPSConfigError):
        make_client("nope")


def test_no_config_at_all_raises(monkeypatch):
    _clear(monkeypatch)
    with pytest.raises(IPSConfigError):
        make_client()
