# IPS migration — workflow (greenfield v1)

The step-by-step for migrating a subtree from a **source** to a **target** IP-Symcon instance.
Read the `SKILL.md` non-negotiables first. Function signatures: ipsymcon skill's
[ips-functions.md](../../ipsymcon/references/ips-functions.md).

Throughout: pass the source instance name as `instance` on **read** calls, the target name on
**write** calls (multi-instance via `IPS_INSTANCES_FILE`). Single-instance setups omit it.

## Inputs to confirm before you start

| Input | Meaning |
|---|---|
| `source` instance + `root_id` | the subtree to migrate (resolve `root_id` by name/tree, never guess) |
| `target` instance + `target_parent_id` | where the subtree is recreated (`0` = target root) |

## Step 1 — Export the source

`ips_export_subtree(root_id, instance=source)` → rich nested JSON: categories, variables
(type/profile/value), scripts (content), instances (`module_id` + `configuration`), events
(`IPS_GetEvent` detail), links (`target_id`). Keep this JSON — it is the single source of truth
for the whole migration.

## Step 2 — Pre-flight + plan (NO writes)

Stay read-only. Produce the plan the user approves.

1. **Module check.** Collect every instance `module_id` in the export. Call
   `IPS_GetModuleList` (via `ips_call`, instance=target) and compare. **Missing module → its
   instance cannot be created → flag as a blocker** (offer: install the module on the target, or
   skip that instance + its dependents).
2. **Reference scan.** Gather every ID reference that will need remapping:
   - **Scripts:** object IDs inside ID-bearing calls in the PHP (`GetValue(<id>)`,
     `SetValue(<id>,…)`, `RequestAction(<id>,…)`, `IPS_*` taking an ID, `@<id>`…).
   - **Links:** `target_id`.
   - **Events:** variable IDs in triggers (`TriggerVariableID`) and any script/target IDs in the
     event detail.
   - **Instances:** IDs embedded in the `configuration` JSON (parent gateway/IO, linked variables)
     and the connection (parent I/O instance).
   Split them into **in-subtree** (will be in the id_map → remappable) and **out-of-subtree**
   (→ flag "external reference, not remappable").
3. **Smell flags** (surface, do not fix): disabled or empty objects, scripts referencing IDs that
   don't exist even on the source, obviously dead/duplicate structure.
4. **Present the plan and STOP** (plan template below). No write tool runs until the user approves.

### Plan template

```
MIGRATION PLAN  source:<src> root <root_id>  →  target:<tgt> under <parent_id>

Create (Pass 1):
  Categories <n> · Variables <n> · Scripts <n> · Events <n> · Links <n> · Instances <n>

Wire (Pass 2):
  Script ID rewrites:   <count>  (show each: file → old→new IDs, with the surrounding call)
  Link targets:         <count>
  Event triggers:       <count>
  Instance configs:     <count>  (+ connections to parent I/O)

FLAGS (need your decision):
  [BLOCKER] module <guid> not installed on target → instance "<name>" (and N dependents)
  [EXTERNAL] script "<name>" references id <old> outside the subtree → left as-is
  [SMELL]   event "<name>" is disabled on source → recreate disabled? 
```

## Step 3 — Pass 1: create every object, build the id_map

Order matters only in that **all creation happens before any wiring** (Step 4). The id_map
accumulates **old→new** for *every* object.

1. **Structure (deterministic):** `ips_import_subtree(tree=<export>, target_parent_id, instance=target)`.
   It creates **categories, variables, scripts** and returns `id_map` (old→new) + `skipped`
   (the instances/events/links it does not touch). Start your total id_map from its `id_map`.
2. **Instances / events / links (skipped → create shells via `ips_call`, instance=target):**
   walking the export in tree order, for each skipped node create the shell and record old→new:
   - **Instance:** `IPS_CreateInstance(<module_id>)` → `IPS_SetParent(new,<mapped parent>)` →
     `IPS_SetName(new,<name>)`. Configuration + connection come in Pass 2.
   - **Event:** `IPS_CreateEvent(<EventType>)` → `IPS_SetParent` → `IPS_SetName`. Trigger detail in Pass 2.
   - **Link:** `IPS_CreateLink()` → `IPS_SetParent` → `IPS_SetName`. Target in Pass 2.

   Use the **mapped** parent ID (the parent was created already, so it is in the id_map). After
   this step the id_map is **complete** — every source object has a target counterpart.

## Step 4 — Pass 2: wire references (id_map now complete)

Apply only the rewrites shown in the approved plan.

- **Instances:** take the source `configuration` JSON, replace every in-subtree ID with its
  mapped value (leave external IDs, they were flagged) →
  `IPS_SetConfiguration(new, <remapped json>)` → `IPS_ApplyChanges(new)`. Connect to its parent
  I/O if it had one: `IPS_ConnectInstance(new, <mapped parent I/O>)`.
  > `IPS_ApplyChanges` may error when the real hardware/network is absent on a fresh target.
  > That is **expected**, not fatal — record it and move on (the instance exists, it just can't
  > talk to its device yet).
- **Events:** recreate the trigger from the exported event detail with **mapped** IDs:
  `IPS_SetEventTrigger(new, <type>, <mapped TriggerVariableID>)` (or `IPS_SetEventCyclic` /
  schedule actions for cyclic/weekly), then `IPS_SetEventActive(new, <active as on source>)`.
- **Links:** `IPS_SetLinkTargetID(new_link, <mapped target_id>)`.
- **Scripts:** for each script with ID references, rewrite **only** the IDs inside ID-bearing
  calls (per the approved diff) → `ips_set_script_content(new_script, <rewritten php>)`. Leave
  every integer you are not certain is an object ID untouched.

## Step 5 — Verify + report

1. `ips_export_subtree(<new root>, instance=target)` and compare structurally to the source
   (names, types, profiles, values, script content; IDs are expected to differ — compare modulo IDs).
2. **Report:**
   - the complete **id_map** (old→new),
   - **unresolved references** (external IDs left as-is) for manual fixing,
   - **ApplyChanges results** (which instances applied cleanly, which errored on missing hardware),
   - all **flags** carried from the plan.

## `ips_call` recipe cheat-sheet (target instance)

| Purpose | Call |
|---|---|
| List installed modules | `IPS_GetModuleList` → array of module GUIDs |
| Create instance | `IPS_CreateInstance(<module_id>)` → new id |
| Configure instance | `IPS_SetConfiguration(<id>, <json>)` then `IPS_ApplyChanges(<id>)` |
| Connect to parent I/O | `IPS_ConnectInstance(<id>, <parent_io_id>)` |
| Create event | `IPS_CreateEvent(<0 triggered|1 cyclic|2 weekly>)` → new id |
| Event trigger | `IPS_SetEventTrigger(<id>, <triggerType>, <variableID>)` + `IPS_SetEventActive(<id>, <bool>)` |
| Create link | `IPS_CreateLink()` → new id; `IPS_SetLinkTargetID(<id>, <target>)` |
| Delete (rollback) | type-specific — `IPS_DeleteVariable/Category/Script/Event/Instance/Link`, **children before parent** (no generic `IPS_DeleteObject`) |

## Flag catalogue

| Flag | Meaning | Default action |
|---|---|---|
| **BLOCKER — module missing** | target lacks the module for an instance | don't create the instance (or its dependents); ask user to install or skip |
| **EXTERNAL — reference out of subtree** | an ID points outside the migrated tree | leave the reference unchanged; list it for manual fixing |
| **SMELL — disabled/empty/dead** | source object looks unused or off | migrate as-is (preserve state); note it; refactoring is a later skill |
| **APPLY-FAILED** | `IPS_ApplyChanges` errored (no hardware) | expected on greenfield; report, don't roll back |

## Common mistakes

- **Wiring in one pass.** Setting a reference before its target exists → broken link/trigger.
  Always create everything first (Step 3), wire second (Step 4).
- **Blind number replacement in scripts.** Replacing every integer that happens to match an old
  ID corrupts logic (thresholds, timeouts, array indices). Only IDs inside ID-bearing calls, and
  only after the user has seen the diff.
- **Guessing an external ID.** If it's not in the id_map, it is not yours to remap. Flag it.
- **Treating ApplyChanges errors as failure.** On a fresh target without the device, that's
  normal. The object is there; the hardware link is a separate, later concern.
- **Skipping the plan.** This skill exists to *not* change a live house before you've shown the
  plan. If you're about to call a write tool without an approved plan — stop.
