#!/usr/bin/env python3
"""Bygg ett paket att ta med till Claude Design.

  design_export.py [cv.json|ansökningsmapp] [--home MAPP] [--ut MAPP]

Paketet hamnar i <home>/design/till-claude-design/ (och som .zip bredvid):
  cv-exempel.html            hennes riktiga innehåll, med slot-attribut (data-slot …)
  brev-exempel.html          personligt brev i samma stil
  komponenter/*.html         en del per fil, med <!-- @dsCard group="CV" --> först
  tokens.css, mall.css       färger, typsnitt och mått som CSS-variabler + standardstil
  fonts/                     typsnitten (OFL)
  README-for-claude-design.md  instruktionen att klistra in i Claude Design (brief + regler)

Innehållet hämtas i ordningen: argumentet, senaste ansökningen med cv.json,
<home>/design/underlag/cv.json, annars exemplet i pluginen (då står det i svaret).
Resultatet skrivs som JSON.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mall_slots as ms  # noqa: E402
import render  # noqa: E402

SLOTS = render.MALLAR / "cv" / "slots"
DSCARD = '<!-- @dsCard group="CV" -->'


def hitta_innehall(arg: str | None, home: Path) -> tuple[dict, Path, bool]:
    if arg:
        dok, mapp, _ = render._las_dok(arg, "cv")
        return dok, mapp, False
    kand = sorted((home / "ansokningar").glob("*/cv.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    kand.append(home / "design" / "underlag" / "cv.json")
    for p in kand:
        if p.exists():
            return render.las_json(p), p.parent, False
    return render.las_json(render.FIXTURER / "cv-kort-sv.json"), render.FIXTURER, True


def hitta_brev(mapp: Path, cv: dict) -> dict:
    p = mapp / "brev.json"
    brev = render.las_json(p) if p.exists() else render.las_json(render.FIXTURER / f"brev-{cv.get('sprak', 'sv')}.json")
    return {**brev, "person": cv.get("person") or brev.get("person") or {}}


def tokens_fil(design: dict) -> str:
    """tokens.css: CSS-variabler + @font-face mot fonts/ (relativt)."""
    t = render.klamp_tokens(design.get("tokens", {}))
    rader = [render.tokens_css(t)]
    for namn in dict.fromkeys([t["font_rubrik"], t["font_brod"]]):
        for fil, stil in render.TYPSNITT.get(namn, {}).get("filer", []):
            if (render.MALLAR / "fonts" / fil).exists():
                rader.append(f'@font-face{{font-family:"{namn}";src:url("fonts/{fil}") format("truetype");'
                             f"font-weight:200 900;font-style:{stil};font-display:block}}")
    kommentar = ("/* Tokens från jobbsok. Använd var(--farg-accent) osv. i stilen, så går färger och "
                 "storlekar att justera senare utan att mallen görs om. */\n")
    return kommentar + "\n".join(rader) + "\n"


def _dokument(titel: str, kropp: str, css: str, klass: str = "cv", lang: str = "sv", dscard: bool = False) -> str:
    huvud = DSCARD + "\n" if dscard else ""
    return (f'{huvud}<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{titel}</title>\n'
            f'{css}</head>\n<body class="{klass}">\n<main class="sida">\n{kropp}\n</main>\n</body>\n</html>\n')


def _hitta(rot: ms.Nod, villkor):
    return [x for x in rot.iter() if x.typ == "el" and villkor(x)]


def komponenter(cv_html: str, brev_html: str, lang: str) -> dict[str, str]:
    rot, brot = ms.parsa(cv_html), ms.parsa(brev_html)
    ser = ms.serialisera
    css = '<link rel="stylesheet" href="../tokens.css">\n<link rel="stylesheet" href="../mall.css">\n'
    sek = {x.get("data-sektion"): x for x in _hitta(rot, lambda x: x.har("data-sektion"))}
    huvud = _hitta(rot, lambda x: x.tag == "header")
    post = _hitta(rot, lambda x: x.get("data-repeat") == "poster")
    punkter = _hitta(rot, lambda x: x.tag == "ul" and any(b.get("data-repeat") == "punkter" for b in x.element()))
    ut = {}
    if huvud:
        ut["sidhuvud"] = ser(huvud[0])
    forsta = sek.get("erfarenhet") or sek.get("profil")
    if forsta is not None:
        ut["sektion"] = ser(forsta)
    if post:
        ut["post"] = ser(post[0])
    if punkter:
        ut["punktlista"] = ser(punkter[0])
    if "kompetenser" in sek:
        ut["kompetenslista"] = ser(sek["kompetenser"])
    if forsta is not None:
        sida = "".join(ser(sek[k]) for k in ("kompetenser", "sprak") if k in sek)
        ut["sidokolumn"] = (f'<div class="kropp kropp-sidokolumn">\n<div class="huvudspalt">{ser(forsta)}</div>\n'
                            f'<aside class="sidospalt">{sida}</aside>\n</div>')
    bh = _hitta(brot, lambda x: x.tag == "header")
    mott = _hitta(brot, lambda x: "mottagare" in x.klasser())
    if bh:
        ut["brevhuvud"] = ser(bh[0]) + (ser(mott[0]) if mott else "")
    titlar = {"sidhuvud": "Sidhuvud", "sektion": "Sektion", "post": "Post (roll)", "punktlista": "Punktlista",
              "kompetenslista": "Kompetenslista", "sidokolumn": "Sidokolumn (valfri)", "brevhuvud": "Brevhuvud"}
    return {k: _dokument(titlar[k], v, css, "brev" if k == "brevhuvud" else "cv", lang, dscard=True)
            for k, v in ut.items()}


README = """# Instruktion till Claude Design: CV-mall för {namn}

Klistra in den här texten i Claude Design tillsammans med filerna i paketet
(cv-exempel.html, brev-exempel.html, komponenter/, tokens.css, mall.css, fonts/).

## Vad vi gör
Vi gör en **CV-mall som ska återanvändas för alla jobb**. Texten byts automatiskt
per ansökan, så designen måste tåla både korta och långa CV, svenska och engelska.
Exemplet innehåller hennes riktiga innehåll. Designa med det, men tänk på att
antalet roller och punkter varierar.

## Briefen
{brief}

## Absoluta regler (annars går mallen inte att fylla)
1. **Behåll alla data-attribut**: `data-slot`, `data-slot-rubrik`, `data-sektion`,
   `data-repeat`, `data-if`. De talar om var namn, rubriker, roller och punkter ska in.
   Flytta, styla och slå in elementen i nya `<div>`-ar hur du vill, men ta inte bort attributen.
2. Ett element med `data-repeat` upprepas per post/punkt. Behåll **ett** exempel per
   lista; fler exempel tas bort automatiskt.
3. Hitta inte på nytt innehåll i stället för slots (inga påhittade rubriker eller texter).
4. Sidan är **A4** (210 × 297 mm). Behåll `@page {{ size: A4 }}`.
5. **En kolumn**, eller en **smal sidokolumn** (högst ca 55 mm) med bara kontakt,
   kompetenser och språk. Huvudtexten ska komma först i HTML:en.
6. **Inga bilder av text**, inga ikoner i stället för ord, inga kompetensstaplar.
7. **Inga tabeller för layout.** Använd flex eller grid.
8. **Minsta textstorlek 9 pt** (brödtext helst 10–11,5 pt). Text mot bakgrund ska ha
   kontrast minst 4,5:1, brödtext helst 7:1. Inga ljusa pastellfärger på text.
9. Högst två typsnitt. Använd gärna `var(--font-rubrik)` och `var(--font-brod)` och
   färgerna `var(--farg-text)`, `var(--farg-accent)`, `var(--farg-dampad)` från tokens.css,
   så går de att justera senare utan att mallen görs om.
10. Vänsterjusterad text, aldrig marginaljusterad. Inget viktigt i sidhuvud/sidfot.
11. Varje roll (`data-repeat="poster"`) ska hålla ihop: `break-inside: avoid`.
12. Fotot (`data-if="person.foto"`) är valfritt. Ta bort elementet om hon inte vill ha foto.

## Typografi som fungerar
- Brödtext 10–11,5 pt, rubriker 11–16 pt, namn 20–30 pt, radavstånd 1,2–1,45.
- Marginaler 15–20 mm. Luft mellan sektioner 3–9 mm.
- En accentfärg, mörkgrå text. Mörka, dämpade accenter håller utskrivna.

## Gör inte
- Två lika breda kolumner, text i cirklar eller diagram, betyg i staplar eller stjärnor.
- Rubriker som "Min resa" i stället för Erfarenhet/Utbildning/Kompetenser.
- Fast höjd eller `overflow: hidden` på sidan eller sektionerna (långt innehåll klipps då).
- Text som bilder eller SVG-text, bakgrundsbilder bakom text.

## Varianter (valfritt)
Vill hon ha flera utformningar (till exempel **stram** för myndigheter, **standard**
och **kreativ** för byrå/kultur), gör en sida per variant med samma attribut. Exportera
varje sida som egen HTML. Varianterna delar typsnitt och färgsystem.

## När du är klar
Exportera som **fristående HTML** (eller zip). Hon tar filen tillbaka till Claude,
som gör om den till en mall och kontrollerar att inget innehåll tappas.
"""

BRIEF_SAKNAS = ("(Ingen brief sparad ännu. Fyll i: vem som läser CV:t, tre ord för känslan, "
                "foto ja/nej, förebilder.)")


def exportera(arg: str | None, home: Path, ut: Path | None = None) -> dict:
    ut = ut or (home / "design" / "till-claude-design")
    if ut.exists():
        shutil.rmtree(ut)
    (ut / "komponenter").mkdir(parents=True)
    (ut / "fonts").mkdir()
    cv, mapp, ar_exempel = hitta_innehall(arg, home)
    design_p = render.hitta_design(None, home)
    design = render.las_json(design_p)
    bas = [mapp, home, render.FIXTURER]
    # Exemplet visar standarduppläget; egna mallar exporteras inte här.
    d = dict(design, layout="klassisk")
    visa_foto = bool((design.get("tokens") or {}).get("visa_foto"))
    d["tokens"] = dict(design.get("tokens") or {}, visa_foto=visa_foto)
    ctx, _ = render.bygg_kontext(cv, d, bas, "cv")
    tok = tokens_fil(d)
    (ut / "tokens.css").write_text(tok, "utf-8")
    shutil.copy(SLOTS / "mall.css", ut / "mall.css")
    mallcss = (SLOTS / "mall.css").read_text("utf-8")
    inline = f"\n{tok}\n{mallcss}"
    cv_html = ms.fyll_mall((SLOTS / "cv.html").read_text("utf-8"), ctx, inline, d.get("sektioner"))
    (ut / "cv-exempel.html").write_text(cv_html, "utf-8")
    brev = hitta_brev(mapp, cv)
    bctx, _ = render.bygg_kontext(brev, d, bas, "brev")
    brev_html = ms.fyll_mall((SLOTS / "brev.html").read_text("utf-8"), bctx, inline)
    (ut / "brev-exempel.html").write_text(brev_html, "utf-8")
    for namn, text in komponenter(cv_html, brev_html, ctx["sprak"]).items():
        (ut / "komponenter" / f"{namn}.html").write_text(text, "utf-8")
    t = render.klamp_tokens(d.get("tokens", {}))
    for namn in dict.fromkeys([t["font_rubrik"], t["font_brod"]]):
        for fil, _ in render.TYPSNITT.get(namn, {}).get("filer", []):
            src = render.MALLAR / "fonts" / fil
            if src.exists():
                shutil.copy(src, ut / "fonts" / fil)
    for lic in (render.MALLAR / "fonts").glob("OFL-*.txt"):
        shutil.copy(lic, ut / "fonts" / lic.name)
    brief_p = home / "design" / "brief.md"
    brief = brief_p.read_text("utf-8").strip() if brief_p.exists() else BRIEF_SAKNAS
    (ut / "README-for-claude-design.md").write_text(
        README.format(namn=(cv.get("person") or {}).get("namn", "henne"), brief=brief), "utf-8")
    zip_p = ut.parent / "till-claude-design.zip"
    with zipfile.ZipFile(zip_p, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(ut.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(ut))
    return {"mapp": str(ut), "zip": str(zip_p), "cv_exempel": str(ut / "cv-exempel.html"),
            "instruktion": str(ut / "README-for-claude-design.md"),
            "komponenter": sorted(p.name for p in (ut / "komponenter").glob("*.html")),
            "innehall_fran": str(mapp), "exempelinnehall": ar_exempel, "brief_saknas": not brief_p.exists(),
            "design": str(design_p)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mal", nargs="?", help="cv.json eller ansökningsmapp (standard: senaste)")
    ap.add_argument("--home")
    ap.add_argument("--ut", help="utmapp (standard: <home>/design/till-claude-design)")
    a = ap.parse_args(argv)
    home = render.hem(a.home)
    res = exportera(a.mal, home, Path(a.ut).expanduser() if a.ut else None)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
