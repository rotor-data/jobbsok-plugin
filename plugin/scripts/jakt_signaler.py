#!/usr/bin/env python3
"""Tillväxtsignaler ur pressmeddelanden (dolda marknaden) för skillen jobbjakt.

  python3 jakt_signaler.py [--bolag "Namn" ...] [--cision-slug slug ...] [--rss URL ...]
                           [--sok "nyanställer Uppsala" ...] [--fran-kallor] [--dagar 60]
                           [--alla] [--nya] [--home DIR]

Källor:
  - Cision (tillåtet i robots.txt): https://news.cision.com/se/ListItems?format=rss
      per bolag:  https://news.cision.com/se/<slug>/ListItems?format=rss
      fritext:    ...ListItems?format=rss&q=<ord>
  - Bolagens egna pressrums-RSS (--rss). robots.txt kontrolleras före varje hämtning.
  - MFN används INTE: mfn.se förbjuder *.rss i robots.txt.
Utan källflaggor: Cisions allmänna flöde plus fritextsökningar på tillväxtorden.

Filtrerar på tillväxtord (nyanställer, expanderar, nytt kontor, förvärv, kapital, ny vd/chef,
upphandling) och knyter träffarna till målbolag (--bolag, och med --fran-kallor namnen i
sok/kallor.json). --alla visar även träffar utan tillväxtord. Fynden sparas i sok/signaler.json;
--nya visar bara sådant som inte setts förut.
Utdata: kompakt JSON, en rad per signal (≤200 tecken utdrag). Nätfel: exit 3.
"""
import argparse
import datetime as dt
import re
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET

import jakt_common as jc
import sok_common as sc

CISION = "https://news.cision.com/se/ListItems"
SIGNALER = {
    "nyanställer": r"nyanställ|anställer|rekryter|söker fler|växer med \d+ (personer|medarbetare)|hiring|new hires",
    "expanderar": r"expander|expansion|växer|utökar|satsning|skalar upp|bygger ut|ökar kapaciteten|expands",
    "nytt_kontor": r"nytt kontor|öppnar kontor|nya kontor|etablerar|ny etablering|öppnar i|nytt huvudkontor|new office",
    "förvärv": r"förvärv|köper\b|uppköp|går samman|fusion|acquir|merger",
    "kapital": r"nyemission|kapitalanskaffning|tar in \d|riskkapital|finansieringsrunda|investering på|raises|funding round|series [abc]\b",
    "ny_ledning": r"ny vd|utser .{0,40}(vd|chef|direktör)|utnämn|tillträder|ny chef|rekryterar .{0,30}(vd|chef)|appoints|new ceo|ny styrelseordförande",
    "upphandling": r"upphandling|tilldela|vinner (avtal|order|uppdrag)|ramavtal|tecknar avtal|order värd|kontrakt|awarded|contract",
}
SOKORD = ["nyanställer", "rekryterar", "etablerar", "nytt kontor", "förvärvar", "utser ny vd", "vinner upphandling"]
_robots = {}


def tillats(url):
    p = urllib.parse.urlsplit(url)
    bas = f"{p.scheme}://{p.netloc}"
    if bas not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _, txt, _ = sc.http(bas + "/robots.txt", timeout=10)
            rp.parse(txt.splitlines())
        except sc.HttpFel:
            rp.parse([])          # ingen robots.txt = tillåtet
        except sc.NatFel as e:
            sc.natfel_avslut(e)
        _robots[bas] = rp
    return _robots[bas].can_fetch(sc.USER_AGENT, url)


def tolka_flode(xml):
    """RSS 2.0 eller Atom -> [{titel, url, datum, text}]"""
    xml = xml.lstrip("﻿")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    ut = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        f = {}
        for c in it:
            n = c.tag.split("}")[-1]
            if n == "title":
                f["titel"] = (c.text or "").strip()
            elif n == "link":
                f["url"] = (c.text or c.get("href") or "").strip()
            elif n in ("pubDate", "published", "updated") and "datum" not in f:
                f["datum"] = sc.iso_datum(c.text)
            elif n in ("description", "summary", "content") and not f.get("text"):
                f["text"] = sc.html_till_text(c.text or "")
        if f.get("titel"):
            ut.append(f)
    return ut


def hamta(url):
    if not tillats(url):
        return None, f"robots.txt tillåter inte {url}"
    try:
        _, txt, _ = sc.http(url, headers=dict(Accept="application/rss+xml, application/xml, text/xml"))
    except sc.NatFel as e:
        sc.natfel_avslut(e)
    except sc.HttpFel as e:
        return None, str(e)
    return tolka_flode(txt), None


def klassa(text):
    t = text.lower()
    return [k for k, m in SIGNALER.items() if re.search(m, t)]


def bolag_ur_url(url):
    m = re.search(r"news\.cision\.com/\w+/([\w-]+)/r/", url or "")
    return m.group(1) if m else None


def matcha_bolag(post, bolag):
    hay = sc.norm(" ".join([post.get("titel", ""), post.get("text", "")[:600], post.get("url", "")]))
    for b in bolag:
        nb = sc.norm(b)
        if nb and re.search(r"\b" + re.escape(nb) + r"\b", hay):
            return b
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bolag", action="append", default=[], help="målbolag att knyta träffar till (och söka på)")
    ap.add_argument("--cision-slug", action="append", default=[], help="bolagets slug på news.cision.com/se/<slug>")
    ap.add_argument("--rss", action="append", default=[], help="egen pressrums-RSS")
    ap.add_argument("--sok", action="append", default=[], help="fritextsökning i Cision")
    ap.add_argument("--fran-kallor", action="store_true", help="använd namnen i sok/kallor.json som målbolag")
    ap.add_argument("--dagar", type=int, default=60)
    ap.add_argument("--alla", action="store_true", help="visa även träffar utan tillväxtord")
    ap.add_argument("--nya", action="store_true", help="bara sådant som inte setts i tidigare körningar")
    ap.add_argument("--antal", type=int, default=40)
    sc.add_home_arg(ap)
    a = ap.parse_args(argv)
    home = sc.hem(a.home)

    bolag = list(a.bolag)
    if a.fran_kallor:
        bolag += [k["namn"] for k in (sc.las_json(sc.sokv(home, "kallor.json"), {}) or {}).get("kallor", [])
                  if k.get("namn") and k.get("typ") not in ("jobtech", "mejl")]
    urls = [f"https://news.cision.com/se/{s}/ListItems?format=rss" for s in a.cision_slug]
    urls += [r for r in a.rss if "mfn.se" not in r]
    hoppade = [{"url": r, "skal": "MFN förbjuder automatisk läsning av RSS (robots.txt)"} for r in a.rss if "mfn.se" in r]
    sok = list(a.sok) + [f'"{b}"' for b in a.bolag]
    if not (urls or sok):
        urls.append(CISION + "?format=rss&pageSize=50")
        sok = SOKORD
    urls += [CISION + "?" + urllib.parse.urlencode({"format": "rss", "q": q, "pageSize": 50}) for q in sok]

    gransen = (dt.datetime.now() - dt.timedelta(days=a.dagar)).isoformat()
    sedda_fil = sc.sokv(home, "signaler.json")
    sparat = sc.las_json(sedda_fil) or {"schema_version": 1, "signaler": []}
    kanda = {s["url"] for s in sparat["signaler"]}
    ut, fel, sett = [], [], set()
    for u in urls:
        poster, f = hamta(u)
        if f:
            fel.append(f)
            continue
        for p in poster:
            if not p.get("url") or p["url"] in sett:
                continue
            sett.add(p["url"])
            if p.get("datum") and p["datum"] < gransen:
                continue
            sig = klassa(p["titel"] + " " + p.get("text", "")[:1500])
            mal = matcha_bolag(p, bolag) if bolag else None
            if not sig and not a.alla:
                continue
            if a.nya and p["url"] in kanda:
                continue
            ut.append({"bolag": mal or bolag_ur_url(p["url"]), "malbolag": bool(mal), "signaler": sig,
                       "titel": p["titel"][:160], "datum": (p.get("datum") or "")[:10], "url": p["url"],
                       "utdrag": sc.utdrag(p.get("text", ""), 200)})
    ut.sort(key=lambda x: x["datum"], reverse=True)
    ut.sort(key=lambda x: (not x["malbolag"], -len(x["signaler"])))
    ut = ut[: a.antal]
    for s in ut:
        if s["url"] not in kanda:
            sparat["signaler"].append(dict(s, sedd=sc.idag()))
    sparat["signaler"] = sparat["signaler"][-500:]
    sc.skriv_json(sedda_fil, sparat)
    jc.skriv({"antal": len(ut), "kallor": len(urls), "fel": fel, "hoppade": hoppade, "signaler": ut,
              "tolkning": "en signal är ett skäl att kontakta bolaget, inte en annons. Föreslå utkast till "
                          "kontaktmejl/spontanansökan (aldrig autoskick) eller hypotes av typ tillvaxtsignal."})


if __name__ == "__main__":
    main()
