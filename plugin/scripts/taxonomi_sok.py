#!/usr/bin/env python3
"""Slår upp taxonomi-id för yrken och platser i JobTech Taxonomy (cache i cache/taxonomy).

  python3 taxonomi_sok.py <typ> <etikett> [<etikett> ...] [--antal 5] [--home DIR]

typ: occupation-name (yrke), occupation-group (yrkesgrupp, = SSYK nivå 4), municipality (kommun), region (län).
Hela listan för typen hämtas en gång och cachas i cache/taxonomy/<typ>.json; sedan sker matchning lokalt:
exakt etikett först, därefter början av ord och delsträng. Utdata JSON:
  {"<etikett>": [{"id":"otaF_bQY_4ZD","etikett":"Uppsala","typ":"municipality","match":"exakt"}, ...]}
(Kompetenser slås upp av taxonomy.py, inte här.)
"""
import argparse
import json
import urllib.parse

import sok_common as sc

URL = "https://taxonomy.api.jobtechdev.se/v1/taxonomy/main/concepts"
ALIAS = {"yrke": "occupation-name", "yrkesgrupp": "occupation-group", "kommun": "municipality",
         "lan": "region", "län": "region"}
TYPER = ("occupation-name", "occupation-group", "municipality", "region")
# JobSearch-parametern occupation-group motsvarar taxonomitypen ssyk-level-4 (verifierat 2026-10-01).
API_TYP = {"occupation-group": "ssyk-level-4"}


def lista(home, typ):
    cp = sc.cachev(home, "taxonomy", f"{typ}.json")
    d = sc.las_json(cp)
    if d is None:
        _, raa, _ = sc.http_json(URL + "?" + urllib.parse.urlencode({"type": API_TYP.get(typ, typ)}), timeout=60)
        d = [{"id": x["taxonomy/id"], "etikett": x["taxonomy/preferred-label"]} for x in raa or []]
        if typ == "region":  # bara svenska län (de har 'län' i namnet)
            d = [x for x in d if "län" in x["etikett"].lower()] or d
        if d:
            sc.skriv_json(cp, d)
    return d


def sok(home, typ, etikett, antal=5):
    typ = ALIAS.get(typ, typ)
    if typ not in TYPER:
        raise SystemExit(f"Okänd typ {typ}. Använd {', '.join(TYPER)}")
    e = etikett.strip().lower()
    ut = []
    for x in lista(home, typ):
        l = x["etikett"].lower()
        if l == e or (typ == "region" and l in (e + " län", e + "s län")):
            m = 0
        elif l.startswith(e) or any(w.startswith(e) for w in l.replace(",", " ").replace("/", " ").split()):
            m = 1
        elif e in l:
            m = 2
        else:
            continue
        ut.append((m, len(l), x))
    ut.sort(key=lambda t: (t[0], t[1]))
    return [{"id": x["id"], "etikett": x["etikett"], "typ": typ, "match": ("exakt", "början", "delsträng")[m]}
            for m, _, x in ut[:antal]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("typ")
    ap.add_argument("etiketter", nargs="+")
    ap.add_argument("--antal", type=int, default=5)
    sc.add_home_arg(ap)
    a = ap.parse_args()
    home = sc.hem(a.home)
    try:
        print(json.dumps({e: sok(home, a.typ, e, a.antal) for e in a.etiketter}, ensure_ascii=False, indent=1))
    except sc.NatFel as e:
        sc.natfel_avslut(e)


if __name__ == "__main__":
    main()
