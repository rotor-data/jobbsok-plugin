#!/usr/bin/env python3
"""Webbrecept: sparade webbsökfrågor mot rekryteringssystem och nischsajter (skillen jobbjakt).

Själva webbsöket görs av Claude (webbsökverktyget). Skriptet gör frågorna och tar hand om svaren.

  python3 jakt_webbrecept.py skapa <namn> [--hypotes h-003] [--titel "..." ...] [--ort "..." ...]
                             [--plattform teamtailor,lever,...] [--nisch kommunikation,ideellt,...]
                             [--sajt exempel.se ...] [--oppen] [--max-fragor 20]
        utan --titel/--ort läses preferenser.json (riktningar[].sokord/namn, orter[].namn)
  python3 jakt_webbrecept.py lista
  python3 jakt_webbrecept.py visa <namn>                 frågorna, en per rad
  python3 jakt_webbrecept.py normalisera <namn> [--ingest] < resultat.json
        resultat.json: [{"url","titel","snippet","fraga"?}] (eller {"resultat":[...]}).
        Ger ingest-poster (kalla=webb, hittad_via=receptets hypotes eller namn). Avvisar
        LinkedIn/Indeed m.fl. (villkoren förbjuder skrapning) och sidor som inte är annonser.
        --ingest: matar in direkt via jakt_hypoteser.py ingest (eller ingest.py) och loggar körningen.
  python3 jakt_webbrecept.py plattformar                 vilka plattformar och nischsajter som finns

Filer: sok/webbrecept/<namn>.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

import jakt_common as jc
import sok_common as sc

PLATTFORMAR = {   # namn -> site:-domän
    "teamtailor": "teamtailor.com",
    "lever": "jobs.lever.co",
    "varbi": "varbi.com",
    "ashby": "jobs.ashbyhq.com",
    "greenhouse": "boards.greenhouse.io",
    "greenhouse2": "job-boards.greenhouse.io",
    "smartrecruiters": "jobs.smartrecruiters.com",
    "workday": "myworkdayjobs.com",
    "reachmee": "reachmee.com",
}
STANDARD = ["teamtailor", "varbi", "lever", "ashby", "greenhouse"]

# Levande nischsajter enligt docs/research/jobbsajter.md (kontrollerat 2026-10-01).
# Utelämnade (döda eller stängda för robotar): Blocket Jobb, StepStone.se, Jobbdirekt, Kulturjobb,
# Vårdjobb, Techjobs, Jobbland. Jobbsafari/Jooble/Careerjet = mest dubbletter av Platsbanken.
NISCH = {
    "kommunikation": ["sverigeskommunikatorer.se", "resume.se", "dagensmedia.se"],
    "ideellt": ["jobb.arenaopinion.se", "arenaide.se"],
    "startup": ["thehub.io"],
    "ingenjor": ["ingenjorsjobb.se"],
    "distans": ["remoteok.com", "weworkremotely.com", "remotive.com"],
    "eu": ["eu-careers.europa.eu"],
    "bemanning": ["jobb.jurek.se", "wise.se", "academicwork.se"],
}
NISCH_ORD = {
    "kommunikation": r"kommunik|pr\b|press|content|redakt|marknad|varumärke|copy",
    "ideellt": r"ideell|civilsamh|opinion|bistånd|organisation med uppdrag|non.?profit|hållbar",
    "startup": r"startup|scale.?up|tillväxtbolag",
    "ingenjor": r"ingenjör|teknik|konstruk",
    "distans": r"distans|remote",
    "eu": r"\beu\b|europeisk|internationell",
}
FORBJUDNA = {"linkedin.com": "LinkedIn förbjuder skrapning: spara som jobbavisering i mejl i stället",
             "indeed.com": "Indeed förbjuder skrapning: spara som jobbavisering i mejl i stället",
             "glassdoor": "Glassdoor: bara för research om arbetsgivaren",
             "jobbland.se": "Jobbland stänger ute robotar (robots.txt)",
             "mfn.se": "MFN förbjuder automatisk läsning"}
ANNONS_MONSTER = {
    "teamtailor": r"/jobs/\d+",
    "lever": r"jobs\.lever\.co/[^/]+/[0-9a-f-]{20,}",
    "ashby": r"jobs\.ashbyhq\.com/[^/]+/[0-9a-f-]{20,}",
    "greenhouse": r"greenhouse\.io/[^/]+/jobs/\d+",
    "varbi": r"what:job|jobID:|/job/",
    "smartrecruiters": r"smartrecruiters\.com/[^/]+/\d+",
    "workday": r"/job/",
    "reachmee": r"job_id=|/job/|jobid",
}


def mapp(home):
    return sc.sokv(home, "webbrecept")


def fil(home, namn):
    if not re.fullmatch(r"[\w.-]{1,60}", namn):
        sys.exit("Receptnamnet får bara innehålla bokstäver, siffror, punkt, bindestreck och understreck.")
    return os.path.join(mapp(home), namn + ".json")


def citera(s):
    return '"%s"' % s.strip().replace('"', "")


def fran_profil(home):
    pref = sc.las_json(os.path.join(home, "profil", "preferenser.json"), {}) or {}
    titlar = []
    for r in pref.get("riktningar", []):
        for t in (r.get("sokord") or ([r["namn"]] if r.get("namn") else [])):
            if t and t.lower() not in [x.lower() for x in titlar]:
                titlar.append(t)
    orter = [o["namn"] for o in pref.get("orter", []) if o.get("namn")]
    d = (pref.get("hårda_gränser") or pref.get("harda_granser") or {}).get("distans_dagar") or {}
    distans = (d.get("max") or 0) >= 3
    text = json.dumps(pref, ensure_ascii=False).lower()
    nisch = [n for n, m in NISCH_ORD.items() if re.search(m, text)]
    return titlar, orter, distans, nisch


def ort_del(orter):
    if not orter:
        return ""
    if len(orter) == 1:
        return " " + citera(orter[0])
    return " (" + " OR ".join(citera(o) for o in orter) + ")"


def skapa_fragor(titlar, orter, plattformar, sajter, oppen, maxn):
    fr = []
    od = ort_del(orter)
    for t in titlar:                     # titlar först: bredd över plattformar per titel
        for p in plattformar:
            fr.append({"fraga": f"site:{PLATTFORMAR[p]} {citera(t)}{od}", "plattform": p, "titel": t})
        for s in sajter:
            fr.append({"fraga": f"site:{s} {citera(t)}{od}", "plattform": "nisch:" + s, "titel": t})
        if oppen:
            fr.append({"fraga": f'{citera(t)}{od} ("lediga jobb" OR "vi söker" OR "sök tjänsten") '
                                f'-site:linkedin.com -site:indeed.com -site:arbetsformedlingen.se',
                       "plattform": "oppen", "titel": t})
    # varva så att begränsningen inte bara tar första titeln
    per_t = {}
    for f in fr:
        per_t.setdefault(f["titel"], []).append(f)
    varvat = []
    while any(per_t.values()) and len(varvat) < maxn:
        for t in list(per_t):
            if per_t[t] and len(varvat) < maxn:
                varvat.append(per_t[t].pop(0))
    for i, f in enumerate(varvat, 1):
        f["id"] = f"q{i}"
    return varvat


def plattform_for(url):
    u = url.lower()
    for p, dom in PLATTFORMAR.items():
        if dom in u:
            return "greenhouse" if p == "greenhouse2" else p
    return None


def arbetsgivare_ur_url(url, plattform):
    p = urllib.parse.urlsplit(url)
    vard, delar = p.netloc.lower(), [x for x in p.path.split("/") if x]
    slug = None
    if plattform in ("teamtailor", "varbi") and vard.count(".") >= 2:
        slug = vard.split(".")[0]
        if slug in ("www", "career", "careers", "jobb", "jobs"):
            slug = None
    elif plattform in ("lever", "ashby", "greenhouse", "smartrecruiters") and delar:
        slug = delar[0]
    elif plattform == "workday":
        slug = vard.split(".")[0]
    if not slug:
        return None
    return re.sub(r"[-_]+", " ", urllib.parse.unquote(slug)).strip().title()


def stada_titel(titel, arbetsgivare=None):
    t = re.sub(r"\s+", " ", titel or "").strip()
    t = re.sub(r"\s*[|–—-]\s*(teamtailor|varbi|lever|ashby|greenhouse|smartrecruiters|workday|career site|karriär\w*|lediga jobb|jobs?)\s*$",
               "", t, flags=re.I)
    if arbetsgivare:
        t = re.sub(r"\s*[|–—-]\s*" + re.escape(arbetsgivare) + r".*$", "", t, flags=re.I)
    return t[:150]


def normalisera(resultat, recept):
    poster, avvisade, sett = [], [], set()
    hv = recept.get("hypotes") or ("webbrecept:" + recept["namn"])
    orter = recept.get("orter") or []
    for r in resultat:
        url = (r.get("url") or "").strip()
        if not url.startswith("http"):
            avvisade.append({"url": url, "skal": "saknar url"})
            continue
        url = url.split("#")[0]
        if any(x in url.lower() for x in ("utm_",)):
            p = urllib.parse.urlsplit(url)
            q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.startswith("utm_")]
            url = urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode(q)))
        vard = urllib.parse.urlsplit(url).netloc.lower()
        forb = next((s for d, s in FORBJUDNA.items() if d in vard), None)
        if forb:
            avvisade.append({"url": url, "skal": forb})
            continue
        if url in sett:
            continue
        sett.add(url)
        pl = plattform_for(url)
        if pl and pl in ANNONS_MONSTER and not re.search(ANNONS_MONSTER[pl], url, re.I):
            avvisade.append({"url": url, "skal": f"{pl}-sida men inte en enskild annons (lista eller startsida)"})
            continue
        ag = r.get("arbetsgivare") or arbetsgivare_ur_url(url, pl)
        snippet = re.sub(r"\s+", " ", r.get("snippet") or "").strip()
        ort = r.get("ort") or next((o for o in orter if o.lower() in (snippet + " " + (r.get("titel") or "")).lower()), None)
        distans = "distans" if re.search(r"\b(remote|distans)\b", snippet + " " + (r.get("titel") or ""), re.I) else None
        poster.append({k: v for k, v in {
            "titel": stada_titel(r.get("titel"), ag) or None, "arbetsgivare": ag, "url": url, "ort": ort,
            "distans": distans, "utdrag": snippet[:300] or None, "kalla": "webb", "hittad_via": hv,
            "publicerad": r.get("datum"),
        }.items() if v})
    return poster, avvisade


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sc.add_home_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("skapa")
    s.add_argument("namn")
    s.add_argument("--hypotes")
    s.add_argument("--titel", action="append")
    s.add_argument("--ort", action="append")
    s.add_argument("--plattform", help="kommaseparerat, standard " + ",".join(STANDARD))
    s.add_argument("--nisch", help="kommaseparerat: " + ",".join(NISCH) + " (standard: ur profilen)")
    s.add_argument("--sajt", action="append", default=[], help="egen nischsajt (domän)")
    s.add_argument("--oppen", action="store_true", help="lägg till en öppen webbfråga per titel")
    s.add_argument("--max-fragor", type=int, default=20)
    sub.add_parser("lista")
    sub.add_parser("plattformar")
    v = sub.add_parser("visa")
    v.add_argument("namn")
    n = sub.add_parser("normalisera")
    n.add_argument("namn")
    n.add_argument("--ingest", action="store_true")
    a = ap.parse_args(argv)
    home = sc.hem(a.home)

    if a.cmd == "plattformar":
        jc.skriv({"plattformar": [f"{k}: site:{v}" for k, v in PLATTFORMAR.items()],
                  "nisch": [f"{k}: {', '.join(v)}" for k, v in NISCH.items()],
                  "forbjudna": list(FORBJUDNA)})
    elif a.cmd == "skapa":
        ptitlar, porter, distans, pnisch = fran_profil(home)
        titlar = a.titel or ptitlar
        orter = a.ort if a.ort is not None else porter
        if not titlar:
            sys.exit("Inga titlar: ange --titel eller fyll i riktningar[].sokord i preferenser.json.")
        plattformar = [p.strip() for p in (a.plattform or ",".join(STANDARD)).split(",") if p.strip()]
        okanda = [p for p in plattformar if p not in PLATTFORMAR]
        if okanda:
            sys.exit(f"Okänd plattform: {okanda}. Finns: {list(PLATTFORMAR)}")
        nisch = [x.strip() for x in a.nisch.split(",")] if a.nisch else pnisch + (["distans"] if distans else [])
        sajter = list(dict.fromkeys([d for x in nisch for d in NISCH.get(x, [])] + a.sajt))
        fr = skapa_fragor(titlar, orter, plattformar, sajter, a.oppen, a.max_fragor)
        p = fil(home, a.namn)
        gammal = sc.las_json(p) or {}
        recept = {"schema_version": 1, "namn": a.namn, "hypotes": a.hypotes or gammal.get("hypotes"),
                  "titlar": titlar, "orter": orter, "plattformar": plattformar, "nisch": nisch, "sajter": sajter,
                  "fragor": fr, "skapad": gammal.get("skapad") or sc.idag(), "andrad": sc.idag(),
                  "senast_kord": gammal.get("senast_kord"), "korningar": gammal.get("korningar", [])}
        sc.skriv_json(p, recept)
        jc.skriv({"sparad": p, "antal_fragor": len(fr), "fragor": [f'{f["id"]}: {f["fraga"]}' for f in fr]})
    elif a.cmd == "lista":
        ut = []
        if os.path.isdir(mapp(home)):
            for f in sorted(os.listdir(mapp(home))):
                if f.endswith(".json"):
                    r = sc.las_json(os.path.join(mapp(home), f), {})
                    k = r.get("korningar", [])
                    ut.append({"namn": r.get("namn"), "hypotes": r.get("hypotes"), "fragor": len(r.get("fragor", [])),
                               "senast_kord": r.get("senast_kord"), "fynd_totalt": sum(x.get("nya", 0) for x in k)})
        jc.skriv({"webbrecept": ut})
    elif a.cmd == "visa":
        r = sc.las_json(fil(home, a.namn))
        if not r:
            sys.exit(f"Inget webbrecept som heter {a.namn}.")
        jc.skriv({"namn": r["namn"], "hypotes": r.get("hypotes"), "senast_kord": r.get("senast_kord"),
                  "fragor": [f'{f["id"]}: {f["fraga"]}' for f in r.get("fragor", [])]})
    elif a.cmd == "normalisera":
        p = fil(home, a.namn)
        r = sc.las_json(p)
        if not r:
            sys.exit(f"Inget webbrecept som heter {a.namn}.")
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.exit(f"Ogiltig JSON på stdin: {e}")
        res = data.get("resultat", []) if isinstance(data, dict) else data
        poster, avvisade = normalisera(res, r)
        if not a.ingest:
            print(json.dumps({"poster": poster, "avvisade": avvisade}, ensure_ascii=False))
            return
        if r.get("hypotes"):
            cmd = [sys.executable, os.path.join(jc.SKRIPT, "jakt_hypoteser.py"), "--home", home, "ingest", r["hypotes"]]
        else:
            cmd = [sys.executable, os.path.join(jc.SKRIPT, "ingest.py"), "--home", home, "--kalla", "webb",
                   "--hittad-via", "webbrecept:" + r["namn"]]
        pr = subprocess.run(cmd, input=json.dumps(poster, ensure_ascii=False), capture_output=True, text=True)
        if pr.returncode != 0:
            sys.stderr.write(pr.stderr)
            sys.exit(pr.returncode)
        ing = json.loads(pr.stdout or "{}")
        r["senast_kord"] = sc.nu_iso()
        r.setdefault("korningar", []).append({"datum": r["senast_kord"], "resultat": len(res), "poster": len(poster),
                                              "nya": ing.get("nya", 0), "avvisade": len(avvisade)})
        r["korningar"] = r["korningar"][-30:]
        sc.skriv_json(p, r)
        print(json.dumps({"recept": a.namn, "hypotes": r.get("hypotes"), "nya": ing.get("nya"),
                          "uppdaterade": ing.get("uppdaterade"), "uid": ing.get("uid"),
                          "avvisade": avvisade}, ensure_ascii=False))


if __name__ == "__main__":
    main()
