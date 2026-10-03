"""Gemensamt för jakt_*.py (skillen jobbjakt). Bara Python 3 stdlib.

Bygger på sok_common (HTTP med User-Agent, 1 anrop/s per värd, NatFel -> exit 3).
Allt som skrivs ut är kompakt JSON: ingen rå HTML eller hela annonser till modellen.
"""
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import urllib.parse

import sok_common as sc

JOBSEARCH = "https://jobsearch.api.jobtechdev.se/search"
HISTORICAL = "https://historical.api.jobtechdev.se/search"
TAXONOMY = "https://taxonomy.api.jobtechdev.se/v1/taxonomy"
SKRIPT = os.path.dirname(os.path.abspath(__file__))


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def skriv(data):
    """Kompakt JSON: en rad per listpost, så att modellen läser lite men tydligt."""
    if not isinstance(data, dict):
        print(_j(data))
        return
    rader = []
    for k, v in data.items():
        if isinstance(v, list) and v:
            rader.append(f"{_j(k)}:[\n  " + ",\n  ".join(_j(x) for x in v) + "\n]")
        else:
            rader.append(f"{_j(k)}:{_j(v)}")
    print("{\n" + ",\n".join(rader) + "\n}")


def api(url, params=None, home=None):
    """GET mot JobTech. Nätfel avslutar med kod 3 (Claudes webbverktyg tar över)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    try:
        _, data, _ = sc.http_json(url, home=home)
    except sc.NatFel as e:
        sc.natfel_avslut(e)
    except sc.HttpFel as e:
        sys.stderr.write(f"FEL: {e} {e.text[:200]}\n")
        sys.exit(2)
    return data


def ar_sedan(ar):
    return (_dt.date.today() - _dt.timedelta(days=int(365 * ar))).isoformat()


# ---------------------------------------------------------------- taxonomi

def autocomplete(term, typ, home=None):
    """Lista med (id, etikett, alternativa) för en fri term."""
    d = api(TAXONOMY + "/suggesters/autocomplete", {"query-string": term, "type": typ}, home) or []
    return [(x["taxonomy/id"], x["taxonomy/preferred-label"], x.get("taxonomy/alternative-labels", []))
            for x in d]


def basta_traff(term, kandidater):
    t = sc.norm(term)
    def rang(k):
        _id, lab, alt = k
        etik = [sc.norm(lab)] + [sc.norm(a) for a in alt] + [sc.norm(x) for x in lab.split("/")]
        if t in etik:
            return 0
        if any(e.startswith(t) for e in etik):
            return 1
        return 2
    return sorted(kandidater, key=rang)[0] if kandidater else None


def ar_id(s):
    return bool(re.fullmatch(r"[A-Za-z0-9]{4}_[A-Za-z0-9]{3}_[A-Za-z0-9]{3}", s or ""))


def los_upp(term, typ, home=None):
    """Taxonomi-id för en term (eller id:t självt). Returnerar (id, etikett) eller (None, term)."""
    if ar_id(term):
        return term, term
    b = basta_traff(term, autocomplete(term, typ, home))
    return (b[0], b[1]) if b else (None, term)


def graphql(query, home=None):
    d = api(TAXONOMY + "/graphql", {"query": query}, home) or {}
    return (d.get("data") or {})


# ---------------------------------------------------------------- annonser

def stats(url, params, typ, limit=30, home=None):
    p = dict(params, limit=0, stats=typ)
    p["stats.limit"] = limit
    d = api(url, p, home) or {}
    for s in d.get("stats", []):
        if s.get("type") == typ:
            return d.get("total", {}).get("value", 0), s.get("values", [])
    return d.get("total", {}).get("value", 0), []


def traffar(url, params, max_antal=500, home=None):
    """Bläddrar annonser (100 per sida, högst offset 2000). Ger (total, hits)."""
    ut, total, offset = [], 0, 0
    while offset < min(max_antal, 2000):
        d = api(url, dict(params, limit=min(100, max_antal - offset), offset=offset), home) or {}
        total = d.get("total", {}).get("value", 0)
        h = d.get("hits", [])
        ut.extend(h)
        if len(h) < 100:
            break
        offset += 100
    return total, ut


STOPP_FORE = re.compile(r"^(.{0,40}?\bsöker( nu)?( efter)?( en| ett| dig som| två| flera)?|nu söker vi( en| ett)?"
                        r"|rekryterar:?|we are hiring:?|join us as( an?)?|ny tjänst:?)\s+", re.I)
STOPP_EFTER = re.compile(r"\s+(sökes|sökes nu|wanted)$", re.I)
SKARV = re.compile(r"\s+(till|för|hos|inom|på|i|med|at|to|for|in)\s+|\s*[-–—|,:(/]\s*|\s+\d", re.I)


def rubrik_till_titel(rubrik):
    """'Vi söker en kommunikatör till Region X' -> 'kommunikatör'."""
    s = re.sub(r"\s+", " ", (rubrik or "").lower()).strip()
    s = STOPP_FORE.sub("", s)
    s = SKARV.split(s, maxsplit=1)[0]
    s = re.sub(r"[^\wåäöéü ]+", " ", s)
    s = STOPP_EFTER.sub("", re.sub(r"\s+", " ", s).strip())
    return s if 2 < len(s) <= 60 else None


# ---------------------------------------------------------------- andra skript

def kor_skript(namn, args, stdin=None):
    """Kör ett syskonskript. Returnerar (kod, stdout, stderr) eller None om skriptet saknas."""
    p = os.path.join(SKRIPT, namn)
    if not os.path.exists(p):
        return None
    r = subprocess.run([sys.executable, p] + list(args), input=stdin, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr
