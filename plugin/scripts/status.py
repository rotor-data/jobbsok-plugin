#!/usr/bin/env python3
"""Statusrapport för jobbsok-mappen. Läser bara, skriver inget.

    python3 status.py [--home DIR] [--format json|text|bada] [--idag YYYY-MM-DD]

JSON-fält: home, finns, coach, faktabank, design, kallor, jobb, ansokningar,
uppfoljning_forfallen, nasta_steg.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobbsok_common as jc  # noqa: E402

FASER = ["intake", "identity", "energy_log", "needs_profile", "options", "experiments", "decision"]
FASNAMN = {"intake": "nuläge", "identity": "identitet", "energy_log": "energilogg", "needs_profile": "behovsprofil",
           "options": "möjliga vägar", "experiments": "prototyper", "decision": "beslut", "klar": "klar"}
STATUSAR = ["utkast", "skickad", "intervju", "nej", "erbjudande"]


def _safe(path):
    try:
        return jc.read_json(path)
    except (ValueError, OSError):
        return None


def faktabank(f):
    if not isinstance(f, dict):
        return {"finns": False, "fyllnadsgrad": 0, "roller": 0, "meriter": 0, "saknas": ["faktabank"]}
    p = f.get("person") or {}
    roller = f.get("roller") or []
    meriter = sum(len(r.get("meriter") or []) for r in roller)
    kontroller = {
        "namn": bool(p.get("namn")), "kontakt": bool(p.get("epost") or p.get("telefon")),
        "sammanfattning": bool(f.get("sammanfattning_rad")), "roller": len(roller) > 0,
        "meriter_per_roll": bool(roller) and all(len(r.get("meriter") or []) >= 1 for r in roller),
        "utbildning": bool(f.get("utbildning")), "sprak": bool(f.get("sprak")),
        "kompetenser": bool(f.get("kompetenser")), "aldrig_pastaa": bool(f.get("aldrig_pastaa")),
        "engelska": any((m.get("text") or {}).get("en") for r in roller for m in (r.get("meriter") or [])),
    }
    grad = round(100 * sum(kontroller.values()) / len(kontroller))
    return {"finns": True, "fyllnadsgrad": grad, "roller": len(roller), "meriter": meriter,
            "saknas": [k for k, v in kontroller.items() if not v]}


def coach(c):
    if not isinstance(c, dict):
        return {"finns": False, "aktuell_fas": None, "aktuell_fas_namn": None, "klara_faser": [], "klar": False}
    faser = c.get("faser") or {}
    klara = [f for f in FASER if faser.get(f)]
    akt = (c.get("status") or {}).get("aktuell_fas")
    return {"finns": True, "aktuell_fas": akt, "aktuell_fas_namn": FASNAMN.get(akt, akt),
            "klara_faser": klara, "klar": akt == "klar" or bool(faser.get("decision"))}


def jobb(home):
    db = home / "sok" / "jobb.sqlite"
    if not db.exists():
        return {"finns": False, "ny": 0, "per_status": {}}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT status, COUNT(*) FROM jobb WHERE dubblett_av IS NULL GROUP BY status").fetchall()
        con.close()
    except sqlite3.Error:
        return {"finns": True, "ny": 0, "per_status": {}, "fel": "kunde inte läsa jobb.sqlite"}
    per = {s or "ny": n for s, n in rows}
    return {"finns": True, "ny": per.get("ny", 0), "per_status": per}


def ansokningar(home, idag):
    rot = home / "ansokningar"
    per = {s: 0 for s in STATUSAR}
    forfallna, lista = [], []
    if rot.is_dir():
        for d in sorted(rot.iterdir()):
            if not d.is_dir():
                continue
            logg = _safe(d / "logg.json") or {}
            st = logg.get("status", "utkast")
            per[st] = per.get(st, 0) + 1
            lista.append({"mapp": d.name, "status": st, "skickad": logg.get("skickad")})
            fu = logg.get("foljupp_datum")
            if fu and st in ("skickad", "intervju") and str(fu)[:10] <= idag:
                forfallna.append({"mapp": d.name, "status": st, "foljupp_datum": fu, "kontakt": logg.get("kontakt", "")})
    return {"totalt": len(lista), "per_status": per, "lista": lista}, forfallna


def build(home, idag=None):
    idag = idag or dt.date.today().isoformat()
    r = {"home": str(home), "finns": home.is_dir(), "idag": idag}
    r["coach"] = coach(_safe(home / "profil" / "coach.json"))
    r["faktabank"] = faktabank(_safe(home / "profil" / "fakta.json"))
    pref = _safe(home / "profil" / "preferenser.json") or {}
    r["preferenser"] = {"finns": bool(pref.get("riktningar") or pref.get("orter"))}
    d = _safe(home / "design" / "design.json")
    r["design"] = {"finns": isinstance(d, dict), "namn": (d or {}).get("namn"), "version": (d or {}).get("version")}
    k = _safe(home / "sok" / "kallor.json") or {}
    recdir = home / "sok" / "recept"
    r["kallor"] = {"antal": len(k.get("kallor") or []), "aktiva": sum(1 for x in k.get("kallor") or [] if x.get("aktiv", True)),
                   "recept": sorted(p.stem for p in recdir.glob("*.json")) if recdir.is_dir() else []}
    r["jobb"] = jobb(home)
    r["ansokningar"], r["uppfoljning_forfallen"] = ansokningar(home, idag)
    r["nasta_steg"] = nasta_steg(r)
    return r


def nasta_steg(r):
    if not r["finns"]:
        return {"skill": "jobbsok-start", "varfor": "Mappen finns inte än."}
    if r["uppfoljning_forfallen"]:
        return {"skill": "jobbsok-start", "varfor": "Det är dags att följa upp skickade ansökningar."}
    if not r["coach"]["klar"] and not r["preferenser"]["finns"]:
        return {"skill": "karriarcoach", "varfor": "Ta reda på vad du vill innan vi letar."}
    if r["faktabank"]["fyllnadsgrad"] < 60:
        return {"skill": "faktabank", "varfor": "Faktabanken behöver fyllas på."}
    if not r["design"]["finns"]:
        return {"skill": "cv-design", "varfor": "Ingen CV-design är vald än."}
    if not r["kallor"]["antal"] or not r["kallor"]["recept"]:
        return {"skill": "jobbkallor", "varfor": "Inga jobbkällor eller sökningar är inlagda."}
    if r["jobb"]["ny"]:
        return {"skill": "jobbsok", "varfor": f"{r['jobb']['ny']} nya jobb att titta på."}
    return {"skill": "jobbsok", "varfor": "Kör en ny sökning."}


def text(r):
    rader = [f"Mapp: {r['home']}" + ("" if r["finns"] else " (finns inte)")]
    c = r["coach"]
    rader.append("Coach: " + ("inte påbörjad" if not c["finns"] else "klar" if c["klar"] else f"pågår, fas {c.get('aktuell_fas_namn') or '–'}"
                              f" ({len(c['klara_faser'])}/7 faser med innehåll)"))
    f = r["faktabank"]
    rader.append(f"Faktabank: {f['fyllnadsgrad']} % ifylld, {f['roller']} roller, {f['meriter']} meriter"
                 + (f" – saknas: {', '.join(f['saknas'])}" if f["saknas"] else ""))
    d = r["design"]
    rader.append("CV-design: " + (f"{d['namn'] or 'namnlös'} (version {d['version']})" if d["finns"] else "inte vald"))
    k = r["kallor"]
    rader.append(f"Jobbkällor: {k['aktiva']} aktiva, {len(k['recept'])} sparade sökningar")
    rader.append(f"Nya jobb: {r['jobb']['ny']}")
    a = r["ansokningar"]
    rader.append(f"Ansökningar: {a['totalt']} (" + ", ".join(f"{s} {n}" for s, n in a["per_status"].items() if n) + ")"
                 if a["totalt"] else "Ansökningar: inga än")
    for u in r["uppfoljning_forfallen"]:
        rader.append(f"  Följ upp: {u['mapp']} (sedan {u['foljupp_datum']})")
    rader.append(f"Nästa steg: {r['nasta_steg']['skill']} – {r['nasta_steg']['varfor']}")
    return "\n".join(rader)


def main(argv=None):
    ap = jc.add_home_arg(argparse.ArgumentParser(description="Statusrapport för jobbsok."))
    ap.add_argument("--format", choices=["json", "text", "bada"], default="bada")
    ap.add_argument("--idag", help="datum för förfallna uppföljningar (standard: idag)")
    a = ap.parse_args(argv)
    r = build(jc.resolve_home(a.home), a.idag)
    if a.format in ("json", "bada"):
        print(json.dumps(r, ensure_ascii=False, indent=2))
    if a.format == "bada":
        print("---")
    if a.format in ("text", "bada"):
        print(text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
