"""Tests für die Auslieferung der Runbooks über die MCP-Schnittstelle.

Der Kern dieser Tests ist nicht "läuft der Code durch", sondern die eine
Eigenschaft, die das Modul verspricht: **es gibt keine Kopie des Skill-Textes.**
Ein Test, der nur prüft, dass ein Prompt irgendetwas zurückgibt, würde eine
eingefrorene Kopie genauso bestehen — und damit exakt den Fehler durchlassen,
gegen den das Modul gebaut ist.
"""

from __future__ import annotations

import pytest

from ipsymcon_mcp import skills


def test_jeder_registrierte_skill_existiert_auch_als_datei():
    """Die gepflegte Liste darf nicht von den Dateien abweichen — in beide Richtungen."""
    aus_liste = set(skills.SKILLS)
    aus_verzeichnis = {p.name for p in skills.SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()}
    assert aus_liste == aus_verzeichnis, (
        "SKILLS und skills/ laufen auseinander — genau die Drift, die dieses Modul verhindern soll"
    )


def test_prompt_liest_die_datei_statt_einer_kopie(tmp_path, monkeypatch):
    """Der eigentliche Test: Datei ändern → Prompt-Ausgabe ändert sich mit.

    Eine hartkodierte Kopie im Modul würde hier durchfallen.
    """
    fake = tmp_path / "ipsymcon"
    (fake / "references").mkdir(parents=True)
    (fake / "SKILL.md").write_text("---\nname: x\n---\n\nURSPRUNG", encoding="utf-8")
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)

    assert "URSPRUNG" in skills.render_skill("ipsymcon")

    (fake / "SKILL.md").write_text("---\nname: x\n---\n\nGEAENDERT", encoding="utf-8")
    ausgabe = skills.render_skill("ipsymcon")
    assert "GEAENDERT" in ausgabe
    assert "URSPRUNG" not in ausgabe


def test_referenzen_werden_angehaengt_und_sind_abschaltbar(tmp_path, monkeypatch):
    fake = tmp_path / "ipsymcon"
    (fake / "references").mkdir(parents=True)
    (fake / "SKILL.md").write_text("HAUPTTEXT", encoding="utf-8")
    (fake / "references" / "workflow.md").write_text("REFERENZTEXT", encoding="utf-8")
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)

    assert "REFERENZTEXT" in skills.render_skill("ipsymcon", mit_referenzen=True)
    assert "REFERENZTEXT" not in skills.render_skill("ipsymcon", mit_referenzen=False)


def test_fehlende_installation_meldet_die_quelle_statt_zu_schweigen(tmp_path, monkeypatch):
    """Nur das pip-Paket ohne Repo: klare Meldung mit Bezugsquelle, kein leerer String."""
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    with pytest.raises(skills.SkillNotAvailableError) as exc:
        skills.render_skill("ipsymcon")
    assert skills.REPO_URL in str(exc.value)


def test_unbekannter_name_nennt_die_gueltigen():
    with pytest.raises(skills.SkillNotAvailableError) as exc:
        skills.render_skill("gibt-es-nicht")
    assert "ipsymcon" in str(exc.value)


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        ("---\nname: x\n---\n\nInhalt", "Inhalt"),
        # Kein Frontmatter, aber führende Linie: darf NICHT bis zum nächsten --- köpfen.
        ("---\n\nNur eine Linie", "---\n\nNur eine Linie"),
        ("Kein Frontmatter", "Kein Frontmatter"),
    ],
)
def test_frontmatter_stripping(text, erwartet):
    assert skills.strip_frontmatter(text) == erwartet


def test_instructions_tragen_die_schreibgrenze_und_den_zeiger():
    """`instructions` ist der einzige Weg, der auch ohne Plugin ankommt.

    Fällt hier etwas heraus, verliert genau der Client die Sicherheitsregel, der
    sie am dringendsten braucht: der, der die Skills nie installiert hat.
    """
    text = skills.INSTRUCTIONS
    assert "Plan" in text and "Freigabe" in text
    assert skills.REPO_URL in text
    for tool in ("ips_set_value", "ips_request_action", "ips_run_script"):
        assert tool in text


async def test_alle_runbooks_sind_als_prompt_registriert_und_liefern_inhalt():
    # `asyncio_mode = auto` in pytest.ini — kein Marker nötig.
    """Gegen den echten Server, nicht gegen eine Attrappe."""
    from ipsymcon_mcp.server import mcp

    registriert = {p.name for p in await mcp.list_prompts()}
    assert set(skills.SKILLS).issubset(registriert)

    ergebnis = await mcp.render_prompt("ips-automation")
    text = "".join(
        m.content.text for m in ergebnis.messages if getattr(m.content, "text", None)
    )
    assert "Runbook `ips-automation`" in text
    assert len(text) > 1000, "verdächtig kurz — vermutlich wurde die Datei nicht gelesen"
