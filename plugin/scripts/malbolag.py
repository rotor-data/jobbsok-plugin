#!/usr/bin/env python3
"""Förslag på målbolag: arbetsgivare som återkommande annonserat valda yrken i valda regioner.

  python3 malbolag.py [--yrke ID ...] [--yrkesgrupp ID ...] [--q "fritext"] [--kommun ID ...] [--region ID ...]
                      [--ar 3] [--antal 30] [--home DIR]

Utan yrke/ort-flaggor läses yrkes_id och orter ur profil/preferenser.json.
Källa: JobTech Historical ads (historical.api.jobtechdev.se). Varje år hämtas för sig (högst 2000
annonser per år och fråga, resdet=brief). Resultatet cachas i cache/malbolag/<hash>.json och skrivs
på stdout som JSON: [{"arbetsgivare","orgnr","antal","per_ar":{"2024":n},"senast","titlar":[...]}],
sorterat efter antal. Det är en förslagslista; användaren väljer själv vilka som blir målbolag.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import urllib.parse

import sok_common as sc

URL = "https://historical.api.jobtechdev.se/search"


def hamta(params, ar_n):
    nu = dt.date.today()
    per = collections.defaultdict(lambda: {"antal": 0, "per_ar": collections.Counter(), "senast": "",
                                          "titlar": collections.Counter(), "orgnr": None, "namn": None})
    trunk = []
    for i in range(ar_n):
        fran = nu.replace(year=nu.year - i - 1)
        till = nu.replace(year=nu.year - i)
        offset, tot = 0, 0
        while True:
            q = params + [("published-after", fran.isoformat() + "T00:00:00"),
                          ("published-before", till.isoformat() + "T00:00:00"),
                          ("limit", "100"), ("offset", str(offset)), ("request-timeout", "120")]
            _, d, _ = sc.http_json(URL + "?" + urllib.parse.urlencode(q), timeout=150)
            hits = (d or {}).get("hits") or []
            tot = ((d or {}).get("total") or {}).get("value") or 0
            for h in hits:
                e = h.get("employer") or {}
                namn = (e.get("name") or "").strip()
                if not namn:
                    continue
                nyckel = e.get("organization_number") or sc.norm(namn)
                p = per[nyckel]
                p["namn"] = p["namn"] or namn
                p["orgnr"] = p["orgnr"] or e.get("organization_number")
                p["antal"] += 1
                p["per_ar"][(h.get("publication_date") or "")[:4]] += 1
                p["senast"] = max(p["senast"], (h.get("publication_date") or "")[:10])
                if h.get("headline"):
                    p["titlar"][h["headline"].strip()] += 1
            offset += len(hits)
            if not hits or offset >= tot or offset >= 2000:
                break
        if tot > 2000:
            trunk.append(f"{fran.year}-{till.year}: {tot} annonser, bara de 2000 första räknade")
    return per, trunk


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yrke", nargs="*", default=[])
    ap.add_argument("--yrkesgrupp", nargs="*", default=[])
    ap.add_argument("--q")
    ap.add_argument("--kommun", nargs="*", default=[])
    ap.add_argument("--region", nargs="*", default=[])
    ap.add_argument("--ar", type=int, default=3)
    ap.add_argument("--antal", type=int, default=30)
    sc.add_home_arg(ap)
    a = ap.parse_args()
    home = sc.hem(a.home)
    yrke, kommun, region = list(a.yrke), list(a.kommun), list(a.region)
    if not (yrke or a.yrkesgrupp or a.q) or not (kommun or region):
        pref = sc.las_json(os.path.join(home, "profil", "preferenser.json"), {}) or {}
        if not (yrke or a.yrkesgrupp or a.q):
            yrke = [i for r in pref.get("riktningar") or [] for i in r.get("yrkes_id") or []]
        if not (kommun or region):
            kommun = [o["kommun_id"] for o in pref.get("orter") or [] if o.get("kommun_id")]
            region = [o["region_id"] for o in pref.get("orter") or [] if o.get("region_id")]
    if not (yrke or a.yrkesgrupp or a.q):
        raise SystemExit("Ange --yrke/--yrkesgrupp/--q eller fyll i riktningar.yrkes_id i preferenser.json")
    params = [("occupation-name", y) for y in yrke] + [("occupation-group", g) for g in a.yrkesgrupp]
    params += [("municipality", k) for k in kommun] + [("region", r) for r in region]
    if a.q:
        params.append(("q", a.q))
    params.append(("resdet", "brief"))
    nyckel = hashlib.sha1(json.dumps([params, a.ar, sc.idag()[:7]]).encode()).hexdigest()[:16]
    cp = sc.cachev(home, "malbolag", nyckel + ".json")
    res = sc.las_json(cp)
    if res is None:
        try:
            per, trunk = hamta(params, a.ar)
        except sc.NatFel as e:
            sc.natfel_avslut(e)
        lista = sorted(per.values(), key=lambda p: (-p["antal"], p["namn"]))
        res = {"fraga": params, "ar": a.ar, "avkortat": trunk, "arbetsgivare": [
            {"arbetsgivare": p["namn"], "orgnr": p["orgnr"], "antal": p["antal"],
             "per_ar": dict(sorted(p["per_ar"].items())), "senast": p["senast"],
             "titlar": [t for t, _ in p["titlar"].most_common(3)]} for p in lista]}
        sc.skriv_json(cp, res)
    res = dict(res)
    res["arbetsgivare"] = res["arbetsgivare"][: a.antal]
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
