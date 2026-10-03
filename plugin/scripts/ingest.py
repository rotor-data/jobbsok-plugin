#!/usr/bin/env python3
"""Lägger in annonser som JSON på stdin i sok/jobb.sqlite (samma upsert som fetch.py).

  python3 ingest.py [--kalla webb|mejl|lank] [--home DIR] < poster.json

Används när skriptens nät är begränsat (Claude hämtar med webbverktyg), för jobbaviseringar
i mejl (LinkedIn, Indeed m.fl.) och för länkar som användaren klistrar in.

Indata: en lista med objekt, eller {"poster": [...]}. Fält (bara titel eller url krävs):
  titel, arbetsgivare, url, ort, kommun_id, orgnr, distans (0/1/2 eller "hybrid"/"distans"/"på plats"),
  publicerad, deadline, anstallningsform (tillsvidare|visstid|vikariat|timanstallning|konsult|praktik),
  omfattning (heltid|deltid), kompetenser (lista med namn eller {"id","namn","typ"}),
  text (fulltext, valfri), utdrag, kalla_id, kalla,
  hittad_via (recept-, webbrecept- eller hypotes-id; annars värdet av --hittad-via).
Utan kalla_id används url som id, så samma länk två gånger blir samma jobb.
"""
import argparse
import json
import sys

import sok_common as sc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kalla", default="webb", help="källnamn om posten saknar 'kalla' (standard webb)")
    ap.add_argument("--hittad-via", help="standardvärde för hittad_via om posten saknar det")
    sc.add_home_arg(ap)
    a = ap.parse_args()
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.exit(f"Ogiltig JSON på stdin: {e}")
    poster = data.get("poster", []) if isinstance(data, dict) else data
    rader, fel = [], []
    for i, p in enumerate(poster):
        if not isinstance(p, dict) or not (p.get("titel") or p.get("url")):
            fel.append(f"post {i}: saknar titel och url")
            continue
        if a.hittad_via:
            p.setdefault("hittad_via", a.hittad_via)
        rader.append(sc.normalisera(p, a.kalla))
    home = sc.hem(a.home)
    c = sc.db(home)
    nya, upd = sc.upsert(c, home, rader)
    print(json.dumps({"nya": nya, "uppdaterade": upd, "fel": fel,
                      "uid": [r["uid"] for r in rader]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
