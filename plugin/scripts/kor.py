#!/usr/bin/env python3
"""Kör hela kedjan fetch -> dedupe -> score -> lista för ett eller alla recept. Det här schemaläggs.

  python3 kor.py --recept <namn> | --alla  [--enrich] [--jokrar 2] [--min-poang N] [--antal 20]
                 [--alla-traffar] [--utan-bevakade] [--home DIR]

Som standard hämtas också alla bevakade källor i kallor.json som inte ingår i något recept
(fetch.py --alla-bevakade); --utan-bevakade stänger av det. --jokrar N (standard 2) tar med N jobb
under min-poäng som matchar energigivare/värden (score.py --jokrar).

Skriver en kort rapport och topplistan över NYA träffar sedan förra körningen (--alla-traffar visar
hela topplistan). min-poäng tas från receptets filter.min_poang om inget anges.
Kod 3 = inget nät nådde fram (fall tillbaka på webbverktyg + ingest.py).
"""
import argparse
import glob
import json
import os
import sys

import dedupe
import fetch
import lista
import score
import sok_common as sc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recept")
    g.add_argument("--alla", action="store_true")
    ap.add_argument("--enrich", action="store_true")
    ap.add_argument("--min-poang", type=int)
    ap.add_argument("--antal", type=int, default=20)
    ap.add_argument("--alla-traffar", action="store_true")
    ap.add_argument("--utan-bevakade", action="store_true")
    ap.add_argument("--jokrar", type=int, default=2)
    sc.add_home_arg(ap)
    a = ap.parse_args()
    home = sc.hem(a.home)
    namn = [a.recept] if a.recept else sorted(os.path.splitext(os.path.basename(p))[0]
                                              for p in glob.glob(sc.sokv(home, "recept", "*.json")))
    if not namn:
        sys.exit("Inga recept finns i " + sc.sokv(home, "recept"))
    logg = sc.korning_logg(home)
    start = sc.nu_iso()
    sc.skriv_json(sc.sokv(home, "senaste_korning.json"),
                  {"forra_start": logg.get("senaste_start"), "senaste_start": start, "recept": namn})
    rapporter, natfel, min_p = [], [], []
    for n in namn:
        r = fetch.kor_recept(home, n)
        rapporter.append(r)
        natfel += r.get("natfel", [])
        rec = sc.las_json(sc.sokv(home, "recept", n + ".json"), {}) or {}
        min_p.append(((rec.get("filter") or {}).get("min_poang")) or 0)
    if not a.utan_bevakade:
        r = fetch.kor_bevakade(home, utom=fetch.recept_kallor(home))
        if r["kallor"]:
            rapporter.append(r)
            natfel += r.get("natfel", [])
    d = dedupe.dedupe(home)
    mp = a.min_poang if a.min_poang is not None else min(min_p)
    s = score.score(home, med_enrich=a.enrich, jokrar=a.jokrar, min_poang=mp)
    rs = lista.rader(home, min_poang=mp, nya=not a.alla_traffar, antal=a.antal)
    print("## Hämtning")
    for r in rapporter:
        for k in r["kallor"]:
            if "fel" in k:
                print(f"- {r['recept']}/{k['id']}: FEL {k['fel']}")
            elif "hoppad" in k:
                print(f"- {r['recept']}/{k['id']}: hoppad ({k['hoppad']}, matas in via ingest.py)")
            else:
                print(f"- {r['recept']}/{k['id']}: {k['hamtade']} hämtade, {k['nya']} nya, {k['stangda']} stängda")
    print(f"- dubbletter: {d['dubbletter']}, poängsatta: {s['poangsatta']}"
          + ("" if s.get("preferenser") else " (OBS: profil/preferenser.json saknas, poängen är grov)"))
    print(f"\n## {'Topplista' if a.alla_traffar else 'Nya träffar'} (min {mp} poäng)")
    print("uid | titel | arbetsgivare | ort | distans | deadline | poäng | kompetenser | utdrag")
    for r in rs:
        print(lista.formatera(r))
    if not rs:
        print("(inga)")
    jk = s.get("jokrar") or []
    if jk:
        print("\n## Jokrar (under gränsen men matchar det som ger dig energi/dina värden)")
        sett = {r["uid"] for r in rs}
        for j in lista.jokrar(home):
            if j["uid"] not in sett:
                print(lista.formatera(j) + f" | joker: {', '.join(j['joker'] or [])}")
    if s.get("berikning_fel"):
        print(f"- berikning misslyckades: {s['berikning_fel']}")
    if natfel and not any(k.get("hamtade") is not None for r in rapporter for k in r["kallor"]):
        sc.natfel_avslut("; ".join(natfel))


if __name__ == "__main__":
    main()
