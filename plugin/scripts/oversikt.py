#!/usr/bin/env python3
"""Bygger översiktssidan oversikt.html ur jobbsok-mappen. Läser bara datan, skriver en HTML-fil.

    python3 oversikt.py [--home DIR] [--out FIL] [--oppna] [--idag YYYY-MM-DD]

Sidan är självförsörjande: datan bäddas in som JSON, mallen ligger i
templates/oversikt/. Ingen server, inget nätverk (utom ev. Google Fonts med systemfallback).
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobbsok_common as jc  # noqa: E402
import status as st  # noqa: E402

MALL = jc.PLUGIN_ROOT / "templates" / "oversikt"

FRASER = {
    "karriarcoach": "Hjälp mig ta reda på vad jag vill jobba med.",
    "faktabank": "Hjälp mig fylla på min faktabank.",
    "cv-design": "Jag vill välja hur mitt CV ska se ut.",
    "jobbkallor": "Hjälp mig bestämma var vi ska leta jobb.",
    "jobbsok": "Leta nya jobb åt mig.",
    "jobbjakt": "Jaga jobb åt mig på nya ställen.",
    "jobbsok-start": "Var är jag i jobbsökandet?",
}


def _safe(p):
    try:
        return jc.read_json(p)
    except (ValueError, OSError):
        return None


def _txt(v):
    if isinstance(v, dict):
        return v.get("sv") or v.get("en") or ""
    return v or ""


def _json(s, default):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


def resa(s, hyp):
    c, f, d, k, j, a = s["coach"], s["faktabank"], s["design"], s["kallor"], s["jobb"], s["ansokningar"]
    steg = []

    def add(id_, namn, status, rad, fras):
        steg.append({"id": id_, "namn": namn, "status": status, "rad": rad, "fras": fras})

    if c["klar"] or s["preferenser"]["finns"]:
        add("vill", "Vad vill du", "klar", "Klar", FRASER["karriarcoach"])
    elif c["finns"]:
        add("vill", "Vad vill du", "pagar", f"Pågår · {c.get('aktuell_fas_namn') or 'nuläge'}", "Fortsätt där vi var med vad jag vill.")
    else:
        add("vill", "Vad vill du", "ej", "Ej påbörjad", FRASER["karriarcoach"])
    g = f["fyllnadsgrad"]
    add("fakta", "Faktabank", "klar" if g >= 60 else "pagar" if f["finns"] and g else "ej",
        f"{g} %" if f["finns"] else "Tom", FRASER["faktabank"])
    add("design", "CV-design", "klar" if d["finns"] else "ej",
        (d["namn"] or "Vald") if d["finns"] else "Ej vald", FRASER["cv-design"])
    kl = k["antal"] and k["recept"]
    add("kallor", "Källor", "klar" if kl else "pagar" if k["antal"] else "ej",
        f"{k['aktiva']} " + ("källa" if k["aktiva"] == 1 else "källor") + f" · {len(k['recept'])} " + ("sökning" if len(k["recept"]) == 1 else "sökningar") if k["antal"] else "Inga", FRASER["jobbkallor"])
    add("jakt", "Jakt", "klar" if (j["finns"] and sum(j["per_status"].values())) else "pagar" if hyp else "ej",
        (f"{j['ny']} nya" if j["finns"] else "Ej körd") + (f" · {len(hyp)} " + ("idé" if len(hyp) == 1 else "idéer") if hyp else ""),
        FRASER["jobbsok"])
    skickade = sum(a["per_status"].get(x, 0) for x in ("skickad", "intervju", "erbjudande", "nej"))
    add("ansok", "Ansökningar", "klar" if skickade else "pagar" if a["totalt"] else "ej",
        f"{skickade} av {a['totalt']} skickade" if a["totalt"] else "Inga", "Gör en ansökan till ett av mina jobb.")
    n = s["nasta_steg"]
    if s["uppfoljning_forfallen"]:
        fras = "Hjälp mig följa upp mina ansökningar."
    else:
        fras = FRASER.get(n["skill"], FRASER["jobbsok-start"])
    return steg, {"varfor": n["varfor"], "fras": fras, "skill": n["skill"]}


def profil(home):
    p = home / "profil"
    md = ""
    try:
        md = (p / "det-har-vet-vi.md").read_text(encoding="utf-8")
    except OSError:
        pass
    stycken = []
    for blk in re.split(r"\n\s*\n", md):
        t = re.sub(r"^#+\s*", "", blk.strip(), flags=re.M)
        t = re.sub(r"[*_`]", "", t).strip()
        if t and not blk.strip().startswith("#") or (t and len(t) > 60):
            stycken.append(re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M))
        if sum(len(x) for x in stycken) > 550:
            break
    pref = _safe(p / "preferenser.json") or {}
    hg = pref.get("hårda_gränser") or pref.get("harda_granser") or {}
    granser = []
    if hg.get("max_pendling_min"):
        granser.append(f"≤ {hg['max_pendling_min']} min pendling")
    dd = hg.get("distans_dagar") or {}
    if dd.get("max") or dd.get("min"):
        granser.append(f"{dd.get('min', 0)}–{dd.get('max', 5)} dagar distans")
    if hg.get("max_resdagar_manad") is not None:
        granser.append(f"≤ {hg['max_resdagar_manad']} resdagar/mån")
    if hg.get("lonegolv_manad"):
        granser.append(f"≥ {hg['lonegolv_manad']:,} kr/mån".replace(",", " "))
    if hg.get("anstallningsform"):
        granser += [x.capitalize() for x in hg["anstallningsform"]]
    if hg.get("omfattning"):
        granser += [x.capitalize() for x in hg["omfattning"]]
    fakta = _safe(p / "fakta.json") or {}
    person = fakta.get("person") or {}
    return {"namn": person.get("namn") or "", "titel": _txt(person.get("titel")),
            "stycken": stycken, "varden": [v for v in (pref.get("varden_topp5") or []) if v][:5], "granser": granser,
            "riktningar": [r.get("namn") for r in pref.get("riktningar") or [] if r.get("namn")],
            "orter": [o.get("namn") for o in pref.get("orter") or [] if o.get("namn")]}


def motivering(sk):
    """Vad hon HAR som efterfrågas (från score.py), plus jokerns skäl. Gränsbrott och hårda krav visas separat."""
    delar = []
    if sk.get("joker_traff"):
        delar.append("Utanför dina vanliga filter men nära det som ger dig energi: " + ", ".join(map(str, sk["joker_traff"][:4])) + ".")
    mot = sk.get("matchning_motivering") or sk.get("motivering")
    if mot:
        delar += [m for m in str(mot).splitlines() if m.strip() and not m.startswith(("Bryter mot din gräns", "Hårt krav"))]
    elif sk.get("kompetens_traff"):
        delar.append("Du har: " + ", ".join(map(str, sk["kompetens_traff"][:4])) + " – det efterfrågas.")
    ex = [a for a in sk.get("avdrag") or [] if not str(a).startswith("hårt krav")]
    if ex:
        delar.append("Obs: nämner " + ", ".join(ex) + ".")
    return " ".join(delar)


def arbetsgivarkort(home):
    """{orgnr|normaliserat namn: kort-sammanfattning} ur sok/arbetsgivare/*.json."""
    ut = {}
    d = home / "sok" / "arbetsgivare"
    if not d.is_dir():
        return ut
    for p in sorted(d.glob("*.json")):
        if p.name.startswith("_"):
            continue
        k = _safe(p) or {}
        m = k.get("matchning") or {}
        info = {"slug": k.get("slug") or p.stem, "namn": k.get("arbetsgivare") or p.stem,
                "stammer": len(m.get("stammer") or []), "skaver": len(m.get("skaver") or []),
                "varningar": len(m.get("varningsflaggor") or []), "fil": f"sok/arbetsgivare/{p.name}"}
        if k.get("orgnr"):
            ut[str(k["orgnr"]).replace("-", "")] = info
        if k.get("arbetsgivare"):
            ut[_norm(k["arbetsgivare"])] = info
    return ut


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b(ab|aktiebolag|kommun|region|hb|kb)\b", " ", s)
    return re.sub(r"[^a-zåäö0-9]+", "", s)


def jobb(home):
    db = home / "sok" / "jobb.sqlite"
    if not db.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM jobb WHERE dubblett_av IS NULL AND COALESCE(status,'ny') IN ('ny','intressant') "
                           "ORDER BY COALESCE(poang,-1) DESC LIMIT 300").fetchall()
        con.close()
    except sqlite3.Error:
        return []
    ut = []
    kort = arbetsgivarkort(home)
    for r in rows:
        r = dict(r)
        sk = _json(r.get("poang_skal_json"), {})
        if sk.get("uteslutet"):
            continue
        ak = kort.get((r.get("orgnr") or "").replace("-", "")) or kort.get(_norm(r.get("arbetsgivare")))
        ut.append({"etikett": sk.get("matchning_etikett") or "", "granbrott": sk.get("granbrott") or [],
                   "hart_krav": sk.get("hart_krav_saknas") or [], "strackjobb": sk.get("strackjobb") or "",
                   "flaggor": [f for f in sk.get("flaggor") or []][:3], "arbetsgivarkort": ak,"uid": r["uid"], "titel": r.get("titel") or "Utan titel", "bolag": r.get("arbetsgivare") or "",
                   "ort": r.get("ort") or "", "distans": r.get("distans"), "deadline": (r.get("deadline") or "")[:10],
                   "publicerad": (r.get("publicerad") or "")[:10], "poang": r.get("poang"), "status": r.get("status") or "ny",
                   "url": r.get("url") or "", "utdrag": (r.get("utdrag") or "")[:280], "joker": bool(sk.get("joker")),
                   "motivering": motivering(sk), "forst_sedd": (r.get("forst_sedd") or "")[:10]})
    return ut


def _annons_meta(path):
    meta = {"rubrik": "", "deadline": ""}
    try:
        txt = path.read_text(encoding="utf-8")[:3000]
    except OSError:
        return meta
    m = re.search(r"^#\s+(.+)$", txt, re.M)
    if m:
        meta["rubrik"] = m.group(1).strip()
    m = re.search(r"(?:deadline|sista ansökningsdag)[^0-9]{0,20}(\d{4}-\d{2}-\d{2})", txt, re.I)
    if m:
        meta["deadline"] = m.group(1)
    return meta


def ansokningar(home):
    rot = home / "ansokningar"
    ut = []
    if not rot.is_dir():
        return ut
    for d in sorted(rot.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        logg = _safe(d / "logg.json") or {}
        brev = _safe(d / "brev.json") or {}
        meta = _annons_meta(d / "annons.md")
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)$", d.name)
        datum, rest = (m.group(1), m.group(2)) if m else ("", d.name)
        # logg.json (skrivs av ansokan) först; mappnamnet är bara en sista gissning
        bolag = logg.get("bolag") or (brev.get("mottagare") or {}).get("bolag") or rest.split("-")[0].capitalize()
        roll = logg.get("roll") or meta["rubrik"] or rest.replace("-", " ").capitalize()
        filer = {n: f"ansokningar/{d.name}/{n}" for n in ("cv.pdf", "brev.pdf", "mejl.md", "annons.md", "intervju.md")
                 if (d / n).exists()}
        iv = _safe(d / "intervju.json") or {}
        omg = sorted([o for o in iv.get("omgangar") or [] if isinstance(o, dict)], key=lambda o: o.get("datum") or "")
        kommande = next((o for o in omg if (o.get("datum") or "") >= dt.date.today().isoformat()), omg[-1] if omg else None)
        intervju = None
        if iv:
            fr = iv.get("fragor_troliga") or []
            intervju = {"datum": (kommande or {}).get("datum") or "", "tid": (kommande or {}).get("tid") or "",
                        "format": (kommande or {}).get("format") or "", "omgang": (kommande or {}).get("nr"),
                        "forberedelse": filer.get("intervju.md"),
                        "klara": sum(1 for f in fr if f.get("status") == "klar"), "fragor": len(fr)}
        ut.append({"mapp": d.name, "datum": datum, "bolag": bolag, "roll": roll, "status": logg.get("status", "utkast"),
                   "skickad": logg.get("skickad"), "foljupp": logg.get("foljupp_datum"), "kontakt": logg.get("kontakt", ""),
                   "deadline": logg.get("deadline") or meta["deadline"], "filer": filer,
                   "annons_url": logg.get("annons_url") or "", "jobb_uid": logg.get("jobb_uid") or "", "intervju": intervju,
                   "anteckning": ((logg.get("anteckningar") or [{}])[-1] or {}).get("text", "") if logg.get("anteckningar") else ""})
    return ut


METOD_TEXT = {"jakt_titlar": "andra titlar", "jakt_arbetsgivare": "arbetsgivare", "jakt_signaler": "nyheter om bolag",
              "webbrecept": "webbsökning", "recept": "Platsbanken", "malbolag": "målbolag", "manuell": "egen idé"}


def bevakning(home):
    k = _safe(home / "sok" / "kallor.json") or {}
    utb = _safe(home / "sok" / "utbyte.json") or {}

    def andel(d):
        if not d or not d.get("totalt"):
            return None
        bra = d.get("intressant", 0) + d.get("sokt", 0)
        return {"totalt": d["totalt"], "bra": bra}

    kallor = [{"id": x.get("id"), "namn": x.get("namn") or x.get("id"), "typ": x.get("typ"), "url": x.get("url") or "",
               "aktiv": x.get("aktiv", True), "egen": x.get("tillagd_av") == "anvandare",
               "anteckning": x.get("anteckning") or "", "senast": (x.get("senast_hamtad") or "")[:10],
               "utbyte": andel((utb.get("per_kalla") or {}).get(x.get("id")))} for x in k.get("kallor") or []]
    recept = []
    rd = home / "sok" / "recept"
    if rd.is_dir():
        for p in sorted(rd.glob("*.json")):
            r = _safe(p) or {}
            recept.append({"id": p.stem, "namn": r.get("namn") or p.stem, "q": (r.get("jobtech") or {}).get("q") or "",
                           "senast": (r.get("senast_kord") or "")[:10], "utbyte": andel((utb.get("per_recept") or {}).get(p.stem))})
    h = _safe(home / "sok" / "hypoteser.json") or {}
    hl = h.get("hypoteser") if isinstance(h, dict) else h if isinstance(h, list) else []
    hyp = []
    for x in hl or []:
        if not isinstance(x, dict):
            continue
        # formatet från jakt_hypoteser.py: beskrivning, metod, status, korningar, utbyte{fynd,andel,...}
        hid = x.get("id") or ""
        u = x.get("utbyte") or {}
        nk = len(x.get("korningar") or [])
        if u.get("fynd"):
            utf = f"{u['fynd']} fynd" + (f", {round(u['andel'] * 100)} % intressanta" if u.get("andel") is not None else "")
        elif nk:
            utf = f"{nk} " + ("körning" if nk == 1 else "körningar") + ", inga fynd än"
        else:
            utf = "inte prövad än"
        hyp.append({"id": hid, "text": _txt(x.get("beskrivning")), "metod": METOD_TEXT.get(x.get("metod"), ""),
                    "status": x.get("status") or "", "utfall": utf,
                    "utbyte": andel((utb.get("per_hittad_via") or {}).get(hid))})
    return {"kallor": kallor, "recept": recept, "hypoteser": hyp}


FAS_NAMN = {"intake": "nuläge", "identity": "identitet", "energy_log": "energilogg", "needs_profile": "behov",
            "options": "vägar", "experiments": "prototyper", "decision": "beslut", "det-har-vet-vi": "profilen",
            "preferenser": "preferenser"}


def riktningar(home):
    """Rollkorten (sok/rollkort/) med matrisen. Läser bara filer, inget nät."""
    if not (home / "sok" / "rollkort").is_dir():
        return {"kort": [], "vikter": {}}
    try:
        import rollkort as rk
        m = rk.jamfor(str(home))
        korten = {k["slug"]: k for k in rk.alla_kort(str(home))}
    except Exception:  # översikten ska byggas även om ett kort är trasigt
        return {"kort": [], "vikter": {}}

    def v(k, f):
        return (k.get(f) or {}).get("varde")
    ut = []
    for r in m["rader"]:
        k = korten.get(r["slug"]) or {}
        vol = v(k, "volym") or {}
        g = v(k, "glapp") or {}
        lon = v(k, "lon") or {}
        pr = lon.get("per_region") or {}
        reg = next((x for x in pr if x != "riket"), "riket") if pr else None
        lonrad = None
        if reg and ((pr.get(reg) or {}).get("alla") or {}).get("manadslon_medel"):
            lonrad = f"{pr[reg]['alla']['manadslon_medel']:,} kr i snitt ({reg}, SCB {lon.get('ar')})".replace(",", " ")
        cit = lambda lista: [{"text": x.get("text"), "citat": x.get("citat"), "fas": FAS_NAMN.get(x.get("fas"), x.get("fas"))}
                             for x in lista or []]
        ut.append({
            "slug": r["slug"], "titel": r["titel"], "roll": (k.get("roll") or {}).get("fraga"), "typ": r["typ"], "total": r["total"], "tackning": r["tackning"],
            "etikett": r.get("etikett") or "", "motivering": r.get("motivering") or "",
            "passar": cit(v(k, "passar_for_att")), "skav": cit(v(k, "skav")),
            "volym": {"ar": vol.get("senaste_hela_ar"), "trend": vol.get("trend"), "procent": vol.get("trend_procent"),
                      "nu": vol.get("oppna_nu"), "per_ar": vol.get("per_ar") or []} if vol else None,
            "glapp": {"harda_saknas": [x.get("krav") for x in g.get("saknas") or [] if x.get("hart")],
                      "onsk_har": sum(1 for x in g.get("har") or [] if not x.get("hart")),
                      "onsk_av": sum(1 for f in ("har", "osakert", "saknas") for x in g.get(f) or [] if not x.get("hart")),
                      "saknas": [x.get("krav") for x in g.get("saknas") or [] if not x.get("hart")][:4]}
                     if g and k.get("typ") != "stanna" else None,
            "uppgifter": [{"text": t.get("sammanfattning") or t.get("tema"), "andel": t.get("andel_annonser")}
                          for t in (v(k, "arbetsuppgifter") or [])[:6]],
            "arbetsgivare": [a.get("namn") for a in (v(k, "arbetsgivare") or [])[:4]],
            "titlar": [t.get("titel") for t in (v(k, "titlar") or [])[:5]],
            "annonser": [{"rubrik": a.get("rubrik"), "bolag": a.get("arbetsgivare"), "url": a.get("url")} for a in v(k, "annonser") or []],
            "tisdag": v(k, "vanlig_tisdag"), "lon": lonrad,
            "crafting": (v(k, "crafting") or {}).get("andringar") and [x.get("text") for x in v(k, "crafting")["andringar"]][:4],
            "dims": [{"namn": rk.DIM_NAMN[d], "visa": x["visa"], "poang": x["poang"]} for d, x in r["dimensioner"].items()],
        })
    return {"kort": ut, "vikter": m["vikter"], "vikter_egna": m["vikter_kalla"] != "standardvärden"}


def kalender(jobblista, ans, idag):
    h = []
    for a in ans:
        namn = f"{a['roll']}, {a['bolag']}"
        if a["deadline"] and a["status"] == "utkast" and a["deadline"] >= idag:
            h.append({"datum": a["deadline"], "typ": "deadline", "text": f"Sista dag att skicka: {namn}"})
        if a["foljupp"] and a["status"] in ("skickad", "intervju"):
            h.append({"datum": str(a["foljupp"])[:10], "typ": "folj", "text": f"Följ upp: {namn}"})
    for a in ans:
        iv = a.get("intervju") or {}
        if iv.get("datum") and iv["datum"] >= idag:
            h.append({"datum": iv["datum"], "typ": "intervju", "text": f"Intervju{' ' + iv['tid'] if iv.get('tid') else ''}: {a['roll']}, {a['bolag']}"})
    for j in jobblista:
        if j["deadline"] and j["deadline"] >= idag and j["status"] == "intressant":
            h.append({"datum": j["deadline"], "typ": "jobb", "text": f"Sista ansökningsdag: {j['titel']}, {j['bolag']}", "uid": j["uid"]})
    return sorted(h, key=lambda x: x["datum"])[:40]


def bygg_data(home, idag=None):
    idag = idag or dt.date.today().isoformat()
    s = st.build(home, idag)
    bev = bevakning(home)
    steg, nasta = resa(s, bev["hypoteser"])
    j = jobb(home)
    a = ansokningar(home)
    return {"idag": idag, "genererad": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "home": str(home),
            "finns": s["finns"], "resa": steg, "nasta": nasta, "profil": profil(home), "jobb": j,
            "ansokningar": a, "forfallna": [u["mapp"] for u in s["uppfoljning_forfallen"]],
            "bevakning": bev, "kalender": kalender(j, a, idag), "riktningar": riktningar(home)}


def rendera(data):
    html = (MALL / "oversikt.html").read_text(encoding="utf-8")
    css = (MALL / "oversikt.css").read_text(encoding="utf-8")
    js = (MALL / "oversikt.js").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    return html.replace("/*__CSS__*/", css).replace("/*__JS__*/", js).replace("/*__DATA__*/", blob)


def main(argv=None):
    ap = jc.add_home_arg(argparse.ArgumentParser(description="Bygger oversikt.html."))
    ap.add_argument("--out", help="utfil (standard: <home>/oversikt.html)")
    ap.add_argument("--oppna", action="store_true", help="öppna sidan efteråt (macOS)")
    ap.add_argument("--idag", help="datum för beräkningar, YYYY-MM-DD")
    a = ap.parse_args(argv)
    home = jc.resolve_home(a.home)
    out = Path(a.out).expanduser().resolve() if a.out else home / "oversikt.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(rendera(bygg_data(home, a.idag)), encoding="utf-8")
    os.replace(tmp, out)
    print(out)
    if a.oppna and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
