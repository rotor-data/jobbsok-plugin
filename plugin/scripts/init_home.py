#!/usr/bin/env python3
"""Skapa datamappen för jobbsok (~/Jobbsok eller --home). Idempotent.

Skapar mappar, README.md och tomma startfiler som validerar. Befintliga
filer skrivs aldrig över. Skriver en JSON-rapport: {"home", "skapade", "fanns"}.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobbsok_common as jc  # noqa: E402

MAPPAR = ["profil", "design", "sok", "sok/recept", "ansokningar", "import", "cache", "cache/taxonomy", "cache/enrich"]

STARTFILER = {
    "profil/fakta.json": {
        "schema_version": 1,
        "person": {"namn": "", "titel": {}, "ort": "", "epost": "", "telefon": "", "lankar": [], "foto": None, "korkort": None},
        "sammanfattning_rad": {}, "roller": [], "utbildning": [], "kurser": [], "sprak": [],
        "kompetenser": [], "ideella": [], "referenser": [], "aldrig_pastaa": [],
    },
    "profil/coach.json": {
        "schema_version": 1,
        "faser": {f: {} for f in ["intake", "identity", "energy_log", "needs_profile", "options", "experiments", "decision"]},
        "status": {"aktuell_fas": "intake", "senast": None},
    },
    "profil/preferenser.json": {
        "schema_version": 1, "riktningar": [], "orter": [], "hårda_gränser": {}, "varden_topp5": [],
        "vitaminer": {}, "arbetsdag": {"idealvecka": [], "energigivare": [], "energitjuvar": []},
        "kompetens_id": [], "exkludera_arbetsgivare": [], "sprak_ansokan": ["sv"],
    },
    "profil/rost.json": {
        "schema_version": 1, "gillade_formuleringar": [], "aldrig_ord": [], "tonblandningar": [],
        "smyra": {"kim_persona_id": {"sv": None, "en": None}},
    },
    "sok/kallor.json": {"schema_version": 1, "kallor": []},
}

README = """# Jobbsök – din mapp

Här ligger allt som jobbsök-pluginen sparar om dig. Det är dina filer, och de
finns kvar även när pluginen uppdateras. Du behöver aldrig öppna dem själv –
säg bara till Claude vad du vill ändra.

## profil/
- **fakta.json** – din faktabank: kontaktuppgifter, roller, meriter, utbildning,
  språk och kompetenser. Allt som står i dina CV och brev hämtas härifrån.
  `aldrig_pastaa` är saker som aldrig får påstås om dig.
- **coach.json** – det du och karriärcoachen kommit fram till, fas för fas.
- **preferenser.json** – vad du söker: riktningar, orter, gränser (pendling,
  lön, distans) och dina viktigaste värden. Styr jobbsökningen.
- **rost.json** – hur du vill låta: formuleringar du gillar och ord du aldrig vill se.

## design/
- **design.json** – din valda CV-design (typsnitt, färger, ordning på delarna).
  Äldre versioner sparas i historiken.

## sok/
- **kallor.json** – var vi letar jobb (Arbetsförmedlingen, bolagens karriärsidor m.m.).
- **recept/** – sparade sökningar.
- **jobb.sqlite** – alla jobb vi hittat, med status och poäng.

## ansokningar/
En mapp per ansökan, t.ex. `2026-10-01-region-uppsala-kommunikator/`, med annonsen,
analysen, ditt CV och brev (som PDF också), följemejlet och en logg över vad som hänt.

## import/
Lägg gamla CV:n eller LinkedIn-exporten (ZIP) här, så hittar Claude dem.

## cache/
Tillfälliga data som kan hämtas igen. Kan raderas utan att något går förlorat.

Filer som slutar på `.bak` är automatiska säkerhetskopior av förra versionen.
"""


def init_home(home):
    home = jc.resolve_home(home) if not hasattr(home, "mkdir") else home
    skapade, fanns = [], []
    home.mkdir(parents=True, exist_ok=True)
    for m in MAPPAR:
        p = home / m
        (fanns if p.exists() else skapade).append(m + "/")
        p.mkdir(parents=True, exist_ok=True)
    readme = home / "README.md"
    if readme.exists():
        fanns.append("README.md")
    else:
        readme.write_text(README, encoding="utf-8")
        skapade.append("README.md")
    for rel, data in STARTFILER.items():
        p = home / rel
        if p.exists():
            fanns.append(rel)
        else:
            jc.write_json(p, data, backup=False)
            skapade.append(rel)
    return {"home": str(home), "skapade": skapade, "fanns": fanns}


def main(argv=None):
    ap = jc.add_home_arg(argparse.ArgumentParser(description="Skapa jobbsok-mappen."))
    a = ap.parse_args(argv)
    print(json.dumps(init_home(jc.resolve_home(a.home)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
