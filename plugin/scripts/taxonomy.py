#!/usr/bin/env python3
"""Sök i JobTech Taxonomy och cacha svaren i <home>/cache/taxonomy/.

    python3 taxonomy.py sok "projektledning" [--typ skill] [--home DIR] [--offline]
    python3 taxonomy.py spara "projektledning" --fil svar.json [--typ skill] [--home DIR]

`sok` läser först cachen, annars API:t:
  https://taxonomy.api.jobtechdev.se/v1/taxonomy/main/concepts?type=<typ>&preferred-label=<term>
och om den exakta sökningen ger noll träffar prefixsökningen
  https://taxonomy.api.jobtechdev.se/v1/taxonomy/suggesters/autocomplete?query-string=<term>&type=<typ>
Om nätet är blockerat (vanligt i Coworks sandlåda) blir exit-kod 3 och utskriften
innehåller "natverk": false och den URL som Claude då hämtar med sitt webbverktyg.
Det svaret sparas sedan i cachen med `spara`.

Utskrift (JSON): {"term", "typ", "fran": "cache|api|saknas", "traffar": [{"id", "namn", "typ"}], "url"}
Typer: skill, occupation-name, ssyk-level-4, municipality, region ...
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobbsok_common as jc  # noqa: E402

BAS = "https://taxonomy.api.jobtechdev.se/v1/taxonomy/main/concepts"
AUTO = "https://taxonomy.api.jobtechdev.se/v1/taxonomy/suggesters/autocomplete"


def url_for(term, typ):
    """Exakt träff på preferred-label (skiftlägeskänslig)."""
    return BAS + "?" + urllib.parse.urlencode({"type": typ, "preferred-label": term})


def auto_url(term, typ):
    """Prefixsökning, används när exakt träff saknas."""
    return AUTO + "?" + urllib.parse.urlencode({"query-string": term, "type": typ})


def _hamta(url, timeout):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "jobbsok-plugin"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def cache_path(home, term, typ):
    return home / "cache" / "taxonomy" / f"{typ}-{jc.slugify(term, 60)}.json"


def normalisera(raw):
    out = []
    for c in raw if isinstance(raw, list) else []:
        cid = c.get("taxonomy/id") or c.get("id")
        namn = c.get("taxonomy/preferred-label") or c.get("preferred_label") or c.get("preferred-label")
        if cid:
            out.append({"id": cid, "namn": namn, "typ": c.get("taxonomy/type") or c.get("type")})
    return out


def sok(home, term, typ="skill", offline=False, timeout=10):
    res = {"term": term, "typ": typ, "url": url_for(term, typ)}
    cp = cache_path(home, term, typ)
    cached = jc.read_json(cp)
    if cached is not None:
        return {**res, "fran": "cache", "traffar": cached.get("traffar", []), "natverk": None}
    if offline:
        return {**res, "fran": "saknas", "traffar": [], "natverk": False}
    try:
        raw = _hamta(res["url"], timeout)
        if not raw:
            res["url"] = auto_url(term, typ)
            raw = _hamta(res["url"], timeout)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {**res, "fran": "saknas", "traffar": [], "natverk": False, "fel": str(e)[:200]}
    traffar = normalisera(raw)
    jc.write_json(cp, {"term": term, "typ": typ, "traffar": traffar}, backup=False)
    return {**res, "fran": "api", "traffar": traffar, "natverk": True}


def spara(home, term, typ, raw):
    traffar = normalisera(raw) if isinstance(raw, list) else raw.get("traffar", [])
    jc.write_json(cache_path(home, term, typ), {"term": term, "typ": typ, "traffar": traffar}, backup=False)
    return {"term": term, "typ": typ, "fran": "sparad", "traffar": traffar}


def main(argv=None):
    ap = argparse.ArgumentParser(description="JobTech Taxonomy: sök och cache.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("sok", "spara"):
        p = jc.add_home_arg(sub.add_parser(n))
        p.add_argument("term")
        p.add_argument("--typ", default="skill")
        if n == "sok":
            p.add_argument("--offline", action="store_true")
        else:
            p.add_argument("--fil", required=True, help="JSON från API:t (lista) eller {traffar:[...]}")
    a = ap.parse_args(argv)
    home = jc.resolve_home(a.home)
    if a.cmd == "sok":
        r = sok(home, a.term, a.typ, a.offline)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 3 if r["natverk"] is False else 0
    r = spara(home, a.term, a.typ, jc.read_json(a.fil))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
