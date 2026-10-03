#!/usr/bin/env python3
"""Arbetsgivarkort: vad går att veta om en arbetsgivare innan hon söker, och vad måste hon fråga om?

  python3 arbetsgivarkort.py bygg <arbetsgivare|orgnr> [--annons UID] [--orgnr NR] [--typ kommun|region|stat|privat|ideell]
                                  [--ar 5] [--cision SLUG] [--arsredovisning URL|FIL] [--utan-nat] [--home DIR]
  python3 arbetsgivarkort.py satt <slug> --falt glassdoor|linkedin_stannar|personer_att_fraga|egna_intryck --text '...'
  python3 arbetsgivarkort.py visa <slug>

Skriver sok/arbetsgivare/<slug>.json (schema: arbetsgivarkort). Varje block har `kalla` {typ, url, datum,
parametrar} och `status` (auto | manuellt | saknas | kraver_nyckel | fel | ej_tillampligt).

Huvudspåret fungerar för ALLA arbetsgivare:
  rekrytering   JobTech Historical: annonser per år, roller som annonseras om och om igen (OSÄKER signal
                om personalomsättning; stora arbetsgivare annonserar samma roll ofta bara för att de är stora).
  annonssprak   Ord- och temalistor (prestation/tävling–samarbete/omsorg, autonomi–kontroll, tempo m.fl.).
                SJÄLVBESKRIVNING: säger vad arbetsgivaren säger om sig själv, inte hur det är (Gaucher 2011,
                He & Kang 2025). Mappas mot kultursatserna i karriarcoach/references/kultur-qsort.md om den
                finns, annars mot sex OCP-dimensioner.
  ekonomi       Bolagsverkets API för värdefulla datamängder (digitala årsredovisningar, iXBRL): medelantal
                anställda, omsättning, resultat över år. Kräver gratis API-nyckel:
                JOBBSOK_BOLAGSVERKET_ID och JOBBSOK_BOLAGSVERKET_SECRET. Utan nyckel: status kraver_nyckel.
                allabolag.se används inte automatiskt (villkor).
  press         Cision-nyhetsrum (news.cision.com/se/<slug>): omorganisation, varsel, ny vd, förvärv, tillväxt.
  manuellt      Glassdoor, LinkedIn (hur länge folk stannar), personer att fråga, egna intryck. Bevaras vid ombyggnad.
  okant         Allt som inte gick att ta reda på blir intervjufrågor (till chef, kollega, HR eller nätverket).
  matchning     Mot preferenser.kultur_ideal, ledarskap_krav och varningssignaler: stämmer / skaver / okänt.
                Ingen totalpoäng. Varningssignaler blir flaggor, aldrig uteslutning.
Litet tillägg för offentliga: Kolada v3 (HME och sjukfrånvaro för kommun/region, med trend och rikssnitt)
och, för statliga myndigheter, sjukfrånvaro ur årsredovisningen (förordning 2000:605 7 kap 3 §) via
pdftotext om en PDF-länk ges med --arsredovisning; annars manuellt.

Nätfel i en delkälla stoppar inte kortet: blocket får status "fel" och en fråga i `okant`.
"""
import argparse
import collections
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jakt_common as jc  # noqa: E402
import jobbsok_common as jbc  # noqa: E402
import sok_common as sc  # noqa: E402

KOLADA = "https://api.kolada.se/v3"
BV_TOKEN = "https://portal.api.bolagsverket.se/oauth2/token"
BV_API = "https://gw.api.bolagsverket.se/vardefulla-datamangder/v1"
CISION = "https://news.cision.com/se/"
PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QSORT = os.path.join(PLUGIN, "skills", "karriarcoach", "references", "kultur-qsort.md")
SJALVBESKRIVNING = ("Annonsspråk är arbetsgivarens självbeskrivning: vad de säger om sig själva, inte hur det är "
                    "att jobba där (Gaucher m.fl. 2011; He & Kang 2025). Använd som underlag för frågor.")


# ---------------------------------------------------------------- nät (patchas i testerna)

def hamta_json(url, method="GET", data=None, headers=None):
    _, d, _ = sc.http_json(url, method=method, data=data, headers=headers)
    return d


def hamta_text(url):
    _, t, _ = sc.http(url)
    return t


def hamta_bytes(url, headers=None):
    h = {"User-Agent": sc.USER_AGENT}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise sc.HttpFel(e.code, url)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise sc.NatFel(str(e))


def kalla(typ, url=None, parametrar=None):
    return {"typ": typ, "url": url, "parametrar": parametrar or {}, "datum": sc.idag()}


# ---------------------------------------------------------------- typ

def norm_orgnr(s):
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else None


def avgor_typ(namn, orgnr):
    """kommun | region | stat | privat | ideell, plus hur det avgjordes."""
    n = (namn or "").lower()
    o = norm_orgnr(orgnr) or ""
    if o.startswith("2120"):
        return ("region" if re.search(r"\bregion\b|landsting", n) else "kommun"), "orgnr 212000-…"
    if o.startswith("2321"):
        return "region", "orgnr 232100-…"
    if o.startswith("2021") or o.startswith("2022"):
        return "stat", "orgnr 202100-… (statlig myndighet)"
    if o[:1] == "8" or o[:2] == "71":
        return "ideell", "orgnr 8…/71… (förening/stiftelse)"
    if o[:1] in ("5", "9"):
        return "privat", "orgnr 5…/9… (bolag/handelsbolag)"
    if re.search(r"\bkommun\b|\bstad\b", n):
        return "kommun", "namn"
    if re.search(r"^region\b|\bregion \w+$|landsting", n):
        return "region", "namn"
    if re.search(r"myndighet|verket\b|inspektion|universitet|högskola|försäkringskassan|polisen|domstol|"
                 r"länsstyrelse|statens|kammarkollegiet|\bivo\b|\bslu\b", n):
        return "stat", "namn"
    if re.search(r"förening|stiftelse|förbund|ideell", n):
        return "ideell", "namn"
    return "privat", "antagande (inget offentligt mönster i namn/orgnr)"


# ---------------------------------------------------------------- JobTech Historical

def _ar_intervall(ar):
    return f"{ar}-01-01T00:00:00", f"{ar}-12-31T23:59:59"


def hitta_orgnr(namn):
    _, hits = jc.traffar(jc.HISTORICAL, {"q": namn, "historical-from": jc.ar_sedan(3)}, 100)
    n, namnet = collections.Counter(), {}
    nb = sc.norm(namn)
    for h in hits:
        e = h.get("employer") or {}
        o = norm_orgnr(e.get("organization_number"))
        en = sc.norm(e.get("name"))
        if o and en and (nb in en or en in nb):
            n[o] += 1
            namnet[o] = e.get("name")
    if not n:
        return None, None
    o = n.most_common(1)[0][0]
    return o, namnet[o]


def rekrytering(orgnr, antal_ar=5, roll=None, max_hits=500):
    idag = dt.date.today()
    per_ar = []
    for ar in range(idag.year - antal_ar, idag.year + 1):
        fr, til = _ar_intervall(ar)
        d = jc.api(jc.HISTORICAL, {"employer": orgnr, "historical-from": fr, "historical-to": til, "limit": 0}) or {}
        per_ar.append({"ar": ar, "annonser": d.get("total", {}).get("value", 0), "hela_aret": ar < idag.year})
    fran = f"{idag.year - 3}-01-01T00:00:00"
    _, hits = jc.traffar(jc.HISTORICAL, {"employer": orgnr, "historical-from": fran}, max_hits)
    titlar = collections.defaultdict(list)
    for h in hits:
        t = jc.rubrik_till_titel(h.get("headline")) or sc.norm((h.get("occupation") or {}).get("label"))
        if t:
            titlar[t].append((h.get("publication_date") or "")[:10])
    upprepade = []
    for t, datum in titlar.items():
        halvar = {d[:4] + ("a" if d[5:7] < "07" else "b") for d in datum if d}
        if len(datum) >= 3 and len(halvar) >= 2:
            upprepade.append({"titel": t, "annonser": len(datum), "halvar": len(halvar),
                              "forsta": min(datum), "senaste": max(datum)})
    upprepade.sort(key=lambda x: (-x["halvar"], -x["annonser"], x["titel"]))
    hela = [p for p in per_ar if p["hela_aret"]]
    trend = None
    if len(hela) >= 2 and hela[-2]["annonser"]:
        f = (hela[-1]["annonser"] - hela[-2]["annonser"]) / hela[-2]["annonser"]
        trend = "okar" if f > 0.15 else "minskar" if f < -0.15 else "stabil"
    egen_roll = None
    if roll:
        r = jc.rubrik_till_titel(roll) or sc.norm(roll)
        d = sorted(titlar.get(r, []))
        egen_roll = {"titel": r, "annonser_3ar": len(d), "datum": d[-10:]}
    return {
        "status": "auto",
        "per_ar": per_ar,
        "trend_senaste_hela_ar": trend,
        "underlag_3ar": len(hits),
        "upprepade_roller": upprepade[:10],
        "annonserad_roll": egen_roll,
        "osakert": True,
        "tolkning": ("Samma roll som annonseras om och om igen KAN betyda hög personalomsättning, men också "
                     "tillväxt, många likadana tjänster eller vikariat. Stora arbetsgivare annonserar samma roll "
                     "ofta bara för att de är stora. Jämför mot antal anställda och fråga."),
        "kalla": kalla("jobtech_historical", jc.HISTORICAL, {"employer": orgnr, "ar": antal_ar}),
    }, hits


# ---------------------------------------------------------------- annonsspråk

TEMAN = {
    "prestation_tavling": ["results-driven", "ambitious", "competitive", "high-performing", "target", "resultatorient", "resultatdriv", "prestation", "tävling", "konkurren", "vinna", "vinnar",
                           "ambitiös", "driven", "målinriktad", "målorient", "leverera", "framgång", "bäst",
                           "säljmål", "high perform", "ledande", "excellens"],
    "samarbete_omsorg": ["collaborat", "together", "supportive", "caring", "inclusive", "team player", "samarbet", "tillsammans", "kollegor", "lagspel", "teamkänsla", "stöttande", "stödjande",
                         "omtänksam", "omtanke", "gemenskap", "lyhörd", "inkluderande", "välkomnande", "hjälpsam",
                         "trygg", "förstående", "laganda"],
    "autonomi": ["autonom", "independen", "ownership", "freedom", "self-driven", "självständig", "eget ansvar", "stort ansvar", "frihet", "påverka", "mandat", "egna initiativ",
                 "eget initiativ", "förtroende", "självgående", "flexib", "möjlighet att forma"],
    "kontroll": ["routines", "guidelines", "compliance", "procedures", "accurate", "regulat", "rutiner", "riktlinjer", "noggrann", "struktur", "följa upp", "regelverk", "processer", "kontroll",
                 "rapportera", "dokumentation", "ordning", "instruktioner", "lagstiftning", "föreskrifter"],
    "tempo": ["fast-paced", "fast paced", "dynamic", "rapid", "högt tempo", "snabbt tempo", "snabb", "föränderlig", "dynamisk", "intensiv", "full fart",
              "hektisk", "snabbrörlig", "stresstålig", "prestigelös och snabb", "tempofylld", "fart"],
    "stabilitet_balans": ["balans", "långsiktig", "trygg anställning", "friskvård", "flextid", "hållbar",
                          "arbetsmiljö", "kollektivavtal", "förmåner", "semester"],
    "innovation": ["innovati", "creative", "cutting-edge", "curious", "innovat", "nytänk", "kreativ", "experiment", "testa nya", "utvecklingsarbete", "förändringsresa",
                   "digitaliser", "framåt", "nyfiken", "pionjär"],
    "mening_uppdrag": ["samhälle", "uppdrag", "göra skillnad", "meningsfull", "nytta", "invånare", "patient",
                       "medborgare", "hållbarhet", "värdegrund", "människor"],
}
AXLAR = [("prestation_tavling", "samarbete_omsorg"), ("autonomi", "kontroll"), ("tempo", "stabilitet_balans")]
OCP = {  # sex OCP-dimensioner (O'Reilly m.fl. 1991, förenklad) <- teman
    "innovation": ["innovation"],
    "stabilitet": ["stabilitet_balans", "kontroll"],
    "manniskoorientering": ["samarbete_omsorg", "mening_uppdrag"],
    "resultatorientering": ["prestation_tavling"],
    "detaljorientering": ["kontroll"],
    "teamorientering": ["samarbete_omsorg"],
}
# Nyckelord för att koppla en kultursats (fritext) till teman.
TEMA_NYCKEL = {
    "prestation_tavling": ["resultat", "prestation", "tävl", "vinn", "konkurr", "mål", "ambiti", "mäts"],
    "samarbete_omsorg": ["samarbet", "tillsammans", "kolleg", "omsorg", "omtank", "stött", "hjälp", "team", "trygg", "gemenskap"],
    "autonomi": ["frihet", "självständ", "ansvar", "påverk", "mandat", "autonom", "själv"],
    "kontroll": ["regler", "rutin", "kontroll", "struktur", "process", "hierarki", "detalj", "noggrann", "tydlig"],
    "tempo": ["tempo", "snabb", "stress", "fart", "intensiv", "press"],
    "stabilitet_balans": ["balans", "stabil", "lugn", "förutsäg", "långsiktig", "hållbar"],
    "innovation": ["innovat", "nytt", "nya", "experiment", "förändr", "kreativ", "utveckl"],
    "mening_uppdrag": ["mening", "samhäll", "nytta", "uppdrag", "skillnad", "värde", "syfte"],
}


def las_qsort(sokvag=None):
    """Kultursatser {id: text} ur kultur-qsort.md (rader med s1..s18). Tom dict om filen saknas."""
    sokvag = sokvag or QSORT
    try:
        txt = open(sokvag, encoding="utf-8").read()
    except OSError:
        return {}
    satser = {}
    for rad in txt.splitlines():
        celler = [c.strip() for c in rad.strip().strip("|").split("|")]
        if len(celler) >= 3 and re.fullmatch(r"s\d{1,2}", celler[0]) and celler[0] not in satser:
            satser[celler[0]] = f"{celler[1]} [{celler[2]}]"  # [dimension] styr temat
            continue
        m = re.search(r"\b(s\d{1,2})\b\W{0,6}\s*(.{8,})", rad)
        if m and m.group(1) not in satser:
            satser[m.group(1)] = re.sub(r"[*`|]+", " ", m.group(2)).strip()
    return satser


DIMENSION_TEMA = {
    "innovation": ["innovation"], "resultat": ["prestation_tavling"], "konkurrens": ["prestation_tavling"],
    "detalj": ["kontroll"], "stabilitet": ["stabilitet_balans"], "samarbete": ["samarbete_omsorg"],
    "stödjande": ["samarbete_omsorg"], "belöning": ["prestation_tavling"], "autonomi": ["autonomi"],
    "gränser": ["stabilitet_balans"], "balans": ["stabilitet_balans"], "socialt ansvar": ["mening_uppdrag"],
    "kund": ["mening_uppdrag"], "integritet": [],
}


def teman_for_text(t):
    t = (t or "").lower()
    dim = re.search(r"\[([^\]]+)\]\s*$", t)
    if dim:  # sats ur kultur-qsort.md: dimensionskolumnen gäller
        ut = []
        for d in re.split(r"[/,]", dim.group(1)):
            ut += [x for x in DIMENSION_TEMA.get(d.strip(), []) if x not in ut]
        return ut
    return [tema for tema, ord_ in TEMA_NYCKEL.items() if any(o in t for o in ord_)]


def annonssprak(texter, egen=None):
    """texter: lista med annonstexter. egen: den annons hon tittar på (vägs dubbelt)."""
    alla = list(texter) + ([egen, egen] if egen else [])
    ordantal = sum(len(re.findall(r"\w+", t or "")) for t in alla) or 1
    teman = {}
    for tema, ord_ in TEMAN.items():
        c = collections.Counter()
        for t in alla:
            lt = (t or "").lower()
            for o in ord_:
                n = len(re.findall(r"\b" + re.escape(o), lt))
                if n:
                    c[o] += n
        tot = sum(c.values())
        teman[tema] = {"traffar": tot, "per_1000_ord": round(1000 * tot / ordantal, 2),
                       "ord": [o for o, _ in c.most_common(5)]}
    axlar = []
    for a, b in AXLAR:
        x, y = teman[a]["traffar"], teman[b]["traffar"]
        lut = None if x + y < 3 else round((x - y) / (x + y), 2)
        axlar.append({"axel": f"{a}–{b}", "lutning": lut,
                      "lasning": ("för lite underlag" if lut is None else
                                  f"lutar mot {a}" if lut > 0.25 else f"lutar mot {b}" if lut < -0.25 else "balanserad")})
    ocp = {d: round(sum(teman[t]["per_1000_ord"] for t in ts) / len(ts), 2) for d, ts in OCP.items()}
    satser = las_qsort()
    mappning = {"mot": "kultur-qsort" if satser else "ocp"}
    if satser:
        rang = sorted(teman, key=lambda k: -teman[k]["per_1000_ord"])
        starka = [k for k in rang[:3] if teman[k]["traffar"]]
        svaga = [k for k in rang[-3:] if k not in starka]
        mappning["antyder_topp"] = sorted({s for s, txt in satser.items() if set(teman_for_text(txt)) & set(starka)})
        mappning["antyder_botten"] = sorted({s for s, txt in satser.items() if set(teman_for_text(txt)) & set(svaga)}
                                            - set(mappning["antyder_topp"]))
    else:
        mappning["dimensioner"] = ocp
    agentiska = teman["prestation_tavling"]["traffar"]
    kommunala = teman["samarbete_omsorg"]["traffar"]
    egen_l = (egen or "").lower()
    return {
        "status": "auto" if texter or egen else "saknas",
        "sjalvbeskrivning": True,
        "varning": SJALVBESKRIVNING,
        "underlag": {"annonser": len(texter) + (1 if egen else 0), "ord": ordantal, "egen_annons": bool(egen)},
        "teman": teman,
        "axlar": axlar,
        "agentiska_vs_kommunala": {"agentiska": agentiska, "kommunala": kommunala},
        "lon_angiven": bool(re.search(r"\d[\d\s]{3,}\s*(kr|sek)|lön(e)?(spann|intervall|nivå)\s*:?\s*\d", egen_l)) if egen else None,
        "chef_namngiven": bool(re.search(r"(närmaste chef|chef|kontaktperson)[^.\n]{0,40}\b[A-ZÅÄÖ][a-zåäö]+ [A-ZÅÄÖ][a-zåäö]+",
                                         egen or "")) if egen else None,
        "mappning": mappning,
        "kalla": kalla("annons", None, {"metod": "ord- och temalistor, deterministisk"}),
    }


# ---------------------------------------------------------------- Bolagsverket (iXBRL)

IXBRL_FALT = {
    "anstallda": ["MedelantaletAnstallda"],
    "omsattning": ["Nettoomsattning", "RorelsensIntakter"],
    "resultat": ["AretsResultat"],
}


def ixbrl_varden(html_text):
    """Plockar medelantal anställda, omsättning och resultat ur en iXBRL-årsredovisning.

    Returnerar {falt: {contextRef: varde}} och {contextRef: period-slut}."""
    ut = collections.defaultdict(dict)
    for m in re.finditer(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", html_text, re.S | re.I):
        attr, inner = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        nm = re.search(r'name="[^":]*:([^"]+)"', attr)
        ctx = re.search(r'contextRef="([^"]+)"', attr)
        if not nm or not ctx:
            continue
        for falt, namn in IXBRL_FALT.items():
            if nm.group(1) in namn and ctx.group(1) not in ut[falt]:
                s = re.sub(r"[^\d,.-]", "", inner).replace(" ", "")
                s = s.replace(".", "").replace(",", ".") if "," in s else s.replace(".", "")
                try:
                    v = float(s)
                except ValueError:
                    continue
                sk = re.search(r'scale="(-?\d+)"', attr)
                if sk:
                    v *= 10 ** int(sk.group(1))
                if re.search(r'sign="-"', attr):
                    v = -v
                ut[falt][ctx.group(1)] = int(v) if v == int(v) else v
    perioder = {}
    for m in re.finditer(r'<xbrli:context\b[^>]*id="([^"]+)"[^>]*>(.*?)</xbrli:context>', html_text, re.S | re.I):
        e = re.search(r"<xbrli:(?:endDate|instant)>([\d-]+)<", m.group(2))
        if e:
            perioder[m.group(1)] = e.group(1)
    return dict(ut), perioder


def bolagsverket_token():
    cid, sec = os.environ.get("JOBBSOK_BOLAGSVERKET_ID"), os.environ.get("JOBBSOK_BOLAGSVERKET_SECRET")
    if not cid or not sec:
        return None
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cid, "client_secret": sec,
                                   "scope": "vardefulla-datamangder:read vardefulla-datamangder:ping"}).encode()
    req = urllib.request.Request(BV_TOKEN, data=body, headers={"Content-Type": "application/x-www-form-urlencoded",
                                                               "User-Agent": sc.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("access_token")
    except urllib.error.HTTPError as e:
        raise sc.HttpFel(e.code, BV_TOKEN)
    except (urllib.error.URLError, OSError) as e:
        raise sc.NatFel(str(e))


def ekonomi(orgnr, typ, max_ar=5):
    k = kalla("bolagsverket_ixbrl", BV_API, {"orgnr": orgnr})
    if typ in ("kommun", "region", "stat"):
        return {"status": "ej_tillampligt", "kalla": k, "anteckning": "Offentlig sektor lämnar inte årsredovisning till Bolagsverket."}
    if not orgnr:
        return {"status": "saknas", "kalla": k, "anteckning": "Orgnr saknas."}
    tok = bolagsverket_token()
    if not tok:
        return {"status": "kraver_nyckel", "kalla": k,
                "anteckning": ("Bolagsverkets API för värdefulla datamängder är gratis men kräver API-nyckel "
                               "(registrera klient på bolagsverket.se, sätt JOBBSOK_BOLAGSVERKET_ID och "
                               "JOBBSOK_BOLAGSVERKET_SECRET). Till dess: läs årsredovisningen manuellt; "
                               "allabolag.se används inte automatiskt.")}
    hd = {"Authorization": f"Bearer {tok}"}
    lista = hamta_json(BV_API + "/dokumentlista", method="POST", data={"identitetsbeteckning": orgnr}, headers=hd) or {}
    dok = sorted(lista.get("dokument", []), key=lambda d: d.get("rapporteringsperiodTom", ""), reverse=True)[:max_ar]
    serie = {}
    for d in dok:
        raw = hamta_bytes(f"{BV_API}/dokument/{d.get('dokumentId')}", hd)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                html_text = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                                    if n.lower().endswith((".xhtml", ".html")))
        except zipfile.BadZipFile:
            html_text = raw.decode("utf-8", "replace")
        varden, perioder = ixbrl_varden(html_text)
        for falt, per_ctx in varden.items():
            for ctx, v in per_ctx.items():
                slut = perioder.get(ctx) or d.get("rapporteringsperiodTom") or ""
                serie.setdefault(slut[:4], {"ar": slut[:4]}).setdefault(falt, v)
    rader = [serie[a] for a in sorted(serie) if a]
    anst = [r.get("anstallda") for r in rader if r.get("anstallda") is not None]
    utv = None
    if len(anst) >= 2 and anst[0]:
        f = (anst[-1] - anst[0]) / anst[0]
        utv = "vaxer" if f > 0.1 else "krymper" if f < -0.1 else "stabil"
    return {"status": "auto" if rader else "saknas", "per_ar": rader, "anstallda_utveckling": utv, "kalla": k,
            "anteckning": "Digitala årsredovisningar finns bara för bolag som lämnat in digitalt (främst K2/K3 från 2019–)."}


# ---------------------------------------------------------------- Cision

PRESS = {
    "omorganisation": r"omorganis|ny organisation|organisationsförändring|förändrad organisation|ny ledningsgrupp",
    "varsel": r"varsel|varslar|neddragning|uppsägning|sparprogram|besparing|effektiviseringsprogram|personalminskning",
    "ny_vd": r"\bny vd\b|utses till vd|utsedd till vd|ny verkställande|tillförordnad vd|vd lämnar|vd avgår|lämnar sin post",
    "forvarv": r"förvärv|förvärvar|köper\b|uppköp|fusion|går samman|offentligt uppköpserbjudande|avyttr",
    "tillvaxt": r"rekryterar|expanderar|nytt kontor|etablerar|öppnar|växer|nyanställ|ny fabrik",
}


def cision_slug(namn):
    s = re.sub(r"\b(ab|publ|aktiebolag|sverige|group|koncernen)\b", " ", (namn or "").lower())
    return jbc.slugify(s, 60)


def press(namn, slug=None):
    slug = slug or cision_slug(namn)
    url = CISION + slug
    k = kalla("cision", url, {"slug": slug})
    if not sc.robots_tillater(url):
        return {"status": "saknas", "kalla": k, "anteckning": "robots.txt tillåter inte hämtning."}
    try:
        html_text = hamta_text(url)
    except sc.HttpFel as e:
        return {"status": "saknas", "kalla": k, "signaler": [], "anteckning":
                f"Inget nyhetsrum på Cision under '{slug}' (HTTP {e.status}). Ange --cision SLUG om du hittar det."}
    poster = []
    for m in re.finditer(r'<a href="(https://news\.cision\.com/se/[^"]+/r/[^"]+)"[^>]*>\s*<h2>(.*?)</h2>\s*'
                         r'<time[^>]*datetime="([^"]+)"', html_text, re.S):
        titel = sc.html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        poster.append({"datum": m.group(3)[:10], "titel": titel, "url": m.group(1)})
    signaler = []
    for p in poster:
        kat = [k_ for k_, rx in PRESS.items() if re.search(rx, p["titel"].lower())]
        if kat and p["datum"] >= jc.ar_sedan(3):
            signaler.append(dict(p, kategorier=kat))
    return {"status": "auto" if poster else "saknas", "kalla": k, "antal_pressmeddelanden": len(poster),
            "signaler": signaler[:15],
            "anteckning": "Bara rubriker på första sidan i nyhetsrummet, senaste tre åren. En rubrik är en signal att fråga om, inte ett facit."}


# ---------------------------------------------------------------- Kolada (kommun, region)

KOLADA_KPI = {
    "kommun": {"total": "U00200", "motivation": "U00201", "ledarskap": "U00202", "styrning": "U00203",
               "sjukfranvaro_pct": "N00090", "andel_langa_pct": "N00091"},
    "region": {"total": "U60200", "motivation": "U60201", "ledarskap": "U60202", "styrning": "U60203",
               "sjukfranvaro_pct": "N60030", "andel_langa_pct": "N60031"},
}


def kolada_id(namn, typ):
    d = hamta_json(f"{KOLADA}/municipality?" + urllib.parse.urlencode({"title": re.sub(r"(?i)\b(kommun|region|stad)\b", "", namn).strip()})) or {}
    want = "L" if typ == "region" else "K"
    for v in d.get("values", []):
        if v.get("type") == want:
            return v["id"], v["title"]
    return None, None


def kolada_serie(kpi, mid):
    d = hamta_json(f"{KOLADA}/data/kpi/{kpi}/municipality/{mid}") or {}
    ut = []
    for p in d.get("values", []):
        t = [v.get("value") for v in p.get("values", []) if v.get("gender") == "T"]
        if t and t[0] is not None:
            ut.append({"ar": p["period"], "varde": round(t[0], 1)})
    return sorted(ut, key=lambda x: x["ar"])


def kolada(namn, typ):
    if typ not in KOLADA_KPI:
        return {"status": "ej_tillampligt"}
    mid, titel = kolada_id(namn, typ)
    if not mid:
        return {"status": "saknas", "kalla": kalla("kolada", KOLADA), "anteckning": f"Hittade inte {namn} i Kolada."}
    ut = {"status": "auto", "kolada_id": mid, "kolada_namn": titel, "matt": {}}
    for falt, kpi in KOLADA_KPI[typ].items():
        s = kolada_serie(kpi, mid)
        riket = kolada_serie(kpi, "0000")
        senaste = s[-1] if s else None
        r_ar = {x["ar"]: x["varde"] for x in riket}
        trend = None
        if len(s) >= 3:
            dv = s[-1]["varde"] - s[-3]["varde"]
            trend = "upp" if dv > 0.5 else "ner" if dv < -0.5 else "stabil"
        ut["matt"][falt] = {"senaste": senaste, "serie": s[-6:], "trend_3_matningar": trend,
                            "riket_samma_ar": r_ar.get(senaste["ar"]) if senaste else None,
                            "kalla": kalla("kolada", f"{KOLADA}/data/kpi/{kpi}/municipality/{mid}", {"kpi": kpi})}
    ut["anteckning"] = ("HME gäller hela organisationen, inte din enhet. Högre HME är bättre; för sjukfrånvaro är lägre "
                        "bättre. Rikssnitt saknas i Kolada för HME (null).")
    return ut


# ---------------------------------------------------------------- statlig årsredovisning

def sjukfranvaro_ur_text(txt):
    """Första 'total sjukfrånvaro … X,Y %' i årsredovisningstext. Returnerar (värde, rad) eller (None, None)."""
    rader = [r.strip() for r in txt.splitlines()]
    # Vanligast: tabell "Sjukfrånvaro i procent  2025 2024 2023" följd av "Totalt 3,76 4,65 4,48".
    for i, r in enumerate(rader):
        ar = re.findall(r"\b(20\d\d)\b", r)
        if re.search(r"(?i)sjukfrånvaro", r) and ar:
            for r2 in rader[i + 1:i + 6]:
                if re.match(r"(?i)total(t|a)?\b", r2):
                    tal = re.findall(r"\d{1,2}[,.]\d{1,2}", r2)
                    if tal:
                        return float(tal[0].replace(",", ".")), f"{ar[0]}: {r2[:150]}"
    for i, r in enumerate(rader):
        if re.search(r"(?i)total(a)? sjukfrånvaro|sjukfrånvaro,? totalt|sjukfrånvaro totalt", r):
            fonster = " ".join(rader[i:i + 3])
            m = re.search(r"(\d{1,2}[,.]\d)\s*%?", fonster[fonster.lower().find("sjukfrånvaro"):])
            if m:
                return float(m.group(1).replace(",", ".")), fonster[:200]
    return None, None


def stat_arsredovisning(namn, kallfil=None):
    k = kalla("arsredovisning", kallfil, {"forordning": "2000:605 7 kap 3 §"})
    bas = {"kalla": k, "anteckning": "Myndigheter ska redovisa sjukfrånvaro i årsredovisningen (förordning 2000:605 7 kap 3 §)."}
    if not kallfil:
        return dict(bas, status="manuellt", sjukfranvaro_pct=None,
                    att_gora=f"Sök '{namn} årsredovisning pdf' och kör om med --arsredovisning <url>.")
    if not shutil.which("pdftotext"):
        return dict(bas, status="manuellt", sjukfranvaro_pct=None, att_gora="pdftotext saknas; läs siffran manuellt.")
    with tempfile.TemporaryDirectory() as td:
        pdf = kallfil
        if re.match(r"https?://", kallfil):
            pdf = os.path.join(td, "ar.pdf")
            with open(pdf, "wb") as f:
                f.write(hamta_bytes(kallfil))
        r = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True)
    v, rad = sjukfranvaro_ur_text(r.stdout or "")
    if v is None:
        return dict(bas, status="manuellt", sjukfranvaro_pct=None, att_gora="Hittade ingen siffra i PDF:en; läs den manuellt.")
    return dict(bas, status="auto", sjukfranvaro_pct=v, belagg=rad)


# ---------------------------------------------------------------- preferenser och matchning

def _platta(x):
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    if isinstance(x, dict):
        ut = []
        for k, v in x.items():
            if k in ("topp", "botten", "ideal"):
                continue
            ut += _platta(v)
        return ut
    if isinstance(x, list):
        ut = []
        for v in x:
            if isinstance(v, dict):
                t = v.get("text") or v.get("krav") or v.get("signal") or v.get("namn") or v.get("sats")
                ut += [t] if t else _platta(v)
            else:
                ut += _platta(v)
        return ut
    return [str(x)]


def _stammar(t):
    return [w[:6] for w in re.findall(r"[\wåäö]+", (t or "").lower()) if len(w) >= 4 and w not in
            {"inte", "ingen", "eller", "måste", "vill", "ska", "som", "med", "från", "över", "under", "mycket"}]


def matchning(pref, kort, satser=None):
    satser = satser if satser is not None else las_qsort()
    ki = pref.get("kultur_ideal")
    lk = pref.get("ledarskap_krav")
    vs = pref.get("varningssignaler")
    ut = {"stammer": [], "skaver": [], "okant": [], "varningsflaggor": [],
          "las_sa_har": "Ingen totalpoäng. Annonsspråk är självbeskrivning; stämmer betyder 'de säger så om sig själva'."}
    if ki is None and lk is None and vs is None:
        ut["anteckning"] = "preferenser saknar kultur_ideal, ledarskap_krav och varningssignaler (karriarcoach fyller dem)."
        return ut
    sp = kort.get("annonssprak") or {}
    tem = sp.get("teman") or {}
    snitt = (sum(v["per_1000_ord"] for v in tem.values()) / len(tem)) if tem else 0
    motsats = {}
    for a, b in AXLAR:
        motsats[a], motsats[b] = b, a
    # kultur_ideal: satsid (s12) eller fritext; topp = vill ha, botten = vill inte ha
    ideal = []
    if isinstance(ki, dict):
        ideal += [(s, True) for s in _platta(ki.get("topp") or (ki.get("ideal") or {}).get("topp") or [])]
        ideal += [(s, False) for s in _platta(ki.get("botten") or (ki.get("ideal") or {}).get("botten") or [])]
        ideal += [(s, True) for s in _platta({k: v for k, v in ki.items() if k not in ("topp", "botten", "ideal", "instrument")})]
    else:
        ideal += [(s, True) for s in _platta(ki)]
    for s, vill in ideal:
        text = satser.get(s.strip(), s) if re.fullmatch(r"s\d{1,2}", s.strip()) else s
        tt = teman_for_text(text)
        if not tt or not tem:
            ut["okant"].append({"onskemal": s, "text": text, "varfor": "ingen koppling till annonsspråket"})
            continue
        stark = [t for t in tt if tem[t]["per_1000_ord"] > max(snitt, 0.3)]
        mot = [t for t in tt if motsats.get(t) and tem[motsats[t]]["per_1000_ord"] > max(snitt, 0.3)
               and tem[motsats[t]]["traffar"] > tem[t]["traffar"]]
        post = {"onskemal": s, "text": text, "teman": tt, "kalla": "annonssprak (självbeskrivning)"}
        if vill and stark:
            ut["stammer"].append(dict(post, belagg=[tem[t]["ord"] for t in stark]))
        elif (vill and mot) or (not vill and stark):
            ut["skaver"].append(dict(post, belagg=[tem[t]["ord"] for t in (stark if not vill else [motsats[x] for x in mot])]))
        else:
            ut["okant"].append(dict(post, varfor="annonserna säger lite om detta"))
    # ledarskap_krav: annonser säger nästan aldrig något om chefen; HME-ledarskap om det finns
    hme = (((kort.get("offentligt") or {}).get("kolada") or {}).get("matt") or {}).get("ledarskap") or {}
    if isinstance(lk, dict):
        CHEF = {"tillganglig": "en tillgänglig chef", "ger_riktning": "en chef som ger riktning",
                "ger_frihet": "en chef som ger frihet", "skyddar": "en chef som skyddar teamet",
                "utvecklar": "en chef som utvecklar dig"}
        lk_lista = [CHEF.get(c, c) for c in lk.get("chefsegenskaper_topp3") or []]
        if lk.get("avstamning_frekvens"):
            lk_lista.append(f"avstämning med chefen {lk['avstamning_frekvens'].replace('_', ' ')}")
        lk_lista += _platta(lk.get("krav"))
    else:
        lk_lista = _platta(lk)
    for krav in lk_lista:
        if hme.get("senaste"):
            ut["okant"].append({"onskemal": krav, "varfor": f"HME-ledarskap {hme['senaste']['varde']} ({hme['senaste']['ar']}) "
                                "gäller hela organisationen, inte din chef", "kalla": "kolada"})
        else:
            ut["okant"].append({"onskemal": krav, "varfor": "chefen syns inte i offentliga data"})
    # varningssignaler: sök i annonsord, pressrubriker och rekryteringsmönster
    pool = []
    for t, v in tem.items():
        if v["traffar"] >= 3 and v["per_1000_ord"] > max(snitt, 0.3):  # bara teman som sticker ut
            pool.append((" ".join(v["ord"]) + " " + t.replace("_", " "), f"annonsspråk: {t}"))
    for p in (kort.get("press") or {}).get("signaler", []):
        pool.append((p["titel"] + " " + " ".join(p["kategorier"]), f"press {p['datum']}: {p['titel']}"))
    for r in (kort.get("rekrytering") or {}).get("upprepade_roller", [])[:5]:
        pool.append((f"{r['titel']} återkommande rekrytering omsättning", f"rekrytering: {r['titel']} {r['annonser']} ggr"))
    for v in _platta(vs):
        st = _stammar(v)
        traff = [kalla_ for txt, kalla_ in pool if any(s in txt.lower() for s in st)]
        if traff:
            ut["varningsflaggor"].append({"signal": v, "belagg": traff[:3], "osakert": True})
            ut["skaver"].append({"onskemal": f"varningssignal: {v}", "belagg": traff[:3]})
        else:
            ut["okant"].append({"onskemal": f"varningssignal: {v}", "varfor": "syns inte i data; fråga"})
    return ut


# ---------------------------------------------------------------- okänt -> frågor

def fragor(kort, pref):
    F = []

    def q(fraga, varfor, till, kalla_=None):
        F.append({"fraga": fraga, "varfor": varfor, "till": till, "kalla": kalla_})

    rek = kort.get("rekrytering") or {}
    ar = (kort.get("annonssprak") or {})
    roll = rek.get("annonserad_roll")
    if roll and roll.get("annonser_3ar", 0) >= 3:
        q(f"Jag ser att {roll['titel']} har annonserats {roll['annonser_3ar']} gånger på tre år. Vad hände med dem som "
          "hade rollen innan, och hur länge stannade de?", "upprepad rekrytering kan vara omsättning (osäkert)",
          "chef", "jobtech_historical")
    elif rek.get("upprepade_roller"):
        r = rek["upprepade_roller"][0]
        n_ = rek.get("underlag_3ar")
        del_ = f" av deras senaste {n_} annonser" if n_ else ""
        q(f"{r['titel'].capitalize()} har annonserats {r['annonser']} gånger{del_} (sedan {r['forsta'][:7]}). Hur ser "
          "personalomsättningen ut i teamet, och varför slutar folk?", "upprepad rekrytering (osäker signal)",
          "chef eller blivande kollega", "jobtech_historical")
    q("Hur många har slutat i teamet de senaste två åren, och vart gick de?", "personalomsättning finns inte i öppna data",
      "chef eller blivande kollega")
    q("Berätta om senaste gången någon i teamet sa emot dig eller tog upp ett misstag. Vad hände sedan?",
      "psykologisk trygghet går bara att fråga om", "chef")
    q("Vilka beslut kan jag fatta själv första halvåret, och vilka ska stämmas av?", "autonomi i praktiken, inte i annonsen",
      "chef")
    q("Hur ofta har ni avstämning, och vad pratar ni om då?", "chefens närvaro och stil", "chef")
    q("Hur ser en vanlig vecka ut, och hur ofta jobbar folk kväll eller helg?", "tempo och belastning", "blivande kollega")
    for ax in ar.get("axlar") or []:
        if ax["lutning"] is not None and ax["lutning"] > 0.25 and ax["axel"].startswith("prestation"):
            q("Hur mäts framgång i rollen efter ett år? Vad händer när målen inte nås?",
              "annonsen betonar prestation (självbeskrivning)", "chef", "annonssprak")
        if ax["lutning"] is not None and ax["lutning"] > 0.25 and ax["axel"].startswith("tempo"):
            q("Ni skriver om högt tempo. Vad betyder det konkret en tung vecka, och vad prioriteras bort då?",
              "annonsen betonar tempo (självbeskrivning)", "blivande kollega", "annonssprak")
        if ax["lutning"] is not None and ax["lutning"] < -0.25 and ax["axel"].startswith("autonomi"):
            q("Hur detaljstyrt är arbetet? Ge ett exempel på något någon i teamet förändrat på eget initiativ.",
              "annonsen betonar rutiner och kontroll (självbeskrivning)", "blivande kollega", "annonssprak")
    for p in (kort.get("press") or {}).get("signaler", [])[:3]:
        q(f"I {p['datum'][:7]} gick ni ut med \"{p['titel'][:90]}\". Hur har det påverkat teamet?",
          f"pressignal: {', '.join(p['kategorier'])}", "chef eller nätverket", "cision")
    eko = kort.get("ekonomi") or {}
    if eko.get("status") in ("kraver_nyckel", "saknas", "fel"):
        q("Hur har bolaget utvecklats de senaste åren: växer ni, står ni still eller drar ni ner?",
          "ekonomi och antal anställda saknas i kortet", "chef eller HR", "bolagsverket_ixbrl")
    elif eko.get("anstallda_utveckling") == "krymper":
        q("Antalet anställda har minskat de senaste åren. Hur ser planen ut framåt för min del av verksamheten?",
          "krympande personalstyrka", "chef", "bolagsverket_ixbrl")
    off = kort.get("offentligt") or {}
    sj = (((off.get("kolada") or {}).get("matt") or {}).get("sjukfranvaro_pct") or {})
    if sj.get("senaste") and sj.get("riket_samma_ar") and sj["senaste"]["varde"] > sj["riket_samma_ar"]:
        q("Sjukfrånvaron ligger över rikssnittet. Hur ser den ut på min arbetsplats, och vad gör ni åt den?",
          "Kolada sjukfrånvaro över riket", "chef eller HR", "kolada")
    if kort.get("typ", {}).get("varde") == "privat":
        q("Hur ser sjukfrånvaron och personalomsättningen ut? Finns det i hållbarhetsrapporten?",
          "privata bolag redovisar det sällan; större bolag ibland i hållbarhetsrapporten", "HR")
    for o in (kort.get("matchning") or {}).get("okant", [])[:6]:
        q(f"Fråga om det som är viktigt för dig: \"{o['onskemal']}\". Hur ser det ut här i praktiken? Ge ett exempel.",
          o.get("varfor", "okänt"), "chef eller blivande kollega", "preferenser")
    sedda, ut = set(), []
    for f in F:
        if f["fraga"] not in sedda:
            sedda.add(f["fraga"])
            ut.append(f)
    return ut


# ---------------------------------------------------------------- bygg

MANUELLT_FALT = ("glassdoor", "linkedin_stannar", "personer_att_fraga", "egna_intryck")


def tomt_manuellt():
    return {
        "glassdoor": {"varde": "", "status": "manuellt", "instruktion": "Läs omdömen på Glassdoor/Indeed: teman plus och minus. "
                      "Positivitetsbias och få svar: läs som vittnesmål, inte statistik."},
        "linkedin_stannar": {"varde": "", "status": "manuellt", "instruktion": "Sök anställda på LinkedIn i liknande roll: hur länge "
                             "har de stannat? Många korta anställningar i samma team är en signal."},
        "personer_att_fraga": {"varde": [], "status": "manuellt", "instruktion": "Vem i ditt nätverk jobbar eller har jobbat där? "
                               "En informationsintervju säger mer än allt annat i kortet."},
        "egna_intryck": {"varde": "", "status": "manuellt", "instruktion": "Dina egna intryck efter samtal, intervju eller besök."},
    }


def annons_ur_db(home, uid):
    p = sc.sokv(home, "jobb.sqlite")
    if not uid or not os.path.exists(p):
        return None
    r = sc.db(home).execute("SELECT * FROM jobb WHERE uid=?", (uid,)).fetchone()
    if not r:
        return None
    return {"uid": uid, "titel": r["titel"], "arbetsgivare": r["arbetsgivare"], "orgnr": r["orgnr"],
            "text": sc.las_text(home, r["text_hash"]) or r["utdrag"] or ""}


def kor_del(kort, nyckel, fn, *args):
    try:
        return fn(*args)
    except sc.NatFel as e:
        return {"status": "fel", "anteckning": f"nätfel: {e}"}
    except sc.HttpFel as e:
        return {"status": "fel", "anteckning": f"HTTP {e.status}"}
    except SystemExit:
        return {"status": "fel", "anteckning": "nätfel"}


def bygg(home, mal, annons=None, orgnr=None, typ=None, antal_ar=5, cision=None, arsred=None, utan_nat=False):
    a = annons_ur_db(home, annons) if annons else None
    namn = mal
    if norm_orgnr(mal) and re.fullmatch(r"[\d\s-]{10,13}", mal.strip()):
        orgnr, namn = norm_orgnr(mal), None
    if a:
        namn = namn or a["arbetsgivare"]
        orgnr = orgnr or norm_orgnr(a["orgnr"])
    orgnr = norm_orgnr(orgnr)
    if not utan_nat and (not orgnr or not namn):
        try:
            o, n = hitta_orgnr(namn or orgnr)
            orgnr = orgnr or o
            namn = namn or n
        except SystemExit:
            pass
    namn = namn or orgnr or mal
    t, hur = (typ, "angiven") if typ else avgor_typ(namn, orgnr)
    slug = jbc.slugify(namn, 50)
    vag = sc.sokv(home, "arbetsgivare", f"{slug}.json")
    gammalt = sc.las_json(vag) or {}
    kort = {
        "schema_version": 1, "slug": slug, "arbetsgivare": namn, "orgnr": orgnr,
        "typ": {"varde": t, "hur": hur, "kalla": kalla("regel", None, {"orgnr": orgnr, "namn": namn})},
        "skapad": gammalt.get("skapad") or sc.idag(), "uppdaterad": sc.idag(),
        "annons": {"uid": a["uid"], "titel": a["titel"]} if a else None,
    }
    hits = []
    if utan_nat or not orgnr:
        kort["rekrytering"] = {"status": "saknas", "anteckning": "orgnr saknas eller körning utan nät",
                               "kalla": kalla("jobtech_historical", jc.HISTORICAL)}
    else:
        try:
            kort["rekrytering"], hits = rekrytering(orgnr, antal_ar, a["titel"] if a else None)
        except SystemExit:
            kort["rekrytering"] = {"status": "fel", "anteckning": "nätfel", "kalla": kalla("jobtech_historical", jc.HISTORICAL)}
    texter = [sc.html_till_text((h.get("description") or {}).get("text") or "") for h in hits[:40]]
    kort["annonssprak"] = annonssprak([x for x in texter if x], a["text"] if a else None)
    kort["ekonomi"] = ({"status": "saknas", "anteckning": "körning utan nät"} if utan_nat
                       else kor_del(kort, "ekonomi", ekonomi, orgnr, t))
    kort["press"] = ({"status": "saknas", "anteckning": "körning utan nät"} if utan_nat or t in ("kommun", "region")
                     else kor_del(kort, "press", press, namn, cision))
    off = {}
    if t in ("kommun", "region"):
        off["kolada"] = {"status": "saknas"} if utan_nat else kor_del(kort, "kolada", kolada, namn, t)
    if t == "stat":
        off["arsredovisning"] = kor_del(kort, "arsredovisning", stat_arsredovisning, namn, arsred)
    kort["offentligt"] = off or None
    man = tomt_manuellt()
    for k_, v in (gammalt.get("manuellt") or {}).items():
        if k_ in man and v.get("varde"):
            man[k_] = v
    kort["manuellt"] = man
    pref = sc.las_json(os.path.join(home, "profil", "preferenser.json")) or {}
    kort["matchning"] = matchning(pref, kort)
    kort["okant"] = fragor(kort, pref)
    sc.skriv_json(vag, kort)
    return vag, kort


def sammanfatta(kort):
    rek = kort.get("rekrytering") or {}
    sp = kort.get("annonssprak") or {}
    m = kort.get("matchning") or {}
    off = kort.get("offentligt") or {}
    return {
        "slug": kort["slug"], "arbetsgivare": kort["arbetsgivare"], "orgnr": kort["orgnr"], "typ": kort["typ"]["varde"],
        "annonser_per_ar": [(p["ar"], p["annonser"]) for p in rek.get("per_ar", [])],
        "upprepade_roller": [(r["titel"], r["annonser"]) for r in rek.get("upprepade_roller", [])[:3]],
        "annonssprak_axlar": [(x["axel"], x["lasning"]) for x in sp.get("axlar", [])],
        "ekonomi": (kort.get("ekonomi") or {}).get("status"),
        "press": [(s["datum"], s["kategorier"], s["titel"][:70]) for s in (kort.get("press") or {}).get("signaler", [])[:5]],
        "kolada": {k: (v.get("senaste"), v.get("riket_samma_ar"), v.get("trend_3_matningar"))
                   for k, v in ((off.get("kolada") or {}).get("matt") or {}).items()},
        "arsredovisning": {k: (off.get("arsredovisning") or {}).get(k) for k in ("status", "sjukfranvaro_pct")} if off.get("arsredovisning") else None,
        "matchning": {k: len(m.get(k, [])) for k in ("stammer", "skaver", "okant", "varningsflaggor")},
        "fragor": len(kort.get("okant", [])),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bygg")
    b.add_argument("mal")
    b.add_argument("--annons")
    b.add_argument("--orgnr")
    b.add_argument("--typ", choices=["kommun", "region", "stat", "privat", "ideell"])
    b.add_argument("--ar", type=int, default=5)
    b.add_argument("--cision")
    b.add_argument("--arsredovisning")
    b.add_argument("--utan-nat", action="store_true")
    s = sub.add_parser("satt")
    s.add_argument("slug")
    s.add_argument("--falt", required=True, choices=MANUELLT_FALT)
    s.add_argument("--text", required=True)
    v = sub.add_parser("visa")
    v.add_argument("slug")
    for p in (b, s, v):
        sc.add_home_arg(p)
    a = ap.parse_args(argv)
    home = sc.hem(a.home)
    if a.cmd == "bygg":
        vag, kort = bygg(home, a.mal, a.annons, a.orgnr, a.typ, a.ar, a.cision, a.arsredovisning,
                         a.utan_nat or os.environ.get("JOBBSOK_OFFLINE") == "1")
        jc.skriv(dict(fil=vag, **sammanfatta(kort)))
        return 0
    vag = sc.sokv(home, "arbetsgivare", f"{a.slug}.json")
    kort = sc.las_json(vag)
    if not kort:
        sys.stderr.write(f"FEL: inget kort {vag}\n")
        return 2
    if a.cmd == "satt":
        val = a.text
        if a.falt == "personer_att_fraga":
            val = [x.strip() for x in a.text.split(";") if x.strip()]
        kort["manuellt"][a.falt].update({"varde": val, "status": "ifylld", "datum": sc.idag()})
        kort["uppdaterad"] = sc.idag()
        sc.skriv_json(vag, kort)
    jc.skriv(sammanfatta(kort))
    return 0


if __name__ == "__main__":
    sys.exit(main())
