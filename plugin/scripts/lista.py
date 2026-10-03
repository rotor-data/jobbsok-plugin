#!/usr/bin/env python3
"""Kompakt topplista ur sok/jobb.sqlite, för Claude. En rad per jobb.

  python3 lista.py [--status ny,intressant] [--min-poang 50] [--nya] [--antal 20] [--json] [--home DIR]
  python3 lista.py visa <uid> [--max-tecken 8000]   hämtar fulltext (JobTech /ad/{id} eller källans URL)
  python3 lista.py satt <uid> <ny|intressant|nej|sokt|stangd> [--orsak "fritext"] [--taggar a,b]
      orsak och taggar sparas i kolumnen bedomning_json: {"status","orsak","taggar","datum"}
      (lärande för jobbjakt/utbyte.py; taggar läggs till befintliga)

Rad: uid | titel | arbetsgivare | ort | distans | deadline | etikett | poäng | ≤10 kompetenser | ≤300 tecken utdrag
Under raden (indragna): motivering och flaggor, t.ex. "! Bryter mot din gräns: vikariat".
Etiketten och motiveringen är huvudbudskapet; poängen är bara sortering, visa den inte som procent.
--nya: bara jobb som först sågs vid senaste körningen av kor.py (sok/senaste_korning.json).
Jokrar (score.py --jokrar) visas med status 'joker' i --json och "JOKER" i poängfältet.
Dubbletter (dubblett_av satt) och uteslutna (exkluderad arbetsgivare) visas inte. Jobb som bryter
mot en hård gräns visas, med flaggan; hon avgör själv.
"""
import argparse
import json
import sys

import sok_common as sc

DIST = {0: "på plats", 1: "hybrid", 2: "distans", None: "?"}


def jokrar(home):
    c = sc.db(home)
    ut = []
    for r in c.execute("SELECT * FROM jobb WHERE dubblett_av IS NULL AND status IN ('ny','intressant') "
                       "AND poang_skal_json LIKE '%\"joker\": true%'").fetchall():
        d = _rad(r)
        d["joker"] = json.loads(r["poang_skal_json"]).get("joker_traff")
        ut.append(d)
    return ut


def _rad(r):
    komp = [k.get("namn") for k in json.loads(r["kompetenser_json"] or "[]")
            if k.get("typ") not in ("yrke", "yrkesgrupp") and k.get("namn")]
    return {"uid": r["uid"], "titel": r["titel"], "arbetsgivare": r["arbetsgivare"], "ort": r["ort"],
            "distans": DIST.get(r["distans"], "?"), "deadline": (r["deadline"] or "")[:10] or None,
            "poang": r["poang"], "kompetenser": komp[:10], "utdrag": sc.utdrag(r["utdrag"], 300),
            "status": r["status"], "hittad_via": r["hittad_via"],
            "etikett": _sk(r).get("matchning_etikett"), "motivering": _sk(r).get("matchning_motivering"),
            "granbrott": _sk(r).get("granbrott") or [],
            "flaggor": [f"bryter mot din gräns: {b}" for b in _sk(r).get("granbrott") or []] + (_sk(r).get("flaggor") or []) + [f"hårt krav oklart: {k}" for k in _sk(r).get("hart_krav_saknas") or []]}


def _sk(r):
    try:
        return json.loads(r["poang_skal_json"] or "{}")
    except (ValueError, TypeError):
        return {}


def rader(home, status=("ny", "intressant"), min_poang=0, nya=False, antal=20):
    c = sc.db(home)
    q = "SELECT * FROM jobb WHERE dubblett_av IS NULL AND status IN (%s) AND COALESCE(poang,0) >= ?" % \
        ",".join("?" * len(status))
    args = list(status) + [min_poang]
    if nya:
        sedan = sc.korning_logg(home).get("senaste_start")
        if sedan:
            q += " AND forst_sedd >= ?"
            args.append(sedan)
    q += " ORDER BY COALESCE(poang,-1) DESC, COALESCE(deadline,'9999') ASC, publicerad DESC LIMIT ?"
    args.append(antal)
    ut = []
    for r in c.execute(q, args).fetchall():
        sk = json.loads(r["poang_skal_json"] or "{}")
        if sk.get("uteslutet"):
            continue
        ut.append(_rad(r))
    return ut


def formatera(r, detalj=False):
    rad = " | ".join([r["uid"], r["titel"] or "?", r["arbetsgivare"] or "?", r["ort"] or "?", r["distans"],
                       r["deadline"] or "-", r.get("etikett") or "-", ("JOKER " if r.get("joker") is not None else "") + str(r["poang"] if r["poang"] is not None else "-"),
                       ", ".join(r["kompetenser"]) or "-", r["utdrag"] or ""])
    if not detalj:
        return rad
    extra = [("    " + m) for m in (r.get("motivering") or "").splitlines() if m.strip()]
    extra += [f"    ! {f[0].upper() + f[1:]}" for f in r.get("flaggor") or []]
    return "\n".join([rad] + extra)


def visa(home, uid, max_tecken=8000):
    c = sc.db(home)
    r = c.execute("SELECT * FROM jobb WHERE uid=?", (uid,)).fetchone()
    if not r:
        sys.exit(f"Hittar inget jobb med uid {uid}")
    text = None
    kalla = sc.las_json(sc.sokv(home, "kallor.json"), {}) or {}
    typ = {k["id"]: k.get("typ") for k in kalla.get("kallor", [])}.get(r["kalla"])
    try:
        af_id = r["kalla_id"] if (r["kalla_id"] or "").isdigit() else None
        if not af_id and "arbetsformedlingen.se" in (r["url"] or ""):
            af_id = (r["url"].rstrip("/").rsplit("/", 1)[-1])
            af_id = af_id if af_id.isdigit() else None
        if af_id and (typ == "jobtech" or "arbetsformedlingen.se" in (r["url"] or "")):
            _, d, _ = sc.http_json(f"https://jobsearch.api.jobtechdev.se/ad/{af_id}", home=home, cache=True)
            text = ((d or {}).get("description") or {}).get("text")
        if not text:
            text = sc.las_text(home, r["text_hash"])
        if not text and r["url"]:
            _, h, _ = sc.http(r["url"], home=home, cache=True)
            text = sc.html_till_text(h)
    except sc.NatFel as e:
        text = sc.las_text(home, r["text_hash"])
        if not text:
            sc.natfel_avslut(f"{e}. Hämta i stället {r['url']} med webbverktyget")
    except sc.HttpFel as e:
        text = sc.las_text(home, r["text_hash"]) or f"(Kunde inte hämta: {e}. Annonsen kan ha tagits bort.)"
    sc.spara_text(home, r["text_hash"], text)
    huvud = [f"# {r['titel']}", f"Arbetsgivare: {r['arbetsgivare'] or '?'}", f"Ort: {r['ort'] or '?'} "
             f"({DIST.get(r['distans'], '?')})", f"Sista ansökningsdag: {(r['deadline'] or '-')[:10]}",
             f"Källa: {r['url'] or r['kalla']}", f"Poäng: {r['poang']}  Status: {r['status']}", ""]
    t = (text or "").strip()
    if len(t) > max_tecken:
        t = t[:max_tecken] + "\n…(avkortad)"
    return "\n".join(huvud) + t


def satt(home, uid, status, orsak=None, taggar=None):
    if status not in sc.STATUSAR:
        sys.exit(f"Ogiltig status {status}. Tillåtna: {', '.join(sc.STATUSAR)}")
    c = sc.db(home)
    r = c.execute("SELECT bedomning_json FROM jobb WHERE uid=?", (uid,)).fetchone()
    if not r:
        sys.exit(f"Hittar inget jobb med uid {uid}")
    b = json.loads(r["bedomning_json"] or "{}")
    b["status"] = status
    b["datum"] = sc.nu_iso()
    if orsak:
        b["orsak"] = orsak
    if taggar:
        b["taggar"] = sorted(set(b.get("taggar", [])) | {t.strip() for t in taggar.split(",") if t.strip()})
    c.execute("UPDATE jobb SET status=?, bedomning_json=? WHERE uid=?", (status, json.dumps(b, ensure_ascii=False), uid))
    c.commit()
    return f"{uid}: status = {status}"


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("visa", "satt"):
        ap = argparse.ArgumentParser(prog="lista.py " + argv[0])
        ap.add_argument("uid")
        if argv[0] == "satt":
            ap.add_argument("status")
            ap.add_argument("--orsak")
            ap.add_argument("--taggar")
        else:
            ap.add_argument("--max-tecken", type=int, default=8000)
        sc.add_home_arg(ap)
        a = ap.parse_args(argv[1:])
        home = sc.hem(a.home)
        print(visa(home, a.uid, a.max_tecken) if argv[0] == "visa" else satt(home, a.uid, a.status, a.orsak, a.taggar))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", default="ny,intressant")
    ap.add_argument("--min-poang", type=int, default=0)
    ap.add_argument("--nya", action="store_true")
    ap.add_argument("--antal", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--jokrar", action="store_true", help="visa även jokrar (markerade av score.py --jokrar)")
    sc.add_home_arg(ap)
    a = ap.parse_args(argv)
    rs = rader(sc.hem(a.home), tuple(s.strip() for s in a.status.split(",") if s.strip()), a.min_poang, a.nya, a.antal)
    if a.jokrar:
        sett = {r["uid"] for r in rs}
        rs += [j for j in jokrar(sc.hem(a.home)) if j["uid"] not in sett]
    if a.json:
        print(json.dumps(rs, ensure_ascii=False, indent=1))
    else:
        print("uid | titel | arbetsgivare | ort | distans | deadline | etikett | poäng | kompetenser | utdrag")
        for r in rs:
            print(formatera(r, detalj=True))
        if not rs:
            print("(inga träffar)")


if __name__ == "__main__":
    main()
