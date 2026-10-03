#!/usr/bin/env python3
"""Identifierar rekryteringssystemet bakom en karriärsida och föreslår ett kallor.json-objekt.

  python3 upptack_ats.py <karriärsida-url> [--namn "Bolag"] [--home DIR]

Letar efter Teamtailor, Lever, Ashby, Greenhouse, SmartRecruiters, Workday, Varbi (RSS what:rssfeed)
och jobbrelaterade RSS/Atom-länkar i URL:en och i sidans
HTML (även <link rel="alternate" type="application/rss+xml">). Varje kandidat verifieras genom att
flödet faktiskt hämtas. Utdata JSON:
  {"forslag": {kallor-objekt}, "verifierad": true|false, "antal_annonser": n, "system": "...",
   "kandidater": [...], "anteckning": "..."}
Utan flöde: pagehash (jobblista, med 'lankmonster' när annonslänkar hittas), sok_url (jobbsajt med
sökfilter i querysträngen) eller mejl (LinkedIn/Indeed m.fl. där skrapning inte är tillåten).
ReachMee har inget öppet flöde; annonserna finns oftast i Platsbanken (JobTech).
"""
import argparse
import collections
import json
import re
import sys
import urllib.parse

import fetch
import sok_common as sc

MONSTER = [
    ("teamtailor_rss", r"https?://([\w-]+)\.teamtailor\.com", lambda m: f"https://{m.group(1)}.teamtailor.com/jobs.rss"),
    ("lever", r"(?:jobs|api)\.(eu\.)?lever\.co/(?:v0/postings/)?([\w.-]+)",
     lambda m: f"https://api.{m.group(1) or ''}lever.co/v0/postings/{m.group(2)}?mode=json"),
    ("ashby", r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([\w.%-]+)",
     lambda m: f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}?includeCompensation=true"),
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([\w-]+)",
     lambda m: f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs?content=true"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([\w-]+)",
     lambda m: f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs?content=true"),
    ("smartrecruiters", r"(?:careers|jobs|api)\.smartrecruiters\.com/(?:v1/companies/)?([\w-]+)",
     lambda m: f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings"),
    ("rss", r"https?://([\w-]+)\.varbi\.com", lambda m: f"https://{m.group(1)}.varbi.com/what:rssfeed/"),
    ("workday", r"https?://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)",
     lambda m: f"https://{m.group(1)}.{m.group(2)}.myworkdayjobs.com/wday/cxs/{m.group(1)}/{m.group(3)}/jobs"),
]
OGILTIGA_SLUGS = {"www", "embed", "js", "v0", "v1", "postings", "jobs", "api", "www", "static", "assets", "careers"}
BARA_MEJL = {"linkedin.com": "LinkedIn", "indeed.com": "Indeed", "indeed.se": "Indeed", "glassdoor.com": "Glassdoor",
             "glassdoor.se": "Glassdoor"}
INGET_API = {"reachmee.com": "ReachMee", "jobs.jobylon.com": "Jobylon",
             "emp.jobylon.com": "Jobylon"}
JOBBSAJTER = ("arbetsformedlingen.se", "jobbsafari", "monster.se", "stepstone", "academicwork", "jobbland",
              "offentligajobb", "careerbuilder", "blocket.se/jobb", "ledigajobb", "jobsinstockholm",
              "karriarguiden", "uptrail", "jobindex")


def _id(namn):
    return re.sub(r"[^a-z0-9]+", "-", sc.norm(namn))[:30].strip("-") or "kalla"


def kandidater_ur(text):
    ut, sett = [], set()
    for typ, rx, bygg in MONSTER:
        for m in re.finditer(rx, text):
            if m.groups()[-1].lower() in OGILTIGA_SLUGS:
                continue
            url = bygg(m)
            if url not in sett:
                sett.add(url)
                ut.append((typ, url))
    return ut


def verifiera(typ, url, namn, home):
    try:
        poster, _ = fetch.ADAPTRAR[typ]({"url": url, "namn": namn}, {}, home, None)
        return True, len(poster), None
    except (sc.HttpFel, ValueError, KeyError, IndexError, Exception) as e:  # noqa: BLE001 - rapporteras
        if isinstance(e, sc.NatFel):
            raise
        return False, 0, f"{type(e).__name__}: {e}"


def lankmonster(url, html_text):
    """Hittar annonslänkar på en jobblista och returnerar (regex, antal, exempel) eller (None, 0, [])."""
    bas = urllib.parse.urlsplit(url)
    trf = [(h, t) for h, t in sc.lankar(html_text, url)
           if sc.JOBBLANK.search(urllib.parse.urlsplit(h).path + "/") and t and len(t) > 3
           and urllib.parse.urlsplit(h).path.rstrip("/") != bas.path.rstrip("/")]
    grupper = collections.defaultdict(list)
    for h, t in trf:
        u = urllib.parse.urlsplit(h)
        segs = [s for s in u.path.split("/") if s]
        if len(segs) < 2:
            continue
        prefix = f"{u.scheme}://{u.netloc}/" + "/".join(segs[:-1]) + "/"
        grupper[prefix].append((h, t))
    if not grupper:
        return None, 0, []
    def annonslik(h):
        """2 = id-liknande (siffror), 1 = lång slug, 0 = annat."""
        sist = [x for x in urllib.parse.urlsplit(h).path.split("/") if x][-1]
        return 2 if re.search(r"\d{3,}", sist) else (1 if sist.count("-") >= 3 else 0)

    def poang(kv):
        unika = {h for h, _ in kv[1]}
        return (sum(annonslik(h) for h in unika), len(unika))
    prefix, lst = max(grupper.items(), key=poang)
    if poang((prefix, lst))[0] < 5:  # minst 3 id-länkar eller 5 långa slugs, annars är det troligen meny
        return None, 0, []
    lst = [(h, t) for h, t in lst if annonslik(h)]
    return "^" + re.escape(prefix) + r"[^?#/]*(\d{3,}|-[^/?#]*-[^/?#]*-)[^?#]*$", len({h for h, _ in lst}), [t for _, t in lst[:3]]


def upptack(url, home, namn=None):
    if not re.match(r"https?://", url):
        url = "https://" + url
    host = urllib.parse.urlsplit(url).netloc.lower()
    namn = namn or host.replace("www.", "").split(".")[0].capitalize()
    res = {"url": url, "kandidater": [], "anteckning": ""}
    for dom, sajt in BARA_MEJL.items():
        if host.endswith(dom):
            res.update(system=sajt, verifierad=False, antal_annonser=None, forslag={
                "id": _id(sajt + " avisering"), "typ": "mejl", "namn": f"{sajt}-aviseringar", "url": url,
                "aktiv": True, "instruktion": f"Skapa en jobbavisering på {sajt} med dina filter. Aviseringsmejlen läses "
                f"via Gmail-kopplingen, eller klistra in länkar. {sajt} får inte skrapas enligt sina villkor."})
            return res
    kand = kandidater_ur(url)
    html_text = ""
    if not kand:
        if not sc.robots_tillater(url):
            res.update(verifierad=False, anteckning="robots.txt tillåter inte att sidan hämtas automatiskt.",
                       system=None, antal_annonser=None, forslag={"id": _id(namn), "typ": "mejl", "namn": namn,
                       "url": url, "aktiv": True, "instruktion": "Sidan får inte hämtas automatiskt. Använd sajtens "
                       "mejlavisering om den finns, eller klistra in länkar."})
            return res
        _, html_text, _ = sc.http(url, home=home, cache=True)
        for m in re.finditer(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', html_text, re.I):
            h = re.search(r'href=["\']([^"\']+)', m.group(0))
            if h and re.search(r"job|jobb|karri|career|ledig|vacanc|rssfeed", h.group(1), re.I):
                typ = "teamtailor_rss" if "teamtailor" in html_text.lower() else "rss"
                kand.append((typ, urllib.parse.urljoin(url, h.group(1))))
        kand += [k for k in kandidater_ur(html_text) if k not in kand]
        if "teamtailor" in html_text.lower() and not any(t == "teamtailor_rss" for t, _ in kand):
            u = urllib.parse.urlsplit(url)
            kand.append(("teamtailor_rss", f"{u.scheme}://{u.netloc}/jobs.rss"))
    for typ, furl in kand:
        ok, n, fel = verifiera(typ, furl, namn, home)
        res["kandidater"].append({"typ": typ, "url": furl, "ok": ok, "antal": n, "fel": fel})
        if ok:
            res.update(system=typ, verifierad=True, antal_annonser=n, forslag={
                "id": _id(namn), "typ": typ, "namn": namn, "url": furl, "aktiv": True,
                "anteckning": f"upptäckt från {url}"})
            return res
    # inget flöde
    for dom, sajt in INGET_API.items():
        if dom in host or dom in html_text:
            res["anteckning"] = f"{sajt} har inget öppet API. Annonserna finns oftast i Platsbanken (JobTech). "
    q = urllib.parse.urlsplit(url).query
    jobbsajt = any(j in url.lower() for j in JOBBSAJTER)
    monster, antal, exempel = lankmonster(url, html_text) if html_text else (None, 0, [])
    if q and (jobbsajt or antal):
        typ = "sok_url"
        res["anteckning"] += "Sök-URL med dina filter sparas; nya annonslänkar plockas ut vid varje körning."
    else:
        typ = "pagehash"
        res["anteckning"] += ("Inget flöde hittades. Sidan bevakas: nya annonslänkar plockas ut."
                              if monster else "Inget flöde hittades. Sidan bevakas med en hash av texten.")
    f = {"id": _id(namn), "typ": typ, "namn": namn, "url": url, "aktiv": True}
    if monster:
        f["lankmonster"] = monster
    res.update(system=None, verifierad=bool(monster) or typ == "pagehash", antal_annonser=antal or None,
               exempel=exempel, forslag=f)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--namn")
    sc.add_home_arg(ap)
    a = ap.parse_args()
    try:
        r = upptack(a.url, sc.hem(a.home), a.namn)
    except sc.NatFel as e:
        sc.natfel_avslut(e)
    except sc.HttpFel as e:
        sys.exit(f"Kunde inte hämta sidan: {e}")
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
