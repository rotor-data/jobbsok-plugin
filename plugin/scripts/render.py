#!/usr/bin/env python3
"""Renderar CV, personligt brev och designförslag till HTML och PDF.

Användning:
  render.py cv    <ansökningsmapp|cv.json>   [--design PATH] [--out MAPP] [--home MAPP] [--bild]
  render.py brev  <ansökningsmapp|brev.json> [--design PATH] [--out MAPP] [--home MAPP] [--bild]
  render.py forslag <ansökningsmapp|cv.json|fixturmapp> --forval a,b,c [--out MAPP]
  render.py stresstest [--design PATH] [--out MAPP]

Bara stdlib. Mallmotorn är egen (escaping som standard), inte Jinja.
PDF-motor i fallback-ordning: Chrome/Chromium headless, Playwright, WeasyPrint,
annars bara HTML med instruktion om att skriva ut till PDF. JOBBSOK_PDF_MOTOR tvingar en motor.
WeasyPrint (pip install --user weasyprint) kräver systembiblioteken Pango/HarfBuzz; finns de inte
misslyckas importen och nästa steg (HTML + utskriftsinstruktion) tar vid.
`render.py motorer` skriver vilka motorer som finns (JSON).
Resultatet skrivs som JSON på stdout.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
MALLAR = PLUGIN / "templates"
FORVAL = MALLAR / "design-forval"
FIXTURER = PLUGIN / "tests" / "fixtures" / "cv-exempel"
LAYOUTER = ("klassisk", "sidokolumn", "kompakt", "portratt")
MAX_SIDOR = {"cv": 2, "brev": 1}

# ---------------------------------------------------------------- mallmotor
#   {{ a.b }}            escapat värde
#   {{ a.b|raw }}        oescapat (bara för HTML vi själva byggt)
#   {% if a %}..{% else %}..{% endif %}   ({% if not a %} går också)
#   {% for x in a.b %}..{% endfor %}      (loop.first / loop.last / loop.index)
#   {% include "_del.html" %}

_TOKEN = re.compile(r"({{.*?}}|{%.*?%})", re.S)


class MallFel(Exception):
    pass


def _uppslag(ctx: list, uttryck: str):
    delar = uttryck.strip().split(".")
    varde = None
    for scope in reversed(ctx):
        if isinstance(scope, dict) and delar[0] in scope:
            varde = scope[delar[0]]
            break
    else:
        return None
    for d in delar[1:]:
        if isinstance(varde, dict):
            varde = varde.get(d)
        elif isinstance(varde, list) and d.isdigit():
            i = int(d)
            varde = varde[i] if i < len(varde) else None
        else:
            return None
    return varde


def _parsa(tokens: list, pos: int, slut: tuple):
    noder = []
    while pos < len(tokens):
        t = tokens[pos]
        if t.startswith("{%"):
            inne = t[2:-2].strip()
            ord_ = inne.split()
            nyckel = ord_[0] if ord_ else ""
            if nyckel in slut:
                return noder, pos, nyckel
            if nyckel == "if":
                ja, pos, stopp = _parsa(tokens, pos + 1, ("else", "endif"))
                nej = []
                if stopp == "else":
                    nej, pos, stopp = _parsa(tokens, pos + 1, ("endif",))
                if stopp != "endif":
                    raise MallFel("if utan endif")
                noder.append(("if", inne[2:].strip(), ja, nej))
            elif nyckel == "for":
                m = re.match(r"for\s+(\w+)\s+in\s+([\w.]+)$", inne)
                if not m:
                    raise MallFel(f"felaktig for: {inne}")
                kropp, pos, stopp = _parsa(tokens, pos + 1, ("endfor",))
                if stopp != "endfor":
                    raise MallFel("for utan endfor")
                noder.append(("for", m.group(1), m.group(2), kropp))
            elif nyckel == "include":
                noder.append(("include", inne[7:].strip().strip("\"'")))
            else:
                raise MallFel(f"okänd tagg: {inne}")
        elif t.startswith("{{"):
            noder.append(("var", t[2:-2].strip()))
        else:
            noder.append(("text", t))
        pos += 1
    if slut:
        raise MallFel(f"saknar {'/'.join(slut)}")
    return noder, pos, None


def _sant(ctx, uttryck: str) -> bool:
    uttryck = uttryck.strip()
    if uttryck.startswith("not "):
        return not _sant(ctx, uttryck[4:])
    v = _uppslag(ctx, uttryck)
    return bool(v) and v != "0"


def _kor(noder, ctx, mappar) -> str:
    ut = []
    for n in noder:
        typ = n[0]
        if typ == "text":
            ut.append(n[1])
        elif typ == "var":
            uttr = n[1]
            raw = uttr.endswith("|raw")
            if raw:
                uttr = uttr[:-4]
            v = _uppslag(ctx, uttr)
            if v is None or v is False:
                continue
            s = str(v)
            ut.append(s if raw else html.escape(s, quote=True))
        elif typ == "if":
            ut.append(_kor(n[2] if _sant(ctx, n[1]) else n[3], ctx, mappar))
        elif typ == "for":
            lista = _uppslag(ctx, n[2]) or []
            for i, el in enumerate(lista):
                loop = {"index": i + 1, "first": i == 0, "last": i == len(lista) - 1}
                ut.append(_kor(n[3], ctx + [{n[1]: el, "loop": loop}], mappar))
        elif typ == "include":
            ut.append(_kor(kompilera(_hitta(n[1], mappar)), ctx, mappar))
    return "".join(ut)


def _hitta(namn: str, mappar) -> Path:
    for m in mappar:
        p = Path(m) / namn
        if p.exists():
            return p
    raise MallFel(f"hittar inte mallen {namn}")


_CACHE: dict = {}


def kompilera(path: Path):
    key = str(path)
    if key not in _CACHE:
        tokens = [t for t in _TOKEN.split(path.read_text("utf-8")) if t]
        _CACHE[key], _, _ = _parsa(tokens, 0, ())
    return _CACHE[key]


def fyll(mall: str | Path, data: dict, mappar=None) -> str:
    """Fyll en mallfil (Path) eller en mallsträng (str) med data."""
    if isinstance(mall, Path):
        noder = kompilera(mall)
        mappar = mappar or [mall.parent, MALLAR]
    else:
        noder, _, _ = _parsa([t for t in _TOKEN.split(mall) if t], 0, ())
        mappar = mappar or [MALLAR]
    return _kor(noder, [data], mappar)


# ---------------------------------------------------------------- data & design

def hem(arg: str | None = None) -> Path:
    return Path(arg or os.environ.get("JOBBSOK_HOME") or Path.home() / "Jobbsok").expanduser()


def las_json(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def forval_path(namn: str) -> Path:
    p = Path(namn)
    if p.suffix == ".json" and p.exists():
        return p
    p = FORVAL / f"{namn}.json"
    if not p.exists():
        finns = ", ".join(sorted(x.stem for x in FORVAL.glob("*.json")))
        raise SystemExit(f"Okänt förval '{namn}'. Finns: {finns}")
    return p


def hitta_design(arg: str | None, home: Path) -> Path:
    if arg:
        return forval_path(arg)
    egen = home / "design" / "design.json"
    return egen if egen.exists() else forval_path("konservativ")


STANDARD_TOKENS = {
    "font_rubrik": "Source Serif 4", "font_brod": "Source Sans 3",
    "storlek_brod_pt": 10.5, "storlek_namn_pt": 24, "storlek_rubrik_pt": 13,
    "radavstand": 1.3, "farg_text": "#1d1d1f", "farg_accent": "#2f5d62", "farg_dampad": "#5f6368",
    "marginal_mm": 18, "sektion_luft_mm": 6, "visa_foto": False,
    "rubrik_stil": "linje",
}
STANDARD_SEKTIONER = ["profil", "erfarenhet", "utbildning", "kompetenser", "sprak", "kurser", "ideella"]

# Regler (references/typografi.md). (min, max, rimligt_min, rimligt_max)
GRANSER = {
    "storlek_brod_pt": (8, 14, 10, 11.5),
    "storlek_namn_pt": (14, 40, 20, 30),
    "storlek_rubrik_pt": (9, 20, 11, 16),
    "radavstand": (1.0, 2.0, 1.2, 1.45),
    "marginal_mm": (8, 30, 15, 20),
    "sektion_luft_mm": (1, 15, 3, 9),
}
RUBRIK_STILAR = ("linje", "versaler", "vanlig", "accentstreck")


def _ljushet(hexf: str) -> float:
    h = hexf.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def kontrast(a: str, b: str = "#ffffff") -> float:
    la, lb = sorted((_ljushet(a), _ljushet(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def granska_design(design: dict) -> list[str]:
    """Vänliga varningar när ett val bryter läsbarhet eller ATS. Stoppar inget."""
    t = {**STANDARD_TOKENS, **design.get("tokens", {})}
    v = []
    for k, (_, _, lo, hi) in GRANSER.items():
        x = t.get(k)
        if isinstance(x, (int, float)) and not (lo <= x <= hi):
            v.append(f"{k} = {x} ligger utanför det rekommenderade {lo}–{hi}.")
    for k in ("farg_text", "farg_accent", "farg_dampad"):
        x = str(t.get(k, ""))
        if not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", x):
            v.append(f"{k} = {x!r} är ingen giltig hexfärg (t.ex. #2f5d62).")
            continue
        krav = 7.0 if k == "farg_text" else 4.5
        if kontrast(x) < krav:
            v.append(f"{k} {x} har för låg kontrast mot vitt ({kontrast(x):.1f}:1, behöver minst {krav}:1) "
                     "och blir svår att läsa, särskilt utskrivet.")
    fonter = {t.get("font_rubrik"), t.get("font_brod")}
    if len(fonter) > 2:
        v.append("Fler än två typsnitt gör sidan rörig.")
    for f in fonter:
        if f and f not in TYPSNITT:
            v.append(f"Typsnittet '{f}' finns inte i pluginen; datorns standardtypsnitt används i stället.")
    if t.get("rubrik_stil") not in RUBRIK_STILAR:
        v.append(f"rubrik_stil bör vara en av {', '.join(RUBRIK_STILAR)}.")
    if design.get("layout") not in LAYOUTER and not str(design.get("layout", "")).startswith("egen:"):
        v.append(f"Okänd layout '{design.get('layout')}', klassisk används.")
    return v


def klamp_tokens(t: dict) -> dict:
    """Håll tokens inom hårda gränser så att renderingen aldrig går sönder."""
    t = {**STANDARD_TOKENS, **t}
    for k, (lo, hi, _, _) in GRANSER.items():
        try:
            t[k] = float(min(max(float(t[k]), lo), hi))
        except (TypeError, ValueError):
            t[k] = STANDARD_TOKENS[k]
    for k in ("farg_text", "farg_accent", "farg_dampad"):
        if not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", str(t.get(k, ""))):
            t[k] = STANDARD_TOKENS[k]
    if t.get("rubrik_stil") not in RUBRIK_STILAR:
        t["rubrik_stil"] = "linje"
    return t


# ---------------------------------------------------------------- typsnitt

SANS = '"Helvetica Neue", Helvetica, Arial, "Liberation Sans", "DejaVu Sans", sans-serif'
SERIF = 'Charter, "Iowan Old Style", Georgia, "Times New Roman", "Liberation Serif", "DejaVu Serif", serif'
TYPSNITT = {
    "Source Sans 3": {"filer": [("SourceSans3-VF.ttf", "normal"), ("SourceSans3-Italic-VF.ttf", "italic")], "fallback": SANS},
    "Source Serif 4": {"filer": [("SourceSerif4-VF.ttf", "normal")], "fallback": SERIF},
    "Inter": {"filer": [("Inter-VF.ttf", "normal")], "fallback": SANS},
    # Systemtypsnitt som också godtas
    "Georgia": {"filer": [], "fallback": SERIF},
    "Helvetica": {"filer": [], "fallback": SANS},
    "Arial": {"filer": [], "fallback": SANS},
}


def fontface_css(namn_lista) -> tuple[str, list[str]]:
    css, saknas = [], []
    for namn in dict.fromkeys(namn_lista):
        info = TYPSNITT.get(namn)
        if not info:
            continue
        for fil, stil in info["filer"]:
            p = MALLAR / "fonts" / fil
            if not p.exists():
                saknas.append(fil)
                continue
            data = base64.b64encode(p.read_bytes()).decode()
            css.append(f'@font-face{{font-family:"{namn}";src:url(data:font/ttf;base64,{data}) format("truetype");'
                       f"font-weight:200 900;font-style:{stil};font-display:block}}")
    return "\n".join(css), saknas


def fontstack(namn: str) -> str:
    fb = TYPSNITT.get(namn, {}).get("fallback", SANS)
    return f'"{namn}", {fb}'


# ---------------------------------------------------------------- vy-modell

RUBRIKER = {
    "profil": ("Profil", "Profile"), "erfarenhet": ("Erfarenhet", "Experience"),
    "utbildning": ("Utbildning", "Education"), "kompetenser": ("Kompetenser", "Skills"),
    "sprak": ("Språk", "Languages"), "kurser": ("Kurser och certifieringar", "Courses and certifications"),
    "ideella": ("Ideellt engagemang", "Volunteering"), "kontakt": ("Kontakt", "Contact"),
    "referenser": ("Referenser", "References"), "ovrigt": ("Övrigt", "Other"),
}
ETIKETTER = {
    "referenser_text": ("Referenser lämnas på begäran.", "References available on request."),
    "epost": ("E-post", "Email"), "telefon": ("Telefon", "Phone"), "ort": ("Ort", "Location"),
    "korkort": ("Körkort", "Driving licence"),
}
ALIAS = {
    "profil": "profil", "profile": "profil", "sammanfattning": "profil", "summary": "profil", "om mig": "profil",
    "erfarenhet": "erfarenhet", "arbetslivserfarenhet": "erfarenhet", "experience": "erfarenhet",
    "work experience": "erfarenhet", "anställningar": "erfarenhet", "yrkeserfarenhet": "erfarenhet",
    "utbildning": "utbildning", "education": "utbildning",
    "kompetenser": "kompetenser", "kompetens": "kompetenser", "skills": "kompetenser", "färdigheter": "kompetenser",
    "verktyg": "kompetenser", "tools": "kompetenser",
    "språk": "sprak", "sprak": "sprak", "languages": "sprak",
    "kurser": "kurser", "courses": "kurser", "certifieringar": "kurser", "certifications": "kurser",
    "kurser och certifieringar": "kurser", "courses and certifications": "kurser",
    "ideella": "ideella", "ideellt engagemang": "ideella", "ideellt": "ideella", "volunteering": "ideella",
    "förtroendeuppdrag": "ideella", "referenser": "referenser", "references": "referenser",
    "övrigt": "ovrigt", "other": "ovrigt",
}
SIDOKOLUMN_NYCKLAR = {"kompetenser", "sprak"}


def _txt(v, sprak):
    """Txt-objekt {"sv","en"} eller sträng till sträng."""
    if isinstance(v, dict):
        return v.get(sprak) or v.get("sv") or v.get("en") or ""
    return "" if v is None else str(v)


def _sakert_url(u: str) -> str | None:
    u = (u or "").strip()
    if re.match(r"^(https?://|mailto:|tel:)", u, re.I):
        return u
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", u, re.I):
        return "https://" + u
    return None


def _kort_url(u: str) -> str:
    return re.sub(r"^(https?://)?(www\.)?", "", u or "").rstrip("/")


def sektion_nyckel(s: dict) -> str:
    for kandidat in (s.get("id"), s.get("typ"), s.get("rubrik")):
        if kandidat:
            k = str(kandidat).strip().lower()
            if k in ALIAS:
                return ALIAS[k]
    typ = s.get("typ") or "text"
    return {"lista": "kompetenser", "text": "ovrigt"}.get(typ, typ)


def _bild_data_uri(p: Path | None) -> str | None:
    if not p or not p.exists() or p.stat().st_size > 8_000_000:
        return None
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    if not mime.startswith("image/"):
        return None
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _foto(person: dict, bas: list[Path]) -> str | None:
    f = person.get("foto")
    if not f:
        return None
    for b in bas:
        p = (b / f) if not Path(f).is_absolute() else Path(f)
        if p.exists():
            return _bild_data_uri(p)
    return None


def person_vy(person: dict, sprak: str, bas: list[Path], visa_foto: bool) -> dict:
    sv = 0 if sprak == "sv" else 1
    kontakt = []
    if person.get("epost"):
        kontakt.append({"text": person["epost"], "url": "mailto:" + person["epost"].strip(),
                        "etikett": ETIKETTER["epost"][sv]})
    if person.get("telefon"):
        tel = re.sub(r"[^\d+]", "", person["telefon"])
        kontakt.append({"text": person["telefon"], "url": "tel:" + tel, "etikett": ETIKETTER["telefon"][sv]})
    if person.get("ort"):
        kontakt.append({"text": _txt(person["ort"], sprak), "url": None, "etikett": ETIKETTER["ort"][sv]})
    for l in person.get("lankar") or []:
        url = _sakert_url(l.get("url", "")) if isinstance(l, dict) else _sakert_url(str(l))
        if url:
            etik = l.get("etikett", "") if isinstance(l, dict) else ""
            kontakt.append({"text": _kort_url(url), "url": url, "etikett": etik})
    if person.get("korkort"):
        kontakt.append({"text": f"{ETIKETTER['korkort'][sv]} {person['korkort']}", "url": None, "etikett": ""})
    foto = _foto(person, bas) if visa_foto else None
    return {"namn": person.get("namn", ""), "titel": _txt(person.get("titel"), sprak),
            "kontakt": kontakt, "foto": foto}


def _post_vy(p: dict, sprak: str) -> dict:
    punkter = [_txt(x, sprak) for x in (p.get("punkter") or []) if _txt(x, sprak).strip()]
    plats = ", ".join(x for x in (_txt(p.get("organisation"), sprak), _txt(p.get("ort"), sprak)) if x)
    return {"titel": _txt(p.get("titel"), sprak), "organisation": _txt(p.get("organisation"), sprak),
            "ort": _txt(p.get("ort"), sprak), "plats": plats, "period": _txt(p.get("period"), sprak),
            "text": _txt(p.get("text"), sprak), "punkter": punkter,
            # Långa poster får brytas mellan punkter; korta hålls hela.
            "lang": len(punkter) > 3 or sum(len(x) for x in punkter) > 420}


def sektion_vy(s: dict, nyckel: str, sprak: str) -> dict:
    sv = 0 if sprak == "sv" else 1
    rubrik = _txt(s.get("rubrik"), sprak) or RUBRIKER.get(nyckel, ("", ""))[sv] or nyckel.capitalize()
    grupper = []
    for g in s.get("grupper") or []:
        poster = [_txt(x, sprak) for x in (g.get("poster") or []) if _txt(x, sprak).strip()]
        if poster:
            grupper.append({"etikett": _txt(g.get("etikett"), sprak), "poster": poster,
                            "rad": " · ".join(poster)})
    if not grupper and s.get("poster") and all(isinstance(x, (str, dict)) and not (isinstance(x, dict) and "titel" in x)
                                               for x in s["poster"]) and s.get("typ") == "lista":
        poster = [_txt(x, sprak) for x in s["poster"]]
        grupper = [{"etikett": "", "poster": poster, "rad": " · ".join(poster)}]
    poster = [] if s.get("typ") == "lista" else [_post_vy(p, sprak) for p in (s.get("poster") or []) if isinstance(p, dict)]
    text = _txt(s.get("text"), sprak)
    stycken = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()] if text else []
    return {"nyckel": nyckel, "rubrik": rubrik, "typ": s.get("typ") or "text",
            "poster": poster, "grupper": grupper, "stycken": stycken,
            "ar_lista": bool(grupper), "ar_poster": bool(poster), "ar_text": bool(stycken),
            "tom": not (grupper or poster or stycken)}


def ordna_sektioner(cv: dict, design: dict, sprak: str) -> tuple[list[dict], list[str]]:
    ordning = list(design.get("sektioner") or STANDARD_SEKTIONER)
    alla = []
    if cv.get("profil"):
        alla.append(sektion_vy({"typ": "text", "text": cv["profil"]}, "profil", sprak))
    for s in cv.get("sektioner") or []:
        alla.append(sektion_vy(s, sektion_nyckel(s), sprak))
    alla = [s for s in alla if not s["tom"]]
    varn = []
    ut = []
    for k in ordning:
        ut += [s for s in alla if s["nyckel"] == k]
    rest = [s for s in alla if s["nyckel"] not in ordning]
    if rest:
        varn.append("Sektioner som inte finns i designens ordning lades sist: "
                    + ", ".join(s["rubrik"] for s in rest))
    return ut + rest, varn


def tokens_css(t: dict) -> str:
    rader = {
        "--font-rubrik": fontstack(t["font_rubrik"]), "--font-brod": fontstack(t["font_brod"]),
        "--storlek-brod": f"{t['storlek_brod_pt']}pt", "--storlek-namn": f"{t['storlek_namn_pt']}pt",
        "--storlek-rubrik": f"{t['storlek_rubrik_pt']}pt", "--radavstand": str(t["radavstand"]),
        "--farg-text": t["farg_text"], "--farg-accent": t["farg_accent"], "--farg-dampad": t["farg_dampad"],
        "--marginal": f"{t['marginal_mm']}mm", "--sektion-luft": f"{t['sektion_luft_mm']}mm",
    }
    kropp = ";".join(f"{k}:{v}" for k, v in rader.items())
    m = t["marginal_mm"]
    # @page kan inte läsa CSS-variabler, därför skrivs marginalen in direkt.
    return f":root{{{kropp}}}\n@page{{size:A4;margin:{m * 0.85:.1f}mm {m}mm {m:.1f}mm {m}mm}}"


def bygg_kontext(dok: dict, design: dict, bas: list[Path], typ: str) -> tuple[dict, list[str]]:
    sprak = dok.get("sprak") if dok.get("sprak") in ("sv", "en") else "sv"
    t = klamp_tokens(design.get("tokens", {}))
    layout = design.get("layout") if design.get("layout") in LAYOUTER else "klassisk"
    visa_foto = bool(t.get("visa_foto")) or layout == "portratt"
    css_font, saknas = fontface_css([t["font_rubrik"], t["font_brod"]])
    varn = [f"Typsnittsfil saknas: {f}; systemtypsnitt används." for f in saknas]
    bas_css = (MALLAR / "cv" / "bas.css").read_text("utf-8")
    sv = 0 if sprak == "sv" else 1
    person = person_vy(dok.get("person") or {}, sprak, bas, visa_foto)
    if visa_foto and (dok.get("person") or {}).get("foto") and not person["foto"]:
        varn.append("Fotot hittades inte; CV:t renderades utan foto.")
    ctx = {
        "sprak": sprak, "layout": layout, "typ": typ,
        "css": tokens_css(t) + "\n" + css_font + "\n" + bas_css,
        "rubrik_stil": t["rubrik_stil"], "person": person,
        "rub": {k: v[sv] for k, v in RUBRIKER.items()},
        "etikett": {k: v[sv] for k, v in ETIKETTER.items()},
        "design_namn": design.get("namn", ""),
    }
    if typ == "cv":
        sekt, v2 = ordna_sektioner(dok, design, sprak)
        varn += v2
        if layout == "sidokolumn":
            ctx["huvud"] = [s for s in sekt if s["nyckel"] not in SIDOKOLUMN_NYCKLAR or not s["ar_lista"]]
            ctx["sida"] = [s for s in sekt if s["nyckel"] in SIDOKOLUMN_NYCKLAR and s["ar_lista"]]
        else:
            ctx["huvud"], ctx["sida"] = sekt, []
        ctx["sektioner"] = sekt
        ctx["titel"] = f"{person['namn']} – CV" if sprak == "sv" else f"{person['namn']} – Résumé"
    else:
        mott = dok.get("mottagare") or {}
        ctx["mottagare"] = {"namn": mott.get("namn", ""), "bolag": mott.get("bolag", ""),
                            "adress_rader": [r for r in str(mott.get("adress", "")).split("\n") if r.strip()]}
        ctx["datum"] = dok.get("datum", "")
        ctx["rubrik"] = _txt(dok.get("rubrik"), sprak)
        ctx["stycken"] = [_txt(s, sprak) for s in dok.get("stycken") or [] if _txt(s, sprak).strip()]
        ctx["halsning"] = _txt(dok.get("halsning"), sprak) or ("Vänliga hälsningar" if sprak == "sv" else "Kind regards")
        ctx["titel"] = f"{person['namn']} – {'Personligt brev' if sprak == 'sv' else 'Cover letter'}"
    return ctx, varn


# ---------------------------------------------------------------- PDF-motorer

def _chrome() -> str | None:
    kandidater = []
    if env := os.environ.get("CHROME_PATH"):
        kandidater.append(env)
    if platform.system() == "Darwin":
        for app in ("Google Chrome", "Chromium", "Google Chrome Canary", "Microsoft Edge", "Brave Browser"):
            for rot in ("/Applications", str(Path.home() / "Applications")):
                kandidater.append(f"{rot}/{app}.app/Contents/MacOS/{app}")
    for namn in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        if w := shutil.which(namn):
            kandidater.append(w)
    return next((k for k in kandidater if Path(k).exists()), None)


def _chrome_flaggor(tmp: str) -> list[str]:
    f = ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--hide-scrollbars", "--disable-extensions", f"--user-data-dir={tmp}", "--run-all-compositor-stages-before-draw",
         "--virtual-time-budget=5000"]
    if platform.system() == "Linux":
        f += ["--no-sandbox", "--disable-dev-shm-usage"]
    return f


def _kor_chrome(args: list[str], ut: Path, timeout: float = 90) -> bool:
    """Kör Chrome headless och vänta tills utfilen är klar.

    Chrome avslutar ibland inte själv efter utskrift (t.ex. i sandlådor), så vi
    väntar på att filen blir stabil och avslutar sedan processen."""
    import time
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.Popen([*args[:1], *_chrome_flaggor(tmp), *args[1:]],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        start, storlek, stabil = time.time(), -1, 0
        while time.time() - start < timeout:
            if proc.poll() is not None:
                break
            if ut.exists():
                s = ut.stat().st_size
                stabil = stabil + 1 if s == storlek and s > 0 else 0
                storlek = s
                if stabil >= 3:
                    break
            time.sleep(0.2)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return ut.exists() and ut.stat().st_size > 500


def pdf_chrome(html_p: Path, pdf_p: Path) -> bool:
    exe = _chrome()
    if not exe:
        return False
    return _kor_chrome([exe, "--no-pdf-header-footer", f"--print-to-pdf={pdf_p}", html_p.resolve().as_uri()], pdf_p)


def pdf_playwright(html_p: Path, pdf_p: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return False
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            s = b.new_page()
            s.goto(html_p.resolve().as_uri(), wait_until="networkidle")
            s.pdf(path=str(pdf_p), prefer_css_page_size=True, print_background=True)
            b.close()
        return pdf_p.exists()
    except Exception:
        return False


# WeasyPrint saknar display: contents (kompakt-layoutens rutnät) och räknar inte ut
# color-mix() med var(); därför en liten anpassning som bara används för WeasyPrint.
WEASY_CSS = """
.lay-kompakt .post { display: block; position: relative; padding-left: 32mm; }
.lay-kompakt .post .period { position: absolute; left: 0; top: 0; width: 27mm; }
.kontakt span::before { content: none; }
.kontakt span { margin-left: 0; margin-right: 1.2em; }
.kontakt { margin-left: 0; }
"""


def weasy_html(text: str) -> str:
    m = re.search(r"--farg-accent:\s*(#[0-9a-fA-F]{6})", text)
    if m:
        acc = m.group(1)

        def blanda(mm):
            andel = int(mm.group(1)) / 100
            rgb = [round(int(acc[i:i + 2], 16) * andel + 255 * (1 - andel)) for i in (1, 3, 5)]
            return "#" + "".join(f"{x:02x}" for x in rgb)
        text = re.sub(r"color-mix\(in srgb, var\(--farg-accent\) (\d+)%, #fff\)", blanda, text)
    return text.replace("</head>", f"<style>{WEASY_CSS}</style></head>", 1)


def pdf_weasyprint(html_p: Path, pdf_p: Path) -> bool:
    try:
        import weasyprint  # type: ignore
    except Exception:
        return False
    try:
        weasyprint.HTML(string=weasy_html(html_p.read_text("utf-8")), base_url=str(html_p.parent.resolve()) + "/"
                        ).write_pdf(str(pdf_p))
        return pdf_p.exists()
    except Exception:
        return False


MOTORER = [("chrome", pdf_chrome), ("playwright", pdf_playwright), ("weasyprint", pdf_weasyprint)]


def gor_pdf(html_p: Path, pdf_p: Path) -> str | None:
    """JOBBSOK_PDF_MOTOR=ingen|chrome|playwright|weasyprint tvingar en motor (eller ingen)."""
    tvinga = os.environ.get("JOBBSOK_PDF_MOTOR")
    if tvinga == "ingen":
        return None
    if pdf_p.exists():
        pdf_p.unlink()
    for namn, fn in MOTORER:
        if tvinga and namn != tvinga:
            continue
        if fn(html_p, pdf_p):
            return namn
    return None


def motorer() -> dict:
    ut = {"chrome": bool(_chrome())}
    for namn, mod in (("playwright", "playwright.sync_api"), ("weasyprint", "weasyprint")):
        try:
            __import__(mod)
            ut[namn] = True
        except Exception as e:  # weasyprint ger OSError om Pango saknas
            ut[namn] = False if isinstance(e, ImportError) else f"installerad men fungerar inte: {str(e)[:120]}"
    ut["bild"] = "pdftoppm" if shutil.which("pdftoppm") else "sips" if shutil.which("sips") else "chrome" if ut["chrome"] else None
    ut["forsta"] = next((n for n in ("chrome", "playwright", "weasyprint") if ut[n] is True), "html")
    return ut


def _strommar(data: bytes) -> list[bytes]:
    ut = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        slut = data.find(b"endstream", start)
        if slut < 0:
            continue
        try:
            ut.append(zlib.decompress(data[start:slut]))
        except zlib.error:
            try:
                ut.append(zlib.decompressobj().decompress(data[start:slut]))
            except zlib.error:
                ut.append(data[start:slut])
    return ut


def sidantal(pdf_p: Path) -> int | None:
    data = pdf_p.read_bytes()
    n = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))
    if n == 0:
        n = sum(len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", s)) for s in _strommar(data))
    return n or None


def textlager(pdf_p: Path) -> dict:
    if shutil.which("pdftotext"):
        try:
            r = subprocess.run(["pdftotext", "-layout", str(pdf_p), "-"], capture_output=True, timeout=30)
            text = r.stdout.decode("utf-8", "replace")
            return {"finns": len(text.strip()) > 20, "metod": "pdftotext", "tecken": len(text.strip())}
        except Exception:
            pass
    data = pdf_p.read_bytes()
    ops = sum(len(re.findall(rb"\bBT\b[\s\S]{0,400}?(Tj|TJ)", s)) for s in _strommar(data))
    return {"finns": ops > 0, "metod": "textoperatorer", "tecken": None}


def _tyst(cmd, timeout=60):
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        pass


def gor_bild(pdf_p: Path | None, html_p: Path, png_p: Path) -> str | None:
    """Förhandsbild av sida 1. pdftoppm → sips (macOS) → Chrome --screenshot."""
    if pdf_p and pdf_p.exists():
        if shutil.which("pdftoppm"):
            stam = str(png_p.with_suffix(""))
            _tyst(["pdftoppm", "-png", "-r", "110", "-f", "1", "-l", "1", "-singlefile", str(pdf_p), stam])
            if png_p.exists():
                return "pdftoppm"
        if shutil.which("sips"):
            _tyst(["sips", "-s", "format", "png", "-Z", "1300", str(pdf_p), "--out", str(png_p)])
            if png_p.exists():
                return "sips"
    exe = _chrome()
    if exe:
        if _kor_chrome([exe, "--window-size=794,1123", "--force-device-scale-factor=1.5",
                        f"--screenshot={png_p}", html_p.resolve().as_uri()], png_p):
            return "chrome-screenshot"
    return None


HTML_INSTRUKTION = ("Ingen PDF-motor hittades. Öppna {html} i Chrome, Safari eller Edge, välj Arkiv → Skriv ut "
                    "(Cmd/Ctrl+P), välj 'Spara som PDF', pappersstorlek A4, marginaler 'Standard', "
                    "och slå AV 'Sidhuvud och sidfot'.")


# ---------------------------------------------------------------- huvudflöden

def _las_dok(arg: str, typ: str) -> tuple[dict, Path, Path]:
    p = Path(arg).expanduser()
    if p.is_dir():
        mapp, fil = p, p / f"{typ}.json"
    else:
        mapp, fil = p.parent, p
    if not fil.exists():
        raise SystemExit(f"Hittar inte {fil}")
    return las_json(fil), mapp, fil


def rendera(typ: str, dok: dict, design: dict, ut_mapp: Path, bas: list[Path], stam: str | None = None,
            pdf: bool = True, bild: bool = False) -> dict:
    ut_mapp.mkdir(parents=True, exist_ok=True)
    stam = stam or typ
    import mall_slots  # krok: varianter och egna mallar från Claude Design ("egen:<namn>")
    design = mall_slots.tillampa_variant(design, dok)
    ctx, varn = bygg_kontext(dok, design, bas, typ)
    mall = MALLAR / ("brev/brev.html" if typ == "brev" else f"cv/{ctx['layout']}.html")
    html_p = ut_mapp / f"{stam}.html"
    egen = mall_slots.fyll_egen(typ, ctx, design, bas)
    html_p.write_text(egen or fyll(mall, ctx, [mall.parent, MALLAR / "cv", MALLAR]), "utf-8")
    res = {"typ": typ, "html": str(html_p), "pdf": None, "motor": None, "sidor": None, "overflow": None,
           "textlager": None, "bild": None, "layout": ctx["layout"] if typ == "cv" else "brev", "sprak": ctx["sprak"],
           "design": design.get("namn"), "design_version": design.get("version"),
           "varningar": varn + granska_design(design)}
    if pdf:
        pdf_p = ut_mapp / f"{stam}.pdf"
        motor = gor_pdf(html_p, pdf_p)
        if motor:
            res.update(pdf=str(pdf_p), motor=motor, sidor=sidantal(pdf_p), textlager=textlager(pdf_p))
            if res["sidor"]:
                res["overflow"] = res["sidor"] > MAX_SIDOR[typ]
                if res["overflow"]:
                    res["varningar"].append(f"{typ.upper()} blev {res['sidor']} sidor (max {MAX_SIDOR[typ]}). Korta ner innehållet.")
            if not res["textlager"]["finns"]:
                res["varningar"].append("PDF:en saknar textlager; ATS-system kan inte läsa den.")
        else:
            res["motor"] = "html"
            res["instruktion"] = HTML_INSTRUKTION.format(html=html_p)
    if bild:
        png = ut_mapp / f"{stam}.png"
        if png.exists():
            png.unlink()
        if gor_bild(Path(res["pdf"]) if res["pdf"] else None, html_p, png):
            res["bild"] = str(png)
    return res


def jamforelse(kort: list[dict], ut_mapp: Path, rubrik: str, ingress: str = "") -> Path:
    for i, k in enumerate(kort):
        k.setdefault("bokstav", chr(65 + i))
        for f in ("html", "pdf", "bild"):
            if k.get(f):
                k[f + "_rel"] = os.path.relpath(k[f], ut_mapp)
    sida = fyll(MALLAR / "jamforelse.html", {"kort": kort, "rubrik": rubrik, "ingress": ingress,
                                              "antal": len(kort)})
    p = ut_mapp / "jamforelse.html"
    p.write_text(sida, "utf-8")
    return p


def kor_forslag(arg: str, forval: list[str], ut: Path | None, home: Path, bild: bool = True) -> dict:
    cv, mapp, _ = _las_dok(arg, "cv")
    ut = ut or (mapp / "forslag")
    kort = []
    for namn in forval:
        design = las_json(forval_path(namn))
        stam = f"forslag-{Path(namn).stem}"
        r = rendera("cv", cv, design, ut, [mapp, home], stam=stam, bild=bild)
        r["namn"] = design.get("namn", namn)
        r["beskrivning"] = design.get("beskrivning", "")
        r["id"] = Path(namn).stem
        kort.append(r)
    sida = jamforelse(kort, ut, "Tre förslag – samma innehåll, olika design" if len(kort) == 3 else "Designförslag",
                      "Titta på helheten först: vilken känns mest som du? Du kan kombinera, till exempel "
                      "rubrikerna från B och färgen från A.")
    return {"jamforelse": str(sida), "forslag": kort}


def kor_stresstest(design_p: Path, ut: Path, home: Path, bild: bool = True) -> dict:
    design = las_json(design_p)
    kort = []
    for fil in sorted(FIXTURER.glob("cv-*.json")):
        r = rendera("cv", las_json(fil), design, ut, [FIXTURER, home], stam=f"stress-{fil.stem}", bild=bild)
        r["namn"] = fil.stem.replace("cv-", "").replace("-", " ")
        r["id"] = fil.stem
        kort.append(r)
    for fil in sorted(FIXTURER.glob("brev-*.json")):
        r = rendera("brev", las_json(fil), design, ut, [FIXTURER, home], stam=f"stress-{fil.stem}", bild=bild)
        r["namn"] = fil.stem.replace("-", " ")
        r["id"] = fil.stem
        kort.append(r)
    sida = jamforelse(kort, ut, f"Stresstest: {design.get('namn', '')}",
                      "Kort och långt CV, långa titlar, svenska och engelska. Designen ska hålla i alla.")
    problem = [f"{k['id']}: {v}" for k in kort for v in k["varningar"] if "sidor" in v or "textlager" in v]
    return {"jamforelse": str(sida), "resultat": kort, "problem": problem}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kommando", choices=["cv", "brev", "forslag", "stresstest", "motorer"])
    ap.add_argument("mal", nargs="?", help="ansökningsmapp, cv.json/brev.json eller fixtur")
    ap.add_argument("--design", help="design.json eller förvalsnamn (standard: $JOBBSOK_HOME/design/design.json)")
    ap.add_argument("--forval", default="konservativ,modern,varm", help="kommaseparerade förval eller sökvägar")
    ap.add_argument("--out", help="utmapp (standard: samma mapp som underlaget)")
    ap.add_argument("--home", help="datamapp (standard: $JOBBSOK_HOME eller ~/Jobbsok)")
    ap.add_argument("--bild", action="store_true", help="gör också en PNG-förhandsbild av sida 1")
    ap.add_argument("--ingen-pdf", action="store_true", help="bygg bara HTML")
    a = ap.parse_args(argv)
    if a.kommando == "motorer":
        print(json.dumps(motorer(), ensure_ascii=False, indent=2))
        return 0
    home = hem(a.home)
    out = Path(a.out).expanduser() if a.out else None

    if a.kommando in ("cv", "brev"):
        if not a.mal:
            ap.error("ange ansökningsmapp eller json-fil")
        dok, mapp, _ = _las_dok(a.mal, a.kommando)
        design = las_json(hitta_design(a.design, home))
        if a.kommando == "brev" and not dok.get("person"):
            # brev.json har ingen egen person (schemat tillåter den inte): ta brevhuvud och
            # underskrift från CV:t i samma mapp, annars från faktabanken.
            for kalla in (Path(mapp) / "cv.json", home / "profil" / "fakta.json"):
                if kalla.exists():
                    p = las_json(kalla).get("person")
                    if p:
                        dok = {**dok, "person": p}
                        break
        res = rendera(a.kommando, dok, design, out or mapp, [mapp, home], pdf=not a.ingen_pdf, bild=a.bild)
    elif a.kommando == "forslag":
        if not a.mal:
            ap.error("ange ansökningsmapp, cv.json eller fixtur")
        res = kor_forslag(a.mal, [x.strip() for x in a.forval.split(",") if x.strip()], out, home)
    else:
        d = hitta_design(a.design, home)
        res = kor_stresstest(d, out or (home / "design" / "stresstest"), home)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
