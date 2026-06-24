"""Tests for ips_import_subtree — the deterministic half of a migration: mechanically
recreate a subtree (as produced by ips_export_subtree) under a target parent and return an
old→new ID map. Write-gated. IP-Symcon is mocked at the ``_client`` seam, mirroring test_export.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import ipsymcon_mcp.server as server
from ipsymcon_mcp.server import ImportSubtreeInput, ips_import_subtree


def _run(coro):
    return asyncio.run(coro)


def _calls(fake):
    return [(c.args[0], list(c.args[1])) for c in fake.call.call_args_list]


def test_import_recreates_category_variable_and_script():
    fake = AsyncMock()
    # IPS call return values, in order: each create returns a fresh id, setters return None.
    fake.call.side_effect = [
        1000,   # IPS_CreateCategory (root)
        None,   # IPS_SetParent  [1000, 0]
        None,   # IPS_SetName    [1000, "Schlafzimmer"]
        1001,   # IPS_CreateVariable [2] (Float)
        None,   # IPS_SetParent  [1001, 1000]
        None,   # IPS_SetName    [1001, "Temp"]
        None,   # IPS_SetVariableCustomProfile [1001, "~Temperature"]
        None,   # SetValue       [1001, 21.5]
        1002,   # IPS_CreateScript [0]
        None,   # IPS_SetParent  [1002, 1000]
        None,   # IPS_SetName    [1002, "Logik"]
        None,   # IPS_SetScriptContent [1002, "<?php echo 1;"]
    ]
    tree = {
        "id": 100, "name": "Schlafzimmer", "type": "Category",
        "children": [
            {"id": 200, "name": "Temp", "type": "Variable",
             "variable_type": "Float", "profile": "~Temperature", "value": 21.5},
            {"id": 300, "name": "Logik", "type": "Script", "content": "<?php echo 1;"},
        ],
    }
    with patch.object(server, "_client", return_value=fake), \
         patch.object(server, "_write_enabled", return_value=True):
        out = _run(ips_import_subtree(ImportSubtreeInput(tree=tree, target_parent_id=0)))

    result = json.loads(out)
    assert result["ok"] is True
    assert result["root_id"] == 1000
    assert result["id_map"] == {"100": 1000, "200": 1001, "300": 1002}
    assert result["created"] == 3
    assert result["skipped"] == []

    calls = _calls(fake)
    # Root category created under the target parent (0).
    assert ("IPS_CreateCategory", []) in calls
    assert ("IPS_SetParent", [1000, 0]) in calls
    # Variable: typed correctly, re-parented under the NEW category id (1000, not old 100).
    assert ("IPS_CreateVariable", [2]) in calls
    assert ("IPS_SetParent", [1001, 1000]) in calls
    assert ("IPS_SetVariableCustomProfile", [1001, "~Temperature"]) in calls
    assert ("SetValue", [1001, 21.5]) in calls
    # Script: re-parented under the new category, content set.
    assert ("IPS_SetParent", [1002, 1000]) in calls
    assert ("IPS_SetScriptContent", [1002, "<?php echo 1;"]) in calls


def test_import_boolean_without_profile_still_sets_false_value():
    """value False is valid — must be written; absent profile must not call SetVariableCustomProfile."""
    fake = AsyncMock()
    fake.call.side_effect = [
        2000,   # IPS_CreateVariable [0] (Boolean)
        None,   # IPS_SetParent [2000, 5]
        None,   # IPS_SetName   [2000, "Flag"]
        None,   # SetValue      [2000, False]
    ]
    tree = {"id": 200, "name": "Flag", "type": "Variable",
            "variable_type": "Boolean", "profile": None, "value": False}
    with patch.object(server, "_client", return_value=fake), \
         patch.object(server, "_write_enabled", return_value=True):
        out = _run(ips_import_subtree(ImportSubtreeInput(tree=tree, target_parent_id=5)))

    result = json.loads(out)
    assert result["id_map"] == {"200": 2000}
    calls = _calls(fake)
    assert ("IPS_CreateVariable", [0]) in calls
    assert ("SetValue", [2000, False]) in calls
    assert not any(m == "IPS_SetVariableCustomProfile" for m, _ in calls)


def test_import_skips_unsupported_types_without_aborting():
    """An instance/event/link is not mechanically recreatable — record it under 'skipped',
    keep importing the rest, and never assign it a new id."""
    fake = AsyncMock()
    fake.call.side_effect = [
        3000,   # IPS_CreateCategory (root)
        None,   # IPS_SetParent [3000, 0]
        None,   # IPS_SetName   [3000, "Raum"]
        # the Instance child is skipped (no IPS calls), then the Variable child:
        3001,   # IPS_CreateVariable [1] (Integer)
        None,   # IPS_SetParent [3001, 3000]
        None,   # IPS_SetName   [3001, "Zaehler"]
    ]
    tree = {
        "id": 100, "name": "Raum", "type": "Category",
        "children": [
            {"id": 200, "name": "Gerät", "type": "Instance", "module_id": "{ABC}", "configuration": "{}"},
            {"id": 300, "name": "Zaehler", "type": "Variable", "variable_type": "Integer",
             "profile": None, "value": None},
        ],
    }
    with patch.object(server, "_client", return_value=fake), \
         patch.object(server, "_write_enabled", return_value=True):
        out = _run(ips_import_subtree(ImportSubtreeInput(tree=tree, target_parent_id=0)))

    result = json.loads(out)
    assert result["id_map"] == {"100": 3000, "300": 3001}
    assert result["created"] == 2
    assert result["skipped"] == [{"id": 200, "type": "Instance",
                                  "reason": "not mechanically importable — needs the migration skill "
                                            "(instance/event/link config + reference remapping)"}]
    # Integer variable with no profile and value None: no profile/SetValue calls.
    calls = _calls(fake)
    assert ("IPS_CreateVariable", [1]) in calls
    assert not any(m == "SetValue" for m, _ in calls)


def test_import_requires_write_enabled():
    with patch.object(server, "_write_enabled", return_value=False):
        out = _run(ips_import_subtree(
            ImportSubtreeInput(tree={"id": 1, "name": "x", "type": "Category"}, target_parent_id=0)))
    assert "disabled" in out.lower()
