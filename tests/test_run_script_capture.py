"""Tests for the ips_run_script_capture tool.

The tool wraps IPS_RunScriptWaitEx, which executes a script and returns its
**output** (what the script echoes/prints — IP-Symcon does NOT capture a top-level
PHP ``return``). The IP-Symcon server is the external boundary and is mocked at the
``_client`` seam — these tests pin the tool's own behavior (which IPS method it
calls, the output contract, and the IPS_ENABLE_WRITE gate).
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import ipsymcon_mcp.server as server
from ipsymcon_mcp.server import RunScriptCaptureInput, ips_run_script_capture


def _run(coro):
    return asyncio.run(coro)


def test_returns_captured_script_output_when_write_enabled(monkeypatch):
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    fake = AsyncMock()
    fake.call.return_value = "ECHO-42"  # IPS returns the script's echoed output
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_run_script_capture(RunScriptCaptureInput(script_id=23942)))

    data = json.loads(out)
    assert data["script_id"] == 23942
    assert data["output"] == "ECHO-42"
    assert data["ok"] is True
    fake.call.assert_awaited_once_with("IPS_RunScriptWaitEx", [23942, {}])


def test_passes_named_parameters_to_the_script(monkeypatch):
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    fake = AsyncMock()
    fake.call.return_value = ""
    with patch.object(server, "_client", return_value=fake):
        _run(ips_run_script_capture(
            RunScriptCaptureInput(script_id=100, parameters={"mode": "test"})
        ))

    fake.call.assert_awaited_once_with("IPS_RunScriptWaitEx", [100, {"mode": "test"}])


def test_blocked_when_write_disabled(monkeypatch):
    monkeypatch.setenv("IPS_ENABLE_WRITE", "false")
    fake = AsyncMock()
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_run_script_capture(RunScriptCaptureInput(script_id=1)))

    assert "IPS_ENABLE_WRITE" in out
    fake.call.assert_not_awaited()
