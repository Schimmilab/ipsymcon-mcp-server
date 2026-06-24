# IP-Symcon function reference (for `ips_call`)

The `ipsymcon` MCP has dedicated tools for the common cases — values, scripts, and the
**basic create** of categories/variables/events (`ips_create_category` /
`ips_create_variable` / `ips_create_event`). Everything else — event trigger/cyclic
config, instances, profiles, renaming, moving, deleting — goes through
`ips_call(method, params)`, where `params` is the **positional** argument list of the
IP-Symcon PHP function. The create recipes below show the underlying calls (useful when a
dedicated tool isn't enough, e.g. wiring an event's trigger after `ips_create_event`).

Always verify exotic signatures against the official command reference:
https://www.symcon.de/service/dokumentation/befehlsreferenz/ — IP-Symcon versions add and
change functions, and getting a parameter order wrong on a write is exactly what the plan
step is there to catch.

## Object basics (apply to every object type)

- `IPS_SetParent(int ID, int ParentID)` — move an object under a parent (`0` = root).
- `IPS_SetName(int ID, string Name)` — rename.
- `IPS_SetIdent(int ID, string Ident)` — set the machine ident (unique under a parent).
- `IPS_SetInfo(int ID, string Info)` — free-text note.
- `IPS_SetPosition(int ID, int Position)` — sort order among siblings.
- `IPS_SetHidden(int ID, bool Hidden)` — hide from visualisation.
- `IPS_SetDisabled(int ID, bool Disabled)` — disable (good reversible alternative to delete).
- **Delete is type-specific — there is NO generic `IPS_DeleteObject`** (verified live 2026-06-24: it returns error -44001 "Method not found"). Use the matching function and delete **children before their parent** (a non-empty category won't delete):
  - `IPS_DeleteVariable(int ID)` · `IPS_DeleteCategory(int ID)` · `IPS_DeleteScript(int ID, bool DeleteFile)` · `IPS_DeleteEvent(int ID)` · `IPS_DeleteInstance(int ID)` · `IPS_DeleteLink(int ID)` · `IPS_DeleteMedia(int ID, bool DeleteFile)`.
  - All **destructive** — plan explicitly. `IPS_SetDisabled` (above) is the reversible alternative.
- `IPS_GetObjectIDByIdent(string Ident, int ParentID)` — resolve by ident.

## Variables

Types: `0` Boolean · `1` Integer · `2` Float · `3` String.

Create and configure a variable (recipe):
```
new_id = ips_call("IPS_CreateVariable", [2])            # 2 = Float
         ips_call("IPS_SetParent",  [new_id, <parent_id>])
         ips_call("IPS_SetName",    [new_id, "Außentemperatur Soll"])
         ips_call("IPS_SetVariableCustomProfile", [new_id, "Temperature"])   # optional
         ips_call("IPS_SetVariableCustomAction",  [new_id, <script_id>])      # optional: makes it actionable
```
Write a value: `SetValue(id, value)` (dedicated tool `ips_set_value`) or typed
`SetValueFloat`/`SetValueInteger`/`SetValueBoolean`/`SetValueString`. Actuate via
`RequestAction(id, value)` (dedicated tool `ips_request_action`).

## Events (automations) — type via `IPS_CreateEvent`

Event types: `0` triggered (ausgelöst) · `1` cyclic (zyklisch/Timer) · `2` scheduled
(Wochenplan).

An event either runs its own inline PHP (`IPS_SetEventScript`) or — more commonly for
clean structure — you keep the logic in a real Script object and have a triggered event
fire on a variable change that calls it.

### Triggered event on a variable change (recipe)
```
eid = ips_call("IPS_CreateEvent", [0])                                  # 0 = triggered
      ips_call("IPS_SetParent", [eid, <parent_id>])
      ips_call("IPS_SetName",   [eid, "Wenn Tür öffnet"])
      ips_call("IPS_SetEventTrigger", [eid, 1, <trigger_variable_id>])  # 1 = on change
      ips_call("IPS_SetEventScript",  [eid, "<?php // PHP that runs on trigger ?>"])
      ips_call("IPS_SetEventActive",  [eid, true])
```
`IPS_SetEventTrigger(EventID, TriggerType, VariableID)` trigger types:
`0` on update · `1` on change · `2` on greater-than-limit · `3` on less-than-limit ·
`4` on specific value (combine with `IPS_SetEventTriggerValue`).

### Cyclic (timer) event
```
eid = ips_call("IPS_CreateEvent", [1])                                  # 1 = cyclic
      ips_call("IPS_SetParent", [eid, <parent_id>])
      ips_call("IPS_SetName",   [eid, "Alle 5 Minuten"])
      # IPS_SetEventCyclic(EventID, DateType, DateValue, DateDay, DateDayValue, TimeType, TimeValue)
      # For "every N seconds" use the TimeType/TimeValue interval form; the date/time
      # config is intricate — confirm the exact parameters in the command reference.
      ips_call("IPS_SetEventScript", [eid, "<?php /* ... */ ?>"])
      ips_call("IPS_SetEventActive", [eid, true])
```
The cyclic timing parameters are the one place to slow down and check the reference; an
inverted parameter can make a timer fire far too often.

## Categories and instances

- Category: `ips_call("IPS_CreateCategory", [])` → id, then `IPS_SetParent` / `IPS_SetName`.
- Instance (a module/device): `ips_call("IPS_CreateInstance", ["<ModuleGUID>"])` → id,
  then `IPS_SetParent` / `IPS_SetName`, configure with
  `IPS_SetConfiguration(id, "<json>")` and apply with `IPS_ApplyChanges(id)`. Module GUIDs
  come from the module — creating instances is advanced; read an existing instance of the
  same module first to learn its configuration shape.

## Variable profiles (formatting + value ranges)

```
ips_call("IPS_CreateVariableProfile", ["MyTemp", 2])                    # 2 = Float
ips_call("IPS_SetVariableProfileText",   ["MyTemp", "", " °C"])         # prefix, suffix
ips_call("IPS_SetVariableProfileValues", ["MyTemp", -20, 40, 0.5])      # min, max, step
ips_call("IPS_SetVariableProfileDigits", ["MyTemp", 1])
ips_call("IPS_SetVariableProfileIcon",   ["MyTemp", "Temperature"])
# Associations (for enums / named states):
ips_call("IPS_SetVariableProfileAssociation", ["MyMode", 0, "Aus", "", -1])  # value, name, icon, color
```

## Reading for context before you write

- `IPS_GetObject`, `IPS_GetChildrenIDs`, `IPS_GetVariable`, `IPS_GetScriptContent`
  (all have dedicated read tools) — use them to resolve IDs and capture before-state.
- `IPS_GetEvent(EventID)` — read an event's configuration (trigger, cyclic settings,
  script) before modifying it. Call via `ips_call("IPS_GetEvent", [eid])`.
- `IPS_ObjectExists(ID)` — cheap existence check before acting on an assumed ID.
