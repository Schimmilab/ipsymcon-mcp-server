"""Tests für das zweistufige Write-Gate und den Config-Export.

Beide entstanden aus dem Security-Review vom 2026-08-15:

* Das Write-Gate war ein einziges prozessweites Boolean. Wer für die
  Migrations-Zielinstanz schreiben wollte, öffnete zwangsläufig auch die
  Produktivinstanz — ein bewohntes Haus mit Heizung, Rollläden und Steckdosen.
* ``ips_export_subtree`` lieferte ``IPS_GetConfiguration`` mit aus. Diese Blöcke
  tragen regelmäßig Integrations-Zugangsdaten — aus einem Tool, das als
  ``readOnlyHint: True`` markiert ist.

⚠️ Die 42 bestehenden Tests blieben beim Umbau grün, ohne eine Zeile des neuen
Verhaltens zu berühren. Ein grüner Lauf der Altbestände belegt hier nichts.
"""

from __future__ import annotations

import asyncio
import textwrap

import pytest

from ipsymcon_mcp import config, server


@pytest.fixture
def instances_yaml(tmp_path, monkeypatch):
    """Zwei Instanzen: 'home' ausdrücklich schreibgeschützt, 'linux' offen."""
    p = tmp_path / "instances.yaml"
    p.write_text(
        textwrap.dedent(
            """
            default: home
            instances:
              home:
                url: https://192.168.1.10:3777/api/
                enable_write: false
              linux:
                url: https://192.168.1.20:3777/api/
                enable_write: true
              schweigsam:
                url: https://192.168.1.30:3777/api/
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("IPS_INSTANCES_FILE", str(p))
    monkeypatch.delenv("IPS_URL", raising=False)
    return p


# --- Das Gate ----------------------------------------------------------------


def test_global_aus_schlaegt_alles(instances_yaml, monkeypatch):
    """Der globale Schalter bleibt der Hauptschalter — eine Instanz kann ihn nicht überstimmen."""
    monkeypatch.setenv("IPS_ENABLE_WRITE", "false")
    assert server._write_enabled("linux") is False, "enable_write: true darf NIE allein Schreiben erlauben"
    assert server._write_enabled("home") is False


def test_instanz_kann_schreiben_entziehen(instances_yaml, monkeypatch):
    """Der eigentliche Zweck: global offen, das bewohnte Haus trotzdem dicht."""
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    assert server._write_enabled("linux") is True, "Kontrolle — hier MUSS geschrieben werden dürfen"
    assert server._write_enabled("home") is False, "enable_write: false muss trotz globalem Flag greifen"


def test_default_ist_die_geschuetzte_instanz(instances_yaml, monkeypatch):
    """Ein vergessener instance-Parameter fällt auf 'home' zurück — und das ist geschützt.

    Genau dieser Fall war der wahrscheinlichste Schadenspfad: Agent lässt den
    Parameter weg, der Default ist das Haus.
    """
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    assert server._write_enabled(None) is False


def test_instanz_ohne_angabe_erbt_global(instances_yaml, monkeypatch):
    """Rückwärtskompatibilität: sagt eine Instanz nichts, gilt der globale Schalter."""
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    assert server._write_enabled("schweigsam") is True
    monkeypatch.setenv("IPS_ENABLE_WRITE", "false")
    assert server._write_enabled("schweigsam") is False


def test_single_instance_setup_unveraendert(monkeypatch, tmp_path):
    """Ohne YAML (nur IPS_URL) muss sich nichts geändert haben."""
    monkeypatch.delenv("IPS_INSTANCES_FILE", raising=False)
    monkeypatch.setenv("IPS_URL", "https://192.168.1.10:3777/api/")
    monkeypatch.setenv("IPS_ENABLE_WRITE", "true")
    assert server._write_enabled(None) is True
    monkeypatch.setenv("IPS_ENABLE_WRITE", "false")
    assert server._write_enabled(None) is False


def test_yaml_strings_werden_akzeptiert(tmp_path, monkeypatch):
    """YAML kann 'true'/'no' als String liefern — und Unsinn zählt als False."""
    p = tmp_path / "i.yaml"
    p.write_text(
        "default: a\ninstances:\n  a:\n    url: https://x/\n    enable_write: 'yes'\n"
        "  b:\n    url: https://y/\n    enable_write: 'vielleicht'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("IPS_INSTANCES_FILE", str(p))
    monkeypatch.delenv("IPS_URL", raising=False)
    assert config.instance_write_enabled("a") is True
    assert config.instance_write_enabled("b") is False, "Unbekannte Werte muessen als NEIN gelten"


# --- Der Config-Export -------------------------------------------------------


class _FakeClient:
    """Minimaler IPS-Ersatz: eine Instanz mit einem Passwort in der Konfiguration."""

    def __init__(self):
        self.gerufen: list[str] = []

    async def call(self, method, params=None):
        self.gerufen.append(method)
        if method == "IPS_GetObject":
            return {"ObjectName": "FritzBox", "ObjectType": 1}
        if method == "IPS_GetInstance":
            return {"ModuleInfo": {"ModuleID": "{ABC}"}}
        if method == "IPS_GetConfiguration":
            return '{"Password":"geheim123","Host":"fritz.box"}'
        if method == "IPS_GetChildrenIDs":
            return []
        return None


def test_config_wird_ohne_anforderung_nicht_exportiert():
    client = _FakeClient()
    node = asyncio.run(server._export_node(client, 1, 0, 1))
    assert "configuration" not in node, "Zugangsdaten duerfen nicht ungefragt herausgehen"
    assert "configuration_omitted" in node, "Die Auslassung muss sichtbar sein, nicht stillschweigend"
    assert "IPS_GetConfiguration" not in client.gerufen, "Gar nicht erst abrufen"


def test_config_kommt_auf_ausdrueckliche_anforderung():
    """Kontrolle: der Pfad muss funktionieren, sonst testet der Fall oben nichts."""
    client = _FakeClient()
    node = asyncio.run(server._export_node(client, 1, 0, 1, True))
    assert "geheim123" in node["configuration"]
    assert "IPS_GetConfiguration" in client.gerufen
