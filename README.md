# ipsymcon-mcp-server

[![CI](https://github.com/Schimmilab/ipsymcon-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/Schimmilab/ipsymcon-mcp-server/actions/workflows/ci.yml)

MCP-Server für **IP-Symcon** — lässt Claude/Agenten eine IP-Symcon-Hausautomation nicht nur
abfragen und steuern, sondern **entwickeln**: Objektbaum lesen, PHP-Skripte lesen/ändern/anlegen,
Variablen lesen, Geräte schalten. Über die IP-Symcon JSON-RPC-API.

Stack: Python + FastMCP. Companion-Modul für IP-Symcon-seitiges Log-Lesen:
[SymconMCPBridge](https://github.com/Schimmilab/SymconMCPBridge) (MIT).

---

## Sicherheitsmodell (wichtig)

- **Lese-Tools** sind immer verfügbar.
- **Schreib-/Dev-Tools** (`ips_set_value`, `ips_request_action`, `ips_run_script`,
  `ips_set_script_content`, `ips_create_script`, `ips_call`) brauchen die Umgebungsvariable
  **`IPS_ENABLE_WRITE=true`**. Default ist *aus* — der bewusste Riegel, damit ein Agent nicht
  unbemerkt in die laufende Hausautomation schreibt.
- Empfehlung: Schreibzugriff **zuerst gegen eine Test-/Staging-Instanz**, vorher Backup.
  (Dry-Run + automatisches Snapshot-Backup vor Änderungen sind als nächster Ausbauschritt geplant.)

---

## Voraussetzungen in IP-Symcon

1. JSON-RPC-Zugang ist standardmäßig aktiv unter `http://<host>:3777/api/`.
2. Einen Benutzer mit Zugriff anlegen (Systemsteuerung → Benutzerverwaltung) → in `IPS_USER`/`IPS_PASSWORD` eintragen.
   Hat die Installation keine Authentifizierung, bleiben beide leer.

## Installation

```bash
cd ~/workspace/ipsymcon-mcp-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # dann .env mit echten Werten füllen
```

## Konfiguration (`.env`)

| Variable | Bedeutung |
|---|---|
| `IPS_URL` | JSON-RPC-Endpunkt, z. B. `http://192.168.1.10:3777/api/` (das `/api/` wird sonst ergänzt) |
| `IPS_USER` / `IPS_PASSWORD` | Basic-Auth-Zugangsdaten (leer, falls keine Auth) |
| `IPS_ENABLE_WRITE` | `false` (Default) = nur lesen · `true` = Schreib-/Dev-Tools aktiv |
| `IPS_INSTANCES_FILE` | optional: Pfad zu einer YAML mit **mehreren benannten Instanzen** (s. u.) |

### Mehrere Instanzen (Multi-Instance)

Für mehrere IP-Symcon-Ziele (z. B. `home` + ein Migrations-Ziel `linux`): eine YAML-Datei anlegen (Vorlage: [`instances.example.yaml`](instances.example.yaml)) und `IPS_INSTANCES_FILE` darauf zeigen lassen.

```yaml
default: home
instances:
  home:
    url: http://192.168.1.10:3777/api/
    user: ""
    password: ""
  linux:
    url: http://192.168.1.20:3777/api/
```

Jedes Tool nimmt dann einen optionalen `instance`-Parameter (`home`/`linux`); ohne Angabe → `default`. **Abwärtskompatibel:** ohne `IPS_INSTANCES_FILE` gilt das einzelne `IPS_URL` als implizite Default-Instanz — bestehende Setups laufen unverändert. Die echte YAML enthält Credentials → wie `.env` aus git heraushalten (`instances.yaml` ist gitignored).

## Start / Test

```bash
# direkt starten (stdio)
.venv/bin/python -m ipsymcon_mcp

# mit MCP Inspector testen
.venv/bin/python -m mcp dev ipsymcon_mcp/server.py
```

## Registrierung in Claude Code

```bash
claude mcp add ipsymcon -s user -- /Users/<user>/workspace/ipsymcon-mcp-server/.venv/bin/python -m ipsymcon_mcp
```
(Umgebungsvariablen aus `.env` werden geladen; alternativ per `-e IPS_URL=...` etc. übergeben.)

---

## Tools (v0.1)

**Lesen (immer verfügbar):**
| Tool | IPS-Funktion | Zweck |
|---|---|---|
| `ips_get_value` | GetValue | aktuellen Variablenwert lesen |
| `ips_get_variable` | IPS_GetVariable (+Wert+Name) | Variablen-Metadaten (Typ, Profil, Zeitstempel) |
| `ips_get_object` | IPS_GetObject | Objekt-Metadaten + Parent/Children (Tree-Navigation) |
| `ips_list_children` | IPS_GetChildrenIDs | direkte Kinder mit id/name/typ (Baum durchblättern, Start: 0) |
| `ips_find_object_by_name` | IPS_GetObjectIDByName | Objekt-ID per exaktem Namen finden |
| `ips_get_variable_by_path` | IPS_GetObjectIDByName (Pfad-Walk) | Variablenwert per Objektpfad lesen (`Räume/Büro/Zustand`) statt per ID |
| `ips_get_object_tree` | IPS_GetObject/-GetChildrenIDs (rekursiv) | ganzen Teilbaum auf einmal als verschachteltes `{id,name,type,children}` (max_depth) |
| `ips_snapshot_variables` | GetValue (n×) | Werte mehrerer Variablen als Snapshot festhalten |
| `ips_diff_variables` | GetValue (n×) | Snapshot gegen Live-Werte diffen → was hat sich geändert (Wirkungskontrolle) |
| `ips_export_subtree` | IPS_GetObject/-Variable/-ScriptContent/-Event/-Instance/-Link | Teilbaum → reiches JSON für **Backup/Migration** (Variable Typ+Profil+Wert, Skript-Content, Event/Instanz/Link-Detail) |
| `ips_get_script_content` | IPS_GetScriptContent | PHP-Quelltext eines Skripts lesen |

**Schreiben/Entwickeln (nur mit `IPS_ENABLE_WRITE=true`):**
| Tool | IPS-Funktion | Zweck |
|---|---|---|
| `ips_set_value` | SetValue | Variablenwert direkt setzen |
| `ips_request_action` | RequestAction | Aktor schalten (löst Action aus) |
| `ips_run_script` | IPS_RunScript | Skript ausführen (fire-and-confirm, ohne Ausgabe) |
| `ips_run_script_capture` | IPS_RunScriptWaitEx | Skript ausführen **und die Ausgabe zurückgeben** — Basis fürs agentische bauen→ausführen→prüfen→nachbessern. Optionale `parameters` landen im Skript als `$_IPS['key']`. |
| `ips_set_script_content` | IPS_SetScriptContent | PHP-Quelltext überschreiben |
| `ips_create_script` | IPS_CreateScript (+Parent/Name/Content) | neues PHP-Skript anlegen |
| `ips_create_category` | IPS_CreateCategory | Kategorie anlegen (Objektbaum strukturieren) |
| `ips_create_variable` | IPS_CreateVariable (+Profil) | typisierte Variable anlegen (`boolean`/`integer`/`float`/`string`, optional Profil) |
| `ips_create_event` | IPS_CreateEvent | Event-Hülle anlegen (`triggered`/`cyclic`/`weekly`); Detail-Config via `ips_call` |
| `ips_import_subtree` | IPS_CreateCategory/-Variable/-Script (+SetParent/Name/Profil/Wert/Content) | Teilbaum aus `ips_export_subtree`-JSON mechanisch wiederanlegen → **alte→neue ID-Map** (Restore/Migration). Instanzen/Events/Links → `skipped` (Migrations-Skill). |
| `ips_call` | beliebig | Generischer Gateway für volle API-Abdeckung (z. B. IPS_CreateInstance, IPS_SetEventCyclic) |

> **Hinweis zu `ips_run_script_capture`:** IP-Symcon erfasst die **Ausgabe** des Skripts (was es `echo`/`print`t) — ein top-level PHP-`return` wird **nicht** zurückgegeben (kommt leer). Das Skript muss sein Ergebnis also `echo`en.

---

## Skill (Playbook für Claude Code)

Mitgeliefert in [`skills/ipsymcon/`](skills/ipsymcon/) — das Domänen-Können auf den Tools: **Plan-First-Sicherheitsworkflow** (read → plan → approve → execute → report), Tool-Übersicht, IPS-Objektmodell. Aufgeteilt nach dem Prinzip *Anweisung im Skill, Workflow separat*:

- [`SKILL.md`](skills/ipsymcon/SKILL.md) — die Direktive: die eine Regel (vor Schreibzugriff planen), die 22 Tools, Struktur-Primer.
- [`references/workflow.md`](skills/ipsymcon/references/workflow.md) — die detaillierten Workflows + Plan-/Report-Templates + Fallstricke.
- [`references/ips-functions.md`](skills/ipsymcon/references/ips-functions.md) — `ips_call`-Funktions-Cheat-Sheet (Event-Trigger, Profile, Instanzen).

Dazu der eigenständige **Migrations-Skill** [`skills/ips-migration/`](skills/ips-migration/) — Greenfield-Migration eines Teilbaums auf eine andere Instanz (Export → Plan-First mit Modul-Check/Referenz-Scan/Flags → Zwei-Pass: anlegen, dann Referenzen via ID-Map verdrahten → Verify), aufbauend auf `ips_export_subtree`/`ips_import_subtree`.

Und der **Cleanup-Skill** [`skills/ips-cleanup/`](skills/ips-cleanup/) — IPS-Health-Review + *Phase 0* der Migration: Error-Scan (Instanzen mit Status ≥ 200) → Triage → **3-Vektor-Dependency-Analyse** (Kinder · Links · ConnectionID) → Plan-First-Cascade-Delete + sicheres Fixen (Credentials werden geflaggt, nie geraten) → Verify. Erprobte Scan-Snippets mitgeliefert.

Claude Code: nach `~/.claude/skills/ipsymcon/` (bzw. `…/ips-migration/`) kopieren oder dorthin symlinken. So wachsen Tools (MCP) und Playbook (Skill) im selben Repo/Release im Gleichschritt.

---

## Roadmap

- [x] **Multi-Instanz-Support** (v0.4) — benannte Verbindungen über `IPS_INSTANCES_FILE` (YAML), optionaler `instance`-Parameter je Tool (über `_Base`), Default-Instanz, **abwärtskompatibel** zum einzelnen `IPS_URL`. TDD + Live-Test (Default + benannte Instanz + unbekannte Instanz). **Treiber: IPS-Migration auf Linux** — aus Alt- und Neu-Instanz lesen, vergleichen, migrieren, verifizieren.
- [x] **`ips_run_script_capture`** (v0.2) — Skript via `IPS_RunScriptWaitEx` ausführen und die **Ausgabe** zurückgeben (`echo`, nicht `return` — siehe Hinweis oben). Grundlage für agentisches Entwickeln (bauen → ausführen → Ergebnis prüfen → nachbessern). Optionale `$_IPS`-Parameter. Unit-Tests + Live-Test grün.
- [ ] **`ips_read_log`** — Log-Abruf über das Companion-Modul [SymconMCPBridge](https://github.com/Schimmilab/SymconMCPBridge): ein residenter **MessageSink** mit gefiltertem **Ring-Buffer** (`KL_ERROR`/`KL_WARNING`/…), der die öffentliche Funktion `MCPB_GetLog($id, level, count, filter)` per JSON-RPC bereitstellt. `ips_read_log` ruft dann nur diese Funktion (kein Inline-PHP, kein Logfile-Parsen). Hintergrund: IP-Symcon hat kein direktes „getMessages" (Meldungsfenster = Live-Abo); `IPS_GetLogDir()` gäbe nur die rohe Logdatei.
- [x] **Companion-Modul [SymconMCPBridge](https://github.com/Schimmilab/SymconMCPBridge)** (MIT, released) — IP-Symcon-seitiges Modul, das Kernel-Log-Meldungen als gefilterten Ring-Buffer über JSON-RPC bereitstellt. Basis für `ips_read_log` und tiefere Bridge-/Helper-Funktionen. Installation via Module Control (Git-Repo).
- [x] Dedizierte Tools: `ips_create_variable`, `ips_create_event`, `ips_create_category` (v0.2 — TDD + Live-Test). Detail-Config (Trigger/Cyclic/Schedule) via `ips_call`.
- [ ] **Dry-Run-Modus** + automatisches **Snapshot-Backup** vor Schreibzugriffen
- [x] **Beobachtungs-/Navigations-Tools** (v0.3, aus dem Community-Vergleich): `ips_get_object_tree` (ganzer Teilbaum), `ips_get_variable_by_path` (Pfad statt ID), `ips_snapshot_variables` + `ips_diff_variables` (Wirkungskontrolle build→run→diff). TDD + Live-Test.
- [x] **`ips_export_subtree`** — Backup-Hälfte: Teilbaum → reiches JSON (Variable Typ+Profil+Wert, Skript-Content, Event/Instanz/Link-Detail). Deterministisch, read-only. TDD + Live-Test.
- [x] **`ips_import_subtree`** (v0.4 — TDD + Live-Round-Trip) — Restore-/Migrations-Hälfte: cat/var/script mechanisch anlegen, **alte→neue ID-Map** zurückgeben; Instanzen/Events/Links bewusst `skipped`. Deterministisches Struktur-Primitiv.
- [x] **Migrations-Skill** [`skills/ips-migration/`](skills/ips-migration/) — agentische Adaption (Greenfield v1): Export → Plan-First (Modul-Check + Referenz-Scan + Flags) → Zwei-Pass (anlegen → Referenzen via ID-Map verdrahten) → Verify. Semantisches Matching auf bestehende Ziel-Objekte + Bewertung/Refactoring = spätere Skills.
- [x] **Cleanup-Skill** [`skills/ips-cleanup/`](skills/ips-cleanup/) — IPS-Health-Review + Vor-Migrations-Cleanup (*Phase 0*): Error-Scan (Status ≥ 200) → Triage → 3-Vektor-Dependency-Analyse (Kinder/Links/ConnectionID) → Plan-First-Cascade-Delete + sicheres Fixen (Credentials geflaggt) → Verify. Scan-Snippets mitgeliefert, live validiert.
- [ ] Evaluations (mcp-builder Phase 4)
- [ ] Gegenstück: Home-Assistant Dev-MCP (zweite Backend-Schicht des Fusionsprojekts)
