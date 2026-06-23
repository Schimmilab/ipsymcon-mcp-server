"""Tests for the navigation / observation tools: variable-by-path, snapshot, diff,
object-tree. All are read-only (no IPS_ENABLE_WRITE gate). IP-Symcon is mocked at
the ``_client`` seam; tests pin the call sequence and the JSON result shape.
"""

import asyncio
import json
from unittest.mock import AsyncMock, call, patch

import ipsymcon_mcp.server as server
from ipsymcon_mcp.server import (
    DiffVariablesInput,
    GetObjectTreeInput,
    GetVariableByPathInput,
    SnapshotVariablesInput,
    ips_diff_variables,
    ips_get_object_tree,
    ips_get_variable_by_path,
    ips_snapshot_variables,
)


def _run(coro):
    return asyncio.run(coro)


def test_get_variable_by_path_walks_the_tree():
    fake = AsyncMock()
    fake.call.side_effect = [100, 200, 300, True]  # 3x resolve segment, then GetValue
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_get_variable_by_path(GetVariableByPathInput(path="Räume/Büro/Zustand")))
    assert json.loads(out) == {"path": "Räume/Büro/Zustand", "variable_id": 300, "value": True}
    assert fake.call.await_args_list == [
        call("IPS_GetObjectIDByName", ["Räume", 0]),
        call("IPS_GetObjectIDByName", ["Büro", 100]),
        call("IPS_GetObjectIDByName", ["Zustand", 200]),
        call("GetValue", [300]),
    ]


def test_snapshot_variables_reads_each_value():
    fake = AsyncMock()
    fake.call.side_effect = [21.5, False]
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_snapshot_variables(SnapshotVariablesInput(variable_ids=[10, 20])))
    assert json.loads(out) == {"variables": {"10": 21.5, "20": False}, "count": 2}
    assert fake.call.await_args_list == [call("GetValue", [10]), call("GetValue", [20])]


def test_diff_variables_reports_only_changes():
    fake = AsyncMock()
    fake.call.side_effect = [22.0, False]  # 10 changed 21.5->22.0, 20 unchanged
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_diff_variables(DiffVariablesInput(before={"10": 21.5, "20": False})))
    data = json.loads(out)
    assert data == {
        "changed": {"10": {"before": 21.5, "after": 22.0}},
        "changed_count": 1,
        "unchanged_count": 1,
    }
    assert fake.call.await_args_list == [call("GetValue", [10]), call("GetValue", [20])]


def test_get_object_tree_builds_nested_structure_within_depth():
    fake = AsyncMock()
    fake.call.side_effect = [
        {"ObjectName": "", "ObjectType": 0},     # GetObject 0 (root)
        [10, 20],                                # GetChildrenIDs 0
        {"ObjectName": "A", "ObjectType": 0},    # GetObject 10
        [11],                                    # GetChildrenIDs 10
        {"ObjectName": "A1", "ObjectType": 2},   # GetObject 11 (depth 2 -> no children fetch)
        {"ObjectName": "B", "ObjectType": 2},    # GetObject 20
        [],                                      # GetChildrenIDs 20
    ]
    with patch.object(server, "_client", return_value=fake):
        out = _run(ips_get_object_tree(GetObjectTreeInput(root_id=0, max_depth=2)))
    assert json.loads(out) == {
        "id": 0, "name": "", "type": "Category",
        "children": [
            {"id": 10, "name": "A", "type": "Category",
             "children": [{"id": 11, "name": "A1", "type": "Variable"}]},
            {"id": 20, "name": "B", "type": "Variable"},
        ],
    }
