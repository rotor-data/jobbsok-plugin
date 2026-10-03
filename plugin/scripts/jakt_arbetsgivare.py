#!/usr/bin/env python3
"""Arbetsgivare som anställer det hon söker, och likar till bolag hon gillar. (skillen jobbjakt)

  python3 jakt_arbetsgivare.py region --roll kommunikatör [--roll ...] [--yrkesgrupp ID]
                                      --region "Uppsala län" [--kommun Uppsala] [--ar 3] [--antal 30]
  python3 jakt_arbetsgivare.py likar --bolag "Uppsala kommun" | --orgnr 2120003142
                                      [--region "Uppsala län"] [--ar 3] [--antal 20]
  Gemensamt: [--kallor-forslag] [--home DIR]

region: läser Historical ads (och JobSearch för det som är öppet nu) och räknar per arbetsgivare:
        antal annonser, senaste annons, orgnr, typiska rubriker, kommuner, öppna nu.
likar:  tar fram X:s yrkesprofil (vilka yrkesgrupper X annonserar) och hittar arbetsgivare som
        annonserar samma yrkesgrupper. Likhet = viktad överlappning med X:s profil (0–1).
--kallor-forslag: för de översta arbetsgivarna som saknas i sok/kallor.json skrivs förslag ut:
        hitta karriärsidan och registrera den med kalla_lagg_till.py (som kör upptack_ats).

Utdata: kompakt JSON. Nätfel: exit 3 (använd webbsök i stället).
"""
import argparse
import collections
import math

import jakt_common as jc
import sok_common as sc


def ag_nyckel(h):
    e = h.get("employer") or {}
    return (e.get("organization_number") or "").replace("-", "") or "namn:" + sc.norm(e.get("name")), e


def aggregera(hits, kalla, agg):
    for h in hits:
        k, e = ag_nyckel(h)
        p = agg.setdefault(k, {"namn": e.get("name"), "orgnr": e.get("organization_number"), "annonser": 0,
                               "senaste": "", "oppna_nu": 0, "rubriker": collections.Counter(),
                               "kommuner": collections.Counter()})
        if kalla == "nu":
            p["oppna_nu"] += 1
        else:
            p["annonser"] += 1
        d = (h.get("publication_date") or "")[:10]
        p["senaste"] = max(p["senaste"], d)
        t = jc.rubrik_till_titel(h.get("headline"))
        if t:
            p["rubriker"][t] += 1
        m = (h.get("workplace_address") or {}).get("municipality")
        if m:
            p["kommuner"][m] += 1


def kompakt(p, extra=None):
    ut = {"namn": p["namn"], "orgnr": p["orgnr"], "annonser": p["annonser"], "senaste": p["senaste"],
          "oppna_nu": p["oppna_nu"], "rubriker": [t for t, _ in p["rubriker"].most_common(3)],
          "kommuner": [m for m, _ in p["kommuner"].most_common(3)]}
    ut.update(extra or {})
    return ut


def kallor_forslag(home, lista, n=10):
    kallor = (sc.las_json(sc.sokv(home, "kallor.json"), {}) or {}).get("kallor", [])
    kanda = {sc.norm(k.get("namn")) for k in kallor}
    bolag = [{"namn": p["namn"], "orgnr": p["orgnr"]} for p in lista[:n] if sc.norm(p["namn"]) not in kanda]
    return {"instruktion": "hitta karriärsidan med webbsök, visa henne, och efter ja: "
                           'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kalla_lagg_till.py" <url> --namn "<namn>"',
            "bolag": bolag}


def los_yrken(a, home):
    ids, los = [], []
    for r in a.roll:
        yid, lab = jc.los_upp(r, "occupation-name", home)
        los.append({"roll": r, "yrke_id": yid, "yrke": lab})
        if yid:
            ids.append(yid)
    return ids, los


def region_param(a, home):
    p = {}
    if a.region:
        rid, _ = jc.los_upp(a.region, "region", home)
        if rid:
            p["region"] = rid
    if getattr(a, "kommun", None):
        kid, _ = jc.los_upp(a.kommun, "municipality", home)
        if kid:
            p["municipality"] = kid
    return p


def kor_region(a, home):
    ids, los = los_yrken(a, home)
    if not ids and not a.yrkesgrupp:
        raise SystemExit("Hittade inget yrke för --roll. Prova en annan benämning eller ange --yrkesgrupp.")
    rp = region_param(a, home)
    p = dict(rp)
    if ids:
        p["occupation-name"] = ids
    if a.yrkesgrupp:
        p["occupation-group"] = a.yrkesgrupp
    agg = {}
    total, hits = jc.traffar(jc.HISTORICAL, dict(p, **{"historical-from": jc.ar_sedan(a.ar)}), a.max, home)
    aggregera(hits, "historik", agg)
    _, nu = jc.traffar(jc.JOBSEARCH, p, 200, home)
    aggregera(nu, "nu", agg)
    lista = sorted(agg.values(), key=lambda x: (-(x["annonser"] + 2 * x["oppna_nu"]), x["namn"] or ""))
    ut = {"uppslag": los, "region": a.region, "kommun": a.kommun, "fran": jc.ar_sedan(a.ar),
          "annonser_totalt": total, "lasta": len(hits), "arbetsgivare_totalt": len(lista),
          "arbetsgivare": [kompakt(x) for x in lista[: a.antal]]}
    if total > len(hits):
        ut["obs"] = f"läste {len(hits)} av {total} annonser; höj --max eller smalna av med --kommun"
    if a.kallor_forslag:
        ut["kallor_forslag"] = kallor_forslag(home, lista)
    return ut


def hitta_orgnr(bolag, home):
    _, hits = jc.traffar(jc.HISTORICAL, {"q": bolag, "historical-from": jc.ar_sedan(5)}, 100, home)
    n = collections.Counter()
    namn = {}
    nb = sc.norm(bolag)
    for h in hits:
        k, e = ag_nyckel(h)
        if k.startswith("namn:"):
            continue
        en = sc.norm(e.get("name"))
        if nb in en or en in nb:
            n[k] += 1
            namn[k] = e.get("name")
    if not n:
        return None, None
    k = n.most_common(1)[0][0]
    return k, namn[k]


def kor_likar(a, home):
    orgnr, namn = a.orgnr, a.bolag
    if not orgnr:
        orgnr, namn = hitta_orgnr(a.bolag, home)
        if not orgnr:
            raise SystemExit(f"Hittade inget organisationsnummer för '{a.bolag}' i annonserna. Ange --orgnr.")
    orgnr = orgnr.replace("-", "")
    fran = jc.ar_sedan(a.ar)
    tot, grupper = jc.stats(jc.HISTORICAL, {"employer": orgnr, "historical-from": fran}, "occupation-group", 10, home)
    if not grupper:
        raise SystemExit(f"{namn or orgnr} har inga annonser sedan {fran}. Prova större --ar.")
    s = sum(g["count"] for g in grupper)
    profil = {g["concept_id"]: g["count"] / s for g in grupper[:6]}
    rp = region_param(a, home)
    traff = collections.defaultdict(dict)   # arbetsgivare -> grupp -> antal
    agg = {}
    for gid in profil:
        _, hits = jc.traffar(jc.HISTORICAL, dict(rp, **{"occupation-group": gid, "historical-from": fran}),
                             a.max_per_grupp, home)
        for h in hits:
            k, _ = ag_nyckel(h)
            if k == orgnr:
                continue
            traff[k][gid] = traff[k].get(gid, 0) + 1
        aggregera(hits, "historik", agg)
    rad = []
    for k, g in traff.items():
        # bredd (hur stor del av X:s profil de täcker) * volym (log)
        tack = sum(profil[x] for x in g)
        vol = sum(g.values())
        rad.append((round(tack * math.log1p(vol) / math.log1p(50), 3), k))
    rad.sort(key=lambda x: -x[0])
    lista = [kompakt(agg[k], {"likhet": min(1.0, sc_), "gemensamma_grupper": len(traff[k])}) for sc_, k in rad[: a.antal]]
    gnamn = {g["concept_id"]: g["term"] for g in grupper}
    ut = {"bolag": namn, "orgnr": orgnr, "fran": fran, "region": a.region,
          "profil": [{"yrkesgrupp": gnamn[g], "id": g, "andel": round(v, 2)} for g, v in profil.items()],
          "likar": lista,
          "tolkning": "likhet 0–1: täckning av bolagets yrkesprofil gånger annonsvolym. Höga värden = "
                      "anställer samma sorts folk. Bransch och värderingar bedöms separat (webbsök)."}
    if a.kallor_forslag:
        ut["kallor_forslag"] = kallor_forslag(home, lista)
    return ut


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lage", required=True)
    r = sub.add_parser("region", help="arbetsgivare som annonserat rollerna i regionen")
    r.add_argument("--roll", action="append", default=[])
    r.add_argument("--yrkesgrupp", action="append", default=[], help="SSYK-4-id (occupation-group)")
    r.add_argument("--region")
    r.add_argument("--kommun")
    r.add_argument("--ar", type=float, default=3)
    r.add_argument("--max", type=int, default=1000, help="max annonser att läsa (standard 1000)")
    r.add_argument("--antal", type=int, default=30)
    l = sub.add_parser("likar", help="arbetsgivare som annonserar samma yrkesgrupper som X")
    l.add_argument("--bolag")
    l.add_argument("--orgnr")
    l.add_argument("--region")
    l.add_argument("--kommun")
    l.add_argument("--ar", type=float, default=3)
    l.add_argument("--max-per-grupp", type=int, default=300)
    l.add_argument("--antal", type=int, default=20)
    sc.add_home_arg(ap)
    for p in (r, l):
        p.add_argument("--kallor-forslag", action="store_true")
        p.add_argument("--home", default=argparse.SUPPRESS, help="datarot (kan också anges före läget)")
    a = ap.parse_args(argv)
    home = sc.hem(a.home)
    if a.lage == "likar" and not (a.bolag or a.orgnr):
        ap.error("ange --bolag eller --orgnr")
    jc.skriv(kor_region(a, home) if a.lage == "region" else kor_likar(a, home))


if __name__ == "__main__":
    main()
