#!/usr/bin/env python3
"""Läs, ändra och versionera $JOBBSOK_HOME/design/design.json.

Varje ändring höjer versionen, sparar den gamla i design/versioner/design-v<N>.json
och lägger en rad i historik. Med --jamfor <ansökningsmapp|cv.json> renderas
före och efter sida vid sida.

  design_tool.py visa
  design_tool.py init --forval konservativ           (skapa design.json från ett förval)
  design_tool.py set farg_accent=#9a4a2f storlek_brod_pt=10.5 [--anteckning "..."] [--jamfor MAPP]
  design_tool.py kombinera --fran modern --tokens font_rubrik,rubrik_stil [--jamfor MAPP]
  design_tool.py layout sidokolumn [--jamfor MAPP]
  design_tool.py layout egen:<namn>                  (egen mall från Claude Design, se design_import.py)
  design_tool.py sektioner profil,erfarenhet,utbildning,kompetenser,sprak
  design_tool.py variant stram layout=klassisk farg_accent=#333333 sektioner=profil,erfarenhet,utbildning
  design_tool.py variant kreativ --standard          (gör varianten till standard)
  design_tool.py variant stram --ta-bort
  design_tool.py varianter                           (lista varianterna)
  design_tool.py namn "Lugn klassisk"
  design_tool.py historik
  design_tool.py aterstall 3 [--jamfor MAPP]
  design_tool.py frys [--anteckning "..."]

Alla kommandon tar --home. Resultatet skrivs som JSON.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402

KANDA_TOKENS = set(render.STANDARD_TOKENS)
KANDA_SEKTIONER = set(render.RUBRIKER) - {"kontakt"}


def sokvagar(home: Path) -> tuple[Path, Path]:
    d = home / "design"
    return d / "design.json", d / "versioner"


def las(home: Path) -> dict:
    p, _ = sokvagar(home)
    if not p.exists():
        raise SystemExit(json.dumps({"fel": f"{p} finns inte. Kör först: design_tool.py init --forval konservativ"},
                                    ensure_ascii=False))
    return render.las_json(p)


def skriv_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", "utf-8")
    tmp.replace(p)


def arkivera(home: Path, design: dict) -> Path:
    _, vmapp = sokvagar(home)
    p = vmapp / f"design-v{design.get('version', 1)}.json"
    if not p.exists():
        skriv_json(p, design)
    return p


def giltig_layout(namn: str, home: Path) -> bool:
    if namn in render.LAYOUTER:
        return True
    if namn.startswith("egen:"):
        import mall_slots
        return mall_slots.hitta_mall(namn[5:], [home]) is not None
    return False


def tolka_varde(nyckel: str, s: str):
    if nyckel == "visa_foto":
        return s.strip().lower() in ("1", "ja", "true", "yes", "on")
    if nyckel in render.GRANSER:
        try:
            return float(s.replace(",", "."))
        except ValueError:
            raise SystemExit(json.dumps({"fel": f"{nyckel} ska vara ett tal, fick {s!r}"}, ensure_ascii=False))
    return s.strip()


def spara_ny_version(home: Path, gammal: dict, ny: dict, andring: str) -> dict:
    arkivera(home, gammal)
    ny["version"] = int(gammal.get("version", 1)) + 1
    ny.setdefault("historik", [])
    ny["historik"].append({"version": ny["version"], "datum": dt.date.today().isoformat(), "andring": andring})
    p, _ = sokvagar(home)
    skriv_json(p, ny)
    arkivera(home, ny)
    return ny


def jamfor(home: Path, fore: dict, efter: dict, mal: str | None) -> str | None:
    if not mal:
        return None
    cv, mapp, _ = render._las_dok(mal, "cv")
    ut = home / "design" / "fore-efter"
    kort = []
    for etikett, d in (("Före", fore), ("Efter", efter)):
        r = render.rendera("cv", cv, d, ut, [mapp, home], stam=f"{etikett.lower().replace('ö', 'o')}", bild=True)
        r["namn"] = f"{etikett}: version {d.get('version')}"
        r["bokstav"] = etikett[0]
        kort.append(r)
    andr = efter.get("historik", [{}])[-1].get("andring", "")
    return str(render.jamforelse(kort, ut, "Före och efter", andr))


def svar(design: dict, **extra) -> None:
    ut = {"version": design.get("version"), "namn": design.get("namn"), "layout": design.get("layout"),
          "tokens": design.get("tokens"), "sektioner": design.get("sektioner"),
          "varianter": design.get("varianter"), "standardvariant": design.get("standardvariant"),
          "varningar": render.granska_design(design)}
    ut.update({k: v for k, v in extra.items() if v is not None})
    print(json.dumps(ut, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kommando", choices=["visa", "init", "set", "kombinera", "layout", "sektioner", "namn",
                                         "historik", "aterstall", "frys", "variant", "varianter"])
    ap.add_argument("argument", nargs="*")
    ap.add_argument("--home")
    ap.add_argument("--forval", default="konservativ")
    ap.add_argument("--fran", help="förval eller design-fil att hämta tokens från (kombinera)")
    ap.add_argument("--tokens", help="kommaseparerade tokens att hämta (kombinera)")
    ap.add_argument("--anteckning", help="egen beskrivning av ändringen, gärna hennes ord")
    ap.add_argument("--jamfor", help="ansökningsmapp eller cv.json att rendera före/efter med")
    ap.add_argument("--skriv-over", action="store_true", help="init: ersätt befintlig design.json")
    ap.add_argument("--standard", action="store_true", help="variant: gör varianten till standardvariant")
    ap.add_argument("--ta-bort", action="store_true", help="variant: ta bort varianten")
    a = ap.parse_args(argv)
    home = render.hem(a.home)
    p, vmapp = sokvagar(home)

    if a.kommando == "init":
        if p.exists() and not a.skriv_over:
            gammal = render.las_json(p)
            raise SystemExit(json.dumps({"fel": f"design.json finns redan (version {gammal.get('version')}). "
                                                "Använd --skriv-over för att ersätta; den gamla sparas i versioner/."},
                                        ensure_ascii=False))
        ny = render.las_json(render.forval_path(a.forval))
        ny.pop("beskrivning", None)
        if p.exists():
            gammal = render.las_json(p)
            ny = spara_ny_version(home, gammal, ny, f"Ny grund från förvalet {a.forval}")
        else:
            ny["version"] = 1
            ny["historik"] = [{"version": 1, "datum": dt.date.today().isoformat(),
                               "andring": f"Skapad från förvalet {a.forval}"}]
            skriv_json(p, ny)
            arkivera(home, ny)
        svar(ny, fil=str(p))
        return 0

    design = las(home)
    gammal = copy.deepcopy(design)

    if a.kommando == "visa":
        svar(design, fil=str(p))
        return 0
    if a.kommando == "varianter":
        print(json.dumps({"standardvariant": design.get("standardvariant"), "varianter": design.get("varianter") or {}},
                         ensure_ascii=False, indent=2))
        return 0
    if a.kommando == "historik":
        versioner = sorted(x.name for x in vmapp.glob("design-v*.json")) if vmapp.exists() else []
        print(json.dumps({"version": design.get("version"), "historik": design.get("historik", []),
                          "sparade_versioner": versioner}, ensure_ascii=False, indent=2))
        return 0

    if a.kommando == "set":
        if not a.argument:
            ap.error("ange minst en token=värde")
        andr = []
        for par in a.argument:
            if "=" not in par:
                ap.error(f"'{par}' saknar '='")
            k, v = par.split("=", 1)
            k = k.strip()
            if k not in KANDA_TOKENS:
                raise SystemExit(json.dumps({"fel": f"Okänd token '{k}'.", "kanda": sorted(KANDA_TOKENS)},
                                            ensure_ascii=False))
            design.setdefault("tokens", {})[k] = tolka_varde(k, v)
            andr.append(f"{k}={design['tokens'][k]}")
        beskr = a.anteckning or "Ändrade " + ", ".join(andr)
    elif a.kommando == "kombinera":
        if not (a.fran and a.tokens):
            ap.error("kombinera kräver --fran och --tokens")
        kalla = render.las_json(render.forval_path(a.fran))
        valda = [x.strip() for x in a.tokens.split(",") if x.strip()]
        for k in valda:
            if k == "layout":
                design["layout"] = kalla.get("layout")
            elif k in kalla.get("tokens", {}):
                design.setdefault("tokens", {})[k] = kalla["tokens"][k]
            else:
                raise SystemExit(json.dumps({"fel": f"'{k}' finns inte i {a.fran}"}, ensure_ascii=False))
        beskr = a.anteckning or f"Hämtade {', '.join(valda)} från {kalla.get('namn', a.fran)}"
    elif a.kommando == "layout":
        if not a.argument or not giltig_layout(a.argument[0], home):
            ap.error(f"layout ska vara en av {', '.join(render.LAYOUTER)} eller egen:<namn> (en importerad mall)")
        design["layout"] = a.argument[0]
        if a.argument[0] == "portratt":
            design.setdefault("tokens", {})["visa_foto"] = True
        beskr = a.anteckning or f"Bytte layout till {a.argument[0]}"
    elif a.kommando == "sektioner":
        if not a.argument:
            ap.error("ange sektioner, kommaseparerade")
        lista = [x.strip() for x in ",".join(a.argument).split(",") if x.strip()]
        okanda = [x for x in lista if x not in KANDA_SEKTIONER]
        if okanda:
            raise SystemExit(json.dumps({"fel": f"Okända sektioner: {okanda}", "kanda": sorted(KANDA_SEKTIONER)},
                                        ensure_ascii=False))
        design["sektioner"] = lista
        beskr = a.anteckning or "Ny sektionsordning: " + ", ".join(lista)
    elif a.kommando == "namn":
        design["namn"] = " ".join(a.argument).strip() or design.get("namn")
        beskr = a.anteckning or f"Nytt namn: {design['namn']}"
    elif a.kommando == "aterstall":
        if not a.argument:
            ap.error("ange versionsnummer")
        vp = vmapp / f"design-v{int(a.argument[0])}.json"
        if not vp.exists():
            raise SystemExit(json.dumps({"fel": f"Version {a.argument[0]} finns inte sparad."}, ensure_ascii=False))
        aldre = render.las_json(vp)
        design = {**aldre, "historik": gammal.get("historik", [])}
        beskr = a.anteckning or f"Återställde version {a.argument[0]}"
    elif a.kommando == "variant":
        if not a.argument:
            ap.error("ange variantens namn")
        vnamn = a.argument[0].strip()
        varianter = design.setdefault("varianter", {})
        if a.ta_bort:
            varianter.pop(vnamn, None)
            if design.get("standardvariant") == vnamn:
                design.pop("standardvariant")
            beskr = a.anteckning or f"Tog bort varianten {vnamn}"
        else:
            v = varianter.setdefault(vnamn, {})
            for par in a.argument[1:]:
                if "=" not in par:
                    ap.error(f"'{par}' saknar '='")
                k, val = (x.strip() for x in par.split("=", 1))
                if k == "layout":
                    if not giltig_layout(val, home):
                        ap.error(f"okänd layout {val}")
                    v["layout"] = val
                elif k == "sektioner":
                    lista = [x.strip() for x in val.split(",") if x.strip()]
                    okanda = [x for x in lista if x not in KANDA_SEKTIONER]
                    if okanda:
                        raise SystemExit(json.dumps({"fel": f"Okända sektioner: {okanda}"}, ensure_ascii=False))
                    v["sektioner"] = lista
                elif k == "beskrivning":
                    v["beskrivning"] = val
                elif k in KANDA_TOKENS:
                    v.setdefault("token_overrides", {})[k] = tolka_varde(k, val)
                else:
                    raise SystemExit(json.dumps({"fel": f"Okänt fält '{k}' för variant."}, ensure_ascii=False))
            if a.standard:
                design["standardvariant"] = vnamn
            beskr = a.anteckning or f"Variant {vnamn}: " + (", ".join(a.argument[1:]) or "standard")
        if not varianter:
            design.pop("varianter", None)
    elif a.kommando == "frys":
        beskr = a.anteckning or "Fryst: den här versionen används för ansökningar"
    else:  # pragma: no cover
        ap.error("okänt kommando")

    ny = spara_ny_version(home, gammal, design, beskr)
    sida = jamfor(home, gammal, ny, a.jamfor)
    svar(ny, fil=str(p), andring=beskr, fore_version=gammal.get("version"), jamforelse=sida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
