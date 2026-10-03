#!/usr/bin/env python3
"""Sparar ett ställe som användaren själv hittat, så att det bevakas. Hanterar också listan.

  python3 kalla_lagg_till.py <url> [--namn "Bolag"] [--anteckning "..."] [--typ mejl] [--prova] [--home DIR]
  python3 kalla_lagg_till.py --lista
  python3 kalla_lagg_till.py --pausa <id>      (aktiv=false; --aktivera <id> slår på igen)
  python3 kalla_lagg_till.py --ta-bort <id>    flyttar posten till sok/kallor_borttagna.json (ingen radering)

Lägga till: kör upptack_ats-logiken. Hittas ett flöde (Teamtailor, Lever, Ashby, Greenhouse,
SmartRecruiters, Workday, Varbi-RSS eller annan jobb-RSS) registreras det. Annars: jobblista -> pagehash (med 'lankmonster' när
annonslänkar hittas), jobbsajt med sökfilter i querysträngen -> sok_url, LinkedIn/Indeed m.fl. ->
mejl med en instruktion. --typ mejl tvingar mejlaviseringstypen (för sajter som bara har sådana).
Alla får "tillagd_av":"anvandare" och "tillagd": datum. --prova provhämtar direkt och lägger in träffarna.
Utdata: JSON med {"atgard","kalla","beskrivning"} där beskrivning är en mening att bekräfta för användaren.
"""
import argparse
import json
import sys

import fetch
import sok_common as sc
import upptack_ats

BESKR = {
    "teamtailor_rss": "Teamtailor-flödet (RSS) hämtas vid varje körning",
    "lever": "Lever-flödet (JSON) hämtas vid varje körning",
    "ashby": "Ashby-flödet (JSON) hämtas vid varje körning",
    "greenhouse": "Greenhouse-flödet (JSON) hämtas vid varje körning",
    "smartrecruiters": "SmartRecruiters-flödet hämtas vid varje körning",
    "workday": "Workday-listan hämtas vid varje körning (inofficiellt gränssnitt, kan sluta fungera)",
    "pagehash": "sidan läses vid varje körning",
    "sok_url": "den sparade sökningen körs vid varje körning och nya annonslänkar plockas ut",
    "rss": "RSS-flödet hämtas vid varje körning",
    "json_api": "JSON-flödet hämtas vid varje körning",
    "sitemap": "sitemapen läses vid varje körning och bara nya annonssidor hämtas",
    "mejl": "inget hämtas automatiskt; träffar kommer via jobbaviseringar i mejl eller inklistrade länkar",
}


def _kp(home):
    return sc.sokv(home, "kallor.json")


def las(home):
    return sc.las_json(_kp(home), {"schema_version": 1, "kallor": []}) or {"schema_version": 1, "kallor": []}


def beskriv(k):
    b = BESKR.get(k["typ"], k["typ"])
    if k["typ"] == "pagehash":
        b += "; varje ny annonslänk blir en träff" if k.get("lankmonster") else "; en ändring av texten blir en träff"
    return f"{k.get('namn')}: {b}."


def lagg_till(home, url, namn=None, anteckning=None, typ=None):
    data = las(home)
    for k in data["kallor"]:
        if k.get("url") == url or k.get("kalla_url") == url:
            return {"atgard": "fanns_redan", "kalla": k, "beskrivning": beskriv(k)}
    if typ == "mejl":
        r = {"forslag": {"id": upptack_ats._id(namn or url), "typ": "mejl", "namn": namn or url, "url": url,
                         "aktiv": True, "instruktion": "Skapa en jobbavisering på sajten med dina filter. Mejlen "
                         "läses via Gmail-kopplingen, eller klistra in länkar."}}
    else:
        r = upptack_ats.upptack(url, home, namn)
    k = dict(r["forslag"])
    if k["url"] != url:
        k["kalla_url"] = url
    ids = {x["id"] for x in data["kallor"]}
    bas, i = k["id"], 2
    while k["id"] in ids:
        k["id"] = f"{bas}-{i}"
        i += 1
    if anteckning:
        k["anteckning"] = (anteckning + " " + k.get("anteckning", "")).strip()
    if r.get("anteckning"):
        k.setdefault("anteckning", r["anteckning"])
    k.update({"senast_hamtad": None, "etag": None, "hash": None, "tillagd_av": "anvandare", "tillagd": sc.idag()})
    data["kallor"].append(k)
    sc.skriv_json(_kp(home), data)
    return {"atgard": "tillagd", "kalla": k, "verifierad": r.get("verifierad"),
            "antal_annonser_nu": r.get("antal_annonser"), "beskrivning": beskriv(k)}


def satt_aktiv(home, kid, aktiv):
    data = las(home)
    for k in data["kallor"]:
        if k["id"] == kid:
            k["aktiv"] = aktiv
            sc.skriv_json(_kp(home), data)
            return {"atgard": "aktiverad" if aktiv else "pausad", "kalla": k}
    sys.exit(f"Ingen källa med id {kid}")


def ta_bort(home, kid):
    data = las(home)
    k = next((x for x in data["kallor"] if x["id"] == kid), None)
    if not k:
        sys.exit(f"Ingen källa med id {kid}")
    data["kallor"].remove(k)
    bp = sc.sokv(home, "kallor_borttagna.json")
    b = sc.las_json(bp, {"schema_version": 1, "kallor": []}) or {"schema_version": 1, "kallor": []}
    k["borttagen"] = sc.idag()
    b["kallor"].append(k)
    sc.skriv_json(bp, b)
    sc.skriv_json(_kp(home), data)
    return {"atgard": "borttagen", "kalla": k, "sparad_i": bp}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--namn")
    ap.add_argument("--anteckning")
    ap.add_argument("--typ", choices=["mejl"])
    ap.add_argument("--prova", action="store_true")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--pausa")
    ap.add_argument("--aktivera")
    ap.add_argument("--ta-bort")
    sc.add_home_arg(ap)
    a = ap.parse_args()
    home = sc.hem(a.home)
    if a.lista:
        for k in las(home)["kallor"]:
            print(f"{k['id']} | {k['typ']} | {k.get('namn')} | {'aktiv' if k.get('aktiv', True) else 'pausad'} | "
                  f"{k.get('tillagd_av', '-')} {k.get('tillagd') or ''} | senast {k.get('senast_hamtad') or '-'} | {k.get('url')}")
        return
    if a.pausa or a.aktivera:
        r = satt_aktiv(home, a.pausa or a.aktivera, bool(a.aktivera))
    elif a.ta_bort:
        r = ta_bort(home, a.ta_bort)
    elif a.url:
        try:
            r = lagg_till(home, a.url, a.namn, a.anteckning, a.typ)
            if a.prova and r["kalla"]["typ"] not in ("mejl", "jobtech"):
                data = las(home)
                rap, _, _, _ = fetch._kor_kallor(home, data, [r["kalla"]["id"]], {}, "bevakning", None)
                sc.skriv_json(_kp(home), data)
                r["provhamtning"] = rap["kallor"]
        except sc.NatFel as e:
            sc.natfel_avslut(e)
        except sc.HttpFel as e:
            if e.status in (401, 403, 429):
                sys.exit(f"Sidan blockerar automatisk hämtning ({e.status}). Den kan inte bevakas av skripten. "
                         "Använd sajtens mejlavisering (lägg till med --typ mejl) eller låt Claude titta med "
                         "webbverktyget och mata in via ingest.py.")
            sys.exit(f"Kunde inte hämta sidan: {e}")
    else:
        ap.error("ange en url, --lista, --pausa, --aktivera eller --ta-bort")
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
