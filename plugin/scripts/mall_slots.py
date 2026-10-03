#!/usr/bin/env python3
"""Slot-mallar: HTML med data-attribut som fylls med cv.json/brev.json.

Används för egna mallar (design.json.layout = "egen:<namn>"), som hon gör i Claude
Design. Vokabulären står i skills/cv-design/references/slots.md. Kort:

  data-slot="person.namn"          elementets text blir värdet (img: src)
  data-slot-rubrik                 sektionsrubrik (sv/en efter cv.json.sprak)
  data-sektion="erfarenhet"        sektionsbehållare; tas bort om sektionen saknas
  data-repeat="poster"             upprepas per post i närmaste sektion
  data-repeat="sektion:erfarenhet" upprepas per post i den sektionen, var som helst
  data-repeat="punkter|grupper|stycken|person.kontakt|mottagare.adress_rader"
  data-repeat="sektioner"          allmän sektion: alla sektioner som inte har en egen plats
  data-if="person.foto"            tas bort om värdet saknas ("not x" går också)

Sektioner med samma förälder ordnas efter design.json.sektioner. Sektioner som inte
får plats någonstans läggs sist i en enkel standardform, så att inget tappas.
Escaping som render.py: html.escape(quote=True) på allt innehåll.
Bara stdlib.
"""
from __future__ import annotations

import base64
import copy
import html
import mimetypes
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402

TOMMA = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
RAA = {"style", "script"}
SLOT_ATTR = ("data-slot", "data-slot-rubrik", "data-sektion", "data-repeat", "data-if", "data-href")

# ---------------------------------------------------------------- DOM


class Nod:
    __slots__ = ("tag", "attrs", "barn", "foralder", "text", "typ", "meta")

    def __init__(self, typ, tag=None, attrs=None, text=None):
        self.typ = typ          # "el", "text", "kommentar", "raa" (doctype/pi)
        self.tag = tag
        self.attrs = list(attrs or [])
        self.barn: list[Nod] = []
        self.foralder: Nod | None = None
        self.text = text
        self.meta: dict = {}

    # attribut
    def get(self, k, d=None):
        for a, v in self.attrs:
            if a == k:
                return "" if v is None else v
        return d

    def har(self, k):
        return any(a == k for a, _ in self.attrs)

    def satt(self, k, v):
        for i, (a, _) in enumerate(self.attrs):
            if a == k:
                self.attrs[i] = (k, v)
                return
        self.attrs.append((k, v))

    def ta_bort_attr(self, k):
        self.attrs = [(a, v) for a, v in self.attrs if a != k]

    def lagg_till(self, n: "Nod"):
        n.foralder = self
        self.barn.append(n)
        return n

    def element(self):
        return [b for b in self.barn if b.typ == "el"]

    def iter(self):
        yield self
        for b in self.barn:
            yield from b.iter()

    def klasser(self):
        return (self.get("class") or "").split()


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rot = Nod("el", "#rot")
        self.stack = [self.rot]

    def handle_starttag(self, tag, attrs):
        n = Nod("el", tag, attrs)
        # Enkla implicita stängningar
        if tag in ("li", "p", "dt", "dd", "tr", "td", "th", "option"):
            topp = self.stack[-1]
            if topp.tag == tag or (tag in ("dt", "dd") and topp.tag in ("dt", "dd")):
                self.stack.pop()
        self.stack[-1].lagg_till(n)
        if tag not in TOMMA:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].lagg_till(Nod("el", tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].lagg_till(Nod("text", text=data))

    def handle_comment(self, data):
        self.stack[-1].lagg_till(Nod("kommentar", text=data))

    def handle_decl(self, decl):
        self.stack[-1].lagg_till(Nod("raa", text=f"<!{decl}>"))

    def handle_pi(self, data):
        pass


def parsa(text: str) -> Nod:
    p = _Parser()
    p.feed(text)
    p.close()
    return p.rot


def serialisera(n: Nod) -> str:
    ut: list[str] = []
    _ser(n, ut, False)
    return "".join(ut)


def _ser(n: Nod, ut: list, raa: bool):
    if n.typ == "text":
        ut.append(n.text if raa else html.escape(n.text, quote=True))
    elif n.typ == "kommentar":
        ut.append(f"<!--{n.text}-->")
    elif n.typ == "raa":
        ut.append(n.text)
    else:
        if n.tag != "#rot":
            a = "".join(f" {k}" if v is None else f' {k}="{html.escape(v, quote=True)}"' for k, v in n.attrs)
            ut.append(f"<{n.tag}{a}>")
            if n.tag in TOMMA:
                return
        for b in n.barn:
            _ser(b, ut, n.tag in RAA)
        if n.tag != "#rot":
            ut.append(f"</{n.tag}>")


def textinnehall(n: Nod) -> str:
    if n.typ == "text":
        return n.text
    if n.typ != "el" or n.tag in RAA:
        return ""
    sep = " " if n.tag in ("br",) else ""
    return sep + "".join(textinnehall(b) for b in n.barn)


def normtext(s: str) -> str:
    s = html.unescape(s or "").replace("­", "").replace("‑", "-")
    s = re.sub(r"[‒–—−]", "–", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def satt_text(n: Nod, v: str):
    """Ersätt elementets text. Finns exakt en textbärare inuti, behålls strukturen runt den."""
    barare = [t for t in n.iter() if t.typ == "text" and t.text.strip() and t.foralder.tag not in RAA]
    if len(barare) == 1 and barare[0].foralder is not n and not any(
            x.har("data-slot") or x.har("data-repeat") for x in n.iter() if x is not n):
        barare[0].text = v
        return
    n.barn = []
    n.lagg_till(Nod("text", text=v))


def ar_inne_i(n: Nod, attr: str, varde: str | None = None) -> bool:
    p = n.foralder
    while p is not None:
        if p.typ == "el" and p.har(attr) and (varde is None or p.get(attr) == varde):
            return True
        p = p.foralder
    return False


# ---------------------------------------------------------------- kontext & varianter

def tillampa_variant(design: dict, dok: dict | None) -> dict:
    """Lägg en variant (design.json.varianter[namn]) ovanpå designen.

    Varianten väljs med cv.json/brev.json `design_variant`, annars design.json
    `standardvariant`. Okänd variant = designen som den är."""
    varianter = design.get("varianter") or {}
    namn = (dok or {}).get("design_variant") or design.get("standardvariant")
    if not namn or namn not in varianter:
        return design
    v = varianter[namn] or {}
    d = copy.deepcopy(design)
    if v.get("layout"):
        d["layout"] = v["layout"]
    d["tokens"] = {**(d.get("tokens") or {}), **(v.get("token_overrides") or {})}
    if v.get("sektioner"):
        d["sektioner"] = list(v["sektioner"])
    d["namn"] = f"{design.get('namn') or 'Design'} – {namn}"
    return d


def _person_falt(person: dict) -> dict:
    p = dict(person)
    for k in person.get("kontakt") or []:
        url = k.get("url") or ""
        if url.startswith("mailto:"):
            p.setdefault("epost", k["text"])
        elif url.startswith("tel:"):
            p.setdefault("telefon", k["text"])
        elif url.startswith("http"):
            p.setdefault("lankar", []).append(k)
        elif k.get("etikett") in ("Ort", "Location"):
            p.setdefault("ort", k["text"])
    p.setdefault("lankar", [])
    return p


def _uppslag(ctx: list, uttryck: str):
    uttryck = uttryck.strip()
    if uttryck in (".", "varde"):
        for scope in reversed(ctx):
            if isinstance(scope, dict) and "." in scope:
                return scope["."]
        return None
    return render._uppslag(ctx, uttryck)


def _sant(ctx, uttryck: str) -> bool:
    uttryck = uttryck.strip()
    if uttryck.startswith("not "):
        return not _sant(ctx, uttryck[4:])
    v = _uppslag(ctx, uttryck)
    return bool(v) and v != "0"


# ---------------------------------------------------------------- rendering

STANDARD_SEKTION = """<section class="sektion" data-repeat="sektioner">
<h2 data-slot-rubrik>Rubrik</h2>
<div class="post" data-repeat="poster"><div class="post-topp"><h3 class="post-titel" data-slot="titel"></h3>
<span class="period" data-slot="period"></span></div><div class="plats" data-slot="plats"></div>
<p class="post-text" data-slot="text"></p><ul class="punkter"><li data-repeat="punkter"></li></ul></div>
<p class="grupp" data-repeat="grupper"><strong data-slot="etikett"></strong> <span data-slot="rad"></span></p>
<p class="text-stycke" data-repeat="stycken"></p>
</section>"""


# Reservdelar: om mallen saknar en plats för innehåll som finns läggs de till, så att inget tappas.
RESERV_POST = {
    "titel": '<h3 class="post-titel" data-slot="titel"></h3>',
    "period": '<span class="period" data-slot="period"></span>',
    "plats": '<p class="plats" data-slot="plats"></p>',
    "text": '<p class="post-text" data-slot="text"></p>',
    "punkter": '<ul class="punkter"><li data-repeat="punkter"></li></ul>',
}
RESERV_SEKTION = {
    "rubrik": '<h2 data-slot-rubrik></h2>',
    "poster": ('<div class="post" data-repeat="poster"><h3 class="post-titel" data-slot="titel"></h3>'
               '<span class="period" data-slot="period"></span><p class="plats" data-slot="plats"></p>'
               '<p class="post-text" data-slot="text"></p><ul class="punkter"><li data-repeat="punkter"></li></ul></div>'),
    "grupper": '<p class="grupp" data-repeat="grupper"><strong data-slot="etikett"></strong> <span data-slot="rad"></span></p>',
    "stycken": '<p class="text-stycke" data-repeat="stycken"></p>',
}


def _egna(n: Nod):
    """Ättlingar som hör till just det här objektet (inte till ett inre data-repeat-objekt)."""
    for b in n.barn:
        if b.typ != "el":
            continue
        yield b
        if not b.har("data-repeat"):
            yield from _egna(b)


def _komplettera(n: Nod, data: dict, sektion: bool):
    egna = list(_egna(n))
    slots = {x.get("data-slot") for x in egna if x.har("data-slot")}
    rep = {x.get("data-repeat") for x in egna if x.har("data-repeat")}
    saknas = []
    if sektion:
        if not any(x.har("data-slot-rubrik") for x in egna) and data.get("rubrik") and data["nyckel"] != "profil":
            saknas.append(("rubrik", True))
        if data.get("ar_poster") and not ({"poster", f"sektion:{data['nyckel']}"} & rep):
            saknas.append(("poster", False))
        if data.get("ar_lista") and "grupper" not in rep and not data.get("ar_poster"):
            saknas.append(("grupper", False))
        if data.get("ar_text") and "stycken" not in rep and "profil" not in slots:
            saknas.append(("stycken", False))
        delar = RESERV_SEKTION
    elif "rad" in data:  # grupp i en lista
        if data.get("etikett") and "etikett" not in slots:
            saknas.append(("etikett", True))
        if data.get("rad") and not ({"rad", "."} & slots) and "poster" not in rep:
            saknas.append(("rad", False))
        delar = RESERV_GRUPP
    else:
        for falt in ("titel", "period", "text"):
            if data.get(falt) and falt not in slots:
                saknas.append((falt, falt == "titel"))
        if data.get("plats") and not ({"plats", "organisation"} & slots):
            saknas.append(("plats", False))
        if data.get("punkter") and "punkter" not in rep:
            saknas.append(("punkter", False))
        delar = RESERV_POST
    for falt, forst in saknas:
        for d in parsa(delar[falt]).barn:
            d.foralder = n
            d.meta["reserv"] = True
            if forst:
                n.barn.insert(0, d)
            else:
                n.barn.append(d)
    return [f for f, _ in saknas]


RESERV_GRUPP = {"etikett": '<strong class="grupp-etikett" data-slot="etikett"></strong>',
                "rad": '<span class="grupp-rad" data-slot="rad"></span>'}


def _komplettera_person(rot: Nod, c: dict):
    """Yrkestitel och kontaktuppgifter som mallen saknar plats för läggs efter namnet."""
    el = [x for x in rot.iter() if x.typ == "el"]
    slots = {x.get("data-slot") for x in el if x.har("data-slot")}
    namn = next((x for x in el if x.get("data-slot") == "person.namn"), None)
    if namn is None or namn.foralder is None:
        return
    p = c["person"]
    nya = []
    if p.get("titel") and "person.titel" not in slots:
        nya.append('<p class="yrkestitel" data-slot="person.titel"></p>')
    if not any(x.get("data-repeat") == "person.kontakt" for x in el):
        tackta = {str(p.get(k[7:])) for k in slots if k and k.startswith("person.") and k[7:] in ("epost", "telefon", "ort")}
        p["kontakt_ovriga"] = [k for k in p.get("kontakt") or [] if k["text"] not in tackta]
        if p["kontakt_ovriga"]:
            nya.append('<ul class="kontakt"><li data-repeat="person.kontakt_ovriga"><a data-slot="text"></a></li></ul>')
    f = namn.foralder
    i = f.barn.index(namn) + 1
    for html_del in nya:
        for d in parsa(html_del).barn:
            d.foralder = f
            f.barn.insert(i, d)
            i += 1


class _Stat:
    def __init__(self, ctx: dict, ordning: list, behall: bool):
        self.ctx = ctx
        self.ordning = ordning
        self.behall = behall
        self.placerade: set = set()
        self.reserv: list = []
        self.explicita: set = set()
        self.sektioner = ctx.get("sektioner") or []

    def sektion(self, nyckel):
        for s in self.sektioner:
            if s["nyckel"] == nyckel and id(s) not in self.placerade:
                return s
        return None


def _repeat_lista(uttr: str, ctx: list, st: _Stat):
    uttr = uttr.strip()
    if uttr == "sektioner":
        return [s for s in st.sektioner if id(s) not in st.placerade and s["nyckel"] not in st.explicita]
    if uttr.startswith("sektion:"):
        s = st.sektion(uttr.split(":", 1)[1].strip())
        if not s:
            return []
        st.placerade.add(id(s))
        return [{**p, "_sektion": s} for p in s["poster"]]
    v = _uppslag(ctx, uttr)
    return v if isinstance(v, list) else []


def _kor(n: Nod, ctx: list, st: _Stat) -> list[Nod]:
    if n.typ != "el":
        return [n]
    if n.har("data-if") and not _sant(ctx, n.get("data-if")) and not st.behall:
        return []
    if n.har("data-repeat") and not n.meta.get("upprepad"):
        lista = _repeat_lista(n.get("data-repeat"), ctx, st)
        ut = []
        for i, el in enumerate(lista):
            kopia = copy.deepcopy(n)
            kopia.meta["upprepad"] = True
            loop = {"index": i + 1, "first": i == 0, "last": i == len(lista) - 1}
            if isinstance(el, dict):
                scope = [el, {"loop": loop}]
                if n.get("data-repeat") == "sektioner":
                    st.placerade.add(id(el))
                    kopia.meta["sektion"] = el["nyckel"]
            else:
                scope = [{".": el, "loop": loop}]
                if not any(x.har("data-slot") for x in kopia.iter() if x is not kopia):
                    satt_text(kopia, str(el))
            if i > 0:
                kopia.ta_bort_attr("id")
            ut += _kor(kopia, ctx + scope, st)
        return ut
    if n.har("data-sektion"):
        s = st.sektion(n.get("data-sektion").strip())
        if not s:
            return []
        st.placerade.add(id(s))
        n.meta["sektion"] = s["nyckel"]
        ctx = ctx + [s]
    if n.meta.get("sektion") and not n.meta.get("kompletterad"):
        n.meta["kompletterad"] = True
        sd = ctx[-1] if n.har("data-sektion") else ctx[-2]
        st.reserv += [f"{sd['nyckel']}:{f}" for f in _komplettera(n, sd, True)]
    elif n.meta.get("upprepad") and n.get("data-repeat") == "grupper" and isinstance(ctx[-2], dict):
        st.reserv += [f"grupp:{f}" for f in _komplettera(n, ctx[-2], False)]
    elif n.meta.get("upprepad") and n.get("data-repeat") in ("poster",) or (
            n.meta.get("upprepad") and (n.get("data-repeat") or "").startswith("sektion:")):
        post = ctx[-2] if len(ctx) > 1 else {}
        if isinstance(post, dict) and "punkter" in post:
            st.reserv += [f"post:{f}" for f in _komplettera(n, post, False)]
            if post.get("lang"):
                n.satt("data-lang", None)  # lång post får brytas mellan punkter (som i render.py)
    if n.har("data-slot-rubrik"):
        satt_text(n, str(_uppslag(ctx, "rubrik") or ""))
    if n.har("data-slot"):
        uttr = n.get("data-slot").strip()
        if uttr == "profil":
            s = st.sektion("profil")
            if s:
                st.placerade.add(id(s))
            v = "\n\n".join(s["stycken"]) if s else ""
        else:
            v = _uppslag(ctx, uttr)
        v = "" if v is None or v is False else v
        if isinstance(v, list):
            v = " · ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in v)
        v = str(v)
        if n.tag == "img":
            if v:
                n.satt("src", v)
            elif not st.behall:
                return []
        elif not v.strip() and not st.behall:
            return []
        else:
            satt_text(n, v)
            url = _uppslag(ctx, n.get("data-href")) if n.har("data-href") else (
                _uppslag(ctx, "url") if n.tag == "a" and uttr in ("text", ".") else None)
            if n.tag == "a":
                if url:
                    n.satt("href", url)
                elif not n.get("href", "").startswith(("http", "mailto:", "tel:")):
                    n.ta_bort_attr("href")
    elif n.har("data-href"):
        url = _uppslag(ctx, n.get("data-href"))
        if url:
            n.satt("href", url)
    nya: list[Nod] = []
    for b in n.barn:
        for r in _kor(b, ctx, st):
            r.foralder = n
            nya.append(r)
    n.barn = _ordna(nya, st.ordning)
    return [n]


def _ordna(barn: list[Nod], ordning: list) -> list[Nod]:
    platser = [i for i, b in enumerate(barn) if b.meta.get("sektion")]
    if len(platser) < 2:
        return barn
    sekt = [barn[i] for i in platser]
    rang = {k: i for i, k in enumerate(ordning)}
    sekt_sorterad = sorted(sekt, key=lambda b: rang.get(b.meta["sektion"], len(rang)))
    ut = list(barn)
    for i, b in zip(platser, sekt_sorterad):
        ut[i] = b
    return ut


def _injicera_css(rot: Nod, css: str):
    head = next((x for x in rot.iter() if x.typ == "el" and x.tag == "head"), None)
    for x in list(rot.iter()):
        if x.typ == "el" and x.tag == "link" and "stylesheet" in (x.get("rel") or "") \
                and not (x.get("href") or "").startswith(("http:", "https:")):
            x.foralder.barn.remove(x)
    stil = Nod("el", "style", [("data-mall", "")])
    stil.lagg_till(Nod("text", text=css))
    if head is None:
        html_el = next((x for x in rot.iter() if x.typ == "el" and x.tag == "html"), rot)
        head = Nod("el", "head")
        html_el.barn.insert(0, head)
        head.foralder = html_el
    head.lagg_till(stil)


def _bas_mall(n: Nod) -> Nod | None:
    for x in n.iter():
        if x.typ == "el" and x.tag in ("main",):
            return x
    return next((x for x in n.iter() if x.typ == "el" and x.tag == "body"), n)


def fyll_mall(mall_html: str, ctx: dict, css: str = "", ordning: list | None = None,
              behall_tomma: bool = False) -> str:
    """Fyll en slot-mall med en kontext från render.bygg_kontext."""
    rot = parsa(mall_html)
    c = dict(ctx)
    c["person"] = _person_falt(ctx.get("person") or {})
    _komplettera_person(rot, c)
    st = _Stat(c, list(ordning or render.STANDARD_SEKTIONER), behall_tomma)
    for x in rot.iter():
        if x.typ == "el" and not ar_inne_i(x, "data-repeat", "sektioner"):
            if x.har("data-sektion"):
                st.explicita.add(x.get("data-sektion").strip())
    _kor(rot, [c], st)
    # Inget får tappas: sektioner utan plats läggs sist i standardform.
    rest = [s for s in st.sektioner if id(s) not in st.placerade] if ctx.get("typ") == "cv" else []
    if rest:
        st.explicita = set()
        mal = None
        for x in rot.iter():
            if x.typ == "el" and x.meta.get("sektion"):
                mal = x.foralder
        mal = mal or _bas_mall(rot)
        extra = parsa(STANDARD_SEKTION)
        for r in _kor(extra.barn[0], [c], st):
            r.foralder = mal
            mal.barn.append(r)
        mal.barn = _ordna(mal.barn, st.ordning)
    html_el = next((x for x in rot.iter() if x.typ == "el" and x.tag == "html"), None)
    if html_el is not None and ctx.get("sprak"):
        html_el.satt("lang", ctx["sprak"])
    if css:
        _injicera_css(rot, css)
    return serialisera(rot)


# ---------------------------------------------------------------- egna mallar på disk

def mallmappar(bas: list[Path] | None = None) -> list[Path]:
    kand = [Path(b) / "design" / "mallar" for b in (bas or [])]
    kand.append(render.hem() / "design" / "mallar")
    return list(dict.fromkeys(kand))


def hitta_mall(namn: str, bas: list[Path] | None = None) -> Path | None:
    for m in mallmappar(bas):
        if (m / namn / "mall.html").exists():
            return m / namn
    return None


def bada_in_resurser(text: str, mapp: Path) -> str:
    """url(assets/x) och src="assets/x" blir data-URI så att HTML:en blir fristående."""
    def uri(rel: str) -> str | None:
        rel = rel.strip().strip("'\"")
        if rel.startswith(("data:", "http:", "https:", "#")) or not rel:
            return None
        p = (mapp / rel).resolve()
        if not p.exists() or not str(p).startswith(str(mapp.resolve())) or p.stat().st_size > 8_000_000:
            return None
        mime = mimetypes.guess_type(p.name)[0] or ("font/" + p.suffix.lstrip(".") if p.suffix in (".woff", ".woff2", ".ttf", ".otf") else "application/octet-stream")
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()

    def css_ers(m):
        u = uri(m.group(2))
        return f"url({m.group(1)}{u}{m.group(1)})" if u else m.group(0)

    text = re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", css_ers, text)

    def src_ers(m):
        u = uri(m.group(2))
        return f'{m.group(1)}="{u}"' if u else m.group(0)

    return re.sub(r'\b(src)="([^"]+)"', src_ers, text)


def mall_css(design: dict, mapp: Path) -> str:
    t = render.klamp_tokens(design.get("tokens", {}))
    font, _ = render.fontface_css([t["font_rubrik"], t["font_brod"]])
    egen = (mapp / "mall.css").read_text("utf-8") if (mapp / "mall.css").exists() else ""
    return render.tokens_css(t) + "\n" + font + "\n" + bada_in_resurser(egen, mapp)


def fyll_egen(typ: str, ctx: dict, design: dict, bas: list[Path] | None = None) -> str | None:
    """Kroken i render.rendera: HTML för en egen mall, eller None (då används standardmallen)."""
    layout = str(design.get("layout") or "")
    if not layout.startswith("egen:"):
        return None
    mapp = hitta_mall(layout[5:].strip(), bas)
    if not mapp:
        return None
    fil = mapp / ("mall.html" if typ == "cv" else "brev.html")
    if not fil.exists():
        return None
    if typ == "cv":
        ctx["layout"] = layout
    ut = fyll_mall(fil.read_text("utf-8"), ctx, mall_css(design, mapp), design.get("sektioner"))
    return bada_in_resurser(ut, mapp)


def slots_i(mall_html: str) -> dict:
    """Sammanställ vilka slots en mall har (för import och kontroll)."""
    rot = parsa(mall_html)
    ut = {"slot": [], "repeat": [], "sektion": [], "if": [], "rubrik": 0}
    for x in rot.iter():
        if x.typ != "el":
            continue
        if x.har("data-slot"):
            ut["slot"].append(x.get("data-slot"))
        if x.har("data-repeat"):
            ut["repeat"].append(x.get("data-repeat"))
        if x.har("data-sektion"):
            ut["sektion"].append(x.get("data-sektion"))
        if x.har("data-if"):
            ut["if"].append(x.get("data-if"))
        if x.har("data-slot-rubrik"):
            ut["rubrik"] += 1
    return ut
