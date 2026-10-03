#!/usr/bin/env python3
"""Rollkort: en belagd bild av en tänkbar riktning (skillen karriarcoach, fas 5).

  python3 rollkort.py bygg --roll "kommunikatör" [--region "Uppsala län"] [--ar 3] [--max 300] [--fraskt]
  python3 rollkort.py bygg --stanna                 # "stanna/forma om nuvarande jobb" ur coach.json
  python3 rollkort.py glapp <slug>                  # krav mot fakta.json: har/saknas/osäkert
  python3 rollkort.py citat <slug> --typ passar|skav --text "..." --citat "hennes ord" --fas identity --falt values_top5[0].value
  python3 rollkort.py satt <slug> --falt vanlig_tisdag|uppgift --text "..." [--uppgift 0 --uppgift 2]
  python3 rollkort.py kontrollera <slug>|--alla     # flaggar fält utan källa (exit 1 om något saknas)
  python3 rollkort.py jamfor [--md]                 # matris över alla rollkort, vikter ur preferenser.json
  python3 rollkort.py visa <slug> | lista
  Gemensamt: --home DIR

Varje fält i kortet är {"varde": ..., "kallor": [...]}. En källa är en URL/annons-id med frågans
parametrar och datum, ett SCB-uttag, eller hennes egna ord (fas + fält i coach.json, eller
det-har-vet-vi.md). Det som saknar källa ska strykas: kör `kontrollera` innan kortet visas.

Fälten kultur, ledarskap och arbetsidentitet är tomma krokar (status "vantar") tills
docs/research/kultur-ledarskap-evidens.md finns och coachen fyller dem med källa.

Utdata: sok/rollkort/<slug>.json. Anrop cachas i cache/rollkort/ (7 dagar, --fraskt hoppar över).
Nätfel mot JobTech: exit 3 (använd webbsök i stället). SCB-fel: lönen blir en TODO, kortet byggs ändå.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time

import jakt_common as jc
import sok_common as sc

CACHE_DAGAR = 7
SCB_TABELL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/AM/AM0110/AM0110A/LonYrkeRegion4AN"
SCB_MATT = {"000007AS": "manadslon_medel", "000007AU": "ki95", "000007AP": "antal_anstallda"}
# län -> riksområde (NUTS2) i SCB:s tabell
NUTS2 = {**{k: ("SE11", "Stockholm") for k in ["stockholms"]},
         **{k: ("SE12", "Östra Mellansverige") for k in ["uppsala", "södermanlands", "östergötlands", "örebro", "västmanlands"]},
         **{k: ("SE21", "Småland med öarna") for k in ["jönköpings", "kronobergs", "kalmar", "gotlands"]},
         **{k: ("SE22", "Sydsverige") for k in ["blekinge", "skåne"]},
         **{k: ("SE23", "Västsverige") for k in ["hallands", "västra götalands"]},
         **{k: ("SE31", "Norra Mellansverige") for k in ["värmlands", "dalarnas", "gävleborgs"]},
         **{k: ("SE32", "Mellersta Norrland") for k in ["västernorrlands", "jämtlands"]},
         **{k: ("SE33", "Övre Norrland") for k in ["västerbottens", "norrbottens"]}}
# Krokar som fylls efter docs/research/kultur-ledarskap-evidens.md (§7, "Rollkort (tillägg)")
KROK_FORVANTAT = {
    "kultur": {"typiska_kulturer": ["s3", "s9"], "instrument": "kultur-qsort-18-v1",
               "fit_mot_ideal": {"overlapp_topp": 0, "konflikt": []}},
    "ledarskap": {"ledarskapsroll": "ingen|sak|personal", "chef_behov_matchar": []},
    "arbetsidentitet": {"identitet_matchar": {"roller": [], "styrkor": [], "kommentar": ""}},
}
RESEARCH = "docs/research/kultur-ledarskap-evidens.md"
SCB_SEKTOR = {"0": "alla", "1-3": "offentlig", "4-5": "privat"}
TOMMA_KROKAR = ("kultur", "ledarskap", "arbetsidentitet")
STANDARD_VIKTER = {"varden": 3, "arbetsdag": 3, "harda_granser": 2, "glapp": 1, "marknad": 1,
                   "kultur": 1, "ledarskap": 1}
DIM_NAMN = {"varden": "Värden", "arbetsdag": "Arbetsdag och energi", "harda_granser": "Hårda gränser",
            "glapp": "Hårda krav och önskelista", "marknad": "Marknadsvolym", "kultur": "Kultur", "ledarskap": "Ledarskap"}
_FRASKT = False


# ---------------------------------------------------------------- hjälp

def slugga(s):
    s = sc.norm(s).replace(" ", "-")
    return re.sub(r"[^a-z0-9åäöéü-]", "", s)[:60] or "roll"


def falt(varde=None, kallor=None, **extra):
    d = {"varde": varde, "kallor": kallor or []}
    d.update(extra)
    return d


def krok(namn):
    """Tom krok: fylls av coachen med källa (forskning, annons, arbetsgivarkort eller hennes ord)."""
    return falt(None, [], status="vantar", forvantat=KROK_FORVANTAT[namn], research=RESEARCH)


def kort_sokv(home, slug):
    return sc.sokv(home, "rollkort", slug + ".json")


def las_kort(home, slug):
    k = sc.las_json(kort_sokv(home, slug))
    if not k:
        raise SystemExit(f"Hittar inget rollkort '{slug}'. Kör: rollkort.py lista")
    return k


def alla_kort(home):
    d = sc.sokv(home, "rollkort")
    if not os.path.isdir(d):
        return []
    ut = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and not f.startswith("_"):
            k = sc.las_json(os.path.join(d, f))
            if isinstance(k, dict) and k.get("slug"):
                ut.append(k)
    return ut


def capi(url, params=None, home=None):
    """jc.api med filcache (cache/rollkort/<sha>.json). Nätfel -> exit 3 via jc.api."""
    nyckel = url + "?" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    f = sc.cachev(home, "rollkort", hashlib.sha1(nyckel.encode()).hexdigest() + ".json") if home else None
    if f and not _FRASKT:
        c = sc.las_json(f)
        if c and time.time() - c.get("t", 0) < CACHE_DAGAR * 86400:
            return c["data"]
    data = jc.api(url, params, home)
    if f:
        sc.skriv_json(f, {"t": time.time(), "url": url, "params": params, "data": data})
    return data


def fraga_url(url, params):
    import urllib.parse
    return url + "?" + urllib.parse.urlencode(params or {}, doseq=True)


def kalla_jobtech(url, params, annons_id=None):
    k = {"typ": "jobtech_historical" if "historical" in url else "jobtech_search" if "jobsearch" in url else "taxonomi",
         "url": fraga_url(url, params), "parametrar": params, "datum": sc.idag()}
    if annons_id:
        k["annons_id"] = list(annons_id)[:50]
    return k


def bladdra(url, params, max_antal, home):
    ut, total, offset = [], 0, 0
    while offset < min(max_antal, 2000):
        d = capi(url, dict(params, limit=min(100, max_antal - offset), offset=offset), home) or {}
        total = d.get("total", {}).get("value", 0)
        h = d.get("hits", [])
        ut.extend(h)
        if len(h) < 100:
            break
        offset += 100
    return total, ut


def total(url, params, home):
    d = capi(url, dict(params, limit=0), home) or {}
    return d.get("total", {}).get("value", 0)


# ---------------------------------------------------------------- textutvinning

RUBRIK_UPPG = re.compile(r"(arbetsuppgift|du kommer att|dina uppgifter|ditt uppdrag|i rollen|om rollen|om tjänsten|"
                         r"ansvarsområde|vad du kommer|uppdraget|i tjänsten ingår|tjänsten innebär|vad du ska göra|"
                         r"what you will do|responsibilities|the role)", re.I)
RUBRIK_KRAV = re.compile(r"(kvalifikation|om dig|din profil|vi söker dig som|vi söker dig|krav|meriterande|"
                         r"du har|du är|för att lyckas|vem är du|requirements|qualifications|about you)", re.I)
RUBRIK_ANNAT = re.compile(r"(vi erbjuder|om oss|om arbetsplatsen|ansökan|övrigt|anställningsform|tillträde|"
                          r"kontakt|välkommen med|om företaget|we offer|lön|förmåner|placering)", re.I)
MENING_UPPG = re.compile(r"\b(du kommer att|i rollen ingår|i tjänsten ingår|du ansvarar för|ansvarar du för|"
                         r"arbetet innebär|uppdraget innebär|du arbetar med|du kommer (bland annat )?(arbeta|jobba))\b", re.I)
MENING_KRAV = re.compile(r"\b(du har|vi söker dig som|krav|erfarenhet av|utbildning inom|meriterande|"
                         r"vi ser gärna|du behöver)\b", re.I)
MERIT = re.compile(r"meriter|gärna|fördel|plus|önskvärt|bonus", re.I)

STOPP = set("""och att i på för med som av till en ett det den de du vi är har kan ska om eller inom samt
detta dessa din ditt dina vår vårt våra man sig så också även mer mycket bland annat andra olika hela
genom från vid under över efter hos när där här vara bli blir får finns kommer kommer arbeta arbetar
arbete arbetet jobba jobbar tjänsten rollen roll uppdraget uppdrag tillsammans ingår innebär ansvarar
ansvar ansvaret dig oss vill både bra god goda gott stor stort stora nya nytt ny egen eget egna sätt
gäller viktigt viktig även utifrån exempelvis t.ex bl.a etc del delar the and to of in for with you
our will a an is are be as on at by this that your we kunna något några kring mellan mot utan alla allt
alltid därför dessutom vilket vilka kommer vill även ha hade såsom samtliga liksom ser önskar söker
sökes behöver men hög höga övrigt meriterande meriterar önskvärt önskvärd krav kravet gärna fördel
person personen tycker roligt dag dagar samt varje""".split())
GENERISKT_KRAV = {"erfarenhet", "erfarenheter", "kunskaper", "kunskap", "förmåga", "mycket", "goda", "god", "relevant",
                  "motsvarande", "arbetsgivaren", "bedömer", "likvärdig", "minst", "flera", "års", "år", "vikt",
                  "egenskaper", "personliga", "lämplighet", "läggas", "stor", "tal", "skrift", "uttrycka", "såväl"}
BRUS = re.compile(r"ansökan|ansök|välkommen|rekryteringssystem|tillträde|lön enligt|provanställning|"
                  r"urval sker|intervjuer|referenser|registerutdrag|säkerhetsprövning|kontakta", re.I)


def rader(text):
    """Text -> lista med (rad, ar_rubrik). Punktlistor och korta rader räknas som egna rader."""
    ut = []
    for r in re.split(r"\n+", text or ""):
        r = r.strip()
        if not r:
            continue
        r2 = re.sub(r"^[\-–•*·●▪>]+\s*|^\d+[.)]\s+", "", r).strip()
        rubrik = len(r2) <= 60 and not r2.endswith(".") and (r2.endswith(":") or len(r2.split()) <= 6)
        ut.append((r2, rubrik))
    return ut


def meningar(s):
    return [m.strip() for m in re.split(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ])", s) if m.strip()]


def stycken(text):
    """Dela annonstexten i (avsnitt, mening): avsnitt = uppg|krav|annat|okand."""
    ut, avsnitt = [], "okand"
    for r, rubrik in rader(text):
        if rubrik:
            if RUBRIK_UPPG.search(r):
                avsnitt = "uppg"
                continue
            if RUBRIK_KRAV.search(r):
                avsnitt = "krav"
                continue
            if RUBRIK_ANNAT.search(r):
                avsnitt = "annat"
                continue
        for m in meningar(r):
            ut.append((avsnitt, m))
    return ut


def ord_i(m, bort=()):
    w = re.findall(r"[a-zåäöéü][a-zåäöéü\-]{2,}", m.lower())
    return [x for x in w if x not in STOPP and x not in bort and not x.isdigit()]


def stam(w):
    for suf in ("erna", "arna", "orna", "ande", "ende", "else", "ning", "ar", "er", "or", "en", "et", "na", "a", "s"):
        if len(w) > len(suf) + 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def utvinn(hits, typ, bort_ord, n_teman=8):
    if typ == "krav":
        bort_ord = set(bort_ord) | GENERISKT_KRAV
    return _utvinn(hits, typ, bort_ord, n_teman)


def _utvinn(hits, typ, bort_ord, n_teman):
    """Kluster av meningar (typ 'uppg' eller 'krav') på nyckelord. Deterministiskt.

    Returnerar [{tema, nyckelord, andel_annonser, annonser, exempel:[{text, annons_id}], merit_andel}].
    """
    per_annons = {}
    for h in hits:
        aid = str(h.get("id"))
        txt = (h.get("description") or {}).get("text") or ""
        valda = []
        for avsn, m in stycken(txt):
            if len(m) < 25 or len(m) > 400 or BRUS.search(m):
                continue
            if typ == "uppg" and (avsn == "uppg" or (avsn == "okand" and MENING_UPPG.search(m))):
                valda.append(m)
            elif typ == "krav" and (avsn == "krav" or (avsn != "uppg" and MENING_KRAV.search(m))):
                valda.append(m)
        if valda:
            per_annons[aid] = valda
    if not per_annons:
        return [], 0
    bort = {stam(w) for w in bort_ord}
    df = collections.Counter()
    menings_ord = []
    for aid, ms in per_annons.items():
        sedda = set()
        for m in ms:
            st = {stam(w) for w in ord_i(m)} - bort
            menings_ord.append((aid, m, st))
            sedda |= st
        df.update(sedda)
    n = len(per_annons)
    # ytform att visa per stam: vanligaste ordet
    yta = collections.defaultdict(collections.Counter)
    for _, m, _ in menings_ord:
        for w in ord_i(m):
            yta[stam(w)][w] += 1
    kandidater = [w for w, c in df.most_common(60) if c >= max(2, n * 0.04)]
    tagna, teman = set(), []
    for w in kandidater:
        grupp = [(aid, m, st) for aid, m, st in menings_ord if w in st and (aid, m) not in tagna]
        aids = {aid for aid, _, _ in grupp}
        if len(aids) < max(2, n * 0.04):
            continue
        sam = collections.Counter()
        for _, _, st in grupp:
            sam.update(st - {w})
        nyck = [w] + [x for x, c in sam.most_common(6) if c >= 2 and df[x] < n * 0.9][:3]
        exempel, sedda = [], set()
        for aid, m, st in sorted(grupp, key=lambda g: (-len(g[2] & set(nyck)), abs(len(g[1]) - 110))):
            if aid in sedda or sc.norm(m)[:80] in sedda:
                continue
            sedda |= {aid, sc.norm(m)[:80]}
            exempel.append({"text": sc.utdrag(m, 200), "annons_id": aid})
            if len(exempel) == 3:
                break
        tagna |= {(aid, m) for aid, m, _ in grupp}
        teman.append({"tema": " · ".join(yta[x].most_common(1)[0][0] for x in nyck[:3]),
                      "nyckelord": [yta[x].most_common(1)[0][0] for x in nyck],
                      "andel_annonser": round(len(aids) / n, 2), "annonser": len(aids),
                      "merit_andel": round(sum(1 for _, m, _ in grupp if MERIT.search(m)) / len(grupp), 2),
                      "exempel": exempel, "annons_id": sorted(aids)[:30]})
        if len(teman) >= n_teman:
            break
    teman.sort(key=lambda t: -t["andel_annonser"])
    return teman, n


def kompetensrakning(hits, nyckel):
    """must_have/nice_to_have -> [{namn, id, typ, andel, annonser}] (andel av annonserna)."""
    c, namn, typ, aids = collections.Counter(), {}, {}, collections.defaultdict(set)
    for h in hits:
        sedda = set()
        for t in ("skills", "work_experiences", "education", "education_level", "languages"):
            for x in ((h.get(nyckel) or {}).get(t) or []):
                k = x.get("concept_id") or sc.norm(x.get("label"))
                if not k or k in sedda:
                    continue
                sedda.add(k)
                c[k] += 1
                namn[k] = x.get("label")
                typ[k] = t
                aids[k].add(str(h.get("id")))
    n = max(1, len(hits))
    return [{"namn": namn[k], "id": k if jc.ar_id(k) else None, "typ": typ[k], "andel": round(v / n, 2),
             "annonser": v, "annons_id": sorted(aids[k])[:20]} for k, v in c.most_common(15)]


# ---------------------------------------------------------------- lön (SCB)

def scb_lon(ssyk, home, region_namn=None):
    """Genomsnittlig månadslön per SSYK-4 ur SCB:s lönestrukturstatistik (AM0110A/LonYrkeRegion4AN).

    Riket ("SE", inte "RIKET") och, om regionen är känd, riksområdet (NUTS2). Bara medelvärden:
    tabellen har inga percentiler. Cachas per SSYK, region och år. Fel -> (None, None, TODO), aldrig exit.
    """
    if not ssyk:
        return None, None, "TODO: SSYK-kod saknas för yrket; lönen kan inte hämtas ur SCB."
    omr = NUTS2.get(sc.norm(region_namn or "").replace(" lan", "").replace(" län", ""))
    regioner = ["SE"] + ([omr[0]] if omr else [])
    fraga = {"query": [{"code": "Region", "selection": {"filter": "item", "values": regioner}},
                       {"code": "Sektor", "selection": {"filter": "item", "values": list(SCB_SEKTOR)}},
                       {"code": "Yrke2012", "selection": {"filter": "item", "values": [ssyk]}},
                       {"code": "Kon", "selection": {"filter": "item", "values": ["1+2"]}},
                       {"code": "ContentsCode", "selection": {"filter": "item", "values": list(SCB_MATT)}},
                       {"code": "Tid", "selection": {"filter": "top", "values": ["1"]}}],
             "response": {"format": "json"}}
    f = sc.cachev(home, "rollkort", f"scb-{ssyk}-{'-'.join(regioner)}.json")
    c = None if _FRASKT else sc.las_json(f)
    if c and time.time() - c.get("t", 0) < 30 * 86400:
        d = c["data"]
    else:
        try:
            _, d, _ = sc.http_json(SCB_TABELL, method="POST", data=fraga, home=home)
        except (sc.NatFel, sc.HttpFel, ValueError) as e:
            return None, None, (f"TODO: SCB svarade inte ({e}). Hämta lönen för SSYK {ssyk} manuellt i "
                                "statistikdatabasen (AM0110A/LonYrkeRegion4AN, Region SE) och fyll i fältet lon.")
    per, ar = {}, None
    koder = [c["code"] for c in (d or {}).get("columns", []) if c.get("type") == "c"] or list(SCB_MATT)
    for rad in (d or {}).get("data", []):
        reg, sektor, _yrke, _kon, ar = rad["key"]
        vals = {}
        for kod, v in zip(koder, rad["values"]):
            try:
                vals[SCB_MATT[kod]] = int(float(v))
            except (TypeError, ValueError):
                vals[SCB_MATT[kod]] = None
        namn = "riket" if reg == "SE" else (omr[1] if omr else reg)
        per.setdefault(namn, {})[SCB_SEKTOR.get(sektor, sektor)] = vals
    if not any((v.get("alla") or {}).get("manadslon_medel") for v in per.values()):
        return None, None, f"TODO: SCB har ingen (eller för osäker) lönedata för SSYK {ssyk}."
    sc.skriv_json(f, {"t": time.time(), "data": d})
    kalla = {"typ": "scb", "url": SCB_TABELL, "parametrar": {"ssyk": ssyk, "ar": ar, "region": regioner, "kon": "1+2",
             "sektor": list(SCB_SEKTOR), "tabell": "AM0110A/LonYrkeRegion4AN"}, "datum": sc.idag()}
    return {"ar": ar, "ssyk": ssyk, "matt": "genomsnittlig månadslön (kr), inga percentiler", "per_region": per}, kalla, None


# ---------------------------------------------------------------- bygg

def yrke_info(yid, home):
    q = '{concepts(id:"%s"){id preferred_label broader(type:"ssyk-level-4"){id preferred_label ssyk_code_2012}}}' % yid
    d = (capi(jc.TAXONOMY + "/graphql", {"query": q}, home) or {}).get("data") or {}
    c = (d.get("concepts") or [{}])[0]
    g = (c.get("broader") or [{}])[0]
    return {"yrke": c.get("preferred_label"), "yrkesgrupp_id": g.get("id"), "yrkesgrupp": g.get("preferred_label"),
            "ssyk": g.get("ssyk_code_2012")}


def los_upp(term, typ, home):
    if jc.ar_id(term):
        return term, term
    d = capi(jc.TAXONOMY + "/suggesters/autocomplete", {"query-string": term, "type": typ}, home) or []
    kand = [(x["taxonomy/id"], x["taxonomy/preferred-label"], x.get("taxonomy/alternative-labels", [])) for x in d]
    b = jc.basta_traff(term, kand)
    return (b[0], b[1]) if b else (None, term)


def volym(yid, region_id, ar, home):
    idag = dt.date.today()
    per_ar, kallor = [], []
    for y in range(idag.year - int(ar), idag.year + 1):
        p = {"occupation-name": yid, "historical-from": f"{y}-01-01T00:00:00", "historical-to": f"{y}-12-31T23:59:59"}
        if region_id:
            p["region"] = region_id
        n = total(jc.HISTORICAL, p, home)
        per_ar.append({"ar": y, "annonser": n, "hela_aret": y < idag.year})
        kallor.append(kalla_jobtech(jc.HISTORICAL, p))
    hela = [x for x in per_ar if x["hela_aret"]]
    trend, proc = "okänd", None
    if len(hela) >= 2 and hela[0]["annonser"] >= 10:
        proc = round(100 * (hela[-1]["annonser"] - hela[0]["annonser"]) / hela[0]["annonser"])
        trend = "ökar" if proc >= 15 else "minskar" if proc <= -15 else "stabil"
    elif hela and sum(x["annonser"] for x in hela) < 20:
        trend = "för litet underlag"
    elif len(hela) >= 2:
        trend = "osäker (yrkeskoden ny eller sällan använd tidigare år)"
    pn = {"occupation-name": yid}
    if region_id:
        pn["region"] = region_id
    nu = total(jc.JOBSEARCH, pn, home)
    kallor.append(kalla_jobtech(jc.JOBSEARCH, pn))
    senaste = hela[-1]["annonser"] if hela else 0
    return falt({"per_ar": per_ar, "trend": trend, "trend_procent": proc, "senaste_hela_ar": senaste,
                 "oppna_nu": nu}, kallor)


def bygg(a, home):
    yid, lab = los_upp(a.roll, "occupation-name", home)
    if not yid:
        raise SystemExit(f"Hittade inget yrke för '{a.roll}'. Prova en annan benämning eller ett yrkes-id.")
    info = yrke_info(yid, home)
    region_id, region_namn = (los_upp(a.region, "region", home) if a.region else (None, None))
    fran = jc.ar_sedan(a.ar)
    ph = {"occupation-name": yid, "historical-from": fran}
    if region_id:
        ph["region"] = region_id
    total_h, hits = bladdra(jc.HISTORICAL, ph, a.max, home)
    pn = {"occupation-name": yid}
    if region_id:
        pn["region"] = region_id
    total_nu, nu = bladdra(jc.JOBSEARCH, pn, 100, home)
    k_hist = kalla_jobtech(jc.HISTORICAL, ph)
    k_nu = kalla_jobtech(jc.JOBSEARCH, pn)
    alla = hits + nu
    titelord = set(ord_i(a.roll)) | set(ord_i(info.get("yrke") or lab or "")) | set(ord_i(region_namn or ""))

    # titlar
    tc, tag = collections.Counter(), collections.defaultdict(set)
    for h in alla:
        t = jc.rubrik_till_titel(h.get("headline"))
        if t:
            tc[t] += 1
            tag[t].add((h.get("employer") or {}).get("organization_number") or sc.norm((h.get("employer") or {}).get("name")))
    titlar = [{"titel": t, "annonser": n, "arbetsgivare": len(tag[t])}
              for t, n in sorted(tc.items(), key=lambda x: (-len(tag[x[0]]), -x[1]))[:12]]

    # arbetsgivare
    ag = {}
    for h, kalla in [(h, "hist") for h in hits] + [(h, "nu") for h in nu]:
        e = h.get("employer") or {}
        k = (e.get("organization_number") or "").replace("-", "") or "namn:" + sc.norm(e.get("name"))
        p = ag.setdefault(k, {"namn": e.get("name"), "orgnr": e.get("organization_number"), "annonser": 0,
                              "oppna_nu": 0, "annons_id": []})
        p["oppna_nu" if kalla == "nu" else "annonser"] += 1
        if len(p["annons_id"]) < 5:
            p["annons_id"].append(str(h.get("id")))
    agl = sorted(ag.values(), key=lambda x: (-(x["annonser"] + 2 * x["oppna_nu"]), x["namn"] or ""))[:10]

    uppg, n_uppg = utvinn(alla, "uppg", titelord, 8)
    kravtext, n_krav = utvinn(alla, "krav", titelord, 8)
    for t in kravtext:
        t["typ"] = "meriterande" if t["merit_andel"] >= 0.5 else "ska"

    def annonsrad(h):
        e = h.get("employer") or {}
        return {"id": str(h.get("id")), "rubrik": h.get("headline"), "arbetsgivare": e.get("name"),
                "ort": (h.get("workplace_address") or {}).get("municipality"),
                "publicerad": (h.get("publication_date") or "")[:10],
                "sista_dag": (h.get("application_deadline") or "")[:10] or None,
                "url": h.get("webpage_url") or f"https://arbetsformedlingen.se/platsbanken/annonser/{h.get('id')}",
                "anstallningsform": (h.get("employment_type") or {}).get("label"),
                "omfattning": (h.get("working_hours_type") or {}).get("label")}
    aktuella = sorted(nu, key=lambda h: h.get("publication_date") or "", reverse=True)[:3]
    if len(aktuella) < 3:
        aktuella += sorted(hits, key=lambda h: h.get("publication_date") or "", reverse=True)[: 3 - len(aktuella)]

    lon, lon_kalla, lon_todo = scb_lon(info.get("ssyk"), home, region_namn)
    k_tax = {"typ": "taxonomi", "url": jc.TAXONOMY + "/graphql", "parametrar": {"yrke_id": yid}, "datum": sc.idag()}
    slug = a.slug or slugga(a.roll + (" " + region_namn.replace(" län", "") if region_namn else ""))
    gammalt = sc.las_json(kort_sokv(home, slug)) or {}
    kort = {
        "schema_version": 1, "slug": slug, "typ": "marknad", "titel": a.titel or a.roll.capitalize(),
        "skapad": gammalt.get("skapad") or sc.idag(), "uppdaterad": sc.idag(),
        "roll": {"fraga": a.roll, "yrke_id": yid, "yrke": info.get("yrke") or lab, "ssyk": info.get("ssyk"),
                 "yrkesgrupp_id": info.get("yrkesgrupp_id"), "yrkesgrupp": info.get("yrkesgrupp")},
        "region": {"namn": region_namn, "id": region_id},
        "underlag": {"fran": fran, "annonser_historik": total_h, "lasta_historik": len(hits),
                     "oppna_nu": total_nu, "lasta_nu": len(nu), "med_uppgiftstext": n_uppg, "med_kravtext": n_krav},
        "titlar": falt(titlar, [k_hist, k_nu]),
        "arbetsgivare": falt(agl, [k_hist, k_nu]),
        "volym": volym(yid, region_id, a.ar, home),
        "arbetsuppgifter": falt(uppg, [dict(k_hist, annons_id=sorted({i for t in uppg for i in t["annons_id"]})[:50])] if uppg else [],
                                metod="meningar under rubriker som 'arbetsuppgifter'/'du kommer att', klustrade på nyckelord"),
        "krav": falt({"must_have": kompetensrakning(alla, "must_have"), "nice_to_have": kompetensrakning(alla, "nice_to_have"),
                      "fritext": kravtext,
                      "korkort_andel": round(sum(1 for h in alla if h.get("driving_license_required")) / max(1, len(alla)), 2)},
                     [k_hist, k_nu]),
        "annonser": falt([annonsrad(h) for h in aktuella], [k_nu] + ([k_hist] if len(nu) < 3 else [])),
        "lon": falt(lon, [lon_kalla] if lon_kalla else [], **({"todo": lon_todo} if lon_todo else {})),
        "lon_fack": gammalt.get("lon_fack") or falt(None, [], status="vantar", forvantat={
            "kalla": "Saco|Unionen", "p25": None, "median": None, "p75": None, "manuellt_inklistrad": True}),
        "yrkesklassning": falt(dict(info, yrke_id=yid), [k_tax]),
    }
    # det coachen fyllt i behålls vid ombyggnad
    for f in ("passar_for_att", "skav", "vanlig_tisdag", "glapp") + TOMMA_KROKAR:
        kort[f] = gammalt.get(f) or (falt([], []) if f in ("passar_for_att", "skav") else
                                      krok(f) if f in TOMMA_KROKAR else falt(None, []))
    for i, t in enumerate(kort["arbetsuppgifter"]["varde"]):
        g = next((x for x in ((gammalt.get("arbetsuppgifter") or {}).get("varde") or []) if x.get("tema") == t["tema"]), None)
        if g and g.get("sammanfattning"):
            t["sammanfattning"] = g["sammanfattning"]
    sc.skriv_json(kort_sokv(home, slug), kort)
    return kort


def bygg_stanna(a, home):
    coach = sc.las_json(os.path.join(home, "profil", "coach.json")) or {}
    f = coach.get("faser") or {}
    intake, opt = f.get("intake") or {}, f.get("options") or {}
    cr = intake.get("current_role") or {}
    sv = intake.get("stay_vs_leave_balance") or {}
    craft = opt.get("crafting_option") or {}
    titel = "Stanna och forma om"

    def citat_lista(lista, fas, falt_):
        return [{"text": x, "citat": x, "fas": fas, "falt": f"{falt_}[{i}]"} for i, x in enumerate(lista or []) if x]

    passar = citat_lista(sv.get("stay_reasons"), "intake", "stay_vs_leave_balance.stay_reasons")
    skav = citat_lista(sv.get("leave_reasons"), "intake", "stay_vs_leave_balance.leave_reasons")
    andringar = []
    for typ in ("task", "relational", "cognitive"):
        andringar += citat_lista(craft.get(typ), "options", f"crafting_option.{typ}")
    ck = lambda fas, falt_: {"typ": "coach", "fas": fas, "falt": falt_, "fil": "profil/coach.json", "datum": sc.idag()}
    slug = "stanna"
    gammalt = sc.las_json(kort_sokv(home, slug)) or {}
    kort = {
        "schema_version": 1, "slug": slug, "typ": "stanna", "titel": titel,
        "skapad": gammalt.get("skapad") or sc.idag(), "uppdaterad": sc.idag(),
        "roll": {"fraga": cr.get("title") or "nuvarande jobb", "arbetsgivare": cr.get("org")},
        "region": {"namn": intake.get("hard_constraints", {}).get("location"), "id": None},
        "passar_for_att": falt(passar, [ck("intake", "stay_vs_leave_balance.stay_reasons")] if passar else []),
        "skav": falt(skav, [ck("intake", "stay_vs_leave_balance.leave_reasons")] if skav else []),
        "crafting": falt({"andringar": andringar, "genomforbarhet_0_10": craft.get("feasibility_0_10")},
                         [ck("options", "crafting_option")] if craft else []),
        "glapp": falt({"har": [], "saknas": [], "osakert": [], "kommentar": "hon har jobbet"},
                      [ck("intake", "current_role")] if cr else []),
        "vanlig_tisdag": gammalt.get("vanlig_tisdag") or falt(None, []),
    }
    for k in TOMMA_KROKAR:
        kort[k] = gammalt.get(k) or krok(k)
    sc.skriv_json(kort_sokv(home, slug), kort)
    return kort


# ---------------------------------------------------------------- glapp

def fakta_korpus(fakta):
    """[(text, källsökväg, taxonomi_id)] ur fakta.json."""
    def t(v):
        return " ".join(x for x in v.values() if isinstance(x, str)) if isinstance(v, dict) else (v or "")
    ut = []
    for i, k in enumerate(fakta.get("kompetenser") or []):
        ut.append((t(k.get("namn")) + " " + " ".join(k.get("taggar") or []), f"kompetenser[{k.get('id', i)}]", k.get("taxonomi_id")))
    for r in fakta.get("roller") or []:
        ut.append((t(r.get("titel")) + " " + t(r.get("beskrivning")), f"roller[{r.get('id')}]", None))
        for m in r.get("meriter") or []:
            ut.append((t(m.get("text")) + " " + " ".join(m.get("taggar") or []) + " " + (m.get("omfattning") or ""),
                       f"roller[{r.get('id')}].meriter[{m.get('id')}]", None))
    for u in fakta.get("utbildning") or []:
        ut.append((t(u.get("program")) + " " + (u.get("skola") or ""), f"utbildning[{u.get('id')}]", None))
    for k in fakta.get("kurser") or []:
        ut.append((t(k.get("namn")), f"kurser[{k.get('id')}]", None))
    if (fakta.get("person") or {}).get("korkort"):
        ut.append((f"körkort b-körkort {fakta['person']['korkort']}", "person.korkort", None))
    for s in fakta.get("sprak") or []:
        ut.append(((s.get("sprak") or "") + " " + (s.get("niva") or ""), "sprak", None))
    return ut


def _traff(w, st):
    return w in st or any((x.startswith(w) or w.startswith(x)) and min(len(x), len(w)) > 4 for x in st)


def matcha(namn, nyckelord, tid, korpus, typ=None):
    """-> (status, källor). har = id-träff, yrkeserfarenhet med samma titelord, eller (nästan) alla ord
    finns i faktabanken; osäkert = en del av orden; saknas = inget."""
    if tid:
        tr = [k for _, k, i in korpus if i == tid]
        if tr:
            return "har", tr
    ord_ = [stam(w) for w in (nyckelord or ord_i(namn))][:4]
    if not ord_:
        return "osakert", []
    poster = [(k, {stam(w) for w in ord_i(text)}) for text, k, _ in korpus]
    if typ == "work_experiences":
        tr = [k for k, st in poster if re.fullmatch(r"roller\[[^\]]+\]", k) and any(_traff(w, st) for w in ord_)]
        if tr:
            return "har", tr[:3]
    funna, kallor = set(), []
    for w in ord_:
        for k, st in poster:
            if _traff(w, st):
                funna.add(w)
                if k not in kallor and len(kallor) < 3:
                    kallor.append(k)
                break
    andel = len(funna) / len(ord_)
    if andel >= 0.99 or (len(ord_) >= 3 and andel >= 0.66):
        return "har", kallor
    if funna:
        return "osakert", kallor
    return "saknas", []


HART = re.compile(r"legitimation|legitimerad|behörighet|behörig|certifier|auktoris|körkort|säkerhetsprövning|"
                  r"säkerhetsklass|registerkontroll|svenskt medborgarskap|lärarexamen|socionomexamen", re.I)
SPRAKKRAV = re.compile(r"(flytande|mycket goda?|obehindrat|god förmåga).{0,40}(svenska|engelska)|"
                       r"(svenska|engelska).{0,30}(flytande|obehindrat|i tal och skrift)", re.I)


def ar_hart(namn, exempel=None, typ=None, nyckel=None):
    """Hårda krav: legitimation, lagstadgad behörighet/certifiering, körkort, säkerhetsprövning,
    centralt språkkrav. Allt annat är arbetsgivarens önskelista."""
    t = f"{namn} {exempel or ''}"
    if HART.search(t):
        return True
    if typ == "languages" and nyckel == "must_have":
        return True
    return bool(exempel and SPRAKKRAV.search(exempel))


def glapp(home, slug):
    kort = las_kort(home, slug)
    if kort.get("typ") == "stanna":
        return kort["glapp"]
    fakta = sc.las_json(os.path.join(home, "profil", "fakta.json")) or {}
    korpus = fakta_korpus(fakta)
    krav = (kort.get("krav") or {}).get("varde") or {}
    ut = {"har": [], "saknas": [], "osakert": []}
    for typ in ("must_have", "nice_to_have"):
        for k in krav.get(typ) or []:
            if k["andel"] < 0.1:
                continue
            s, kl = matcha(k["namn"], None, k.get("id"), korpus, k.get("typ"))
            ut[s].append({"krav": k["namn"], "typ": "ska" if typ == "must_have" else "meriterande", "andel": k["andel"],
                          "hart": ar_hart(k["namn"], None, k.get("typ"), typ) and typ == "must_have",
                          "fakta": kl, "annons_id": k.get("annons_id", [])[:5]})
    for t in krav.get("fritext") or []:
        s, kl = matcha(t["tema"], t["nyckelord"], None, korpus)
        ex = " ".join(e.get("text", "") for e in t.get("exempel") or [])
        ut[s].append({"krav": t["tema"], "typ": t.get("typ", "ska"), "andel": t["andel_annonser"], "fakta": kl,
                      "hart": t.get("typ") != "meriterande" and ar_hart(t["tema"], ex),
                      "exempel": (t.get("exempel") or [{}])[0].get("text"), "annons_id": t.get("annons_id", [])[:5]})
    kk = krav.get("korkort_andel") or 0
    if kk >= 0.3:
        har_kk = bool(((fakta.get("person") or {}).get("korkort")))
        ut["har" if har_kk else "saknas"].append({"krav": "Körkort", "typ": "ska", "andel": kk, "hart": True,
                                                  "fakta": ["person.korkort"] if har_kk else []})
    for v in ut.values():
        v.sort(key=lambda x: (not x.get("hart"), -x["andel"]))
    alla = [x for v in ut.values() for x in v]
    ut["sammanfattning"] = {
        "harda_krav": {"har": sum(1 for x in ut["har"] if x["hart"]), "saknas": [x["krav"] for x in ut["saknas"] if x["hart"]],
                       "osakert": [x["krav"] for x in ut["osakert"] if x["hart"]]},
        "onskelista": {"har": sum(1 for x in ut["har"] if not x["hart"]),
                       "av": sum(1 for x in alla if not x["hart"])},
        "tolkning": "Annonser är önskelistor. Bara saknade hårda krav (legitimation, behörighet, certifiering, körkort, "
                    "säkerhetsprövning, centralt språkkrav) stänger dörren; resten går ofta att söka ändå."}
    kallor = [{"typ": "fakta", "fil": "profil/fakta.json", "datum": sc.idag()}] + (kort.get("krav") or {}).get("kallor", [])[:1]
    kort["glapp"] = falt(ut, kallor)
    sc.skriv_json(kort_sokv(home, slug), kort)
    return kort["glapp"]


# ---------------------------------------------------------------- citat & ifyllnad

def hamta_vag(obj, vag):
    for del_ in re.findall(r"[^.\[\]]+|\[\d+\]", vag or ""):
        if del_.startswith("["):
            i = int(del_[1:-1])
            obj = obj[i] if isinstance(obj, list) and i < len(obj) else None
        else:
            obj = obj.get(del_) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


def platt(v):
    if isinstance(v, dict):
        return " ".join(platt(x) for x in v.values())
    if isinstance(v, list):
        return " ".join(platt(x) for x in v)
    return str(v) if v is not None else ""


def citat_finns(home, citat, fas, falt_):
    """Finns citatet ordagrant (normaliserat) i coach.json på fas/fält, eller i det-har-vet-vi.md?"""
    n = sc.norm(citat)
    if not n:
        return False
    if fas in ("det-har-vet-vi", "det_har_vet_vi"):
        try:
            with open(os.path.join(home, "profil", "det-har-vet-vi.md"), encoding="utf-8") as f:
                return n in sc.norm(f.read())
        except OSError:
            return False
    if fas == "preferenser":
        return n in sc.norm(platt(hamta_vag(sc.las_json(os.path.join(home, "profil", "preferenser.json")) or {}, falt_)))
    coach = sc.las_json(os.path.join(home, "profil", "coach.json")) or {}
    fasdata = (coach.get("faser") or {}).get(fas)
    if fasdata is None:
        return False
    v = hamta_vag(fasdata, falt_) if falt_ else fasdata
    return v is not None and n in sc.norm(platt(v))


def lagg_citat(home, slug, typ, text, citat, fas, falt_):
    kort = las_kort(home, slug)
    if not citat_finns(home, citat, fas, falt_):
        raise SystemExit(f"Citatet hittas inte i {fas}" + (f".{falt_}" if falt_ else "") + ". Använd hennes ord ordagrant, eller stryk påståendet.")
    f = "passar_for_att" if typ == "passar" else "skav"
    post = {"text": text, "citat": citat, "fas": fas, "falt": falt_}
    kort.setdefault(f, falt([], []))
    kort[f]["varde"] = [x for x in kort[f]["varde"] or [] if x.get("text") != text] + [post]
    kalla = {"typ": "det_har_vet_vi" if fas.startswith("det") else "coach", "fas": fas, "falt": falt_,
             "fil": "profil/det-har-vet-vi.md" if fas.startswith("det") else "profil/coach.json", "datum": sc.idag()}
    if kalla not in kort[f]["kallor"]:
        kort[f]["kallor"].append({k: v for k, v in kalla.items()})
    sc.skriv_json(kort_sokv(home, slug), kort)
    return post


def satt(home, slug, faltnamn, text, uppgifter):
    kort = las_kort(home, slug)
    teman = (kort.get("arbetsuppgifter") or {}).get("varde") or []
    for i in uppgifter:
        if i >= len(teman):
            raise SystemExit(f"Arbetsuppgift {i} finns inte (kortet har {len(teman)}).")
    if faltnamn == "uppgift":
        if len(uppgifter) != 1:
            raise SystemExit("Ange exakt en --uppgift för sammanfattningen.")
        teman[uppgifter[0]]["sammanfattning"] = text
    elif faltnamn == "vanlig_tisdag":
        if not uppgifter and kort.get("typ") != "stanna":
            raise SystemExit("Den vanliga tisdagen ska byggas på riktiga arbetsuppgifter: ange --uppgift N (en eller flera).")
        kl = [{"typ": "arbetsuppgift", "index": i, "tema": teman[i]["tema"], "annons_id": teman[i]["annons_id"][:10]}
              for i in uppgifter]
        if kort.get("typ") == "stanna" and not uppgifter:
            kl = [{"typ": "coach", "fas": "options", "falt": "crafting_option", "fil": "profil/coach.json", "datum": sc.idag()}]
        kort["vanlig_tisdag"] = falt(text, kl)
    elif faltnamn in TOMMA_KROKAR:
        raise SystemExit(f"{faltnamn} fylls med källa: använd --kalla (JSON) via satt-krok.")
    else:
        raise SystemExit("--falt ska vara vanlig_tisdag eller uppgift")
    sc.skriv_json(kort_sokv(home, slug), kort)


def satt_krok(home, slug, faltnamn, text, kalla_json):
    """Fyll kultur/ledarskap/arbetsidentitet. Kräver minst en källa (forskning, annons, hennes ord)."""
    kort = las_kort(home, slug)
    kallor = json.loads(kalla_json) if kalla_json else []
    if isinstance(kallor, dict):
        kallor = [kallor]
    if not kallor:
        raise SystemExit("Ett påstående utan källa stryks. Ange --kalla '{\"typ\":\"forskning\",\"fil\":\"docs/research/...\"}'.")
    try:
        varde = json.loads(text)
    except ValueError:
        varde = text
    kort[faltnamn] = falt(varde, kallor, status="ifylld", forvantat=KROK_FORVANTAT[faltnamn], research=RESEARCH)
    sc.skriv_json(kort_sokv(home, slug), kort)


# ---------------------------------------------------------------- kontrollera

def kontrollera(kort, home=None):
    """Lista med flaggor {falt, problem}. Tomma krokar (status vantar) är info, inte fel."""
    flaggor, info = [], []
    for namn, v in kort.items():
        if not (isinstance(v, dict) and "varde" in v and "kallor" in v):
            continue
        tomt = v["varde"] in (None, [], {}, "") or (isinstance(v["varde"], dict) and not any(v["varde"].values()))
        if tomt:
            if v.get("status") == "vantar":
                info.append({"falt": namn, "problem": "tomt, väntar på research"})
            elif v.get("todo"):
                info.append({"falt": namn, "problem": v["todo"]})
            continue
        if not v["kallor"]:
            flaggor.append({"falt": namn, "problem": "har värde men ingen källa: stryk eller belägg"})
        for i, k in enumerate(v["kallor"]):
            if not isinstance(k, dict) or not (k.get("url") or k.get("annons_id") or k.get("fil") or k.get("fas")
                                               or k.get("typ") == "arbetsuppgift"):
                flaggor.append({"falt": f"{namn}.kallor[{i}]", "problem": "källan saknar URL, annons-id, fil eller fas"})
            elif k.get("url") and not k.get("datum") and k.get("typ") != "arbetsuppgift":
                flaggor.append({"falt": f"{namn}.kallor[{i}]", "problem": "källan saknar datum"})
    for f in ("passar_for_att", "skav"):
        for i, p in enumerate((kort.get(f) or {}).get("varde") or []):
            if not (p.get("citat") and p.get("fas")):
                flaggor.append({"falt": f"{f}[{i}]", "problem": "saknar hennes ord (citat + fas + fält)"})
            elif home and not citat_finns(home, p["citat"], p["fas"], p.get("falt")):
                flaggor.append({"falt": f"{f}[{i}]", "problem": f"citatet finns inte i {p['fas']}.{p.get('falt') or ''}"})
    for i, t in enumerate((kort.get("arbetsuppgifter") or {}).get("varde") or []):
        if not t.get("exempel"):
            flaggor.append({"falt": f"arbetsuppgifter[{i}]", "problem": "inga annonsmeningar som belägg"})
    vt = kort.get("vanlig_tisdag") or {}
    if vt.get("varde") and not vt.get("kallor"):
        flaggor.append({"falt": "vanlig_tisdag", "problem": "ska bygga på arbetsuppgifter (--uppgift)"})
    if kort.get("typ") == "marknad" and not ((kort.get("skav") or {}).get("varde")):
        info.append({"falt": "skav", "problem": "inget skav ifyllt: visa skavet lika tydligt som passformen"})
    return flaggor, info


# ---------------------------------------------------------------- jämför

def coach_ord(home):
    coach = sc.las_json(os.path.join(home, "profil", "coach.json")) or {}
    pref = sc.las_json(os.path.join(home, "profil", "preferenser.json")) or {}
    f = coach.get("faser") or {}
    varden = [v.get("value") for v in (f.get("identity") or {}).get("values_top5") or [] if isinstance(v, dict)]
    varden = [v for v in varden if v] or [v for v in pref.get("varden_topp5") or [] if v]
    el = (f.get("energy_log") or {}).get("patterns") or {}
    ad = pref.get("arbetsdag") or {}
    givare = list(el.get("energizers") or []) + list(el.get("flow_conditions") or []) + list(ad.get("energigivare") or []) + \
        [b.get("activity") or b.get("aktivitet") for b in ((f.get("needs_profile") or {}).get("ideal_week_blocks") or ad.get("idealvecka") or [])]
    tjuvar = list(el.get("drainers") or []) + list(ad.get("energitjuvar") or [])
    return varden, [g for g in givare if g], [t for t in tjuvar if t], pref


def vikter(pref):
    v = dict(STANDARD_VIKTER)
    for k, x in (pref.get("rollkort_vikter") or {}).items():
        if k in v and isinstance(x, (int, float)) and x >= 0:
            v[k] = x
    return v


def anstform(etikett):
    """JobTechs etikett -> preferensernas ord (tillsvidare|visstid|vikariat|timanstallning|konsult|praktik)."""
    e = sc.norm(etikett)
    if "vanlig" in e or "tillsvidare" in e:
        return "tillsvidare"
    if "vikariat" in e:
        return "vikariat"
    if "behov" in e or "tim" in e:
        return "timanstallning"
    if "sommar" in e or "tidsbegr" in e or "visstid" in e or "säsong" in e:
        return "visstid"
    return e


def ordtraff(fraser, nyckelord):
    """Vilka av hennes fraser delar ett ord (stam) med arbetsuppgifternas nyckelord?"""
    nk = {stam(w) for w in nyckelord}
    return [f for f in fraser if {stam(w) for w in ord_i(f)} & nk]


def bedom(kort, home, varden, givare, tjuvar, pref):
    rad = {}
    # värden: hennes topp 5, uppfyllda = citerade i passar, krockar = citerade i skav
    citat_p = " ".join(sc.norm(p.get("citat", "") + " " + p.get("text", "")) for p in (kort.get("passar_for_att") or {}).get("varde") or [])
    citat_s = " ".join(sc.norm(p.get("citat", "") + " " + p.get("text", "")) for p in (kort.get("skav") or {}).get("varde") or [])
    if varden:
        upp = [v for v in varden if sc.norm(v) and sc.norm(v) in citat_p]
        kro = [v for v in varden if sc.norm(v) and sc.norm(v) in citat_s]
        rad["varden"] = {"poang": None if not (upp or kro) else round(max(0, len(upp) - len(kro)) / len(varden), 2),
                         "visa": f"{len(upp)}/{len(varden)}" + (f", krock: {', '.join(kro)}" if kro else "") if (upp or kro) else "ej bedömt",
                         "belagg": {"uppfylls": upp, "krockar": kro, "kalla": "passar_for_att/skav med citat"}}
    else:
        rad["varden"] = {"poang": None, "visa": "värden saknas", "belagg": {}}
    # arbetsdag: hennes energigivare/tjuvar mot arbetsuppgifternas nyckelord
    nyck = [w for t in (kort.get("arbetsuppgifter") or {}).get("varde") or [] for w in t.get("nyckelord", [])]
    if kort.get("typ") == "stanna":
        craft = (kort.get("crafting") or {}).get("varde") or {}
        g = craft.get("genomforbarhet_0_10")
        rad["arbetsdag"] = {"poang": round(g / 10, 2) if isinstance(g, (int, float)) else None,
                            "visa": f"crafting {g}/10" if g is not None else "ej bedömt",
                            "belagg": {"kalla": "options.crafting_option.feasibility_0_10"}}
    elif nyck and (givare or tjuvar):
        gt, tt = ordtraff(givare, nyck), ordtraff(tjuvar, nyck)
        p = (len(gt) - len(tt)) / max(1, len(givare))
        rad["arbetsdag"] = {"poang": round(min(1, max(0, 0.5 + p)), 2), "visa": f"+{len(gt)} / −{len(tt)}",
                            "belagg": {"givare": gt, "tjuvar": tt, "kalla": "arbetsuppgifter.nyckelord mot energilogg/idealvecka"}}
    else:
        rad["arbetsdag"] = {"poang": None, "visa": "ej bedömt", "belagg": {}}
    # hårda gränser: lön mot golv, anställningsform i aktuella annonser
    hg = pref.get("hårda_gränser") or {}
    brott, ok = [], []
    lv = (kort.get("lon") or {}).get("varde") or {}
    pr = lv.get("per_region") or {}
    reg = next((r for r in pr if r != "riket"), "riket")
    medel = ((pr.get(reg) or {}).get("alla") or {}).get("manadslon_medel") or ((pr.get("riket") or {}).get("alla") or {}).get("manadslon_medel")
    if hg.get("lonegolv_manad") and medel:
        (ok if medel >= hg["lonegolv_manad"] else brott).append(
            f"snittlön {medel} kr mot golv {hg['lonegolv_manad']} kr (SCB {lv.get('ar')}, {reg})")
    ann = (kort.get("annonser") or {}).get("varde") or []
    if hg.get("anstallningsform") and ann:
        tillatna = {sc.norm(x) for x in hg["anstallningsform"]}
        m = [a for a in ann if a.get("anstallningsform") and anstform(a["anstallningsform"]) not in tillatna]
        if m:
            brott.append(f"{len(m)} av {len(ann)} aktuella annonser är {', '.join(sorted({a['anstallningsform'] for a in m}))}")
        elif any(a.get("anstallningsform") for a in ann):
            ok.append("aktuella annonser har tillåten anställningsform")
    if kort.get("typ") == "stanna":
        rad["harda_granser"] = {"poang": 1.0, "visa": "uppfyllda idag", "belagg": {"kalla": "nuvarande jobb"}}
    else:
        rad["harda_granser"] = {"poang": None if not (brott or ok) else (0.0 if any("lön" in b for b in brott) else 0.5 if brott else 1.0),
                                "visa": "ok" if ok and not brott else ("; ".join(brott) if brott else "ej bedömt"),
                                "belagg": {"brott": brott, "ok": ok}}
    # glapp
    g = (kort.get("glapp") or {}).get("varde") or {}
    if kort.get("typ") == "stanna":
        rad["glapp"] = {"poang": 1.0, "visa": "inget", "belagg": {}}
    elif g and (g.get("har") or g.get("saknas") or g.get("osakert")):
        hs = [x["krav"] for x in g.get("saknas", []) if x.get("hart")]
        ho = [x["krav"] for x in g.get("osakert", []) if x.get("hart")]
        on = [x for k_ in ("har", "saknas", "osakert") for x in g.get(k_, []) if not x.get("hart")]
        onh = sum(1 for x in g.get("har", []) if not x.get("hart"))
        # bara saknade hårda krav ger avdrag; önskelistan är information, inte underkännande
        p = 0.2 if hs else 0.7 if ho else 1.0
        visa = ("hårda krav saknas: " + ", ".join(hs) if hs else "hårda krav osäkra: " + ", ".join(ho) if ho
                else "hårda krav: ok") + f" · vanligt efterfrågat: du har {onh} av {len(on)}"
        rad["glapp"] = {"poang": p, "visa": visa,
                        "belagg": {"harda_saknas": hs, "harda_osakra": ho, "onskelista_saknas": [x["krav"] for x in g.get("saknas", []) if not x.get("hart")][:5]}}
    else:
        rad["glapp"] = {"poang": None, "visa": "kör glapp", "belagg": {}}
    # marknad
    vol = (kort.get("volym") or {}).get("varde") or {}
    if vol:
        n = vol.get("senaste_hela_ar") or 0
        rad["marknad"] = {"poang": round(min(1, math.log1p(n) / math.log1p(200)), 2),
                          "visa": f"{n} annonser/år, {vol.get('trend')}" + (f" ({vol['trend_procent']:+d} %)" if vol.get("trend_procent") is not None else "")
                                  + f", {vol.get('oppna_nu', 0)} öppna nu",
                          "belagg": {"kalla": "volym (JobTech Historical)"}}
    else:
        rad["marknad"] = {"poang": None, "visa": "–", "belagg": {}}
    for k in ("kultur", "ledarskap"):
        v = kort.get(k) or {}
        rad[k] = {"poang": v.get("poang") if v.get("varde") else None,
                  "visa": "väntar på research" if not v.get("varde") else sc.utdrag(str(v["varde"]), 60), "belagg": {}}
    return rad


def rk_etikett(tot, dims, typ=None):
    """Huvudbudskapet för en riktning. Totalen är sortering, inte betyg; visa aldrig procent först."""
    g = (dims.get("glapp") or {}).get("belagg") or {}
    hg = (dims.get("harda_granser") or {}).get("belagg") or {}
    plus = []
    vb = (dims.get("varden") or {}).get("belagg") or {}
    if vb.get("uppfylls"):
        plus.append("passar det du värdesätter (" + ", ".join(vb["uppfylls"][:3]) + ")")
    ab = (dims.get("arbetsdag") or {}).get("belagg") or {}
    if ab.get("givare"):
        plus.append("arbetsdagen har det som ger dig energi")
    if (dims.get("marknad") or {}).get("poang") is not None and dims["marknad"]["poang"] >= 0.6:
        plus.append("många annonser")
    rad1 = ("Det som talar för: " + "; ".join(plus) + ".") if plus else ""
    if typ == "stanna":
        return "Att stanna – jämförelsepunkt", rad1 or "Ditt nuvarande jobb, med de ändringar du kan göra själv."
    if hg.get("brott"):
        b = "; ".join(hg["brott"])
        return f"Bryter mot din gräns: {b}", "\n".join(filter(None, [rad1, f"Bryter mot din gräns: {b}. Du avgör om det är värt det."]))
    if g.get("harda_saknas"):
        x = ", ".join(g["harda_saknas"])
        return f"Möjlig – kräver {x}", "\n".join(filter(None, [rad1, f"Hårt krav du inte har än: {x}. Allt annat är önskelista."]))
    if tot is None:
        return "För lite underlag än", rad1 or "Kör glapp och citat så går det att säga mer."
    if tot >= 70:
        return "Stark riktning", rad1 or "Det mesta som går att bedöma pekar hit."
    if tot >= 50:
        return "Bra riktning – värd att pröva", rad1 or "Riktningen håller; resten är önskelista och går att lära."
    if g.get("onskelista_saknas") and not g.get("harda_saknas"):
        return "Sträckriktning – pröva gärna", "\n".join(filter(None, [rad1, "Inga hårda krav saknas; det som fattas är önskelista."]))
    return "Svagare riktning", rad1 or "Lite pekar hit än; se vad som skaver."


def jamfor(home):
    varden, givare, tjuvar, pref = coach_ord(home)
    v = vikter(pref)
    rader = []
    for kort in alla_kort(home):
        dims = bedom(kort, home, varden, givare, tjuvar, pref)
        vs = sum(v[k] for k, d in dims.items() if d["poang"] is not None)
        tot = round(100 * sum(v[k] * d["poang"] for k, d in dims.items() if d["poang"] is not None) / vs) if vs else None
        tackning = round(vs / sum(v.values()), 2)
        et, mot = rk_etikett(tot, dims, kort.get("typ"))
        rader.append({"slug": kort["slug"], "titel": kort.get("titel"), "typ": kort.get("typ"), "total": tot,
                      "tackning": tackning, "dimensioner": dims, "etikett": et, "motivering": mot})
    rader.sort(key=lambda r: (r["typ"] != "stanna", -(r["total"] or -1)))
    return {"vikter": v, "vikter_kalla": "preferenser.json: rollkort_vikter" if pref.get("rollkort_vikter") else "standardvärden",
            "dimensioner": DIM_NAMN, "rader": rader,
            "tolkning": "total = viktat snitt (0–100) över dimensioner som går att bedöma; täckning = andel av vikterna som "
                        "hade data. En karta, inte en dom. Ändra vikterna i preferenser.json → rollkort_vikter."}


def matris_md(m):
    dims = list(DIM_NAMN)
    rub = "| | " + " | ".join(r["titel"] for r in m["rader"]) + " |"
    ut = [rub, "|---" * (len(m["rader"]) + 1) + "|"]
    for d in dims:
        ut.append(f"| {DIM_NAMN[d]} (vikt {m['vikter'][d]}) | " + " | ".join(r["dimensioner"][d]["visa"] for r in m["rader"]) + " |")
    ut.append("| **Bedömning** | " + " | ".join(r.get("etikett") or "–" for r in m["rader"]) + " |")
    ut.append("| Totalt (sortering) | " + " | ".join(str(r["total"]) if r["total"] is not None else "–" for r in m["rader"]) + " |")
    ut.append("| Täckning | " + " | ".join(f"{round(100 * r['tackning'])} %" for r in m["rader"]) + " |")
    return "\n".join(ut)


# ---------------------------------------------------------------- utskrift

def kompakt(kort):
    """Det modellen behöver: siffror, teman med 1–2 exempel, inga hela annonser."""
    def v(f):
        return (kort.get(f) or {}).get("varde")
    ut = {"slug": kort["slug"], "titel": kort.get("titel"), "typ": kort.get("typ"), "roll": kort.get("roll"),
          "region": (kort.get("region") or {}).get("namn"), "underlag": kort.get("underlag")}
    if kort.get("typ") == "marknad":
        ut["titlar"] = [f"{t['titel']} ({t['arbetsgivare']} ag)" for t in (v("titlar") or [])[:8]]
        ut["arbetsgivare"] = [f"{a['namn']} ({a['annonser']}+{a['oppna_nu']} nu)" for a in (v("arbetsgivare") or [])[:6]]
        vol = v("volym") or {}
        ut["volym"] = {"per_ar": {x["ar"]: x["annonser"] for x in vol.get("per_ar", [])}, "trend": vol.get("trend"),
                       "trend_procent": vol.get("trend_procent"), "oppna_nu": vol.get("oppna_nu")}
        ut["arbetsuppgifter_till_claude"] = [{"i": i, "tema": t["tema"], "andel": t["andel_annonser"],
                                              "exempel": [e["text"] for e in t["exempel"][:2]]} for i, t in enumerate(v("arbetsuppgifter") or [])]
        k = v("krav") or {}
        ut["krav"] = {"must_have": [f"{x['namn']} {round(100 * x['andel'])} %" for x in k.get("must_have", [])[:8]],
                      "nice_to_have": [f"{x['namn']} {round(100 * x['andel'])} %" for x in k.get("nice_to_have", [])[:6]],
                      "fritext": [{"tema": t["tema"], "typ": t["typ"], "andel": t["andel_annonser"],
                                   "exempel": t["exempel"][0]["text"]} for t in k.get("fritext", [])[:8]]}
        ut["annonser"] = [f"{a['rubrik']} – {a['arbetsgivare']} ({a['publicerad']}) {a['url']}" for a in v("annonser") or []]
        ut["lon"] = v("lon") or (kort.get("lon") or {}).get("todo")
    else:
        ut["passar_for_att"] = v("passar_for_att")
        ut["skav"] = v("skav")
        ut["crafting"] = v("crafting")
    ut["att_gora"] = ("1) sammanfatta varje arbetsuppgift (satt --falt uppgift --uppgift i), 2) glapp, "
                      "3) citat passar/skav med hennes ord, 4) vanlig tisdag ur uppgifterna, 5) kontrollera")
    return ut


def main(argv=None):
    global _FRASKT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sc.add_home_arg(ap)
    sub = ap.add_subparsers(dest="lage", required=True)
    b = sub.add_parser("bygg")
    b.add_argument("--roll", help="titel i fri text eller yrkes-id")
    b.add_argument("--stanna", action="store_true", help="kort för att stanna/forma om nuvarande jobb")
    b.add_argument("--region")
    b.add_argument("--ar", type=float, default=3)
    b.add_argument("--max", type=int, default=300, help="max historiska annonser att läsa (standard 300)")
    b.add_argument("--titel", help="visningsnamn (standard: rollen)")
    b.add_argument("--slug")
    b.add_argument("--fraskt", action="store_true", help="hoppa över cachen")
    g = sub.add_parser("glapp")
    g.add_argument("slug")
    c = sub.add_parser("citat")
    c.add_argument("slug")
    c.add_argument("--typ", choices=["passar", "skav"], required=True)
    c.add_argument("--text", required=True, help="påståendet, kort")
    c.add_argument("--citat", required=True, help="hennes ord, ordagrant")
    c.add_argument("--fas", required=True, help="intake|identity|energy_log|needs_profile|options|experiments|decision|det-har-vet-vi|preferenser")
    c.add_argument("--falt", default="", help="sökväg i fasen, t.ex. values_top5[0].violated_example")
    s = sub.add_parser("satt")
    s.add_argument("slug")
    s.add_argument("--falt", required=True, choices=["vanlig_tisdag", "uppgift"] + list(TOMMA_KROKAR))
    s.add_argument("--text", required=True)
    s.add_argument("--uppgift", type=int, action="append", default=[])
    s.add_argument("--kalla", help="JSON-källa för kultur/ledarskap/arbetsidentitet")
    k = sub.add_parser("kontrollera")
    k.add_argument("slug", nargs="?")
    k.add_argument("--alla", action="store_true")
    j = sub.add_parser("jamfor")
    j.add_argument("--md", action="store_true", help="tabell i markdown (att visa henne)")
    vi = sub.add_parser("visa")
    vi.add_argument("slug")
    vi.add_argument("--allt", action="store_true")
    sub.add_parser("lista")
    for p in (b, g, c, s, k, j, vi):
        p.add_argument("--home", default=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    home = sc.hem(a.home)
    if a.lage == "bygg":
        _FRASKT = a.fraskt
        if a.stanna:
            kort = bygg_stanna(a, home)
        elif a.roll:
            kort = bygg(a, home)
        else:
            ap.error("ange --roll eller --stanna")
        jc.skriv(kompakt(kort))
    elif a.lage == "glapp":
        g = glapp(home, a.slug)["varde"]
        jc.skriv({"harda_krav": g["sammanfattning"]["harda_krav"], "onskelista": g["sammanfattning"]["onskelista"],
                  "tolkning": g["sammanfattning"]["tolkning"],
                  "har": [f"{x['krav']} ← {', '.join(x['fakta'][:2])}" for x in g["har"]],
                  "osakert": [f"{x['krav']} ({round(100 * x['andel'])} %) ~ {', '.join(x['fakta'][:2])}" for x in g["osakert"]],
                  "saknas": [("HÅRT KRAV: " if x.get("hart") else "") + f"{x['krav']} ({round(100 * x['andel'])} % av annonserna)" for x in g["saknas"]]})
    elif a.lage == "citat":
        jc.skriv(lagg_citat(home, a.slug, a.typ, a.text, a.citat, a.fas, a.falt))
    elif a.lage == "satt":
        if a.falt in TOMMA_KROKAR:
            satt_krok(home, a.slug, a.falt, a.text, a.kalla)
        else:
            satt(home, a.slug, a.falt, a.text, a.uppgift)
        print("ok")
    elif a.lage == "kontrollera":
        korten = alla_kort(home) if a.alla or not a.slug else [las_kort(home, a.slug)]
        fel = False
        ut = []
        for kort in korten:
            fl, info = kontrollera(kort, home)
            fel = fel or bool(fl)
            ut.append({"slug": kort["slug"], "ok": not fl, "flaggor": fl, "info": info})
        jc.skriv({"kort": ut})
        return 1 if fel else 0
    elif a.lage == "jamfor":
        m = jamfor(home)
        sc.skriv_json(sc.sokv(home, "rollkort", "_matris.json"), m)
        if a.md:
            print(matris_md(m))
            print(f"\nVikter ({m['vikter_kalla']}): " + ", ".join(f"{DIM_NAMN[k]} {x}" for k, x in m["vikter"].items()))
        else:
            jc.skriv({"vikter": m["vikter"], "rader": [{"slug": r["slug"], "etikett": r["etikett"], "motivering": r["motivering"],
                                                        "total": r["total"], "tackning": r["tackning"],
                                                        **{k: d["visa"] for k, d in r["dimensioner"].items()}} for r in m["rader"]]})
    elif a.lage == "visa":
        kort = las_kort(home, a.slug)
        print(json.dumps(kort, ensure_ascii=False, indent=1) if a.allt else "")
        if not a.allt:
            jc.skriv(kompakt(kort))
    elif a.lage == "lista":
        jc.skriv({"rollkort": [{"slug": k["slug"], "titel": k.get("titel"), "typ": k.get("typ"),
                                "uppdaterad": k.get("uppdaterad")} for k in alla_kort(home)]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
