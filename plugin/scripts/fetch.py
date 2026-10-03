#!/usr/bin/env python3
"""Hämtar annonser för ett recept och lägger in dem i sok/jobb.sqlite.

  python3 fetch.py --recept <namn> [--home DIR] [--full]
  python3 fetch.py --alla-bevakade [--home DIR]   alla aktiva källor (utom jobtech/mejl), även utan recept

Läser sok/recept/<namn>.json och sok/kallor.json. Varje källa hämtas med sin adapter:
jobtech, teamtailor_rss, lever, ashby, greenhouse, smartrecruiters, workday (best effort), pagehash
sok_url, rss (generisk RSS/Atom, t.ex. Varbi), json_api (fältmappning i källposten) och sitemap
(pagehash/sok_url med 'lankmonster' plockar ut nya annonslänkar; robots.txt följs för webbsidor och flöden).
Källfält som styr: "min_intervall_h" (hämta högst så ofta, t.ex. Remotive 12), "signal": true (skrivs till
sok/signaler.json i stället för jobb, t.ex. Cision), "aktiv": false (hoppas över).
Källor av typen 'mejl' matas in via ingest.py och hoppas över här.

JobTech hämtas inkrementellt med published-after = receptets senast_kord (minus 1 h marginal),
om inte --full anges. ATS-flöden hämtas helt (med ETag/If-Modified-Since) och annonser som
försvunnit markeras 'stangd'. Annonser vars deadline passerat markeras också 'stangd'.

Kolumnen hittad_via sätts till receptets namn (eller 'bevakning') när jobbet först hittas.
Fältet distans: 0 = på plats, 1 = hybrid, 2 = helt på distans, NULL = okänt.
Utskrift: en JSON-sammanfattning på stdout. Nätfel ger kod 3 (se sok_common.natfel_avslut).
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import sok_common as sc

JOBTECH = "https://jobsearch.api.jobtechdev.se"
JOBTECH_PARAM = ("q", "occupation-name", "occupation-group", "occupation-field", "skill", "municipality",
                 "region", "remote", "employment-type", "worktime-extent", "experience", "employer")


# ---------------------------------------------------------------- normaliseringshjälp

def anst_form(*etiketter):
    t = " ".join(e for e in etiketter if e).lower()
    if not t:
        return None
    if "tills vidare" in t or "tillsvidare" in t or "permanent" in t or "full-time" in t and "temp" not in t:
        return "tillsvidare"
    if "vikariat" in t:
        return "vikariat"
    if "timanst" in t or "behovsanst" in t or "hourly" in t:
        return "timanstallning"
    if "praktik" in t or "intern" in t:
        return "praktik"
    if "konsult" in t or "contract" in t or "freelance" in t:
        return "konsult"
    if any(x in t for x in ("visstid", "månad", "manad", "sommar", "temporary", "säsong", "tidsbegr", "projekt")):
        return "visstid"
    if "vanlig anställning" in t:
        return "tillsvidare"
    return None


def omfattn(*etiketter):
    t = " ".join(e for e in etiketter if e).lower()
    if not t:
        return None
    if "deltid" in t or "part" in t:
        return "deltid"
    if "heltid" in t or "full" in t:
        return "heltid"
    return None


def distans_av(t):
    t = (t or "").lower()
    if not t:
        return None
    if t in ("remote", "fully", "fully_remote", "distans") or "fully" in t or "helt på distans" in t:
        return 2
    if "hybrid" in t:
        return 1
    if t in ("onsite", "on-site", "on_site", "none", "office", "på plats"):
        return 0
    if "remote" in t:
        return 2
    return None


# ---------------------------------------------------------------- JobTech

def jobtech_post(h):
    """Normaliserar en JobTech-träff (search eller /ad/{id}) till ingest-form."""
    wa = h.get("workplace_address") or {}
    emp = h.get("employer") or {}
    desc = (h.get("description") or {}).get("text") or ""
    komp = []
    for typ, blk in (("must", h.get("must_have")), ("nice", h.get("nice_to_have"))):
        for s in ((blk or {}).get("skills") or []):
            komp.append({"id": s.get("concept_id"), "namn": s.get("label"), "typ": typ})
    occ = h.get("occupation") or {}
    if occ.get("concept_id"):
        komp.append({"id": occ["concept_id"], "namn": occ.get("label"), "typ": "yrke"})
    og = h.get("occupation_group") or {}
    if og.get("concept_id"):
        komp.append({"id": og["concept_id"], "namn": og.get("label"), "typ": "yrkesgrupp"})
    wm = ((h.get("workplace_model") or {}).get("label") or "")
    dist = distans_av(wm) if wm else (2 if h.get("remote_work") else None)
    return {
        "kalla_id": str(h.get("id")),
        "url": h.get("webpage_url"),
        "titel": h.get("headline"),
        "arbetsgivare": emp.get("name"),
        "orgnr": emp.get("organization_number"),
        "ort": wa.get("municipality") or wa.get("city") or wa.get("region"),
        "kommun_id": wa.get("municipality_concept_id"),
        "distans": dist,
        "publicerad": h.get("publication_date"),
        "deadline": h.get("application_deadline"),
        "anstallningsform": anst_form((h.get("duration") or {}).get("label"),
                                      (h.get("employment_type") or {}).get("label")),
        "omfattning": omfattn((h.get("working_hours_type") or {}).get("label")),
        "kompetenser": komp,
        "text": desc,
    }


def jobtech_params(recept, since):
    jt = recept.get("jobtech") or {}
    p = []
    for k in JOBTECH_PARAM:
        v = jt.get(k)
        if v in (None, "", []):
            continue
        for x in (v if isinstance(v, list) else [v]):
            p.append((k, str(x).lower() if isinstance(x, bool) else str(x)))
    for k, v in (jt.get("extra") or {}).items():
        for x in (v if isinstance(v, list) else [v]):
            p.append((k, str(x)))
    if since:
        p.append(("published-after", since))
    return p


def ad_jobtech(kalla, recept, home, since):
    # resdet=brief saknar ort, kompetenser och text (verifierat 2026-10-01), så full används.
    bas = jobtech_params(recept, since)
    ut, offset = [], 0
    while True:
        q = bas + [("limit", "100"), ("offset", str(offset)), ("sort", "pubdate-desc")]
        _, d, _ = sc.http_json(JOBTECH + "/search?" + urllib.parse.urlencode(q))
        hits = d.get("hits") or []
        ut += [jobtech_post(h) for h in hits]
        tot = (d.get("total") or {}).get("value") or 0
        offset += len(hits)
        if not hits or offset >= tot or offset >= 2000:
            break
    return ut, False  # sökningen är inkrementell, så försvunna kan inte avgöras här


# ---------------------------------------------------------------- ATS

def ad_teamtailor(kalla, recept, home, since):
    url = kalla["url"]
    if not url.rstrip("/").endswith(".rss"):
        url = url.rstrip("/") + "/jobs.rss"
    _, text, _ = sc.http(url, home=home, cache=True)
    rot = ET.fromstring(text.encode("utf-8"))
    ns = {"tt": "https://teamtailor.com/locations"}
    ut = []
    for it in rot.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        orter = [l.findtext("tt:city", namespaces=ns) or l.findtext("tt:name", namespaces=ns)
                 for l in it.findall("tt:locations/tt:location", ns)]
        ut.append({
            "kalla_id": g("guid") or g("link"), "url": g("link"), "titel": g("title"),
            "arbetsgivare": kalla.get("namn"), "ort": ", ".join(o for o in orter if o) or None,
            "distans": distans_av(g("remoteStatus")), "publicerad": g("pubDate"),
            "html": g("description"),
        })
    return ut, True


def _slug(url, monster):
    m = re.search(monster, url)
    return m.group(1) if m else url.strip("/").split("/")[-1]


def ad_lever(kalla, recept, home, since):
    url = kalla["url"]
    if "api." not in url:
        eu = ".eu." in url
        slug = _slug(url, r"lever\.co/([^/?#]+)")
        url = "https://api.%slever.co/v0/postings/%s" % ("eu." if eu else "", slug)
    if "mode=json" not in url:
        url += ("&" if "?" in url else "?") + "mode=json"
    _, d, _ = sc.http_json(url, home=home, cache=True)
    ut = []
    for p in d or []:
        cat = p.get("categories") or {}
        text = "\n".join(x for x in (p.get("openingPlain"), p.get("descriptionPlain"), p.get("descriptionBodyPlain"),
                                     *[l.get("text", "") + "\n" + sc.html_till_text(l.get("content", ""))
                                       for l in p.get("lists") or []], p.get("additionalPlain")) if x)
        ut.append({
            "kalla_id": p.get("id"), "url": p.get("hostedUrl"), "titel": p.get("text"),
            "arbetsgivare": kalla.get("namn"), "ort": cat.get("location"),
            "distans": distans_av(p.get("workplaceType")), "publicerad": p.get("createdAt"),
            "anstallningsform": anst_form(cat.get("commitment")), "omfattning": omfattn(cat.get("commitment")),
            "text": text,
        })
    return ut, True


def ad_ashby(kalla, recept, home, since):
    url = kalla["url"]
    if "api.ashbyhq.com" not in url:
        url = "https://api.ashbyhq.com/posting-api/job-board/" + _slug(url, r"ashbyhq\.com/([^/?#]+)")
    _, d, _ = sc.http_json(url, home=home, cache=True)
    ut = []
    for j in (d or {}).get("jobs", []):
        if j.get("isListed") is False:
            continue
        ut.append({
            "kalla_id": j.get("id"), "url": j.get("jobUrl"), "titel": j.get("title"),
            "arbetsgivare": kalla.get("namn"), "ort": j.get("location"),
            "distans": 2 if j.get("isRemote") and (j.get("workplaceType") or "").lower() != "hybrid"
            else distans_av(j.get("workplaceType")),
            "publicerad": j.get("publishedAt"), "anstallningsform": anst_form(j.get("employmentType")),
            "omfattning": omfattn(j.get("employmentType")),
            "text": j.get("descriptionPlain") or sc.html_till_text(j.get("descriptionHtml")),
        })
    return ut, True


def ad_greenhouse(kalla, recept, home, since):
    url = kalla["url"]
    if "boards-api" not in url:
        slug = _slug(url, r"greenhouse\.io/(?:embed/job_board\?for=)?([^/?#&]+)")
        url = "https://boards-api.greenhouse.io/v1/boards/%s/jobs" % slug
    if "content=" not in url:
        url += ("&" if "?" in url else "?") + "content=true"
    _, d, _ = sc.http_json(url, home=home, cache=True)
    ut = []
    for j in (d or {}).get("jobs", []):
        ut.append({
            "kalla_id": j.get("id"), "url": j.get("absolute_url"), "titel": j.get("title"),
            "arbetsgivare": kalla.get("namn"), "ort": (j.get("location") or {}).get("name"),
            "publicerad": j.get("first_published") or j.get("updated_at"),
            "html": sc.html.unescape(j.get("content") or ""),
        })
    return ut, True


def ad_smartrecruiters(kalla, recept, home, since):
    url = kalla["url"]
    if "api.smartrecruiters.com" not in url:
        slug = _slug(url, r"smartrecruiters\.com/([^/?#]+)")
        url = "https://api.smartrecruiters.com/v1/companies/%s/postings" % slug
    ut, offset = [], 0
    while True:
        _, d, _ = sc.http_json(url + ("&" if "?" in url else "?") + f"limit=100&offset={offset}")
        rader = (d or {}).get("content") or []
        for j in rader:
            loc = j.get("location") or {}
            ut.append({
                "kalla_id": j.get("id"), "titel": j.get("name"),
                "url": f"https://jobs.smartrecruiters.com/{(j.get('company') or {}).get('identifier', '')}/{j.get('id')}",
                "arbetsgivare": kalla.get("namn") or (j.get("company") or {}).get("name"),
                "ort": loc.get("city"), "distans": 2 if loc.get("remote") else (1 if loc.get("hybrid") else None),
                "publicerad": j.get("releasedDate"),
                "anstallningsform": anst_form((j.get("typeOfEmployment") or {}).get("label")),
                "omfattning": omfattn((j.get("typeOfEmployment") or {}).get("label")),
            })
        offset += len(rader)
        if not rader or offset >= (d.get("totalFound") or 0) or offset >= 1000:
            break
    return ut, True


def ad_workday(kalla, recept, home, since):
    """Inofficiellt och skört. url = https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    eller en vanlig karriärsides-URL https://{tenant}.wd{N}.myworkdayjobs.com/{sv-SE/}{site}."""
    url = kalla["url"]
    u = urllib.parse.urlsplit(url)
    if "/wday/cxs/" not in url:
        tenant = u.netloc.split(".")[0]
        delar = [x for x in u.path.split("/") if x and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", x)]
        url = f"{u.scheme}://{u.netloc}/wday/cxs/{tenant}/{delar[0]}/jobs"
    bas = url.rsplit("/jobs", 1)[0]
    publ = f"{u.scheme}://{u.netloc}/" + bas.split("/wday/cxs/", 1)[1].split("/", 1)[1]
    ut, offset = [], 0
    while True:
        _, d, _ = sc.http_json(url, method="POST", data={"appliedFacets": {}, "limit": 20, "offset": offset,
                                                          "searchText": kalla.get("sokord", "")})
        rader = (d or {}).get("jobPostings") or []
        for j in rader:
            ut.append({
                "kalla_id": j.get("externalPath") or j.get("title"), "titel": j.get("title"),
                "url": publ + (j.get("externalPath") or ""), "arbetsgivare": kalla.get("namn"),
                "ort": j.get("locationsText"), "utdrag": j.get("postedOn"),
            })
        offset += len(rader)
        if not rader or offset >= (d.get("total") or 0) or offset >= 400:
            break
    return ut, True


def _lankposter(kalla, html_text):
    rx = re.compile(kalla["lankmonster"]) if kalla.get("lankmonster") else None
    bas_path = urllib.parse.urlsplit(kalla["url"]).path.rstrip("/")
    sett, ut = set(), []
    for h, t in sc.lankar(html_text, kalla["url"]):
        if rx:
            if not rx.search(h):
                continue
        elif not (sc.JOBBLANK.search(urllib.parse.urlsplit(h).path + "/")
                  and urllib.parse.urlsplit(h).path.rstrip("/") != bas_path):
            continue
        if h in sett or len(t) < 4:
            continue
        sett.add(h)
        ut.append({"kalla_id": h, "url": h, "titel": t[:200],
                   "arbetsgivare": kalla.get("namn") if kalla.get("typ") != "sok_url" else None,
                   "utdrag": f"Hittad på {kalla.get('namn') or kalla['url']}. Öppna länken för hela annonsen."})
    return ut


def _hamta_sida(kalla, home):
    if not sc.robots_tillater(kalla["url"]):
        raise ValueError("robots.txt tillåter inte automatisk hämtning av sidan")
    _, text, _ = sc.http(kalla["url"], home=home, cache=True)
    return text


def ad_sok_url(kalla, recept, home, since):
    """Sparad sök-URL på en jobbsajt (med filter i querysträngen): nya annonslänkar blir poster."""
    return _lankposter(kalla, _hamta_sida(kalla, home)), True


def ad_pagehash(kalla, recept, home, since):
    """Bevakar en karriärsida. Med 'lankmonster' (regex) blir varje annonslänk en post (länklista-diff);
    annars ger ändrad text en ny post 'Karriärsidan har ändrats'."""
    text = _hamta_sida(kalla, home)
    if kalla.get("lankmonster"):
        return _lankposter(kalla, text), True
    t = sc.html_till_text(text)
    h = hashlib.sha1(sc.norm(t).encode()).hexdigest()[:16]
    kalla["_ny_hash"] = h
    return [{
        "kalla_id": h, "url": kalla["url"],
        "titel": f"Karriärsidan hos {kalla.get('namn') or kalla['url']} har ändrats",
        "arbetsgivare": kalla.get("namn"), "publicerad": sc.nu_iso(),
        "utdrag": "Sidan bevakas utan flöde. Öppna den och se om något nytt jobb har kommit upp.",
        "text": t[:20000],
    }], True


def ad_rss(kalla, recept, home, since):
    """Generisk RSS 2.0/Atom (Varbi what:rssfeed, We Work Remotely, Cision m.fl.).
    Valfritt i källposten: "arbetsgivare_ur_titel": true delar 'Bolag: Titel' (WWR)."""
    if not sc.robots_tillater(kalla["url"]):
        raise ValueError("robots.txt tillåter inte automatisk läsning av flödet")
    _, text, _ = sc.http(kalla["url"], home=home, cache=True)
    rot = ET.fromstring(text.encode("utf-8"))
    ut = []
    A = "{http://www.w3.org/2005/Atom}"
    poster = list(rot.iter("item")) or list(rot.iter(A + "entry"))
    for it in poster:
        def g(*taggar):
            for t in taggar:
                e = it.find(t)
                if e is not None:
                    if t.endswith("link") and e.get("href"):
                        return e.get("href")
                    if (e.text or "").strip():
                        return e.text.strip()
            return ""
        titel = g("title", A + "title")
        arb = kalla.get("namn")
        if kalla.get("arbetsgivare_ur_titel") and ": " in titel:
            arb, titel = titel.split(": ", 1)
        lank = g("link", A + "link")
        ut.append({"kalla_id": g("guid", A + "id") or lank, "url": lank, "titel": titel, "arbetsgivare": arb,
                   "publicerad": g("pubDate", A + "published", A + "updated"),
                   "ort": g("{https://teamtailor.com/locations}city") or None,
                   "html": g("description", A + "summary", A + "content",
                             "{http://purl.org/rss/1.0/modules/content/}encoded")})
    return ut, True


def ad_json_api(kalla, recept, home, since):
    """Generisk JSON-lista med fältmappning i källposten:
    "lista": punkt-sökväg till listan (tom = roten), "falt": {"id","titel","url","arbetsgivare","publicerad",
    "ort","text","deadline"} som punkt-sökvägar, "distans": 0/1/2 för alla poster (valfritt).
    Poster utan titel hoppas över (t.ex. Remote OK:s första element med villkorstext)."""
    if not sc.robots_tillater(kalla["url"]):
        raise ValueError("robots.txt tillåter inte automatisk hämtning")
    _, d, _ = sc.http_json(kalla["url"], home=home, cache=True)
    lst = sc.hamta_sokvag(d, kalla["lista"]) if kalla.get("lista") else d
    f = kalla.get("falt") or {}
    ut = []
    for x in lst or []:
        v = lambda k: sc.hamta_sokvag(x, f[k]) if f.get(k) else None
        titel = v("titel")
        if not titel:
            continue
        text = v("text") or ""
        ut.append({"kalla_id": str(v("id") or v("url")), "url": v("url"), "titel": str(titel),
                   "arbetsgivare": v("arbetsgivare"), "publicerad": v("publicerad"), "ort": v("ort"),
                   "deadline": v("deadline"), "distans": kalla.get("distans"),
                   "html" if "<" in str(text) else "text": str(text)})
    return ut, True


def ad_sitemap(kalla, recept, home, since):
    """Läser en sitemap och plockar annons-URL:er som matchar "monster" (regex). Bara NYA URL:er hämtas
    (högst "max_nya", standard 25 per körning) och tolkas via JSON-LD JobPosting. "krav" (regex, valfri)
    måste finnas i annonsens ort/land/text för att den ska läggas in, t.ex. "Sweden|Sverige|Stockholm"."""
    if not sc.robots_tillater(kalla["url"]):
        raise ValueError("robots.txt tillåter inte automatisk läsning av sitemapen")
    _, text, _ = sc.http(kalla["url"], home=home, cache=True)
    rx = re.compile(kalla.get("monster") or ".")
    urls = [u.strip() for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text) if rx.search(u)]
    sett_p = sc.cachev(home, "sitemap", kalla["id"] + ".json")
    sett = set(sc.las_json(sett_p, []) or [])
    krav = re.compile(kalla["krav"], re.I) if kalla.get("krav") else None
    ut, nya = [], 0
    for u in urls:
        if u in sett:
            ut.append({"kalla_id": u, "url": u, "_bara_sedd": True})
            continue
        if nya >= int(kalla.get("max_nya", 25)):
            continue
        nya += 1
        sett.add(u)
        try:
            _, h, _ = sc.http(u, timeout=20)
        except sc.HttpFel:
            continue
        j = sc.jsonld_jobb(h) or {"titel": (re.search(r"<title>(.*?)</title>", h, re.S | re.I) or [None, u])[1],
                                  "text": sc.html_till_text(h)[:5000]}
        if krav and not krav.search(" ".join(str(j.get(k) or "") for k in ("ort", "land", "text"))):
            continue
        j.pop("land", None)
        j.update({"kalla_id": u, "url": u})
        j["arbetsgivare"] = j.get("arbetsgivare") or None
        ut.append(j)
    sc.skriv_json(sett_p, sorted(sett))
    return ut, True


ADAPTRAR = {"jobtech": ad_jobtech, "teamtailor_rss": ad_teamtailor, "lever": ad_lever, "ashby": ad_ashby,
            "greenhouse": ad_greenhouse, "smartrecruiters": ad_smartrecruiters, "workday": ad_workday,
            "pagehash": ad_pagehash, "sok_url": ad_sok_url, "rss": ad_rss, "json_api": ad_json_api,
            "sitemap": ad_sitemap}


# ---------------------------------------------------------------- körning

def filtrera(poster, recept):
    f = recept.get("filter") or {}
    ord_ = [w.lower() for w in f.get("exkludera_ord") or []]
    arb = [sc.norm(a) for a in f.get("exkludera_arbetsgivare") or []]
    ut = []
    for p in poster:
        if any(w in (p.get("titel") or "").lower() for w in ord_):
            continue
        if arb and sc.norm(p.get("arbetsgivare")) in arb:
            continue
        ut.append(p)
    return ut


def spara_signaler(home, kalla, poster):
    """Källor med "signal": true (t.ex. Cision) hamnar i sok/signaler.json, inte i jobb.
    "signalord" (lista, valfri) filtrerar på ord i titel/text. Högst 500 sparas."""
    p = sc.sokv(home, "signaler.json")
    d = sc.las_json(p, {"schema_version": 1, "signaler": []}) or {"schema_version": 1, "signaler": []}
    finns = {s.get("url") for s in d["signaler"]}
    ord_ = [w.lower() for w in kalla.get("signalord") or []]
    nya = 0
    for x in poster:
        text = sc.html_till_text(x.get("html") or "") if x.get("html") else (x.get("text") or "")
        hay = f"{x.get('titel', '')} {text}".lower()
        if x.get("url") in finns or (ord_ and not any(w in hay for w in ord_)):
            continue
        d["signaler"].append({"kalla": kalla["id"], "titel": x.get("titel"), "url": x.get("url"),
                              "publicerad": sc.iso_datum(x.get("publicerad")), "utdrag": sc.utdrag(text, 300),
                              "sedd": sc.nu_iso()})
        nya += 1
    d["signaler"] = d["signaler"][-500:]
    sc.skriv_json(p, d)
    return nya


def _kor_kallor(home, kallor, kids, recept, hittad_via, since):
    per_id = {k["id"]: k for k in kallor.get("kallor", [])}
    c = sc.db(home)
    start = sc.nu_iso()
    rapport = {"kallor": [], "natfel": []}
    lyckade, jobtech_fel = 0, False
    for kid in kids:
        k = per_id.get(kid)
        if not k:
            rapport["kallor"].append({"id": kid, "fel": "saknas i kallor.json"})
            continue
        if not k.get("aktiv", True) or k.get("typ") == "mejl":
            rapport["kallor"].append({"id": kid, "hoppad": k.get("typ") if k.get("aktiv", True) else "pausad"})
            continue
        if k.get("min_intervall_h") and k.get("senast_hamtad"):
            sedan = dt.datetime.now() - dt.datetime.fromisoformat(k["senast_hamtad"][:19])
            if sedan < dt.timedelta(hours=float(k["min_intervall_h"])):
                rapport["kallor"].append({"id": kid, "hoppad": f"min_intervall_h {k['min_intervall_h']}"})
                continue
        ad = ADAPTRAR.get(k.get("typ"))
        if not ad:
            rapport["kallor"].append({"id": kid, "fel": f"okänd typ {k.get('typ')}"})
            continue
        try:
            raa, fullst = ad(k, recept, home, since)
        except sc.NatFel as e:
            rapport["natfel"].append(str(e))
            rapport["kallor"].append({"id": kid, "fel": "nätfel: " + str(e)})
            jobtech_fel |= k["typ"] == "jobtech"
            continue
        except (sc.HttpFel, ValueError, ET.ParseError, KeyError, IndexError, TypeError) as e:
            rapport["kallor"].append({"id": kid, "fel": f"{type(e).__name__}: {e}"})
            jobtech_fel |= k["typ"] == "jobtech"
            continue
        lyckade += 1
        if k.get("signal"):
            n = spara_signaler(home, k, raa)
            k["senast_hamtad"] = start
            rapport["kallor"].append({"id": kid, "typ": k["typ"], "signaler": len(raa), "nya_signaler": n,
                                      "hamtade": 0, "nya": 0, "stangda": 0})
            continue
        bara_sedda = [sc.gor_uid(kid, p["kalla_id"]) for p in raa if p.get("_bara_sedd")]
        if bara_sedda:
            c.executemany("UPDATE jobb SET senast_sedd=? WHERE uid=?", [(start, u) for u in bara_sedda])
        raa = filtrera([p for p in raa if not p.get("_bara_sedd")], recept)
        for p in raa:
            p.setdefault("hittad_via", hittad_via)
        rader = [sc.normalisera(p, kid) for p in raa]
        nya, upd = sc.upsert(c, home, rader)
        stangda = sc.stang_forsvunna(c, kid, [r["uid"] for r in rader] + bara_sedda) if fullst else 0
        k["senast_hamtad"] = start
        if k.get("_ny_hash"):
            k["hash"] = k.pop("_ny_hash")
        rapport["kallor"].append({"id": kid, "typ": k["typ"], "hamtade": len(rader), "nya": nya,
                                  "uppdaterade": upd, "stangda": stangda})
    rapport["stangda_deadline"] = sc.stang_utgangna(c)
    return rapport, lyckade, jobtech_fel, start


def kor_recept(home, namn, full=False):
    rp = sc.sokv(home, "recept", namn + ".json")
    recept = sc.las_json(rp)
    if recept is None:
        raise SystemExit(f"Receptet finns inte: {rp}")
    kp = sc.sokv(home, "kallor.json")
    kallor = sc.las_json(kp, {"schema_version": 1, "kallor": []})
    since = None
    if recept.get("senast_kord") and not full:
        since = (dt.datetime.fromisoformat(recept["senast_kord"][:19]) - dt.timedelta(hours=1)).isoformat()
    rapport, lyckade, jobtech_fel, start = _kor_kallor(home, kallor, recept.get("kallor", []), recept, namn, since)
    rapport = {"recept": namn, "inkrementell_fran": since, **rapport}
    if lyckade:
        if not jobtech_fel:  # annars hämtas samma tidsfönster igen nästa gång
            recept["senast_kord"] = start
            sc.skriv_json(rp, recept)
        sc.skriv_json(kp, kallor)
    rapport["ok"] = lyckade > 0 or not recept.get("kallor")
    return rapport


def kor_bevakade(home, utom=()):
    """Hämtar alla aktiva källor (utom jobtech, som kräver recept, och de i 'utom')."""
    kp = sc.sokv(home, "kallor.json")
    kallor = sc.las_json(kp, {"schema_version": 1, "kallor": []})
    kids = [k["id"] for k in kallor.get("kallor", []) if k["id"] not in set(utom)
            and k.get("typ") not in ("jobtech", "mejl") and k.get("aktiv", True)]
    rapport, lyckade, _, _ = _kor_kallor(home, kallor, kids, {}, "bevakning", None)
    if lyckade:
        sc.skriv_json(kp, kallor)
    rapport = {"recept": "(bevakade källor)", **rapport}
    rapport["ok"] = lyckade > 0 or not kids
    return rapport


def recept_kallor(home):
    import glob
    ut = set()
    for p in glob.glob(sc.sokv(home, "recept", "*.json")):
        ut |= set((sc.las_json(p, {}) or {}).get("kallor") or [])
    return ut


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recept")
    g.add_argument("--alla-bevakade", action="store_true",
                   help="hämta alla aktiva källor i kallor.json, även de som inte ingår i något recept")
    ap.add_argument("--full", action="store_true", help="ignorera senast_kord och hämta allt")
    sc.add_home_arg(ap)
    a = ap.parse_args()
    home = sc.hem(a.home)
    r = kor_recept(home, a.recept, a.full) if a.recept else kor_bevakade(home)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if not r["ok"] and r["natfel"]:
        sc.natfel_avslut("; ".join(r["natfel"]))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
