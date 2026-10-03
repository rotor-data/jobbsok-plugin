#!/usr/bin/env python3
"""Hypoteser om var rätt jobb finns: sok/hypoteser.json (skillen jobbjakt).

  python3 jakt_hypoteser.py lista [--status aktiv,pausad] [--home DIR]
  python3 jakt_hypoteser.py visa <id>
  python3 jakt_hypoteser.py ny --typ TYP --beskrivning "..." --metod METOD
                               [--param nyckel=värde ...] [--recept NAMN] [--webbrecept NAMN]
                               [--motivering "..."] [--status aktiv]
  python3 jakt_hypoteser.py andra <id> [--status aktiv|pausad|beskuren] [--beskrivning ...] [--metod ...]
                               [--param nyckel=värde ...] [--recept ...] [--webbrecept ...] [--motivering ...]
  python3 jakt_hypoteser.py ta-bort <id>        flyttar till sok/hypoteser_borttagna.json (ingen radering)
  python3 jakt_hypoteser.py korning <id> --fynd N [--uid UID ...] [--anteckning "..."]
  python3 jakt_hypoteser.py ingest <id> [--kalla webb] < poster.json
        sätter hittad_via=<id> på varje post, kör ingest.py och loggar körningen på hypotesen
  python3 jakt_hypoteser.py utbyte [--min-fynd 5]
        räknar utbyte per hypotes ur jobb.sqlite (hittad_via + status), sparar det och föreslår
        beskär/bredda samt de vanligaste orsakerna till nej och ja (för lärandet)

Typer: narliggande_yrke, alternativ_titel, energimatch, liknande_arbetsgivare, likar, vardedriven,
       tillvaxtsignal, webbjakt, nischsajt, dold_marknad, joker.
Metoder: jakt_titlar, jakt_arbetsgivare, jakt_signaler, webbrecept, recept, malbolag, manuell.
Status: aktiv | pausad | beskuren.
"""
import argparse
import collections
import json
import os
import subprocess
import sys

import sok_common as sc

TYPER = ["narliggande_yrke", "alternativ_titel", "energimatch", "liknande_arbetsgivare", "likar",
         "vardedriven", "tillvaxtsignal", "webbjakt", "nischsajt", "dold_marknad", "joker"]
METODER = ["jakt_titlar", "jakt_arbetsgivare", "jakt_signaler", "webbrecept", "recept", "malbolag", "manuell"]
STATUS = ["aktiv", "pausad", "beskuren"]
INTRESSANT = ("intressant", "sokt")


def fil(home):
    return sc.sokv(home, "hypoteser.json")


def las(home):
    d = sc.las_json(fil(home)) or {}
    d.setdefault("schema_version", 1)
    d.setdefault("hypoteser", [])
    return d


def spara(home, d):
    sc.skriv_json(fil(home), d)


def hitta(d, hid):
    for h in d["hypoteser"]:
        if h["id"] == hid:
            return h
    sys.exit(f"Ingen hypotes med id {hid}. Kör 'lista' för att se vilka som finns.")


def nytt_id(d):
    n = max([int(h["id"].split("-")[1]) for h in d["hypoteser"] if h["id"].startswith("h-")] + [0])
    for b in sc.las_json(os.path.join(os.path.dirname(fil(HOME)), "hypoteser_borttagna.json"), {"hypoteser": []})["hypoteser"]:
        if b["id"].startswith("h-"):
            n = max(n, int(b["id"].split("-")[1]))
    return f"h-{n + 1:03d}"


def params(lista):
    ut = {}
    for p in lista or []:
        if "=" not in p:
            sys.exit(f"--param ska vara nyckel=värde, fick '{p}'")
        k, v = p.split("=", 1)
        try:
            v = json.loads(v)
        except ValueError:
            pass
        ut[k] = v
    return ut


def kort(h):
    u = h.get("utbyte") or {}
    return {"id": h["id"], "typ": h["typ"], "status": h["status"], "beskrivning": h["beskrivning"],
            "metod": h["metod"], "korningar": len(h.get("korningar", [])),
            "fynd": u.get("fynd", 0), "andel_intressanta": u.get("andel")}


def logga_korning(h, fynd, uid=None, anteckning=None):
    k = {"datum": sc.nu_iso(), "fynd": int(fynd)}
    if uid:
        k["uid"] = list(uid)
    if anteckning:
        k["anteckning"] = anteckning
    h.setdefault("korningar", []).append(k)
    h["korningar"] = h["korningar"][-30:]   # håll filen liten
    h["senast_kord"] = k["datum"]
    return k


def berakna_utbyte(home, d, min_fynd=5):
    c = sc.db(home)
    kol = {r[1] for r in c.execute("PRAGMA table_info(jobb)")}
    if "hittad_via" not in kol:
        return {"fel": "jobb.sqlite saknar kolumnen hittad_via (äldre version); kör kor.py en gång först"}
    har_bed = "bedomning_json" in kol
    forslag, orsaker = [], {}
    for h in d["hypoteser"]:
        rader = c.execute("SELECT status, dubblett_av%s FROM jobb WHERE hittad_via=?" %
                          (", bedomning_json" if har_bed else ""), (h["id"],)).fetchall()
        st = collections.Counter()
        nej_o, ja_o = collections.Counter(), collections.Counter()
        for r in rader:
            if r["dubblett_av"]:
                st["dubblett"] += 1
                continue
            b = json.loads((r["bedomning_json"] if har_bed else None) or "{}")
            s = r["status"]
            if s == "stangd" and b.get("status") in ("nej", "intressant", "sokt"):
                s = b["status"]
            st[s] += 1
            if b.get("orsak"):
                (nej_o if s == "nej" else ja_o if s in INTRESSANT else collections.Counter())[b["orsak"]] += 1
        fynd = sum(v for k, v in st.items() if k != "dubblett")
        bedomda = st["intressant"] + st["sokt"] + st["nej"]
        andel = round((st["intressant"] + st["sokt"]) / bedomda, 2) if bedomda else None
        h["utbyte"] = {"fynd": fynd, "bedomda": bedomda, "intressant": st["intressant"], "sokt": st["sokt"],
                       "nej": st["nej"], "dubbletter": st["dubblett"], "andel": andel, "beraknad": sc.idag()}
        if nej_o or ja_o:
            orsaker[h["id"]] = {"nej": [o for o, _ in nej_o.most_common(5)], "ja": [o for o, _ in ja_o.most_common(5)]}
        if h["status"] != "aktiv":
            continue
        nk = len(h.get("korningar", []))
        if nk >= 2 and fynd == 0:
            forslag.append({"id": h["id"], "forslag": "beskär eller byt metod", "skal": f"{nk} körningar utan fynd"})
        elif bedomda >= min_fynd and andel is not None and andel < 0.1:
            forslag.append({"id": h["id"], "forslag": "beskär", "skal": f"{andel:.0%} intressanta av {bedomda} bedömda"})
        elif bedomda >= 3 and andel is not None and andel >= 0.3:
            forslag.append({"id": h["id"], "forslag": "bredda", "skal": f"{andel:.0%} intressanta av {bedomda} bedömda"})
    return {"forslag": forslag, "orsaker": orsaker}


def main(argv=None):
    global HOME
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sc.add_home_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("lista")
    l.add_argument("--status", default="aktiv,pausad")
    v = sub.add_parser("visa")
    v.add_argument("id")
    for namn in ("ny", "andra"):
        p = sub.add_parser(namn)
        if namn == "andra":
            p.add_argument("id")
        p.add_argument("--typ", choices=TYPER, required=(namn == "ny"))
        p.add_argument("--beskrivning", required=(namn == "ny"))
        p.add_argument("--metod", choices=METODER, required=(namn == "ny"))
        p.add_argument("--param", action="append")
        p.add_argument("--recept")
        p.add_argument("--webbrecept")
        p.add_argument("--motivering")
        p.add_argument("--status", choices=STATUS)
    t = sub.add_parser("ta-bort")
    t.add_argument("id")
    k = sub.add_parser("korning")
    k.add_argument("id")
    k.add_argument("--fynd", type=int, required=True)
    k.add_argument("--uid", nargs="*")
    k.add_argument("--anteckning")
    i = sub.add_parser("ingest")
    i.add_argument("id")
    i.add_argument("--kalla", default="webb")
    u = sub.add_parser("utbyte")
    u.add_argument("--min-fynd", type=int, default=5)
    a = ap.parse_args(argv)
    HOME = home = sc.hem(a.home)
    d = las(home)

    if a.cmd == "lista":
        st = set(a.status.split(","))
        print(json.dumps([kort(h) for h in d["hypoteser"] if h["status"] in st], ensure_ascii=False, indent=0))
    elif a.cmd == "visa":
        print(json.dumps(hitta(d, a.id), ensure_ascii=False, indent=1))
    elif a.cmd == "ny":
        h = {"id": nytt_id(d), "typ": a.typ, "beskrivning": a.beskrivning, "metod": a.metod,
             "parametrar": params(a.param), "recept": a.recept, "webbrecept": a.webbrecept,
             "motivering": a.motivering, "skapad": sc.idag(), "status": a.status or "aktiv",
             "korningar": [], "utbyte": {}}
        d["hypoteser"].append(h)
        spara(home, d)
        print(json.dumps({"skapad": kort(h)}, ensure_ascii=False))
    elif a.cmd == "andra":
        h = hitta(d, a.id)
        for f in ("typ", "beskrivning", "metod", "recept", "webbrecept", "motivering", "status"):
            if getattr(a, f) is not None:
                h[f] = getattr(a, f)
        if a.param:
            h.setdefault("parametrar", {}).update(params(a.param))
        h["andrad"] = sc.idag()
        spara(home, d)
        print(json.dumps({"andrad": kort(h)}, ensure_ascii=False))
    elif a.cmd == "ta-bort":
        h = hitta(d, a.id)
        d["hypoteser"].remove(h)
        bp = sc.sokv(home, "hypoteser_borttagna.json")
        b = sc.las_json(bp) or {"schema_version": 1, "hypoteser": []}
        h["borttagen"] = sc.idag()
        b["hypoteser"].append(h)
        sc.skriv_json(bp, b)
        spara(home, d)
        print(json.dumps({"flyttad": a.id, "till": bp}, ensure_ascii=False))
    elif a.cmd == "korning":
        h = hitta(d, a.id)
        k = logga_korning(h, a.fynd, a.uid, a.anteckning)
        spara(home, d)
        print(json.dumps({"loggad": a.id, "korning": k}, ensure_ascii=False))
    elif a.cmd == "ingest":
        h = hitta(d, a.id)
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.exit(f"Ogiltig JSON på stdin: {e}")
        poster = data.get("poster", []) if isinstance(data, dict) else data
        for p in poster:
            p["hittad_via"] = a.id
        skript = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingest.py")
        r = subprocess.run([sys.executable, skript, "--kalla", a.kalla, "--hittad-via", a.id, "--home", home],
                           input=json.dumps(poster, ensure_ascii=False), capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            sys.exit(r.returncode)
        res = json.loads(r.stdout)
        logga_korning(h, res.get("nya", 0), res.get("uid"), f"{res.get('nya', 0)} nya, {res.get('uppdaterade', 0)} kända")
        spara(home, d)
        print(json.dumps({"hypotes": a.id, "nya": res.get("nya"), "uppdaterade": res.get("uppdaterade"),
                          "fel": res.get("fel"), "uid": res.get("uid")}, ensure_ascii=False))
    elif a.cmd == "utbyte":
        res = berakna_utbyte(home, d, a.min_fynd)
        spara(home, d)
        res["hypoteser"] = [kort(h) for h in d["hypoteser"]]
        print(json.dumps(res, ensure_ascii=False, indent=0))


HOME = None

if __name__ == "__main__":
    main()
