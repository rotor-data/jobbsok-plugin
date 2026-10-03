"""Gemensamma hjälpfunktioner för jobbsok-skripten. Endast Python 3 stdlib.

Importera från ett annat skript i samma katalog:

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jobbsok_common as jc

API
---
PLUGIN_ROOT, SCHEMA_DIR          Sökvägar inne i pluginen (aldrig användardata).
add_home_arg(parser)             Lägger till --home på en argparse-parser.
resolve_home(cli_home=None)      --home > $JOBBSOK_HOME > ~/Jobbsok. Returnerar absolut Path.
read_json(path, default=None)    Läser UTF-8-JSON. Saknas filen returneras default.
write_json(path, data, backup=True)
                                 Skriver atomiskt (tempfil + os.replace). Finns filen
                                 sedan tidigare kopieras den först till <fil>.bak.
slugify(text, maxlen=40)         "Region Uppsala – Kommunikatör" -> "region-uppsala-kommunikator".
ansokningsmapp(bolag, roll, datum=None)
                                 Mappnamn "<YYYY-MM-DD>-<bolag>-<roll>" (datum: date, str eller None=idag).
"""
import argparse
import datetime as _dt
import json
import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PLUGIN_ROOT / "schemas"
DEFAULT_HOME = "~/Jobbsok"


def add_home_arg(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--home", help="Datamappen (standard: $JOBBSOK_HOME eller ~/Jobbsok)")
    return parser


def resolve_home(cli_home=None) -> Path:
    raw = cli_home or os.environ.get("JOBBSOK_HOME") or DEFAULT_HOME
    return Path(os.path.expanduser(raw)).resolve()


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data, backup=True) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if backup and p.exists():
        shutil.copy2(p, p.with_name(p.name + ".bak"))
    fd, tmp = tempfile.mkstemp(prefix="." + p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return p


_TRANS = str.maketrans({"å": "a", "ä": "a", "ö": "o", "Å": "a", "Ä": "a", "Ö": "o",
                        "é": "e", "ü": "u", "ß": "ss", "æ": "ae", "ø": "o"})


def slugify(text, maxlen=40) -> str:
    s = (text or "").translate(_TRANS)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip("-")
    return s or "okand"


def ansokningsmapp(bolag, roll, datum=None) -> str:
    if datum is None:
        datum = _dt.date.today()
    if isinstance(datum, (_dt.date, _dt.datetime)):
        datum = datum.strftime("%Y-%m-%d")
    return f"{datum[:10]}-{slugify(bolag, 30)}-{slugify(roll, 40)}"
