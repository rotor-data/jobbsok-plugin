#!/usr/bin/env python3
"""Vilka titlar och närliggande yrken finns för det hon vill göra? (skillen jobbjakt)

  python3 jakt_titlar.py --roll kommunikatör [--roll "content lead"] [--kompetens copywriting]
                         [--region "Uppsala län"] [--ar 3] [--max 400] [--antal 25] [--home DIR]

Källor (JobTech, öppet, ingen nyckel):
  1. Historical ads + JobSearch: rubrikerna i annonser filade under yrket (vad arbetsgivare
     faktiskt kallar jobbet), rangordnade efter frekvens.
  2. Historical stats: vilka yrkesbenämningar annonser som nämner rollen/kompetensen hamnar under.
  3. Taxonomin (GraphQL): relaterade jobbtitlar (related), utbytbara yrken (substitutes) och
     syskon i samma yrkesgrupp (SSYK-4).

Utdata: JSON {"titlar": [...], "yrken": [...], "sokord_forslag": [...]} med frekvens och källa.
Nätfel: exit 3 och ett tydligt meddelande (använd då webbsök i stället).
"""
import argparse
import collections

import jakt_common as jc
import sok_common as sc


def yrken_for_roll(roll, home):
    yid, lab = jc.los_upp(roll, "occupation-name", home)
    return yid, lab


def taxonomi_grannar(yid, home):
    q = ('{concepts(id:"%s"){id preferred_label related{id type preferred_label} '
         'substitutes{id type preferred_label} '
         'broader(type:"ssyk-level-4"){id preferred_label narrower(type:"occupation-name"){id preferred_label}}}}' % yid)
    d = jc.graphql(q, home).get("concepts") or []
    if not d:
        return [], [], []
    c = d[0]
    jobbtitlar = [x["preferred_label"] for x in c.get("related", []) if x.get("type") == "job-title"]
    utbytbara = [(x["id"], x["preferred_label"]) for x in c.get("substitutes", []) if x.get("type") == "occupation-name"]
    syskon = []
    for g in c.get("broader", []):
        syskon += [(x["id"], x["preferred_label"], g["preferred_label"]) for x in g.get("narrower", []) if x["id"] != yid]
    return jobbtitlar, utbytbara, syskon


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roll", action="append", default=[], help="roll/titel (fri text eller yrkes-id), flera tillåtna")
    ap.add_argument("--kompetens", action="append", default=[], help="kompetens i fri text, flera tillåtna")
    ap.add_argument("--region", help="län, t.ex. 'Uppsala län' (begränsar rubrikstatistiken)")
    ap.add_argument("--ar", type=float, default=3, help="hur många år bakåt i Historical (standard 3)")
    ap.add_argument("--max", type=int, default=400, help="max annonser att läsa rubriker ur per roll")
    ap.add_argument("--antal", type=int, default=25, help="max rader per lista")
    sc.add_home_arg(ap)
    a = ap.parse_args(argv)
    if not a.roll and not a.kompetens:
        ap.error("ange minst en --roll eller --kompetens")
    home = sc.hem(a.home)
    region_id = jc.los_upp(a.region, "region", home)[0] if a.region else None
    bas = {"historical-from": jc.ar_sedan(a.ar)}
    if region_id:
        bas["region"] = region_id

    titlar = collections.Counter()
    titel_kalla = collections.defaultdict(set)
    titel_ag = collections.defaultdict(set)
    yrken = {}   # id -> post
    tax_titlar = collections.OrderedDict()
    egna = set()
    los = []

    def yrke(yid, namn, antal=0, relation=""):
        p = yrken.setdefault(yid, {"id": yid, "namn": namn, "annonser": 0, "relation": []})
        p["annonser"] = max(p["annonser"], antal)
        if relation and relation not in p["relation"]:
            p["relation"].append(relation)

    for roll in a.roll:
        yid, lab = yrken_for_roll(roll, home)
        los.append({"roll": roll, "yrke_id": yid, "yrke": lab})
        if yid:
            egna.add(yid)
            yrke(yid, lab, relation="eget")
            # 1. rubriker i annonser under yrket (historik + nu)
            for url, kalla, mx in ((jc.HISTORICAL, "historik", a.max), (jc.JOBSEARCH, "nu", 200)):
                p = dict(bas, **{"occupation-name": yid}) if url == jc.HISTORICAL else \
                    ({"occupation-name": yid, "region": region_id} if region_id else {"occupation-name": yid})
                _, hits = jc.traffar(url, p, mx, home)
                for h in hits:
                    t = jc.rubrik_till_titel(h.get("headline"))
                    if t:
                        titlar[t] += 1
                        titel_kalla[t].add(kalla)
                        ag = (h.get("employer") or {})
                        titel_ag[t].add(ag.get("organization_number") or sc.norm(ag.get("name")))
            # 3. taxonomins grannar
            jt, utb, sys_ = taxonomi_grannar(yid, home)
            for t in jt:
                tax_titlar.setdefault(sc.norm(t), t)
            for i, n in utb:
                yrke(i, n, relation="utbytbart (taxonomi)")
            for i, n, g in sys_:
                yrke(i, n, relation=f"samma yrkesgrupp: {g}")
        # 2. yrken som annonser som nämner rollen hamnar under
        tot, vals = jc.stats(jc.HISTORICAL, dict(bas, q=roll), "occupation-name", 30, home)
        for v in vals:
            yrke(v["concept_id"], v["term"], v["count"], f"annonser som nämner '{roll}'")
        # 1b. rubriker i annonser som nämner rollen men är filade under andra yrken
        for v in [v for v in vals if v["concept_id"] not in egna][:4]:
            _, hits = jc.traffar(jc.HISTORICAL, dict(bas, q=roll, **{"occupation-name": v["concept_id"]}), 60, home)
            for h in hits:
                t = jc.rubrik_till_titel(h.get("headline"))
                if t:
                    titlar[t] += 1
                    titel_kalla[t].add("nämner rollen")
                    ag = (h.get("employer") or {})
                    titel_ag[t].add(ag.get("organization_number") or sc.norm(ag.get("name")))

    for k in a.kompetens:
        tot, vals = jc.stats(jc.HISTORICAL, dict(bas, q=k), "occupation-name", 30, home)
        for v in vals:
            yrke(v["concept_id"], v["term"], v["count"], f"annonser som nämner '{k}'")

    # annonsvolym för yrken som saknar siffra (bara de som visas)
    kand = sorted(yrken.values(), key=lambda y: (-len(y["relation"]), -y["annonser"]))[: a.antal * 2]
    for y in kand:
        if not y["annonser"]:
            y["annonser"] = jc.stats(jc.HISTORICAL, dict(bas, **{"occupation-name": y["id"]}),
                                     "occupation-name", 1, home)[0]

    def yrkespoang(y):
        return (0 if "eget" in y["relation"] else 1, -(len(y["relation"]) * 2 + min(y["annonser"], 2000) / 400))

    yrkeslista = sorted([y for y in yrken.values() if y["annonser"] or "eget" in y["relation"]], key=yrkespoang)
    titellista = []
    for t, n in sorted(titlar.items(), key=lambda x: (-len(titel_ag[x[0]]), -x[1])):
        titellista.append({"titel": t, "arbetsgivare": len(titel_ag[t]), "annonser": n,
                           "kalla": sorted(titel_kalla[t]),
                           "i_taxonomin": sc.norm(t) in tax_titlar})
    for nt, t in tax_titlar.items():
        if nt not in titlar:
            titellista.append({"titel": t.lower(), "arbetsgivare": 0, "annonser": 0, "kalla": ["taxonomi"], "i_taxonomin": True})
    titellista = titellista[: a.antal]
    egna_ord = {sc.norm(r) for r in a.roll}
    for r in list(egna_ord):
        egna_ord |= {f"{x} {r}" for x in ("erfaren", "junior", "senior", "ny", "extra", "vikarierande")}
    forslag = [t["titel"] for t in titellista if t["arbetsgivare"] >= 2 and sc.norm(t["titel"]) not in egna_ord][:10]
    jc.skriv({
        "uppslag": los, "region": a.region, "fran": bas["historical-from"],
        "titlar": titellista,
        "yrken": [dict(y, relation="; ".join(y["relation"])) for y in yrkeslista[: a.antal]],
        "sokord_forslag": forslag,
        "tolkning": "titlar = rubriker arbetsgivare faktiskt använt (antal olika arbetsgivare/annonser); yrken = närliggande "
                    "yrkesbenämningar med annonsvolym i perioden. Föreslå hypoteser av typ "
                    "alternativ_titel och narliggande_yrke ur de översta raderna.",
    })


if __name__ == "__main__":
    main()
