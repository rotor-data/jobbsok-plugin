#!/usr/bin/env python3
"""Testar vilka domäner pluginen behöver som går att nå härifrån, och vilka PDF-motorer som finns.

  python3 natkoll.py [--spara] [--home DIR] [--timeout 6]

--spara skriver resultatet till profil/miljo.json (jobbsok-start gör det första gången).
Exit 0 = alla nödvändiga domäner nås, 3 = minst en nödvändig domän är blockerad.

En domän räknas som nåbar om den svarar med vilken HTTP-status som helst, utom ett 403/407 från en
proxy som säger att domänen inte är tillåten (Cowork-sandlådans allowlist). Nätfel, DNS-fel och
timeout räknas som blockerad. JOBBSOK_OFFLINE=1 testar inget och markerar allt som "ej testad".
"""
import argparse
import datetime as dt
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# (domän, test-URL, nödvändig, vad den används till)
DOMANER = [
    ("jobsearch.api.jobtechdev.se", "https://jobsearch.api.jobtechdev.se/search?limit=0", True,
     "Platsbanken: söka jobb"),
    ("taxonomy.api.jobtechdev.se", "https://taxonomy.api.jobtechdev.se/v1/taxonomy/main/concept-types", True,
     "yrken, orter och kompetenser"),
    ("historical.api.jobtechdev.se", "https://historical.api.jobtechdev.se/", False,
     "rollkort: annonser bakåt i tiden"),
    ("jobad-enrichments-api.jobtechdev.se", "https://jobad-enrichments-api.jobtechdev.se/", False,
     "bättre kompetensmatchning"),
    ("api.scb.se", "https://api.scb.se/OV0104/v1/doris/sv/ssd/", False, "rollkort: löner"),
    ("api.kolada.se", "https://api.kolada.se/v3/kpi?title=sjukfr", False, "arbetsgivarkort: kommuner och regioner"),
    ("news.cision.com", "https://news.cision.com/se", False, "arbetsgivarkort: pressmeddelanden"),
    ("gw.api.bolagsverket.se", "https://gw.api.bolagsverket.se/", False, "arbetsgivarkort: ekonomi (kräver nyckel)"),
    ("boards-api.greenhouse.io", "https://boards-api.greenhouse.io/v1/boards/x/jobs", False, "bolagens jobbsidor"),
    ("api.smartrecruiters.com", "https://api.smartrecruiters.com/v1/companies/x/postings", False, "bolagens jobbsidor"),
    ("api.ashbyhq.com", "https://api.ashbyhq.com/posting-api/job-board/x", False, "bolagens jobbsidor"),
    ("teamtailor.com", "https://www.teamtailor.com/", False, "bolagens jobbsidor (Teamtailor)"),
    ("varbi.com", "https://uu.varbi.com/", False, "bolagens jobbsidor (Varbi)"),
    ("pypi.org", "https://pypi.org/simple/weasyprint/", False, "installera PDF-motorn WeasyPrint"),
    ("files.pythonhosted.org", "https://files.pythonhosted.org/", False, "installera PDF-motorn WeasyPrint"),
]

BLOCK_ORD = ("not allowed", "not in allowlist", "allowlist", "blocked", "forbidden by proxy", "egress", "denied")


def prova(url, timeout=6):
    """Returnerar (status, detalj). status: 'ok' | 'blockerad'."""
    req = urllib.request.Request(url, headers={"User-Agent": "jobbsok-natkoll/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            return "ok", f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        try:
            text = e.read(2000).decode("utf-8", "replace").lower()
        except Exception:
            text = ""
        hdr = " ".join(f"{k}: {v}" for k, v in (e.headers or {}).items()).lower()
        if e.code in (403, 407) and any(o in text or o in hdr for o in BLOCK_ORD):
            return "blockerad", f"HTTP {e.code} från proxy"
        return "ok", f"HTTP {e.code}"
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        orsak = getattr(e, "reason", e)
        return "blockerad", str(orsak)[:120]


def kolla(timeout=6, prova_fn=prova):
    offline = os.environ.get("JOBBSOK_OFFLINE") == "1"
    rader = []
    for dom, url, behovs, till in DOMANER:
        if offline:
            st, det = "ej testad", "JOBBSOK_OFFLINE=1"
        else:
            st, det = prova_fn(url, timeout)
        rader.append({"doman": dom, "status": st, "nodvandig": behovs, "anvands_till": till, "detalj": det})
    blockerade = [r["doman"] for r in rader if r["status"] == "blockerad"]
    nodv = [r["doman"] for r in rader if r["status"] == "blockerad" and r["nodvandig"]]
    try:
        import render
        pdf = render.motorer()
    except Exception as e:  # natkoll ska fungera även om render inte går att ladda
        pdf = {"fel": str(e)[:120]}
    lage = "ej testad" if offline else ("reserv" if nodv else "begransat" if blockerade else "fullt")
    return {
        "schema_version": 1,
        "testad": dt.datetime.now().isoformat(timespec="seconds"),
        "lage": lage,
        "domaner": rader,
        "blockerade": blockerade,
        "nodvandiga_blockerade": nodv,
        "pdf": pdf,
        "tolkning": {
            "fullt": "Allt nås. Skripten hämtar själva.",
            "begransat": "Sökningen fungerar; vissa tillägg (se blockerade) hoppas över eller görs via webbverktyget.",
            "reserv": "Platsbanken nås inte från skripten. Reservläge: Claude hämtar med webbverktyget och matar in "
                      "via ingest.py (långsammare). Tillåt domänerna i inställningarna för att slippa det.",
            "ej testad": "Inget testat (offline-läge).",
        }[lage],
    }


def main(argv=None):
    import jobbsok_common as jc
    ap = jc.add_home_arg(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--spara", action="store_true", help="skriv profil/miljo.json")
    ap.add_argument("--timeout", type=float, default=6)
    a = ap.parse_args(argv)
    res = kolla(a.timeout)
    if a.spara:
        home = jc.resolve_home(a.home)
        p = home / "profil" / "miljo.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        res["sparad"] = str(p)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 3 if res["nodvandiga_blockerade"] else 0


if __name__ == "__main__":
    sys.exit(main())
