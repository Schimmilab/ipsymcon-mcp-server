# ipsymcon-mcp-server

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
| `ips_get_script_content` | IPS_GetScriptContent | PHP-Quelltext eines Skripts lesen |

**Schreiben/Entwickeln (nur mit `IPS_ENABLE_WRITE=true`):**
| Tool | IPS-Funktion | Zweck |
|---|---|---|
| `ips_set_value` | SetValue | Variablenwert direkt setzen |
| `ips_request_action` | RequestAction | Aktor schalten (löst Action aus) |
| `ips_run_script` | IPS_RunScript | Skript ausführen |
| `ips_set_script_content` | IPS_SetScriptContent | PHP-Quelltext überschreiben |
| `ips_create_script` | IPS_CreateScript (+Parent/Name/Content) | neues PHP-Skript anlegen |
| `ips_call` | beliebig | Generischer Gateway für volle API-Abdeckung (z. B. IPS_CreateVariable/-Event/-Instance) |

---

## Roadmap

- [ ] **Multi-Instanz-Support** — mehrere IP-Symcon-Ziele gleichzeitig ansprechen über **benannte Verbindungen** (z.B. `home` = aktuelle Instanz, `linux` = Migrationsziel). Jedes Tool bekommt einen optionalen `instance`-Parameter (Default = konfigurierte Standard-Instanz); Config als benannte Map (URL/User/Passwort je Instanz), **abwärtskompatibel** zum einzelnen `IPS_URL`. **Direkter Treiber: eine IPS-Migration auf Linux** — der Agent kann dann aus Alt- und Neu-Instanz lesen, Objekte/Skripte/Events **vergleichen und migrieren** und das Ergebnis verifizieren, statt blind auf einer Instanz zu arbeiten.
- [ ] **`ips_run_script_capture`** — Skript via `IPS_RunScriptWaitEx` ausführen und den `return`-Wert/Output zurückgeben (heute ist `ips_run_script` nur fire-and-confirm). Grundlage für agentisches Entwickeln (bauen → ausführen → Ergebnis prüfen → nachbessern) und fürs Log-Lesen.
- [ ] **`ips_read_log`** — Log-Abruf über das Companion-Modul [SymconMCPBridge](https://github.com/Schimmilab/SymconMCPBridge): ein residenter **MessageSink** mit gefiltertem **Ring-Buffer** (`KL_ERROR`/`KL_WARNING`/…), der die öffentliche Funktion `MCPB_GetLog($id, level, count, filter)` per JSON-RPC bereitstellt. `ips_read_log` ruft dann nur diese Funktion (kein Inline-PHP, kein Logfile-Parsen). Hintergrund: IP-Symcon hat kein direktes „getMessages" (Meldungsfenster = Live-Abo); `IPS_GetLogDir()` gäbe nur die rohe Logdatei.
- [x] **Companion-Modul [SymconMCPBridge](https://github.com/Schimmilab/SymconMCPBridge)** (MIT, released) — IP-Symcon-seitiges Modul, das Kernel-Log-Meldungen als gefilterten Ring-Buffer über JSON-RPC bereitstellt. Basis für `ips_read_log` und tiefere Bridge-/Helper-Funktionen. Installation via Module Control (Git-Repo).
- [ ] Dedizierte Tools: `ips_create_variable`, `ips_create_event`, `ips_create_category`
- [ ] **Dry-Run-Modus** + automatisches **Snapshot-Backup** vor Schreibzugriffen
- [ ] Objektbaum-Snapshot-Tool (kuratierte Gesamtübersicht)
- [ ] Evaluations (mcp-builder Phase 4)
- [ ] Gegenstück: Home-Assistant Dev-MCP (zweite Backend-Schicht des Fusionsprojekts)
