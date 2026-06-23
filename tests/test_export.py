"""Tests for ips_export_subtree — rich, recursive serialization of a subtree for
backup/restore. Read-only. IP-Symcon is mocked at the ``_client`` seam; tests pin
the per-type detail (variable type+profile+value, script content) and nesting.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import ipsymcon_mcp.server as server
from ipsymcon_mcp.server import ExportSubtreeInput, ips_export_subtree


def _run(coro):
    return asyncio.run(coro)


def test_export_serializes_category_variable_and_script():
    fake = AsyncMock()
    fake.call.side_effect = [
        {"ObjectName": "Schlafzimmer", "ObjectType": 0},   # GetObject 100 (category)
        [200, 300],                                        # GetChildrenIDs 100
        {"ObjectName": "Temp", "ObjectType": 2},           # GetObject 200 (variable)
        {"VariableType": 2, "VariableProfile": "~Temperature"},  # GetVariable 200
        21.5,                                              # GetValue 200
        [],                                                # GetChildrenIDs 200
        {"ObjectName": "Logik", "ObjectType": 3},          # GetObject 300 (script)
        "<?php echo 1;",                                   # GetScriptContent 300
        [],                                                # GetChildrenIDs 300
    ]
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_export_subtree(ExportSubtreeInput(root_id=100)))
    assert json.loads(out) == {
        "id": 100, "name": "Schlafzimmer", "type": "Category",
        "children": [
            {"id": 200, "name": "Temp", "type": "Variable",
             "variable_type": "Float", "profile": "~Temperature", "value": 21.5},
            {"id": 300, "name": "Logik", "type": "Script", "content": "<?php echo 1;"},
        ],
    }


def test_export_variable_without_profile_is_none():
    fake = AsyncMock()
    fake.call.side_effect = [
        {"ObjectName": "Flag", "ObjectType": 2},  # GetObject 200 (variable)
        {"VariableType": 0},                       # GetVariable 200 (boolean, no profile)
        False,                                     # GetValue 200
        [],                                        # GetChildrenIDs 200
    ]
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_export_subtree(ExportSubtreeInput(root_id=200, max_depth=1)))
    assert json.loads(out) == {
        "id": 200, "name": "Flag", "type": "Variable",
        "variable_type": "Boolean", "profile": None, "value": False,
    }
