#!/usr/bin/env python3
"""Gör HTML som Claude Design exporterat till en egen CV-mall (eller brevmall).

  design_import.py <exporterad.html|zip> [--namn NAMN] [--variant V] [--brev] [--sida FIL]
                   [--innehall cv.json|ansökningsmapp] [--home MAPP] [--ingen-design]

- Slot-attribut som finns kvar (data-slot, data-repeat …) behålls.
- Där de försvunnit matchas elementen mot hennes kända innehåll (namn, titlar, rubriker,
  punkter). Upprepade syskon blir en mall med data-repeat. Osäkra fynd listas i `osakert`
  så att Claude kan bekräfta med henne.
- Bilder och typsnitt kopieras till mallens assets/ (fjärrfiler hämtas bara om nätet får användas).
- Print-CSS läggs till om den saknas (@page A4, break-inside: avoid per post).
- Sparas i <home>/design/mallar/<namn>/ med versioner, och design.json.layout = "egen:<namn>"
  sätts via design_tool (med --variant: design.json.varianter[V].layout i stället).
Färger, typsnitt och storlekar som ändrats i :root-variablerna förs tillbaka till design.json.
Resultatet skrivs som JSON.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_export  # noqa: E402
import mall_slots as ms  # noqa: E402
import render  # noqa: E402

Nod = ms.Nod
TOKEN_VAR = {"--farg-text": "farg_text", "--farg-accent": "farg_accent", "--farg-dampad": "farg_dampad",
             "--font-rubrik": "font_rubrik", "--font-brod": "font_brod", "--storlek-brod": "storlek_brod_pt",
             "--storlek-namn": "storlek_namn_pt", "--storlek-rubrik": "storlek_rubrik_pt",
             "--radavstand": "radavstand", "--marginal": "marginal_mm", "--sektion-luft": "sektion_luft_mm"}
UTSKRIFT_CSS = """
/* jobbsok: utskrift (lades till vid import) */
[data-repeat="poster"], [data-repeat^="sektion:"], [data-repeat="grupper"] { break-inside: avoid; page-break-inside: avoid; }
[data-repeat="poster"][data-lang], [data-repeat^="sektion:"][data-lang] { break-inside: auto; page-break-inside: auto; }
[data-repeat="punkter"] { break-inside: avoid; }
[data-slot-rubrik] { break-after: avoid; page-break-after: avoid; }
@media print { html, body { height: auto !important; overflow: visible !important; background: #fff !important; } }
"""


def slug(s: str) -> str:
    s = s.lower().translate(str.maketrans("åäöéü", "aaoeu"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "min-mall"


def natet_ok() -> bool:
    return os.environ.get("JOBBSOK_OFFLINE") != "1"


# ---------------------------------------------------------------- hjälpare för trädet

def element(rot: Nod):
    return (x for x in rot.iter() if x.typ == "el" and x.tag not in ("#rot", "html", "head", "title", "style",
                                                                         "script", "meta", "link"))


def i_head(n: Nod) -> bool:
    p = n
    while p is not None:
        if p.tag == "head":
            return True
        p = p.foralder
    return False


def text(n: Nod) -> str:
    return ms.normtext(ms.textinnehall(n))


def forfader(n: Nod):
    p = n.foralder
    while p is not None and p.tag != "#rot":
        yield p
        p = p.foralder


def innehaller(a: Nod, b: Nod) -> bool:
    return a is b or any(p is a for p in forfader(b))


def lca(noder: list[Nod]) -> Nod | None:
    if not noder:
        return None
    kedja = [noder[0]] + list(forfader(noder[0]))
    for k in kedja:
        if all(innehaller(k, n) for n in noder):
            return k
    return None


def ordning(rot: Nod) -> dict:
    return {id(x): i for i, x in enumerate(rot.iter())}


def ta_bort(n: Nod):
    if n.foralder is not None and n in n.foralder.barn:
        n.foralder.barn.remove(n)


def ar_markt(n: Nod) -> bool:
    return any(n.har(a) for a in ms.SLOT_ATTR) or any(p.har("data-slot") for p in forfader(n))


class Hittare:
    """Hittar element vars text matchar ett känt värde."""

    def __init__(self, rot: Nod):
        self.rot = rot
        self.tagna: set = set()

    def exakt(self, varde: str, inom: Nod | None = None, alla=False) -> list[Nod]:
        v = ms.normtext(varde)
        if not v:
            return []
        ut = []
        for x in element(inom or self.rot):
            if i_head(x) or id(x) in self.tagna:
                continue
            if text(x) == v:
                # djupaste: inget barn med samma text
                if not any(b.typ == "el" and text(b) == v for b in x.barn):
                    ut.append(x)
        return ut if alla else ut[:1]

    def ungefar(self, varde: str, inom: Nod | None = None) -> list[Nod]:
        """Element vars text börjar med eller innehåller värdet (osäkert)."""
        v = ms.normtext(varde)
        if len(v) < 4:
            return []
        ut = []
        for x in element(inom or self.rot):
            if i_head(x) or id(x) in self.tagna:
                continue
            t = text(x)
            if v in t and len(t) < len(v) * 2.2 + 20 and not any(b.typ == "el" and v in text(b) for b in x.barn):
                ut.append(x)
        return ut


def objekt_behallare(behallare: Nod, ankare: list[Nod]) -> list[Nod] | None:
    """Ett element per objekt (roll, grupp …) inom behållaren, i dokumentordning.

    Går nedåt genom gemensamma omslag. Ligger objekten platt (rubrik, datum, lista som
    syskon) slås varje objekts syskon in i en <div style="display:contents">."""
    if not ankare:
        return None
    b = behallare
    while True:
        topp = []
        for a in ankare:
            t = a
            while t.foralder is not None and t.foralder is not b:
                t = t.foralder
            if t.foralder is not b:
                return None
            topp.append(t)
        unika = list(dict.fromkeys(id(t) for t in topp))
        if len(unika) == 1 and len(ankare) > 1:
            if topp[0] in ankare:
                return None
            b = topp[0]
            continue
        break
    if len(ankare) == 1:
        return [topp[0]]
    if len(unika) != len(ankare):
        return None
    # Platt? (ankaret är hela toppen och det finns syskon mellan)
    syskon = [x for x in b.barn if x.typ == "el" or (x.typ == "text" and x.text.strip())]
    idx = [syskon.index(t) for t in topp]
    platt = any(idx[i + 1] - idx[i] > 1 for i in range(len(idx) - 1)) and all(
        t is a or text(t) == text(a) for t, a in zip(topp, ankare))
    if not platt:
        return topp
    ut = []
    for i, start in enumerate(idx):
        slut = idx[i + 1] if i + 1 < len(idx) else len(syskon)
        grupp = syskon[start:slut]
        if i + 1 == len(idx):  # sista: bara syskon som liknar föregående objekts längd
            langd = idx[1] - idx[0] if len(idx) > 1 else len(grupp)
            grupp = grupp[:langd]
        omslag = Nod("el", "div", [("style", "display:contents")])
        pos = b.barn.index(grupp[0])
        for g in grupp:
            b.barn.remove(g)
            omslag.lagg_till(g)
        omslag.foralder = b
        b.barn.insert(pos, omslag)
        ut.append(omslag)
    return ut


def slå_in_efter_rubrik(rubrik: Nod, stopp: set) -> Nod:
    """Platt sektion: rubriken och syskonen fram till nästa sektionsrubrik slås in."""
    f = rubrik.foralder
    i = f.barn.index(rubrik)
    grupp = [rubrik]
    for x in f.barn[i + 1:]:
        if x.typ == "el" and (id(x) in stopp or any(id(y) in stopp for y in x.iter())):
            break
        grupp.append(x)
    omslag = Nod("el", "section", [("style", "display:contents")])
    for g in grupp:
        f.barn.remove(g)
        omslag.lagg_till(g)
    omslag.foralder = f
    f.barn.insert(i, omslag)
    return omslag


# ---------------------------------------------------------------- importen

class Import:
    def __init__(self, rot: Nod, ctx: dict, typ: str):
        self.rot = rot
        self.ctx = ctx
        self.typ = typ
        self.h = Hittare(rot)
        self.osakert: list[str] = []
        self.hittat: list[str] = []
        self.sv = 0 if ctx.get("sprak") == "sv" else 1

    def markera(self, n: Nod, attr: str, varde: str | None, beskr: str):
        n.satt(attr, varde)
        self.h.tagna.add(id(n))
        self.hittat.append(beskr)

    def finns(self, attr: str, varde: str | None = None) -> list[Nod]:
        return [x for x in self.rot.iter() if x.typ == "el" and x.har(attr) and (varde is None or x.get(attr) == varde)]

    # --- befintliga attribut: rensa upprepade exemplar
    def rensa_upprepningar(self):
        for x in self.rot.iter():
            if x.typ == "el":
                x.ta_bort_attr("data-lang")
        for x in list(self.rot.iter()):
            if x.typ == "el" and x.har("data-repeat") and x.foralder is not None and x in x.foralder.barn:
                syskon = x.foralder.barn
                i = syskon.index(x)
                for y in list(syskon[i + 1:]):
                    if y.typ == "el" and y.get("data-repeat") == x.get("data-repeat"):
                        ta_bort(y)
                    elif y.typ == "el":
                        # display:contents-omslag från en tidigare import
                        continue

    # --- person
    def person(self):
        p = self.ctx["person"]
        titel_el = next((x for x in self.rot.iter() if x.typ == "el" and x.tag == "title"), None)
        if titel_el is not None and not titel_el.har("data-slot"):
            titel_el.satt("data-slot", "titel")
        for falt in ("namn", "titel"):
            if self.finns("data-slot", f"person.{falt}") or not p.get(falt):
                continue
            kand = self.h.exakt(p[falt], alla=True)
            if self.typ == "brev" and falt == "namn" and len(kand) > 1:
                self.markera(kand[0], "data-slot", "person.namn", "namnet i brevhuvudet")
                self.markera(kand[-1], "data-slot", "person.namn", "namnet under hälsningen")
                continue
            if kand:
                self.markera(kand[0], "data-slot", f"person.{falt}", f"{'namnet' if falt == 'namn' else 'yrkestiteln'}")
            else:
                u = self.h.ungefar(p[falt])
                if u:
                    self.markera(u[0], "data-slot", f"person.{falt}", f"person.{falt} (ungefärlig)")
                    self.osakert.append(f"{'Namnet' if falt == 'namn' else 'Yrkestiteln'} hittades bara ungefär: "
                                        f"\"{ms.textinnehall(u[0]).strip()[:60]}\". Stämmer det?")
                else:
                    self.osakert.append(f"Hittade inte {'namnet' if falt == 'namn' else 'yrkestiteln'} i designen.")
        if not self.finns("data-repeat", "person.kontakt") and not any(
                x.get("data-slot", "").startswith("person.") and x.get("data-slot") not in ("person.namn", "person.titel", "person.foto")
                for x in self.finns("data-slot")):
            self.kontakt(p.get("kontakt") or [])
        self.foto()

    def kontakt(self, kontakt: list):
        traff = []
        for k in kontakt:
            e = self.h.exakt(k["text"]) or self.h.ungefar(k["text"])
            if e:
                traff.append((k, e[0]))
        if not traff:
            if kontakt:
                self.osakert.append("Hittade inte kontaktuppgifterna (e-post, telefon). De läggs inte in automatiskt.")
            return
        if len(traff) >= 2:
            beh = lca([e for _, e in traff])
            obj = objekt_behallare(beh, [e for _, e in traff]) if beh is not None else None
            if obj:
                forsta = obj[0]
                self.markera(forsta, "data-repeat", "person.kontakt", "kontaktraden (upprepas per uppgift)")
                inre = traff[0][1]
                k0 = traff[0][0]
                if k0.get("etikett"):
                    for x in forsta.iter():
                        if x.typ == "el" and text(x) == ms.normtext(k0["etikett"]) and x is not forsta:
                            x.satt("data-slot", "etikett")
                textel = inre if inre is not forsta or not any(b.har("data-slot") for b in forsta.iter()) else inre
                if textel is forsta:
                    textel.satt("data-slot", "text")
                else:
                    textel.satt("data-slot", "text")
                if textel.tag != "a" and forsta.tag != "a":
                    pass
                elif forsta.tag == "a" and textel is not forsta:
                    forsta.satt("data-href", "url")
                for o in obj[1:]:
                    ta_bort(o)
                if len(traff) < len(kontakt):
                    self.osakert.append(f"Kontaktraden: hittade {len(traff)} av {len(kontakt)} uppgifter; "
                                        "alla visas ändå i den form som hittades.")
                return
        namn = {"mailto:": "person.epost", "tel:": "person.telefon"}
        for k, e in traff:
            slot = next((v for p, v in namn.items() if (k.get("url") or "").startswith(p)), None)
            if slot:
                self.markera(e, "data-slot", slot, slot)
            else:
                self.osakert.append(f"Kontaktuppgiften \"{k['text']}\" står ensam; den blir fast text i mallen.")

    def foto(self):
        if self.finns("data-slot", "person.foto"):
            return
        for x in self.rot.iter():
            if x.typ == "el" and x.tag == "img":
                tecken = " ".join([x.get("alt", ""), x.get("class", ""), x.get("src", "")[:80], x.get("id", "")]).lower()
                if re.search(r"foto|photo|portr|avatar|profil|headshot", tecken) or (
                        self.ctx["person"].get("foto") and x.get("src", "").startswith("data:image")):
                    x.satt("data-slot", "person.foto")
                    x.satt("data-if", "person.foto")
                    self.hittat.append("fotot")
                    return

    # --- sektioner
    def rubrik_varden(self, s: dict) -> list[str]:
        v = [s["rubrik"]]
        k = s["nyckel"]
        if k in render.RUBRIKER:
            v += list(render.RUBRIKER[k])
        v += [a for a, n in render.ALIAS.items() if n == k]
        return list(dict.fromkeys(v))

    def sektioner(self):
        alla = self.ctx.get("sektioner") or []
        befintliga = {x.get("data-sektion") for x in self.finns("data-sektion")}
        generisk = self.finns("data-repeat", "sektioner")
        rubriker = {}
        for s in alla:
            if s["nyckel"] in befintliga or s["nyckel"] in rubriker:
                continue
            for v in self.rubrik_varden(s):
                e = self.h.exakt(v)
                if e and not any(innehaller(g, e[0]) for g in generisk):
                    rubriker[s["nyckel"]] = (s, e[0])
                    self.h.tagna.add(id(e[0]))
                    break
        stopp = {id(e) for _, e in rubriker.values()} | {id(x) for x in self.finns("data-sektion")}
        for nyckel, (s, rub) in rubriker.items():
            beh = rub
            for p in forfader(rub):
                andra = [e for k, (_, e) in rubriker.items() if k != nyckel]
                if any(innehaller(p, e) for e in andra) or p.tag in ("body", "main") or any(
                        innehaller(p, x) for x in self.finns("data-sektion")):
                    break
                beh = p
            if beh is rub:
                beh = slå_in_efter_rubrik(rub, stopp - {id(rub)})
            self.markera(beh, "data-sektion", nyckel, f"sektionen {s['rubrik']}")
            rub.satt("data-slot-rubrik", None)
        for beh in self.finns("data-sektion"):
            s = next((x for x in alla if x["nyckel"] == beh.get("data-sektion")), None)
            if s:
                self.sektion_innehall(beh, s)
        for s in alla:
            if s["nyckel"] not in {x.get("data-sektion") for x in self.finns("data-sektion")} and not generisk:
                self.osakert.append(f"Sektionen \"{s['rubrik']}\" hittades inte; den visas sist i en enkel standardform.")

    def sektion_innehall(self, beh: Nod, s: dict):
        if not any(x.har("data-slot-rubrik") for x in beh.iter()):
            for v in self.rubrik_varden(s):
                e = self.h.exakt(v, beh)
                if e:
                    e[0].satt("data-slot-rubrik", None)
                    break
        mallpost = next((x for x in beh.iter() if x.typ == "el" and x.get("data-repeat") in ("poster", f"sektion:{s['nyckel']}")), None)
        if s["ar_poster"] and mallpost is None:
            self.poster(beh, s)
        elif s["ar_poster"]:
            self.post_falt(mallpost, s["poster"][0], s)
        if s["ar_lista"] and not any(x.get("data-repeat") == "grupper" for x in beh.iter()):
            self.grupper(beh, s)
        if s["ar_text"] and not any(x.get("data-repeat") == "stycken" or x.get("data-slot") == "profil"
                                    for x in beh.iter()):
            self.stycken(beh, s)

    def poster(self, beh: Nod, s: dict):
        ankare, faltlista = [], []
        for p in s["poster"]:
            t = self.h.exakt(p["titel"], beh) or self.h.ungefar(p["titel"], beh)
            if t:
                ankare.append(t[0])
                faltlista.append(p)
        if not ankare:
            self.osakert.append(f"Hittade inga roller i \"{s['rubrik']}\".")
            return
        obj = objekt_behallare(beh, ankare)
        if not obj:
            self.osakert.append(f"Rollerna i \"{s['rubrik']}\" gick inte att skilja åt; kontrollera den sektionen.")
            return
        forsta, p = obj[0], faltlista[0]
        self.markera(forsta, "data-repeat", "poster", f"rollerna i {s['rubrik']} (upprepas)")
        if not text(ankare[0]) == ms.normtext(p["titel"]):
            self.osakert.append(f"Rolltiteln i \"{s['rubrik']}\" står ihop med annan text: "
                                f"\"{ms.textinnehall(ankare[0]).strip()[:70]}\".")
        ankare[0].satt("data-slot", "titel")
        self.post_falt(forsta, p, s)
        for o in obj[1:]:
            ta_bort(o)

    def post_falt(self, forsta: Nod, p: dict, s: dict):
        """Platser för en rolls delar (period, plats, punkter …) inom rollens mall."""
        if not any(x.get("data-slot") == "titel" for x in forsta.iter()):
            e = self.h.exakt(p["titel"], forsta)
            if e:
                self.markera(e[0], "data-slot", "titel", f"titel i {s['rubrik']}")
        for falt in ("period", "plats", "organisation", "ort", "text"):
            if p.get(falt) and not any(x.get("data-slot") == falt for x in forsta.iter()):
                if falt in ("organisation", "ort") and any(x.get("data-slot") == "plats" for x in forsta.iter()):
                    continue
                e = self.h.exakt(p[falt], forsta)
                if e:
                    self.markera(e[0], "data-slot", falt, f"{falt} i {s['rubrik']}")
                elif falt in ("period", "plats"):
                    self.osakert.append(f"Hittade inte {'perioden' if falt == 'period' else 'arbetsgivare/ort'} "
                                        f"för rollerna i \"{s['rubrik']}\".")
        if p["punkter"] and not any(x.get("data-repeat") == "punkter" for x in forsta.iter()):
            pa = [e[0] for x in p["punkter"] if (e := self.h.exakt(x, forsta) or self.h.ungefar(x, forsta))]
            if pa:
                pbeh = lca(pa) if len(pa) > 1 else pa[0].foralder
                po = objekt_behallare(pbeh, pa) if pbeh is not None else None
                if po:
                    self.markera(po[0], "data-repeat", "punkter", f"punkterna i {s['rubrik']}")
                    for o in po[1:]:
                        ta_bort(o)
                    if len(pa) < len(p["punkter"]):
                        self.osakert.append(f"Bara {len(pa)} av {len(p['punkter'])} punkter hittades i första rollen "
                                            f"i \"{s['rubrik']}\"; alla visas ändå.")
            else:
                self.osakert.append(f"Hittade inte punkterna i \"{s['rubrik']}\".")

    def grupper(self, beh: Nod, s: dict):
        ankare, gl = [], []
        for g in s["grupper"]:
            e = (self.h.exakt(g["etikett"], beh) if g["etikett"] else []) or self.h.exakt(g["rad"], beh) or (
                self.h.exakt(g["poster"][0], beh) if g["poster"] else [])
            if e:
                ankare.append(e[0])
                gl.append(g)
        if not ankare:
            self.osakert.append(f"Hittade inte innehållet i \"{s['rubrik']}\".")
            return
        if len(ankare) == 1:
            g = gl[0]
            delar = (self.h.exakt(g["etikett"], beh) if g["etikett"] else []) + self.h.exakt(g["rad"], beh)
            for x in g["poster"]:
                delar += self.h.exakt(x, beh)
            forsta = lca(delar) if len(delar) > 1 else delar[0]
            rubrik = next((x for x in beh.iter() if x.typ == "el" and x.har("data-slot-rubrik")), None)
            if forsta is beh or (rubrik is not None and innehaller(forsta, rubrik)):
                forsta = objekt_behallare(beh, [delar[0]])[0]
            while forsta.foralder is not None and forsta.foralder is not beh and text(forsta.foralder) == text(forsta):
                forsta = forsta.foralder
            obj = [forsta]
        else:
            obj = objekt_behallare(beh, ankare)
            if not obj:
                self.osakert.append(f"Grupperna i \"{s['rubrik']}\" gick inte att skilja åt.")
                return
        forsta, g = obj[0], gl[0]
        self.markera(forsta, "data-repeat", "grupper", f"listan i {s['rubrik']}")
        if g["etikett"]:
            e = self.h.exakt(g["etikett"], forsta)
            if e:
                e[0].satt("data-slot", "etikett")
        rad = self.h.exakt(g["rad"], forsta)
        if not rad and text(forsta) == ms.normtext(g["rad"]):
            rad = [forsta]
        if rad:
            rad[0].satt("data-slot", "rad")
        else:
            pe = [e[0] for x in g["poster"] if (e := self.h.exakt(x, forsta))]
            if pe:
                pbeh = lca(pe) if len(pe) > 1 else pe[0].foralder
                po = objekt_behallare(pbeh, pe)
                if po:
                    po[0].satt("data-repeat", "poster")
                    for o in po[1:]:
                        ta_bort(o)
            elif g["etikett"] and self._dela_rad(forsta, g):
                pass
            else:
                self.osakert.append(f"Listan i \"{s['rubrik']}\" har en form som inte gick att tolka säkert.")
        for o in obj[1:]:
            ta_bort(o)

    def _dela_rad(self, el: Nod, g: dict) -> bool:
        """'<b>Verktyg</b> a · b' : lös text efter etiketten blir <span data-slot="rad">."""
        lösa = [b for b in el.barn if b.typ == "text" and b.text.strip()]
        if len(lösa) == 1 and ms.normtext(g["rad"]) in ms.normtext(lösa[0].text):
            span = Nod("el", "span", [("data-slot", "rad")])
            i = el.barn.index(lösa[0])
            el.barn[i] = span
            span.foralder = el
            span.lagg_till(Nod("text", text=lösa[0].text))
            return True
        return False

    def stycken(self, beh: Nod, s: dict):
        pa = [e[0] for x in s["stycken"] if (e := self.h.exakt(x, beh) or self.h.ungefar(x, beh))]
        if not pa:
            self.osakert.append(f"Hittade inte texten i \"{s['rubrik']}\".")
            return
        if len(pa) == 1:
            self.markera(pa[0], "data-repeat", "stycken", f"texten i {s['rubrik']}")
            return
        po = objekt_behallare(lca(pa), pa)
        if po:
            self.markera(po[0], "data-repeat", "stycken", f"texten i {s['rubrik']}")
            for o in po[1:]:
                ta_bort(o)

    def generisk_sektion(self):
        if self.finns("data-repeat", "sektioner"):
            return
        mallar = [x for x in self.finns("data-sektion") if any(y.get("data-repeat") == "poster" for y in x.iter())]
        if not mallar:
            return
        kalla = next((x for x in mallar if x.get("data-sektion") == "erfarenhet"), mallar[0])
        kopia = copy.deepcopy(kalla)
        kopia.ta_bort_attr("data-sektion")
        kopia.satt("data-repeat", "sektioner")
        grupp = next((y for x in self.finns("data-sektion") for y in x.iter() if y.get("data-repeat") == "grupper"), None)
        stycke = next((y for x in self.finns("data-sektion") for y in x.iter() if y.get("data-repeat") == "stycken"), None)
        for extra in (grupp, stycke):
            if extra is not None:
                kopia.lagg_till(copy.deepcopy(extra))
        sista = self.finns("data-sektion")[-1]
        f = sista.foralder
        kopia.foralder = f
        f.barn.insert(f.barn.index(sista) + 1, kopia)
        self.hittat.append("allmän sektion för övriga delar (kurser, ideellt …)")

    # --- brev
    def brev(self):
        c = self.ctx
        for falt, slot in (("rubrik", "rubrik"), ("datum", "datum"), ("halsning", "halsning")):
            if c.get(falt) and not self.finns("data-slot", slot):
                e = self.h.exakt(c[falt]) or self.h.ungefar(c[falt])
                if e:
                    self.markera(e[0], "data-slot", slot, slot)
                else:
                    self.osakert.append(f"Hittade inte {falt} i brevet.")
        m = c.get("mottagare") or {}
        for falt in ("bolag", "namn"):
            if m.get(falt) and not self.finns("data-slot", f"mottagare.{falt}"):
                e = self.h.exakt(m[falt])
                if e:
                    self.markera(e[0], "data-slot", f"mottagare.{falt}", f"mottagare.{falt}")
        if m.get("adress_rader") and not self.finns("data-repeat", "mottagare.adress_rader"):
            pa = [e[0] for r in m["adress_rader"] if (e := self.h.exakt(r))]
            if pa:
                po = objekt_behallare(lca(pa), pa) if len(pa) > 1 else pa
                if po:
                    self.markera(po[0], "data-repeat", "mottagare.adress_rader", "adressen")
                    for o in po[1:]:
                        ta_bort(o)
        if not self.finns("data-repeat", "stycken"):
            pa = [e[0] for x in c.get("stycken") or [] if (e := self.h.exakt(x) or self.h.ungefar(x))]
            if pa:
                po = objekt_behallare(lca(pa), pa) if len(pa) > 1 else pa
                if po:
                    self.markera(po[0], "data-repeat", "stycken", "brevets stycken")
                    for o in po[1:]:
                        ta_bort(o)
            else:
                self.osakert.append("Hittade inte brevets stycken.")


# ---------------------------------------------------------------- CSS och resurser

def las_kalla(arg: Path, sida: str | None) -> tuple[str, Path, list[str]]:
    """Returnerar (html, basmapp för relativa filer, övriga sidor i paketet)."""
    if arg.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="cd-import-"))
        with zipfile.ZipFile(arg) as z:
            for m in z.namelist():
                mal = (tmp / m).resolve()
                if str(mal).startswith(str(tmp.resolve())):
                    z.extract(m, tmp)
        sidor = [p for p in tmp.rglob("*.html") if "komponenter" not in p.parts and "__MACOSX" not in p.parts]
        if sida:
            vald = next((p for p in sidor if p.name == sida or str(p.relative_to(tmp)) == sida), None)
            if not vald:
                raise SystemExit(json.dumps({"fel": f"Sidan {sida} finns inte i zip-filen.",
                                             "sidor": [p.name for p in sidor]}, ensure_ascii=False))
        else:
            sidor.sort(key=lambda p: (not re.search(r"cv|resume|index", p.name, re.I), "brev" in p.name, -p.stat().st_size))
            if not sidor:
                raise SystemExit(json.dumps({"fel": "Zip-filen innehåller ingen HTML-sida."}, ensure_ascii=False))
            vald = sidor[0]
        return vald.read_text("utf-8", "replace"), vald.parent, [p.name for p in sidor if p != vald]
    return arg.read_text("utf-8", "replace"), arg.parent, []


def hamta(url: str) -> bytes | None:
    if not natet_ok():
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 jobbsok"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read(10_000_000)
    except Exception:
        return None


class Resurser:
    def __init__(self, kalla: Path, assets: Path):
        self.kalla = kalla
        self.assets = assets
        self.varningar: list[str] = []
        self.kopierade: list[str] = []

    def spara(self, ref: str, bas_url: str | None = None) -> str | None:
        ref = ref.strip().strip("'\"")
        if not ref or ref.startswith(("data:", "#")):
            return None
        if bas_url and not re.match(r"^https?:", ref):
            ref = urllib.parse.urljoin(bas_url, ref)
        namn = re.sub(r"[^\w.-]", "_", Path(urllib.parse.urlparse(ref).path).name or "fil")[:80]
        if re.match(r"^https?:", ref):
            data = hamta(ref)
            if data is None:
                self.varningar.append(f"Kunde inte hämta {ref[:90]} (inget nät); systemtypsnitt/inget används.")
                return None
        else:
            p = (self.kalla / urllib.parse.unquote(ref)).resolve()
            if not p.exists() or not p.is_file():
                self.varningar.append(f"Filen {ref} saknas i exporten.")
                return None
            data = p.read_bytes()
        self.assets.mkdir(parents=True, exist_ok=True)
        (self.assets / namn).write_bytes(data)
        self.kopierade.append(namn)
        return f"assets/{namn}"

    def css(self, css: str, bas_url: str | None = None) -> str:
        def imp(m):
            url = m.group(2) or m.group(3)
            if re.match(r"^https?:", url or "") and natet_ok():
                data = hamta(url)
                if data:
                    return self.css(data.decode("utf-8", "replace"), url)
            self.varningar.append(f"@import av {url[:90]} togs bort (inget nät eller fjärrfil).")
            return ""
        css = re.sub(r"@import\s+(url\()?['\"]?([^'\")]+)?['\"]?\)?([^;]*);", lambda m: imp(m), css)

        def url(m):
            ny = self.spara(m.group(2), bas_url)
            return f"url({ny})" if ny else m.group(0)
        return re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", url, css)


def plocka_tokens(css: str) -> tuple[str, dict]:
    """Läs :root-variabler som motsvarar tokens och ta bort dem ur CSS:en."""
    funna: dict = {}

    def rot(m):
        kropp = m.group(1)
        rest = []
        for dekl in kropp.split(";"):
            if ":" not in dekl:
                continue
            k, v = dekl.split(":", 1)
            k, v = k.strip(), v.strip()
            if k in TOKEN_VAR:
                funna[TOKEN_VAR[k]] = v
            elif k:
                rest.append(f"{k}:{v}")
        return f":root{{{';'.join(rest)}}}" if rest else ""
    css = re.sub(r":root\s*\{([^}]*)\}", rot, css)
    # inbyggda typsnitt läggs till av renderingen; ta bort dubbletter
    css = re.sub(r"@font-face\s*\{[^}]*(?:fonts/|data:font/ttf)[^}]*\}", "", css)
    # @page som tokens.css skrev (kompakt form) tas bort; renderingen skriver den från tokens
    css = re.sub(r"@page\{size:A4;margin:[\d.]+mm [\d.]+mm [\d.]+mm [\d.]+mm\}", "", css)
    tokens = {}
    for k, v in funna.items():
        if k.startswith("farg_") and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            tokens[k] = v.lower()
        elif k.startswith("font_"):
            namn = v.split(",")[0].strip().strip("'\"")
            if namn in render.TYPSNITT:
                tokens[k] = namn
        elif k == "radavstand":
            try:
                tokens[k] = float(v)
            except ValueError:
                pass
        else:
            m = re.fullmatch(r"([\d.]+)\s*(pt|mm)", v)
            if m:
                tokens[k] = float(m.group(1))
    return css, tokens


def utskrift(css: str) -> tuple[str, list[str]]:
    andrat = []
    if "@page" not in css:
        css += "\n@page { size: A4; margin: 15mm 18mm 18mm 18mm; }\n"
        andrat.append("lade till A4-sidformat (@page)")
    elif re.search(r"@page[^{]*\{[^}]*size\s*:\s*(letter|legal)", css, re.I):
        css = re.sub(r"(size\s*:\s*)(letter|legal)", r"\1A4", css, flags=re.I)
        andrat.append("bytte pappersformat till A4")
    if "jobbsok: utskrift" not in css:
        css += UTSKRIFT_CSS
        andrat.append("lade till att roller och grupper hålls ihop vid sidbrytning")
    return css, andrat


# ---------------------------------------------------------------- spara och versionera

def spara_mall(mapp: Path, filnamn: str, html_text: str, css: str, meta: dict) -> int:
    mapp.mkdir(parents=True, exist_ok=True)
    mp = mapp / "mall.json"
    gammal = json.loads(mp.read_text("utf-8")) if mp.exists() else {}
    version = int(gammal.get("version", 0)) + 1
    if (mapp / filnamn).exists():
        v = mapp / "versioner" / f"v{gammal.get('version', version - 1)}"
        v.mkdir(parents=True, exist_ok=True)
        for f in ("mall.html", "brev.html", "mall.css", "mall.json"):
            if (mapp / f).exists():
                shutil.copy(mapp / f, v / f)
    (mapp / filnamn).write_text(html_text, "utf-8")
    if filnamn == "mall.html" or not (mapp / "mall.css").exists():
        (mapp / "mall.css").write_text(css, "utf-8")
    elif css.strip():
        bef = (mapp / "mall.css").read_text("utf-8")
        if css not in bef:
            (mapp / "mall.css").write_text(bef + "\n/* brev */\n" + css, "utf-8")
    hist = gammal.get("historik", [])
    hist.append({"version": version, "datum": dt.date.today().isoformat(), "fil": filnamn,
                 "kalla": meta.get("kalla")})
    ny = {**gammal, **meta, "version": version, "historik": hist}
    mp.write_text(json.dumps(ny, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (mapp / "versioner" / f"v{version}").mkdir(parents=True, exist_ok=True)
    for f in ("mall.html", "brev.html", "mall.css"):
        if (mapp / f).exists():
            shutil.copy(mapp / f, mapp / "versioner" / f"v{version}" / f)
    return version


def kor_design_tool(args: list[str]) -> dict:
    import design_tool
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            design_tool.main(args)
        except SystemExit as e:
            return {"fel": str(e.code)}
    try:
        return json.loads(buf.getvalue())
    except ValueError:
        return {"utdata": buf.getvalue()[:300]}


def importera(fil: Path, home: Path, namn: str | None = None, variant: str | None = None, brev: bool = False,
              sida: str | None = None, innehall: str | None = None, uppdatera_design: bool = True) -> dict:
    html_text, kalla, andra_sidor = las_kalla(fil, sida)
    cv, mapp, ar_exempel = design_export.hitta_innehall(innehall, home)
    typ = "brev" if brev or re.search(r"brev|letter", fil.name if fil.suffix != ".zip" else (sida or ""), re.I) else "cv"
    dok = design_export.hitta_brev(mapp, cv) if typ == "brev" else cv
    design = render.las_json(render.hitta_design(None, home))
    ctx, _ = render.bygg_kontext(dok, dict(design, layout="klassisk", varianter={}), [mapp, home, render.FIXTURER], typ)
    namn = slug(namn or (variant and f"{variant}") or fil.stem.replace("cv-exempel", "min-mall"))
    mallmapp = home / "design" / "mallar" / namn

    rot = ms.parsa(html_text)
    for x in list(rot.iter()):
        if x.typ == "el" and (x.tag in ("script", "noscript", "iframe", "object", "embed") or
                              (x.tag == "link" and "stylesheet" not in (x.get("rel") or "") and x.get("rel") != "icon")):
            ta_bort(x)
        elif x.typ == "el":
            for a, _ in list(x.attrs):
                if a.lower().startswith("on"):
                    x.ta_bort_attr(a)
    res = Resurser(kalla, mallmapp / "assets")
    css_delar = []
    for x in list(rot.iter()):
        if x.typ == "el" and x.tag == "style":
            css_delar.append("".join(b.text for b in x.barn if b.typ == "text"))
            ta_bort(x)
        elif x.typ == "el" and x.tag == "link" and "stylesheet" in (x.get("rel") or ""):
            href = x.get("href") or ""
            if re.match(r"^https?:", href):
                data = hamta(href)
                if data:
                    css_delar.append(res.css(data.decode("utf-8", "replace"), href))
                else:
                    res.varningar.append(f"Stilmallen {href[:90]} kunde inte hämtas; typsnitt därifrån ersätts med systemtypsnitt.")
            elif (kalla / href).exists():
                css_delar.append((kalla / href).read_text("utf-8", "replace"))
            ta_bort(x)
    css, nya_tokens = plocka_tokens("\n".join(css_delar))
    css = res.css(css)
    css, utskrift_andr = utskrift(css)
    for x in rot.iter():
        if x.typ == "el" and x.tag == "img" and x.get("src") and not x.get("src", "").startswith("data:"):
            ny = res.spara(x.get("src"))
            if ny:
                x.satt("src", ny)
            elif not x.har("data-slot"):
                res.varningar.append(f"Bilden {x.get('src')[:60]} togs bort.")
                ta_bort(x)

    imp = Import(rot, ctx, typ)
    fore = ms.slots_i(ms.serialisera(rot))
    imp.rensa_upprepningar()
    imp.person()
    if typ == "cv":
        imp.sektioner()
        imp.generisk_sektion()
    else:
        imp.brev()
    # länk till stilen
    head = next((x for x in rot.iter() if x.typ == "el" and x.tag == "head"), None)
    if head is not None:
        head.lagg_till(Nod("el", "link", [("rel", "stylesheet"), ("href", "mall.css")]))
    ut_html = ms.serialisera(rot)
    efter = ms.slots_i(ut_html)
    sektionsordning = [x.get("data-sektion") for x in ms.parsa(ut_html).iter()
                       if x.typ == "el" and x.har("data-sektion")]
    filnamn = "brev.html" if typ == "brev" else "mall.html"
    if typ == "brev" and not (mallmapp / "mall.html").exists():
        imp.osakert.append("Brevmallen sparades, men det finns ingen CV-mall med samma namn än.")
    version = spara_mall(mallmapp, filnamn, ut_html, css, {
        "namn": namn, "kalla": str(fil), "importerad": dt.date.today().isoformat(),
        "osakert": imp.osakert, "slots": efter})
    resultat = {
        "mall": str(mallmapp), "fil": str(mallmapp / filnamn), "namn": namn, "typ": typ, "version": version,
        "slots_fore": {k: len(v) if isinstance(v, list) else v for k, v in fore.items()},
        "slots_efter": {k: len(v) if isinstance(v, list) else v for k, v in efter.items()},
        "hittat": imp.hittat, "osakert": imp.osakert, "resurser": res.kopierade,
        "varningar": res.varningar, "utskrift": utskrift_andr, "tokens_fran_design": {k: v for k, v in nya_tokens.items() if (design.get("tokens") or {}).get(k) != v},
        "sektionsordning": sektionsordning, "andra_sidor": andra_sidor, "exempelinnehall": ar_exempel,
    }
    if uppdatera_design and typ == "cv":
        h = ["--home", str(home)]
        if not (home / "design" / "design.json").exists():
            kor_design_tool(["init", "--forval", "konservativ", *h])
        steg = []
        tokens = {k: v for k, v in nya_tokens.items() if (design.get("tokens") or {}).get(k) != v}
        ordning_ny = [k for k in dict.fromkeys(sektionsordning) if k in render.RUBRIKER]
        if variant:
            arg = ["variant", variant, f"layout=egen:{namn}"]
            if tokens:
                arg += [f"{k}={v}" for k, v in tokens.items()]
            if ordning_ny:
                arg.append("sektioner=" + ",".join(ordning_ny + [k for k in render.STANDARD_SEKTIONER
                                                                 if k not in ordning_ny]))
            steg.append(kor_design_tool([*arg, "--anteckning", f"Variant {variant} från Claude Design", *h]))
        else:
            if tokens:
                steg.append(kor_design_tool(["set", *[f"{k}={v}" for k, v in tokens.items()],
                                             "--anteckning", "Färger och typsnitt från Claude Design", *h]))
            if ordning_ny:
                rest = [k for k in (design.get("sektioner") or render.STANDARD_SEKTIONER) if k not in ordning_ny]
                steg.append(kor_design_tool(["sektioner", ",".join(ordning_ny + rest), *h]))
            steg.append(kor_design_tool(["layout", f"egen:{namn}", "--anteckning",
                                         f"Egen mall från Claude Design ({namn}, version {version})", *h]))
        resultat["design"] = [s.get("andring") or s.get("fel") for s in steg]
    return resultat


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fil", help="exporterad HTML eller zip från Claude Design")
    ap.add_argument("--namn", help="mallens namn (standard: filnamnet)")
    ap.add_argument("--variant", help="spara som variant i design.json (t.ex. stram, standard, kreativ)")
    ap.add_argument("--brev", action="store_true", help="filen är en brevmall")
    ap.add_argument("--sida", help="vilken HTML-sida i zip-filen")
    ap.add_argument("--innehall", help="cv.json eller ansökningsmapp att matcha mot")
    ap.add_argument("--ingen-design", action="store_true", help="rör inte design.json")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    fil = Path(a.fil).expanduser()
    if not fil.exists():
        raise SystemExit(json.dumps({"fel": f"Hittar inte {fil}"}, ensure_ascii=False))
    res = importera(fil, render.hem(a.home), a.namn, a.variant, a.brev, a.sida, a.innehall, not a.ingen_design)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
