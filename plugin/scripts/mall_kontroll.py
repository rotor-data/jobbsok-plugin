#!/usr/bin/env python3
"""Kvalitetskontroll av en egen mall (från Claude Design).

  mall_kontroll.py <namn> [--home MAPP] [--out MAPP] [--innehall cv.json|mapp]

Stresstestar mallen med kort och långt innehåll, svenska och engelska, med och utan foto
(plus brevet om mallen har ett), och kontrollerar:
  - att allt innehåll kommer med (inget tappat)
  - läsordningen i PDF:ens textlager (pdftotext)
  - sidantal och innehåll som klipps (overflow)
  - minsta teckenstorlek och kontrast
  - text i bilder och tabeller för layout
Skriver en svensk rapport (fältet `rapport`) med vänliga förslag och en jämförelsesida.
Blockerar (exit 1, `blockerar: true`) bara vid tappat innehåll eller oläslig PDF.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_export  # noqa: E402
import mall_slots as ms  # noqa: E402
import render  # noqa: E402

MIN_PT = 9.0

MATT_JS = r"""
<script>
(function(){
 function rgb(s){var m=(s||'').match(/[\d.]+/g);return m?m.map(Number):[0,0,0,1];}
 function lum(c){var a=c.slice(0,3).map(function(v){v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);});
   return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2];}
 function bg(el){while(el){var c=rgb(getComputedStyle(el).backgroundColor);if(c.length<4||c[3]>0.5)return c;el=el.parentElement;}return [255,255,255];}
 var r={min:[],kontrast:[],klipp:[],bildtext:[],tabeller:0,minsta:99};
 var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n,sett=new Set();
 while((n=w.nextNode())){var t=n.textContent.trim();if(!t)continue;var el=n.parentElement;if(sett.has(el))continue;sett.add(el);
   var cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden'||el.offsetParent===null&&cs.position!=='fixed')continue;
   var pt=parseFloat(cs.fontSize)*0.75;if(pt<r.minsta)r.minsta=pt;if(pt<9)r.min.push([Math.round(pt*10)/10,t.slice(0,50)]);
   var f=rgb(cs.color),b=bg(el),l1=lum(f),l2=lum(b),k=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
   if(f.length>3&&f[3]<1){k=k*f[3];}
   if(k<4.5)r.kontrast.push([Math.round(k*10)/10,t.slice(0,50)]);}
 document.querySelectorAll('body *').forEach(function(el){var cs=getComputedStyle(el);
   if(/hidden|clip/.test(cs.overflow+cs.overflowX+cs.overflowY)&&(el.scrollHeight>el.clientHeight+2||el.scrollWidth>el.clientWidth+2)&&el.textContent.trim())
     r.klipp.push(el.tagName.toLowerCase()+(el.className?'.'+String(el.className).split(' ')[0]:'')+': '+el.textContent.trim().slice(0,50));
   if(cs.backgroundImage&&cs.backgroundImage!=='none'&&!/gradient/.test(cs.backgroundImage)&&el.textContent.trim())r.bildtext.push('bakgrundsbild bakom text: '+el.textContent.trim().slice(0,40));});
 document.querySelectorAll('svg text').forEach(function(t){r.bildtext.push('text i SVG: '+t.textContent.trim().slice(0,40));});
 document.querySelectorAll('img').forEach(function(i){if(!i.hasAttribute('data-slot'))r.bildtext.push('bild: '+(i.alt||i.src.slice(0,40)));});
 r.tabeller=document.querySelectorAll('table').length;
 var p=document.createElement('pre');p.id='jobbsok-kontroll';p.textContent=JSON.stringify(r);document.body.appendChild(p);
})();
</script>
"""


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    s = re.sub(r"[‐-―−-]", "-", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", "", s).lower()


def forvantat(ctx: dict, typ: str) -> tuple[list[str], list[list[str]]]:
    """(alla texter som ska finnas, läsordningskedjor)."""
    p = ctx["person"]
    alla = [p["namn"], p.get("titel") or ""] + [k["text"] for k in p.get("kontakt") or []]
    kedjor = []
    if typ == "cv":
        for s in ctx["sektioner"]:
            alla.append(s["rubrik"])
            kedja = [s["rubrik"]]
            for post in s["poster"]:
                alla += [post["titel"], post["plats"], post["period"], post["text"], *post["punkter"]]
                kedja.append(post["titel"])
            for g in s["grupper"]:
                alla += [g["etikett"], *g["poster"]]
            alla += s["stycken"]
            kedjor.append(kedja)
        kedjor.insert(0, [p["namn"], ctx["sektioner"][0]["rubrik"]] if ctx["sektioner"] else [p["namn"]])
    else:
        m = ctx["mottagare"]
        alla += [m["namn"], m["bolag"], *m["adress_rader"], ctx["datum"], ctx["rubrik"], *ctx["stycken"], ctx["halsning"]]
        kedjor.append([p["namn"], *(x[:40] for x in ctx["stycken"]), ctx["halsning"]])
    return [x for x in alla if x and x.strip()], kedjor


def pdf_text(pdf: Path) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, timeout=30)
        return r.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return None


def html_text(h: str) -> str:
    h = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", h, flags=re.S)
    return ms.html.unescape(re.sub(r"<[^>]+>", " ", h))


def _finns_i_ordning(x: str, t: str) -> bool:
    """Orden i x i ordning i t. Mellan orden får annan text ligga (t.ex. ett datum som
    pdftotext läser in på samma rad som en ombruten rubrik)."""
    pos = 0
    for o in (norm(w) for w in x.split()):
        if not o:
            continue
        p = t.find(o, pos)
        if p < 0 or (pos and p - pos > 120):
            return False
        pos = p + len(o)
    return True


def tappat(alla: list[str], text: str) -> list[str]:
    t = norm(text)
    ut = []
    for x in alla:
        n = norm(x)
        if n and n not in t and not _finns_i_ordning(x, t):
            ut.append(x)
    return ut


def lasordning(kedjor: list[list[str]], text: str) -> list[str]:
    t = norm(text)
    fel = []
    for k in kedjor:
        pos = -1
        for i, x in enumerate(k):
            n = norm(x)[:40]
            if not n:
                continue
            p = t.find(n, pos + 1)
            if p < 0:
                if t.find(n) >= 0 and i > 0:
                    fel.append(f"\"{x[:50]}\" kommer före \"{k[i - 1][:50]}\" i textlagret.")
                break
            pos = p
    return fel


def matt(html_p: Path) -> dict | None:
    exe = render._chrome()
    if not exe:
        return None
    h = html_p.read_text("utf-8")
    h = h.replace("</body>", MATT_JS + "</body>") if "</body>" in h else h + MATT_JS
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "matt.html"
        f.write_text(h, "utf-8")
        try:
            proc = subprocess.Popen([exe, *render._chrome_flaggor(tmp), "--dump-dom", f.as_uri()],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            return None
        # Chrome avslutar inte alltid själv; läs tills DOM:en är skriven och avsluta sedan.
        import os
        import select
        import time
        ut, start = b"", time.time()
        while time.time() - start < 40:
            klar, _, _ = select.select([proc.stdout], [], [], 0.5)
            if klar:
                bit = os.read(proc.stdout.fileno(), 65536)
                if not bit:
                    break
                ut += bit
                if b"</html>" in ut:
                    break
            elif proc.poll() is not None:
                break
        if proc.poll() is None:
            proc.kill()
        proc.wait()
    m = re.search(r'<pre id="jobbsok-kontroll">(.*?)</pre>', ut.decode("utf-8", "replace"), re.S)
    if not m:
        return None
    try:
        return json.loads(ms.html.unescape(m.group(1)))
    except ValueError:
        return None


def statisk_matt(mapp: Path) -> dict:
    css = (mapp / "mall.css").read_text("utf-8") if (mapp / "mall.css").exists() else ""
    h = (mapp / "mall.html").read_text("utf-8")
    små = []
    for v, enh in re.findall(r"font-size\s*:\s*([\d.]+)(pt|px)", css):
        pt = float(v) * (0.75 if enh == "px" else 1)
        if pt < MIN_PT:
            små.append([round(pt, 1), f"font-size: {v}{enh}"])
    return {"min": små, "kontrast": [], "klipp": [], "bildtext": re.findall(r"<svg[^>]*>.*?<text", h, re.S)[:3],
            "tabeller": len(re.findall(r"<table", h)), "statisk": True}


def kontrollera(namn: str, home: Path, ut: Path | None = None, innehall: str | None = None) -> dict:
    mapp = ms.hitta_mall(namn, [home])
    if not mapp:
        raise SystemExit(json.dumps({"fel": f"Mallen '{namn}' finns inte i {home / 'design' / 'mallar'}."},
                                    ensure_ascii=False))
    ut = ut or (mapp / "kontroll")
    if ut.exists():
        shutil.rmtree(ut)
    ut.mkdir(parents=True)
    bas_design = render.las_json(render.hitta_design(None, home))
    design = {**bas_design, "layout": f"egen:{namn}", "varianter": {}, "standardvariant": None}
    har_foto = any(s == "person.foto" for s in ms.slots_i((mapp / "mall.html").read_text("utf-8"))["slot"])
    fall = []
    for f in ("cv-kort-sv", "cv-lang-sv", "cv-kort-en", "cv-lang-en"):
        fall.append(("cv", f, render.las_json(render.FIXTURER / f"{f}.json"), False, [render.FIXTURER, home]))
    if har_foto:
        fall.append(("cv", "cv-kort-sv-foto", render.las_json(render.FIXTURER / "cv-kort-sv.json"), True,
                     [render.FIXTURER, home]))
    try:
        egen, emapp, ar_ex = design_export.hitta_innehall(innehall, home)
        if not ar_ex:
            fall.append(("cv", "hennes-cv", egen, False, [emapp, home]))
    except SystemExit:
        pass
    if (mapp / "brev.html").exists():
        for f in ("brev-sv", "brev-en"):
            fall.append(("brev", f, render.las_json(render.FIXTURER / f"{f}.json"), False, [render.FIXTURER, home]))

    kort, problem, forslag, blockerar = [], [], [], []
    for typ, id_, dok, foto, bas in fall:
        d = {**design, "tokens": {**design.get("tokens", {}), "visa_foto": foto}}
        if typ == "cv" and not foto:
            dok = {**dok, "person": {**dok.get("person", {}), "foto": None}}
        r = render.rendera(typ, dok, d, ut, bas, stam=id_, bild=True)
        ctx, _ = render.bygg_kontext(dok, ms.tillampa_variant(d, dok), bas, typ)
        alla, kedjor = forvantat(ctx, typ)
        fynd = {"id": id_, "sidor": r["sidor"], "motor": r["motor"]}
        if r["pdf"]:
            text = pdf_text(Path(r["pdf"]))
            if text is None:
                text = html_text(Path(r["html"]).read_text("utf-8"))
                fynd["textkalla"] = "html (pdftotext saknas)"
            if not (r["textlager"] or {}).get("finns"):
                blockerar.append(f"{id_}: PDF:en har inget läsbart textlager. Rekryteringssystem kan inte läsa den.")
        else:
            text = html_text(Path(r["html"]).read_text("utf-8"))
            fynd["textkalla"] = "html (ingen PDF-motor)"
        borta = tappat(alla, text)
        if borta:
            blockerar.append(f"{id_}: {len(borta)} delar av innehållet kom inte med, t.ex. "
                             + "; ".join(f"\"{x[:50]}\"" for x in borta[:3]))
        fynd["tappat"] = borta
        ordn = lasordning(kedjor, text)
        if ordn:
            problem.append(f"{id_}: läsordningen avviker: {ordn[0]}")
        fynd["lasordning"] = ordn
        maxs = render.MAX_SIDOR[typ]
        if r["sidor"] and r["sidor"] > maxs:
            kort_innehall = "kort" in id_ or typ == "brev"
            (problem if kort_innehall else forslag).append(
                f"{id_}: blev {r['sidor']} sidor (högst {maxs}). " + (
                    "Mallen tar för mycket plats även med kort innehåll." if kort_innehall else
                    "Med mycket erfarenhet blir mallen lång; minska luften mellan delarna lite eller korta texten per jobb."))
        m = matt(Path(r["html"])) if id_ in ("cv-kort-sv", "cv-lang-sv", "brev-sv", "cv-kort-sv-foto") else None
        if id_ == "cv-kort-sv" and m is None:
            m = statisk_matt(mapp)
        if m:
            fynd["matt"] = {k: v for k, v in m.items() if v}
            if m.get("min"):
                problem.append(f"{id_}: text mindre än {MIN_PT:g} pt ({m['min'][0][0]} pt: \"{m['min'][0][1]}\"). "
                               "Öka till minst 9 pt, brödtext helst 10–11,5 pt.")
            if m.get("kontrast"):
                problem.append(f"{id_}: låg kontrast ({m['kontrast'][0][0]}:1) för \"{m['kontrast'][0][1]}\". "
                               "Välj en mörkare färg (minst 4,5:1 mot bakgrunden).")
            if m.get("klipp"):
                problem.append(f"{id_}: innehåll klipps av en fast höjd: {m['klipp'][0]}. Ta bort fast höjd/overflow: hidden.")
            if m.get("bildtext"):
                problem.append(f"{id_}: {m['bildtext'][0]}. Text i bilder läses inte av rekryteringssystem.")
            if m.get("tabeller"):
                problem.append(f"{id_}: mallen använder tabeller ({m['tabeller']} st). Byt till flex/grid; "
                               "tabeller läses ofta hackigt av rekryteringssystem.")
        r["namn"] = id_.replace("-", " ")
        r["id"] = id_
        kort.append(r)
        fynd["bild"] = r["bild"]
        r["fynd"] = fynd
    sida = render.jamforelse(kort, ut, f"Kontroll av mallen {namn}",
                             "Kort och långt CV, svenska och engelska, med och utan foto. Inget innehåll får tappas.")
    problem = list(dict.fromkeys(problem))
    rapport = []
    if blockerar:
        rapport.append("Mallen kan inte användas än, för att innehåll försvinner eller PDF:en inte går att läsa:")
        rapport += [f"- {x}" for x in blockerar]
    else:
        rapport.append("Allt innehåll kommer med i alla testfall, och PDF:en har ett läsbart textlager.")
    if problem:
        rapport.append("Saker att titta på (mallen fungerar, men kan bli bättre):")
        rapport += [f"- {x}" for x in problem]
    if forslag:
        rapport.append("Bra att veta:")
        rapport += [f"- {x}" for x in forslag]
    if not problem and not blockerar:
        rapport.append("Inga problem med storlek, kontrast, klippt text, text i bilder eller tabeller hittades.")
    return {"mall": str(mapp), "blockerar": bool(blockerar), "rapport": "\n".join(rapport),
            "blockerande": blockerar, "problem": problem, "forslag": forslag, "jamforelse": str(sida),
            "fall": [k["fynd"] for k in kort], "har_foto": har_foto}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("namn", help="mallens namn (mappen i <home>/design/mallar/)")
    ap.add_argument("--home")
    ap.add_argument("--out")
    ap.add_argument("--innehall", help="hennes cv.json eller ansökningsmapp (standard: senaste)")
    a = ap.parse_args(argv)
    namn = a.namn[5:] if a.namn.startswith("egen:") else a.namn
    res = kontrollera(namn, render.hem(a.home), Path(a.out).expanduser() if a.out else None, a.innehall)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 1 if res["blockerar"] else 0


if __name__ == "__main__":
    sys.exit(main())
