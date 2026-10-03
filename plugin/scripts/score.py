#!/usr/bin/env python3
"""Deterministisk poäng 0–100 per jobb mot profil/preferenser.json.

  python3 score.py [--home DIR] [--enrich] [--alla] [--jokrar N --min-poang M]

Uteslutning (poäng 0) bara för exkluderad arbetsgivare; det har hon själv valt bort.
Gränsbrott (preferenser.hårda_gränser) flaggas men utesluter inte; hon avgör själv:
anställningsform eller omfattning utanför tillåtna, distanskrav som annonsen inte uppfyller, ort
utanför önskade kommuner/regioner (när annonsen inte är helt på distans) och pendling.
Pendling: restid går inte att räkna offline. Hemort = hårda_gränser.hemort eller första orten.
Samma kommun som hemorten räknas som inom max_pendling_min; annan kommun i regionen ger flaggan
"kolla restiden"; utanför regionen ger gränsbrottet "pendling troligen över N min (uppskattning)".
Gränsbrotten sparas i poang_skal_json.granbrott, etiketten blir "Bryter mot din gräns: <brott>"
och varje brott drar 10 p (högst 20) så att jobbet hamnar längre ned.
Delpoäng (max): yrke 30, kompetens 30, sökord 15, ort/distans 15, anställningsform 5, omfattning 5.
Samma yrkesgrupp (SSYK 4) som ett önskat yrke ger 70 % av yrkespoängen. Okänd uppgift ger halva delpoängen. Varje exkludera-ord i titel/utdrag drar av 25.
Förklaringen sparas i poang_skal_json.

Princip: annonser är önskelistor. Hon kan söka högt över det hon tror och sakna det mesta, om rollen
inte är certifierad. Därför:
  - Kompetensdelen bygger på TRÄFFAR (vad hon har som efterfrågas), inte på täckningsgrad:
    0 träffar 6 p, sedan 12 + 6 per träff (eller andelen × 30 om den är högre), max 30.
    Två av fyra önskade ger 24 av 30.
  - Krav klassas som hårda eller önskade. Hårda: legitimation (sjuksköterska, läkare, lärare, psykolog
    m.fl.), certifiering/behörighet som krävs enligt lag, körkort när rollen kräver det, säkerhetsprövning
    eller medborgarskap och uttryckligt, centralt språkkrav. Allt annat, inklusive "X års erfarenhet",
    är önskelista. Ett hårt krav som inte syns i faktabanken ger flaggan hart_krav_saknas och -8 p
    (högst -16), aldrig uteslutning (hon kan ha det utan att det står i faktabanken).
  - Sträckjobb: senior/chef/lead/ansvarig i titeln (och inte i hennes nuvarande titel) eller fler års
    erfarenhet än hon har, när riktningen stämmer (yrke eller sökord). Visas med etikett, sorteras inte bort.
  - matchning_etikett (huvudbudskapet; visa aldrig täckningsgrad i procent som huvudbudskap):
      "Svag"                           utesluten (exkluderad arbetsgivare), eller poäng < 50
      "Bryter mot din gräns: <brott>"  minst ett gränsbrott (visas före övriga etiketter)
      "Möjlig – kolla <krav>"          ett hårt krav är oklart
      "Sträckjobb – sök!"              sträckjobb med poäng >= 50
      "Stark matchning"                poäng >= 80 och minst 70 % av önskade kompetenser träffar
      "Bra matchning – värd att söka"  poäng >= 50 (t.ex. hälften av önskelistan + riktning stämmer)
    matchning_motivering: 1–2 korta rader om vad hon HAR som efterfrågas, och bara hårda krav som saknas.
  - Arbetsgivare (valfritt): --arbetsgivarkort läser sok/arbetsgivare/*.json. Delpoängen `arbetsgivare`
    har vikten --arbetsgivare-vikt (standard 0 = räknas inte): vikt * stämmer/(stämmer+skaver), okänt = halva.
    Varningssignaler i kortet blir flaggor (poang_skal_json.flaggor), aldrig uteslutning.

--enrich: berikar kompetenser via JobTech JobAd Enrichments (cachat per text_hash i cache/enrich).
--jokrar N: väljer N jobb UNDER min-poäng (standard 50) som inte är uteslutna men träffar
preferenser.arbetsdag.energigivare, varden_topp5 och sökord i texten. De markeras i poang_skal_json
med "joker": true och "joker_traff": [...] och skrivs ut i rapportens "jokrar". Tidigare
jokermarkeringar rensas vid varje körning. lista.py --jokrar visar dem.
Standard poängsätts bara jobb med status ny/intressant; --alla tar med alla.
"""
import argparse
import datetime as _dt
import glob
import json
import os
import re
import urllib.parse

import sok_common as sc

ENRICH_URL = "https://jobad-enrichments-api.jobtechdev.se/enrichtextdocuments"
TAX_URL = "https://taxonomy.api.jobtechdev.se/v1/taxonomy/main/concepts"
VIKT = {"yrke": 30, "kompetens": 30, "sokord": 15, "ort": 15, "anstallningsform": 5, "omfattning": 5}


# ---------------------------------------------------------------- berikning

def enrich(home, c, uids=None):
    rows = c.execute("SELECT uid, titel, text_hash, kompetenser_json FROM jobb WHERE status IN ('ny','intressant')"
                     ).fetchall()
    att_gora, klara = [], 0
    for r in rows:
        if uids and r["uid"] not in uids:
            continue
        cp = sc.cachev(home, "enrich", f"{r['text_hash']}.json")
        res = sc.las_json(cp)
        if res is None:
            text = sc.las_text(home, r["text_hash"])
            if text:
                att_gora.append((r, cp, text))
            continue
        klara += _lagg_till(c, r, res)
    for i in range(0, len(att_gora), 50):
        bit = att_gora[i:i + 50]
        body = {"documents_input": [{"doc_id": r["text_hash"], "doc_headline": r["titel"] or "",
                                     "doc_text": t[:15000]} for r, _, t in bit],
                "include_terms_info": False, "include_sentences": False, "sort_by_prediction_score": "DESC"}
        _, svar, _ = sc.http_json(ENRICH_URL, method="POST", data=body, timeout=60)
        per = {d.get("doc_id"): d for d in svar or []}
        for r, cp, _ in bit:
            d = per.get(r["text_hash"], {})
            res = [{"namn": k["concept_label"], "p": round(k.get("prediction", 0), 2)}
                   for k in (d.get("enriched_candidates") or {}).get("competencies", [])]
            sc.skriv_json(cp, res)
            klara += _lagg_till(c, r, res)
    c.commit()
    return klara


def _lagg_till(c, r, res):
    komp = json.loads(r["kompetenser_json"] or "[]")
    finns = {(k.get("namn") or "").lower() for k in komp}
    ny = [{"id": None, "namn": k["namn"], "typ": "enrich"} for k in res
          if k.get("p", 0) >= 0.5 and k["namn"].lower() not in finns]
    if ny:
        c.execute("UPDATE jobb SET kompetenser_json=? WHERE uid=?",
                  (json.dumps(komp + ny, ensure_ascii=False), r["uid"]))
    return 1


# ---------------------------------------------------------------- taxonomi-etiketter

def etikett_for_id(home, cid):
    cp = sc.cachev(home, "taxonomy", f"id_{cid}.json")
    d = sc.las_json(cp)
    if d is None:
        try:
            _, d, _ = sc.http_json(TAX_URL + "?" + urllib.parse.urlencode({"id": cid}))
            sc.skriv_json(cp, d)
        except (sc.NatFel, sc.HttpFel):
            return None
    return (d[0].get("taxonomy/preferred-label") if d else None)


def yrkesgrupp_for(home, yrkes_id):
    cp = sc.cachev(home, "taxonomy", f"grupp_{yrkes_id}.json")
    d = sc.las_json(cp)
    if d is None:
        try:
            q = {"type": "ssyk-level-4", "related-ids": yrkes_id, "relation": "broader"}
            _, d, _ = sc.http_json(TAX_URL + "?" + urllib.parse.urlencode(q))
            sc.skriv_json(cp, d)
        except (sc.NatFel, sc.HttpFel):
            return set()
    return {x.get("taxonomy/id") for x in d or []}


def kommuner_i_region(home, region_id):
    cp = sc.cachev(home, "taxonomy", f"region_{region_id}_kommuner.json")
    d = sc.las_json(cp)
    if d is None:
        try:
            q = {"type": "municipality", "related-ids": region_id, "relation": "narrower"}
            _, d, _ = sc.http_json(TAX_URL + "?" + urllib.parse.urlencode(q))
            sc.skriv_json(cp, d)
        except (sc.NatFel, sc.HttpFel):
            return set()
    return {x.get("taxonomy/id") for x in d or []}


# ---------------------------------------------------------------- poäng

def forbered(pref, home, slå_upp=True):
    hg = pref.get("hårda_gränser") or pref.get("harda_granser") or {}
    riktn = pref.get("riktningar") or []
    komp_ids = [k for k in pref.get("kompetens_id") or [] if k]
    komp = {k.lower() for k in komp_ids}
    if slå_upp:
        for k in komp_ids:
            e = etikett_for_id(home, k) if " " not in k and "_" in k else None
            if e:
                komp.add(e.lower())
    regioner = {o.get("region_id") for o in pref.get("orter") or [] if o.get("region_id")}
    region_kommuner = set()
    if slå_upp:
        for rid in regioner:
            region_kommuner |= kommuner_i_region(home, rid)
    yrken = {i for r in riktn for i in r.get("yrkes_id") or []}
    grupper = set()
    if slå_upp:
        for y in yrken:
            grupper |= yrkesgrupp_for(home, y)
    return {
        "region_kommuner": region_kommuner,
        "yrkesgrupper": grupper - yrken,
        "yrken": {i for r in riktn for i in r.get("yrkes_id") or []},
        "sokord": [s.lower() for r in riktn for s in r.get("sokord") or [] if s],
        "exkl_ord": [s.lower() for r in riktn for s in r.get("exkludera_ord") or [] if s],
        "kommuner": {o.get("kommun_id") for o in pref.get("orter") or [] if o.get("kommun_id")},
        "regioner": {o.get("region_id") for o in pref.get("orter") or [] if o.get("region_id")},
        "ortnamn": {sc.norm(o.get("namn")) for o in pref.get("orter") or [] if o.get("namn")},
        "komp": komp,
        "anst": [a.lower() for a in hg.get("anstallningsform") or []],
        "omf": [a.lower() for a in hg.get("omfattning") or []],
        "dist": hg.get("distans_dagar") or {},
        "max_pendling": hg.get("max_pendling_min"),
        "hemort": _hemort(hg, pref),
        "exkl_arb": {sc.norm(a) for a in pref.get("exkludera_arbetsgivare") or []},
    }


def _hemort(hg, pref):
    h = hg.get("hemort")
    if isinstance(h, dict):
        return {"namn": sc.norm(h.get("namn")), "kommun_id": h.get("kommun_id")}
    if isinstance(h, str) and h:
        return {"namn": sc.norm(h), "kommun_id": None}
    o = (pref.get("orter") or [{}])[0] or {}
    return {"namn": sc.norm(o.get("namn")), "kommun_id": o.get("kommun_id")} if o else {}


def granser(r, P):
    """Gränsbrott och flaggor mot hårda_gränser. Returnerar (brott, flaggor, ort_match)."""
    brott, flaggor = [], []
    if r["anstallningsform"] and P["anst"] and r["anstallningsform"] not in P["anst"]:
        if not (r["anstallningsform"] == "vikariat" and "visstid" in P["anst"]):
            brott.append(r["anstallningsform"])
    if r["omfattning"] and P["omf"] and r["omfattning"] not in P["omf"]:
        brott.append(r["omfattning"])
    dmin, dmax = P["dist"].get("min"), P["dist"].get("max")
    if r["distans"] == 0 and dmin:
        brott.append("kräver plats varje dag, du vill ha distansdagar")
    if r["distans"] == 2 and dmax == 0:
        brott.append("helt på distans, du vill vara på plats")
    ort_kand = bool(r["kommun_id"] or r["ort"])
    ort_match = None
    if P["kommuner"] or P["regioner"] or P["ortnamn"]:
        if r["kommun_id"] and r["kommun_id"] in P["kommuner"]:
            ort_match = "kommun"
        elif r["kommun_id"] and r["kommun_id"] in P.get("region_kommuner", ()):
            ort_match = "region"
        elif r["ort"] and any(o and o in sc.norm(r["ort"]) for o in P["ortnamn"]):
            ort_match = "kommun"
    ortnamn = r["ort"] or r["kommun_id"]
    if ort_kand and r["distans"] != 2:
        mp = P.get("max_pendling")
        h = P.get("hemort") or {}
        hemma = bool(h) and ((r["kommun_id"] and r["kommun_id"] == h.get("kommun_id"))
                             or (r["ort"] and h.get("namn") and h["namn"] in sc.norm(r["ort"])))
        if (P["kommuner"] or P["regioner"] or P["ortnamn"]) and not ort_match:
            brott.append(f"ort {ortnamn} utanför dina orter"
                         + (f", pendling troligen över {mp} min (uppskattning)" if mp else ""))
        elif mp and not hemma and ort_match != "kommun":
            flaggor.append(f"pendling: kolla restiden till {ortnamn} (din gräns {mp} min)")
    return brott, flaggor, ort_match


def poang(r, P, text=""):
    """Returnerar (poäng, förklaring)."""
    sk = {"delar": {}, "avdrag": [], "uteslutet": []}
    komp = json.loads(r["kompetenser_json"] or "[]")
    titel = (r["titel"] or "").lower()
    allt = " ".join([titel, (r["utdrag"] or "").lower(), (text or "").lower()])
    # uteslutning: bara arbetsgivare hon själv valt bort
    if P["exkl_arb"] and sc.norm(r["arbetsgivare"]) in P["exkl_arb"]:
        sk["uteslutet"].append("exkluderad arbetsgivare")
        sk["matchning_etikett"], sk["matchning_motivering"] = etikett(0, sk)
        return 0, sk
    # gränsbrott: flaggas, utesluter inte
    brott, gflaggor, ort_match = granser(r, P)
    if brott:
        sk["granbrott"] = brott
    if gflaggor:
        sk["flaggor"] = gflaggor
    dmin = P["dist"].get("min")
    d = sk["delar"]
    # yrke
    jobb_yrken = {k.get("id") for k in komp if k.get("typ") in ("yrke", "yrkesgrupp")}
    if P["yrken"] and jobb_yrken & P["yrken"]:
        d["yrke"] = VIKT["yrke"]
    elif P.get("yrkesgrupper") and jobb_yrken & P["yrkesgrupper"]:
        d["yrke"] = round(VIKT["yrke"] * 0.7)
    elif P["sokord"] and any(s in titel for s in P["sokord"]):
        d["yrke"] = round(VIKT["yrke"] * 0.7)
    elif not jobb_yrken:
        d["yrke"] = round(VIKT["yrke"] * 0.3)
    else:
        d["yrke"] = 0
    # kompetens
    ks = [k for k in komp if k.get("typ") not in ("yrke", "yrkesgrupp")]
    if not ks or not P["komp"]:
        d["kompetens"] = VIKT["kompetens"] // 2
        traff = []
    else:
        w = {"must": 2, "nice": 1, "enrich": 1}
        tot = sum(w.get(k.get("typ"), 1) for k in ks)
        traff = [k for k in ks if (k.get("id") or "").lower() in P["komp"] or (k.get("namn") or "").lower() in P["komp"]]
        trw = sum(w.get(k.get("typ"), 1) for k in traff)
        d["kompetens"] = min(VIKT["kompetens"], max(12 + 6 * len(traff), round(VIKT["kompetens"] * trw / tot))) if traff else 6
        sk["kompetens_andel"] = round(trw / tot, 2) if tot else None
    sk["kompetens_traff"] = [k.get("namn") for k in traff][:10]
    # ort/distans
    if r["distans"] == 2:
        d["ort"] = VIKT["ort"]
    elif ort_match == "kommun":
        d["ort"] = VIKT["ort"] if r["distans"] is not None or not dmin else round(VIKT["ort"] * 0.8)
    elif ort_match == "region":
        d["ort"] = round(VIKT["ort"] * 0.7)
    else:
        d["ort"] = VIKT["ort"] // 2
    if r["distans"] == 1 and dmin:
        d["ort"] = VIKT["ort"]
    # anställningsform, omfattning
    d["anstallningsform"] = VIKT["anstallningsform"] if r["anstallningsform"] else VIKT["anstallningsform"] // 2
    d["omfattning"] = VIKT["omfattning"] if r["omfattning"] else VIKT["omfattning"] // 2
    # sökord
    if not P["sokord"]:
        d["sokord"] = VIKT["sokord"] // 2
    elif any(s in titel for s in P["sokord"]):
        d["sokord"] = VIKT["sokord"]
    elif any(s in allt for s in P["sokord"]):
        d["sokord"] = round(VIKT["sokord"] * 0.6)
    else:
        d["sokord"] = 0
    # arbetsgivarkort (valfritt)
    ak = P.get("arbetsgivarkort") or {}
    kort = ak.get((r["orgnr"] or "").replace("-", "")) or ak.get(sc.norm(r["arbetsgivare"]))
    if kort:
        m = kort.get("matchning") or {}
        for f in m.get("varningsflaggor", []):
            sk.setdefault("flaggor", []).append(f"varningssignal: {f.get('signal')} ({'; '.join(f.get('belagg', [])[:2])})")
        sk["arbetsgivarkort"] = kort.get("slug")
    if P.get("arbetsgivare_vikt"):
        if kort:
            st, sv = len((kort.get("matchning") or {}).get("stammer", [])), len((kort.get("matchning") or {}).get("skaver", []))
            d["arbetsgivare"] = round(P["arbetsgivare_vikt"] * (st / (st + sv) if st + sv else 0.5))
        else:
            d["arbetsgivare"] = round(P["arbetsgivare_vikt"] / 2)
    p = sum(d.values())
    if P.get("arbetsgivare_vikt"):
        p = round(p * 100 / (100 + P["arbetsgivare_vikt"]))
    for w in P["exkl_ord"]:
        if w in titel or w in (r["utdrag"] or "").lower():
            sk["avdrag"].append(w)
            p -= 25
    # hårda krav kontra önskelista
    saknas = [k for k in harda_krav(" ".join([r["titel"] or "", r["utdrag"] or "", text or ""]))
              if not har_krav(k, P.get("fakta") or {})]
    if saknas:
        sk["hart_krav_saknas"] = [k["krav"] for k in saknas]
        sk["avdrag"].append("hårt krav oklart: " + ", ".join(sk["hart_krav_saknas"]))
        p -= min(16, 8 * len(saknas))
    # sträckjobb
    riktning = d.get("yrke", 0) >= round(VIKT["yrke"] * 0.7) or d.get("sokord", 0) >= round(VIKT["sokord"] * 0.6)
    strack = strackorsak(r["titel"] or "", " ".join([r["utdrag"] or "", text or ""]), P.get("fakta") or {})
    if riktning and strack:
        sk["strackjobb"] = strack
    if brott:
        p -= min(20, 10 * len(brott))
    p = max(0, min(100, p))
    sk["matchning_etikett"], sk["matchning_motivering"] = etikett(p, sk)
    return p, sk


# ---------------------------------------------------------------- hårda krav, sträckjobb, etikett

HARDA = [
    ("legitimation", r"\blegitimerad\b|\blegitimation\b|\bleg\. ?(sjuksköterska|läkare|psykolog|lärare|fysioterapeut)"),
    ("lärarbehörighet", r"\blärarbehörighet|behörig lärare|lärarlegitimation"),
    ("certifiering enligt lag", r"(krav på|kräver|ska ha|måste ha)[^.\n]{0,40}(certifiering|behörighet|auktorisation)|auktoriserad revisor|elbehörighet"),
    ("körkort", r"(krav på|kräver|ska ha|måste ha|körkort är ett krav|b-körkort krävs)[^.\n]{0,30}körkort|körkort[^.\n]{0,20}(krav|krävs|ett måste)"),
    ("säkerhetsprövning", r"säkerhetsprövning|säkerhetsklass|registerkontroll"),
    ("medborgarskap", r"svenskt medborgarskap"),
    ("språkkrav", r"(krav på|kräver|ska ha|måste ha|flytande|mycket goda kunskaper i)[^.\n]{0,30}\b(svenska|engelska|finska|tyska|franska|spanska|arabiska)\b"),
]
SPRAKKOD = {"svenska", "engelska", "finska", "tyska", "franska", "spanska", "arabiska"}


def harda_krav(text):
    t = (text or "").lower()
    ut = []
    for krav, rx in HARDA:
        m = re.search(rx, t)
        if m:
            post = {"krav": krav, "belagg": t[max(0, m.start() - 20):m.end() + 20].strip()}
            if krav == "språkkrav":
                post["sprak"] = [s for s in SPRAKKOD if s in m.group(0)]
            ut.append(post)
    return ut


def _fakta_text(f):
    def gå(x):
        if isinstance(x, dict):
            return " ".join(gå(v) for v in x.values())
        if isinstance(x, list):
            return " ".join(gå(v) for v in x)
        return str(x) if x is not None else ""
    return gå({k: f.get(k) for k in ("kurser", "utbildning", "kompetenser", "roller", "sammanfattning_rad")}).lower()


def har_krav(k, fakta):
    if not fakta:
        return False
    if k["krav"] == "körkort":
        return bool((fakta.get("person") or {}).get("korkort"))
    if k["krav"] == "språkkrav":
        kan = {(s.get("sprak") or "").lower() for s in fakta.get("sprak") or []
               if (s.get("niva") or "") in ("modersmål", "flytande", "god")}
        return set(k.get("sprak") or []) <= kan
    txt = _fakta_text(fakta)
    ord_ = {"legitimation": r"legitim", "lärarbehörighet": r"lärarleg|behörig", "certifiering enligt lag": r"certifi|behörig|auktoris",
            "säkerhetsprövning": r"säkerhetsprövad|säkerhetsklass", "medborgarskap": r"medborgar"}[k["krav"]]
    return bool(re.search(ord_, txt))


NIVA = re.compile(r"\b(senior|chef|lead|ledare|head of|manager|ansvarig|director|principal|direktör)\b", re.I)


def ar_erfarenhet(fakta):
    starter = [r.get("start") for r in (fakta or {}).get("roller") or [] if r.get("start")]
    if not starter:
        return None
    try:
        return _dt.date.today().year - int(min(starter)[:4])
    except ValueError:
        return None


def strackorsak(titel, text, fakta):
    roller = sorted((fakta or {}).get("roller") or [], key=lambda r: r.get("start") or "", reverse=True)
    nu = roller[0].get("titel") if roller else ""
    nu = " ".join(nu.values()) if isinstance(nu, dict) else (nu or "")
    m = NIVA.search(titel or "")
    if m and not NIVA.search(nu):
        return f"'{m.group(1).lower()}' i titeln, ett steg upp"
    e = re.search(r"(minst|över|mer än)\s+(\d{1,2})\s+års", (text or "").lower())
    har = ar_erfarenhet(fakta)
    if e and har is not None and int(e.group(2)) > har:
        return f"önskar {e.group(2)} års erfarenhet, du har cirka {har}"
    return None


def etikett(p, sk):
    har = sk.get("kompetens_traff") or []
    rad1 = ("Du har: " + ", ".join(har[:4]) + " – det efterfrågas.") if har else ""
    if sk.get("uteslutet"):
        return "Svag", "Utesluten: " + "; ".join(sk["uteslutet"])
    if sk.get("granbrott"):
        b = "; ".join(sk["granbrott"])
        return (f"Bryter mot din gräns: {b}",
                "\n".join(filter(None, [rad1, f"Bryter mot din gräns: {b}. Du avgör själv om det är värt det."])))
    if sk.get("hart_krav_saknas"):
        x = ", ".join(sk["hart_krav_saknas"])
        return f"Möjlig – kolla {x}", "\n".join(filter(None, [rad1, f"Hårt krav som inte syns i faktabanken: {x}."]))
    if sk.get("strackjobb") and p >= 50:
        return "Sträckjobb – sök!", "\n".join(filter(None, [rad1 or "Riktningen stämmer.", f"Ett steg upp ({sk['strackjobb']}); annonser är önskelistor."]))
    andel = sk.get("kompetens_andel")
    if p >= 80 and (andel is None or andel >= 0.7):
        return "Stark matchning", rad1 or "Riktning, ort och villkor stämmer."
    if p >= 50:
        return "Bra matchning – värd att söka", rad1 or "Riktning och villkor stämmer; resten är önskelista."
    return "Svag", rad1 or "Lite som pekar åt ditt håll."


def las_arbetsgivarkort(home):
    ut = {}
    for f in glob.glob(sc.sokv(home, "arbetsgivare", "*.json")):
        k = sc.las_json(f) or {}
        if k.get("orgnr"):
            ut[str(k["orgnr"]).replace("-", "")] = k
        if k.get("arbetsgivare"):
            ut[sc.norm(k["arbetsgivare"])] = k
    return ut


STOPP = {"och", "att", "med", "för", "som", "det", "den", "inte", "eller", "till", "från", "över", "under",
         "mycket", "lite", "andra", "egen", "eget", "egna", "kunna", "känna", "vara", "jobba", "arbeta"}


def _fraser(lista):
    """Fritextfraser -> [(fras, [ordstammar])]."""
    ut = []
    for f in lista or []:
        if isinstance(f, dict):
            f = f.get("namn") or f.get("text") or ""
        ord_ = [w[:6] for w in sc.re.findall(r"[\wåäö]+", str(f).lower()) if len(w) >= 4 and w not in STOPP]
        if ord_:
            ut.append((str(f), ord_))
    return ut


def joker_poang(r, text, fraser, sokord):
    tokens = set(w[:6] for w in sc.re.findall(r"[\wåäö]+", " ".join([r["titel"] or "", r["utdrag"] or "", text or ""]).lower()))
    traff = [f for f, st in fraser if any(s in tokens for s in st)]
    allt = " ".join([(r["titel"] or ""), (r["utdrag"] or ""), (text or "")]).lower()
    traff += [s for s in sokord if s in allt]
    return 10 * len(traff), traff


def score(home, alla=False, med_enrich=False, jokrar=0, min_poang=50, arbetsgivarkort=False, arbetsgivare_vikt=0):
    pref = sc.las_json(os.path.join(home, "profil", "preferenser.json")) or {}
    c = sc.db(home)
    rapport = {"preferenser": bool(pref)}
    if med_enrich:
        try:
            rapport["berikade"] = enrich(home, c)
        except (sc.NatFel, sc.HttpFel) as e:
            rapport["berikning_fel"] = str(e)
    P = forbered(pref, home)
    P["fakta"] = sc.las_json(os.path.join(home, "profil", "fakta.json")) or {}
    P["arbetsgivare_vikt"] = arbetsgivare_vikt or 0
    if arbetsgivarkort or arbetsgivare_vikt:
        P["arbetsgivarkort"] = las_arbetsgivarkort(home)
    villk = "" if alla else "WHERE status IN ('ny','intressant')"
    rows = c.execute(f"SELECT * FROM jobb {villk}").fetchall()
    fraser = _fraser((pref.get("arbetsdag") or {}).get("energigivare")) + _fraser(pref.get("varden_topp5"))
    kandidater = []
    for r in rows:
        text = sc.las_text(home, r["text_hash"]) or ""
        p, sk = poang(r, P, text)
        if jokrar and not sk["uteslutet"] and p < min_poang and r["dubblett_av"] is None:
            jp, traff = joker_poang(r, text, fraser, P["sokord"])
            if jp:
                kandidater.append((jp, p, r["uid"], traff, sk))
        c.execute("UPDATE jobb SET poang=?, poang_skal_json=? WHERE uid=?",
                  (p, json.dumps(sk, ensure_ascii=False), r["uid"]))
    if jokrar:
        kandidater.sort(key=lambda x: (-x[0], -x[1], x[2]))
        rapport["jokrar"] = []
        for jp, p, uid, traff, sk in kandidater[:jokrar]:
            sk["joker"] = True
            sk["joker_traff"] = traff
            c.execute("UPDATE jobb SET poang_skal_json=? WHERE uid=?", (json.dumps(sk, ensure_ascii=False), uid))
            rapport["jokrar"].append({"uid": uid, "poang": p, "joker_poang": jp, "traff": traff})
    c.commit()
    rapport["poangsatta"] = len(rows)
    return rapport


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enrich", action="store_true")
    ap.add_argument("--alla", action="store_true")
    ap.add_argument("--jokrar", type=int, default=0)
    ap.add_argument("--min-poang", type=int, default=50)
    ap.add_argument("--arbetsgivarkort", action="store_true", help="läs cachade kort i sok/arbetsgivare/ (flaggor)")
    ap.add_argument("--arbetsgivare-vikt", type=int, default=0, help="delpoäng arbetsgivare, standard 0 (av)")
    sc.add_home_arg(ap)
    a = ap.parse_args()
    print(json.dumps(score(sc.hem(a.home), a.alla, a.enrich, a.jokrar, a.min_poang, a.arbetsgivarkort,
                           a.arbetsgivare_vikt), ensure_ascii=False))


if __name__ == "__main__":
    main()
