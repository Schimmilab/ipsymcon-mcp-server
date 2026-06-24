# IPS cleanup — workflow

The step-by-step for auditing and cleaning an IP-Symcon system. Read the `SKILL.md`
non-negotiables first. Function signatures: ipsymcon skill's
[ips-functions.md](../../ipsymcon/references/ips-functions.md).

**Scan pattern.** IP-Symcon has no built-in "list all errors / dependencies". The efficient,
read-only way is a throwaway PHP script: `IPS_CreateScript(0)` → `IPS_SetScriptContent(id, <php>)`
→ `IPS_RunScriptWaitEx(id, [])` (captures the script's `echo` — *not* `return`) →
`IPS_DeleteScript(id, true)`. The scripts below only read; they are safe to run during review.

---

## Phase 1 — Review (read-only): what is red?

Run the **error scan**: every instance whose `InstanceStatus >= 200` (the IPS error range;
102 = active/ok, 104 = inactive-on-purpose, 105 = not-created, **200+ = error**).

```php
<?php
$list = IPS_GetInstanceList();
$err = [];
foreach ($list as $iid) {
  $s = IPS_GetInstance($iid)['InstanceStatus'];
  if ($s >= 200) {
    $err[] = ['id'=>$iid, 'name'=>IPS_GetName($iid), 'status'=>$s,
              'module'=>IPS_GetInstance($iid)['ModuleInfo']['ModuleName']];
  }
}
echo json_encode(['total_instances'=>count($list), 'error_count'=>count($err), 'errors'=>$err], JSON_UNESCAPED_UNICODE);
```

Optional dead-object heuristics (surface, don't act): disabled objects (`IPS_GetObject`→`ObjectIsDisabled`),
variables never updated (`IPS_GetVariable`→`VariableUpdated == 0` or very old), empty categories.

## Phase 2 — Triage: fixable vs dead (you decide)

For each error, read the detail (`IPS_GetInstance`, the status code's meaning is module-specific,
the module name) and classify. Present a table and let the human decide **keep / fix / remove** —
never delete on your own judgement.

| Smell | Likely class |
|---|---|
| Cloud/login/API module in error (Hue, VeSync, OpenWeather, FritzBox…) | **fixable** — config/credentials/reconnect |
| Hardware/IO gone, legacy bridge, discovery leftover, "no longer have that" | **dead** — remove |

## Phase 3 — Safe removal (write, plan-first)

### 3a. Three-vector dependency scan (read-only) — MANDATORY before any delete

Naive children+links is not enough. Also check **ConnectionID** (devices connected through a
gateway are *not* tree-children). Put the removal candidate IDs in `$targets`:

```php
<?php
$targets = [/* candidate instance ids */];
function descendants($id){ $a=[$id]; foreach (IPS_GetChildrenIDs($id) as $c) { $a=array_merge($a, descendants($c)); } return $a; }
$desc = []; foreach ($targets as $t) { $desc[$t] = descendants($t); }
$out = ['targets'=>[], 'incoming_links'=>[], 'connected_instances'=>[]];
foreach ($targets as $t) {
  $kids = []; foreach ($desc[$t] as $x) { if ($x != $t) { $kids[] = ['id'=>$x,'name'=>IPS_GetName($x),'type'=>IPS_GetObject($x)['ObjectType']]; } }
  $out['targets'][$t] = ['name'=>IPS_GetName($t), 'child_count'=>count($kids), 'children'=>$kids];
}
foreach (IPS_GetLinkList() as $lid) { $tg = IPS_GetLink($lid)['TargetID']; foreach ($desc as $t=>$d) { if (in_array($tg,$d)) { $out['incoming_links'][] = ['link'=>$lid,'name'=>IPS_GetName($lid),'points_to'=>$tg,'in'=>$t]; } } }
foreach (IPS_GetInstanceList() as $iid) { $c = @IPS_GetInstance($iid)['ConnectionID']; foreach ($desc as $t=>$d) { if (in_array($c,$d)) { $out['connected_instances'][] = ['instance'=>$iid,'name'=>IPS_GetName($iid),'status'=>IPS_GetInstance($iid)['InstanceStatus'],'through'=>$t]; } } }
echo json_encode($out, JSON_UNESCAPED_UNICODE);
```

The **full removal set** = each target **+ its children + its connected instances** (and *their*
children — re-run the scan with the connected instances added). Incoming links pointing into the
set must be deleted or repointed first, or they orphan.

> Script references can't be found by ID scan reliably — if a target is referenced by a logic
> script, that script is already failing (its device is dead). Flag any such script for the human.

### 3b. Plan + approve

```
REMOVAL PLAN
  <gateway/instance> "<name>"  (status <s>)
     + connected: <device> "<name>", ...
     + children:  <var/...>, ...
     incoming links to repoint/delete: <link>, ...
  ... (per unit)
  Total objects to delete: <n>
```
Present it, then STOP for approval. No delete runs before the user approves this list.

### 3c. Delete — bottom-up, type-specific

Order: incoming links → connected device instances (deepest first) → their children →
the gateway/target instance. Per type: `IPS_DeleteLink`, `IPS_DeleteInstance`,
`IPS_DeleteVariable`, `IPS_DeleteScript(id,true)`, `IPS_DeleteEvent`, `IPS_DeleteCategory`
(a non-empty category won't delete — empty it first). After each unit, confirm with
`IPS_ObjectExists`.

## Phase 4 — Fix the fixable (apply safe, flag credentials)

Per fixable error: read the instance config (`IPS_GetConfiguration`) and module, identify the
cause, then:

- **Apply on your own (safe):** re-apply configuration (`IPS_SetConfiguration` + `IPS_ApplyChanges`),
  reconnect to a parent I/O (`IPS_ConnectInstance`), toggle active, refresh a discovery — anything
  that doesn't need a secret.
- **Flag for the human (never guess):** API keys (e.g. OpenWeatherMap OneCall), cloud logins
  (VeSync/Levoit), passwords, router credentials (FritzBox). State exactly what's needed and where
  to enter it. Apply nothing with invented credentials.

Each fix is plan-first too; show the before/after config change before applying.

## Phase 5 — Verify

Re-run the Phase 1 error scan. Success = the removed/fixed instances are gone from the error list
**and no new errors appeared** (no orphaned devices, no broken links). Report the before/after
error count and anything left for the human (flagged credentials).

## Common mistakes

- **Deleting on a children+links "0 dependencies" result.** ConnectionID is the missing vector —
  always run the full three-vector scan. (This is the whole reason the skill exists.)
- **Top-down delete.** Deleting a gateway before its connected devices orphans them → new red.
  Always bottom-up.
- **Guessing a credential to "just fix it".** Flag it. A wrong key can lock an account.
- **Treating status 104 as an error.** 104 = inactive on purpose. Only `>= 200` is an error.
