#!/usr/bin/env python3
"""Räknar utbyte per källa, recept och hittad_via och skriver sok/utbyte.json.

  python3 utbyte.py [--home DIR] [--dagar N]

Utdata (även på stdout):
{"schema_version":1,"skapad":ISO,"dagar":N|null,
 "per_kalla":      {"<kalla>":      {"totalt":n,"ny":n,"intressant":n,"nej":n,"sokt":n,"stangd":n,"dubbletter":n,"snittpoang":x}},
 "per_hittad_via": {"<id>": {...samma...}},
 "per_recept":     {"<receptnamn>": {...samma, summerat över receptets källor...}}}
'nej' räknas även för jobb som stängts efter att ha bedömts nej (bedomning_json.status).
Dubbletter räknas separat och ingår inte i statusräkningen. --dagar begränsar till jobb först sedda de senaste N dagarna.
"""
import argparse
import datetime as dt
import glob
import json
import os

import sok_common as sc


def tom():
    return {"totalt": 0, "ny": 0, "intressant": 0, "nej": 0, "sokt": 0, "stangd": 0, "dubbletter": 0,
            "_p": 0, "_n": 0}


def lagg(d, r):
    if r["dubblett_av"]:
        d["dubbletter"] += 1
        return
    d["totalt"] += 1
    st = r["status"]
    b = json.loads(r["bedomning_json"] or "{}")
    if st == "stangd" and b.get("status") in ("nej", "sokt", "intressant"):
        st = b["status"]
    d[st] = d.get(st, 0) + 1
    if r["poang"] is not None:
        d["_p"] += r["poang"]
        d["_n"] += 1


def klar(d):
    for v in d.values():
        v["snittpoang"] = round(v.pop("_p") / v["_n"], 1) if v["_n"] else None
        v.pop("_n")
    return d


def utbyte(home, dagar=None):
    c = sc.db(home)
    q, args = "SELECT * FROM jobb", []
    if dagar:
        q += " WHERE forst_sedd >= ?"
        args.append((dt.datetime.now() - dt.timedelta(days=dagar)).isoformat(timespec="seconds"))
    rows = c.execute(q, args).fetchall()
    per_k, per_h, per_r = {}, {}, {}
    recept = {}
    for p in glob.glob(sc.sokv(home, "recept", "*.json")):
        recept[os.path.splitext(os.path.basename(p))[0]] = set((sc.las_json(p, {}) or {}).get("kallor") or [])
    for r in rows:
        lagg(per_k.setdefault(r["kalla"] or "?", tom()), r)
        lagg(per_h.setdefault(r["hittad_via"] or "?", tom()), r)
        for n, kallor in recept.items():
            if r["kalla"] in kallor or r["hittad_via"] == n:
                lagg(per_r.setdefault(n, tom()), r)
    ut = {"schema_version": 1, "skapad": sc.nu_iso(), "dagar": dagar,
          "per_kalla": klar(per_k), "per_hittad_via": klar(per_h), "per_recept": klar(per_r)}
    sc.skriv_json(sc.sokv(home, "utbyte.json"), ut)
    return ut


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dagar", type=int)
    sc.add_home_arg(ap)
    a = ap.parse_args()
    print(json.dumps(utbyte(sc.hem(a.home), a.dagar), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
