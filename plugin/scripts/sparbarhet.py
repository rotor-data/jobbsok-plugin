#!/usr/bin/env python3
"""sparbarhet.py – kontrollerar att CV och brev bara bygger på faktabanken.

Kontroller:
  1. Varje rad i cv.json (punkter, text i poster med kalla) och varje stycke i
     brev.json har `kalla` med id som finns i profil/fakta.json. Ett brevstycke med
     tom lista `[]` blir en varning (avslut utan sakpåståenden), saknad källa ett fel.
  2. Siffror i texten som inte finns i faktabankens `siffror` flaggas.
     Finns siffran någon annanstans i fakta.json blir det en varning, annars fel.
  3. Ord och fraser ur `aldrig_pastaa` (fakta.json) och `aldrig_ord` (rost.json).
     Fritextposter i aldrig_pastaa matchas som hela fraser, plus det som står
     inom citattecken. Längre meningar måste också läsas av Claude.

Användning:
  python3 sparbarhet.py <ansökningsmapp>            # läser cv.json och brev.json där
  python3 sparbarhet.py cv.json brev.json
  Flaggor: --home (annars $JOBBSOK_HOME eller ~/Jobbsok), --fakta, --rost

Exit 0 = inga fel eller varningar, 2 = något flaggat, 1 = fel i indata.
"""
import argparse
import json
import os
import re
import sys

TAL_RE = re.compile(r"\d+(?:[  ]\d{3})*(?:[.,]\d+)?")


def norm_tal(s):
    s = re.sub(r"[ \u00a0\u202f]", "", s)
    s = re.sub(r",(?=\d{3}(?!\d))", "", s)  # engelsk tusentalsavgränsare: 4,000
    return s.replace(",", ".")


def txt(v, sprak="sv"):
    if isinstance(v, dict):
        return v.get(sprak) or next((x for x in v.values() if isinstance(x, str)), "")
    return v if isinstance(v, str) else ""


def alla_strangar(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from alla_strangar(x)
    elif isinstance(v, list):
        for x in v:
            yield from alla_strangar(x)


def fakta_index(fakta):
    ids = set()
    for r in fakta.get("roller", []):
        ids.add(r.get("id"))
        for m in r.get("meriter", []):
            ids.add(m.get("id"))
    for key in ("utbildning", "kurser", "kompetenser", "ideella"):
        for x in fakta.get(key, []):
            ids.add(x.get("id"))
    ids.discard(None)
    siffror = set()
    for r in fakta.get("roller", []):
        for m in r.get("meriter", []):
            for s in m.get("siffror", []) or []:
                for t in TAL_RE.findall(str(s.get("varde", ""))):
                    siffror.add(norm_tal(t))
    # Årtal ur perioderna ("sedan 2014") är belagda, inte lösa siffror.
    for key in ("roller", "utbildning", "kurser", "ideella"):
        for x in fakta.get(key, []) or []:
            for f in ("start", "slut", "ar"):
                if isinstance(x.get(f), str) and re.match(r"\d{4}", x[f]):
                    siffror.add(x[f][:4])
    ovrigt = set()
    for s in alla_strangar({k: v for k, v in fakta.items() if k != "aldrig_pastaa"}):
        for t in TAL_RE.findall(s):
            ovrigt.add(norm_tal(t))
    return ids, siffror, ovrigt


def forbjudna_fraser(fakta, rost):
    fraser = []
    for p in fakta.get("aldrig_pastaa", []) or []:
        p = p.strip()
        if not p:
            continue
        fraser.append(("aldrig_pastaa", p))
        for q in re.findall(r"[\"“”«»'‘’]([^\"“”«»'‘’]{2,60})[\"“”«»'‘’]", p):
            fraser.append(("aldrig_pastaa", q.strip()))
    for o in (rost or {}).get("aldrig_ord", []) or []:
        if o.strip():
            fraser.append(("aldrig_ord", o.strip()))
    return fraser


def rader_cv(cv):
    """(fält, text, kalla|None, kräver_källa)"""
    sprak = cv.get("sprak", "sv")
    ut = []
    if cv.get("profil"):
        ut.append(("profil", txt(cv["profil"], sprak), None, False))
    for si, sek in enumerate(cv.get("sektioner", [])):
        base = f"cv.sektioner[{si}]"
        if sek.get("text"):
            ut.append((f"{base}.text", txt(sek["text"], sprak), None, False))
        for pi, p in enumerate(sek.get("poster", []) or []):
            if not isinstance(p, dict):
                continue
            kalla = p.get("kalla")
            if p.get("text"):
                ut.append((f"{base}.poster[{pi}].text", txt(p["text"], sprak), kalla, False))
            for ri, r in enumerate(p.get("punkter", []) or []):
                ut.append((f"{base}.poster[{pi}].punkter[{ri}]", txt(r, sprak), kalla, True))
    return ut


def rader_brev(brev):
    sprak = brev.get("sprak", "sv")
    kpp = brev.get("kalla_per_stycke", []) or []
    ut = []
    for i, s in enumerate(brev.get("stycken", [])):
        ut.append((f"brev.stycken[{i}]", txt(s, sprak), kpp[i] if i < len(kpp) else None, True))
    return ut


def kontrollera(rader, ids, siffror, ovrigt, fraser):
    fynd = []
    for falt, text, kalla, krav in rader:
        if krav:
            if kalla == [] and falt.startswith("brev."):
                fynd.append({"regel": "stycke_utan_kalla", "falt": falt, "citat": text[:80], "allvar": "varning",
                             "forslag": "Stycket har ingen källa. Okej bara om det saknar påståenden om henne (t.ex. avslutet)."})
            elif not kalla:
                fynd.append({"regel": "saknar_kalla", "falt": falt, "citat": text[:80], "allvar": "fel",
                             "forslag": "Ange vilken merit i faktabanken raden bygger på, eller stryk raden."})
            else:
                okanda = [k for k in kalla if k not in ids]
                if okanda:
                    fynd.append({"regel": "okand_kalla", "falt": falt, "citat": ", ".join(okanda), "allvar": "fel",
                                 "forslag": "Id:t finns inte i fakta.json. Rätta id:t eller lägg in meriten först."})
        for m in TAL_RE.finditer(text):
            t = norm_tal(m.group(0))
            if t in siffror:
                continue
            if t in ovrigt:
                fynd.append({"regel": "siffra_utanfor_siffror", "falt": falt, "citat": m.group(0), "allvar": "varning",
                             "forslag": "Siffran finns i faktabanken men inte under `siffror`. Kontrollera att den används rätt."})
            else:
                fynd.append({"regel": "siffra_saknas_i_fakta", "falt": falt, "citat": m.group(0), "allvar": "fel",
                             "forslag": "Siffran finns inte i faktabanken. Stryk den eller lägg in den i fakta.json efter att hon bekräftat den."})
        low = text.lower()
        for kalla_namn, fras in fraser:
            if re.search(rf"(?<![^\W_]){re.escape(fras.lower())}(?![^\W_])", low):
                fynd.append({"regel": kalla_namn, "falt": falt, "citat": fras, "allvar": "fel",
                             "forslag": "Det här får inte stå i texten. Skriv om utan det."})
    return fynd


def las(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Spårbarhet: CV och brev mot faktabanken.")
    ap.add_argument("vagar", nargs="+", help="ansökningsmapp eller cv.json/brev.json")
    ap.add_argument("--home", default=os.environ.get("JOBBSOK_HOME", os.path.expanduser("~/Jobbsok")))
    ap.add_argument("--fakta")
    ap.add_argument("--rost")
    a = ap.parse_args(argv)
    filer = []
    for v in a.vagar:
        if os.path.isdir(v):
            filer += [os.path.join(v, n) for n in ("cv.json", "brev.json") if os.path.exists(os.path.join(v, n))]
        else:
            filer.append(v)
    fakta_p = a.fakta or os.path.join(a.home, "profil", "fakta.json")
    rost_p = a.rost or os.path.join(a.home, "profil", "rost.json")
    try:
        fakta = las(fakta_p)
        rost = las(rost_p) if os.path.exists(rost_p) else {}
        docs = [(f, las(f)) for f in filer]
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"fel": str(e)}, ensure_ascii=False))
        return 1
    if not docs:
        print(json.dumps({"fel": "Hittade varken cv.json eller brev.json."}, ensure_ascii=False))
        return 1
    ids, siffror, ovrigt = fakta_index(fakta)
    fraser = forbjudna_fraser(fakta, rost)
    fynd = []
    for f, d in docs:
        rader = rader_brev(d) if "stycken" in d else rader_cv(d)
        for x in kontrollera(rader, ids, siffror, ovrigt, fraser):
            x["fil"] = os.path.basename(f)
            fynd.append(x)
        if "stycken" in d and len(d.get("kalla_per_stycke", []) or []) != len(d.get("stycken", [])):
            fynd.append({"fil": os.path.basename(f), "regel": "kalla_per_stycke_langd", "falt": "kalla_per_stycke",
                         "citat": "", "allvar": "fel",
                         "forslag": "kalla_per_stycke måste ha lika många poster som stycken."})
    fel = sum(1 for x in fynd if x["allvar"] == "fel")
    varn = len(fynd) - fel
    sam = "Allt går att spåra till faktabanken." if not fynd else \
        f"{fel} fel och {varn} varningar. Fel betyder att något i texten inte har stöd i faktabanken."
    print(json.dumps({"filer": [f for f, _ in docs], "rent": not fynd, "fynd": fynd, "sammanfattning": sam},
                     ensure_ascii=False, indent=2))
    return 0 if not fynd else 2


if __name__ == "__main__":
    sys.exit(main())
