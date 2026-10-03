"""Tur och retur med Claude Design: export → (simulerad) redigering → import → rendering → kontroll.

Kör: JOBBSOK_OFFLINE=1 python3 -m unittest discover plugin/tests -p 'test_design_roundtrip.py'
Sätt JOBBSOK_TEST_BILDER=<mapp> för att spara PNG före och efter import där.
PDF-delarna skippas om ingen PDF-motor finns; HTML-kontrollerna körs alltid.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN / "scripts"))
import design_export  # noqa: E402
import design_import  # noqa: E402
import mall_kontroll  # noqa: E402
import mall_slots  # noqa: E402
import render  # noqa: E402

FIX = PLUGIN / "tests" / "fixtures" / "cv-exempel"
os.environ.setdefault("JOBBSOK_OFFLINE", "1")


def har_pdf():
    return bool(render._chrome())


def redigera_som_claude_design(h: str) -> str:
    """Simulerar en redigering i Claude Design: ny layout, ny färg, flyttade sektioner,
    några data-attribut borttagna men strukturen kvar."""
    h = h.replace("--farg-accent:#2f5d62", "--farg-accent:#7a3b2e")
    h = h.replace("</style>", """
.cd-ram { display: grid; grid-template-columns: minmax(0,1fr) 50mm; gap: 8mm; }
.cd-ram aside { border-left: 1pt solid var(--farg-accent); padding-left: 4mm; }
.namn { letter-spacing: .02em; text-transform: uppercase; }
</style>""", 1)
    rot = mall_slots.parsa(h)
    alla = [x for x in rot.iter() if x.typ == "el"]
    sek = {x.get("data-sektion"): x for x in alla if x.har("data-sektion")}
    huvudspalt = next(x for x in alla if "huvudspalt" in x.klasser())
    kropp = huvudspalt.foralder
    # sidokolumn med kompetenser och språk
    aside = mall_slots.Nod("el", "aside", [("class", "sidospalt-cd")])
    for k in ("kompetenser", "sprak"):
        n = sek[k]
        n.foralder.barn.remove(n)
        aside.lagg_till(n)
    kropp.satt("class", "kropp cd-ram")
    kropp.lagg_till(aside)
    # flytta utbildning före erfarenhet
    utb, erf = sek["utbildning"], sek["erfarenhet"]
    huvudspalt.barn.remove(utb)
    huvudspalt.barn.insert(huvudspalt.barn.index(erf), utb)
    # tappade attribut: perioder, punktmallar och utbildningssektionens markering
    for x in alla:
        if x.get("data-slot") == "period":
            x.ta_bort_attr("data-slot")
        if x.get("data-repeat") == "punkter":
            x.ta_bort_attr("data-repeat")
    utb.ta_bort_attr("data-sektion")
    # ett omslag runt sidhuvudet
    head = next(x for x in alla if x.tag == "header")
    f = head.foralder
    omslag = mall_slots.Nod("el", "div", [("class", "cd-topp")])
    i = f.barn.index(head)
    f.barn[i] = omslag
    omslag.foralder = f
    omslag.lagg_till(head)
    return mall_slots.serialisera(rot)


def html_text(h):
    return mall_kontroll.html_text(h)


class Roundtrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="cd-roundtrip-"))
        cls.home = cls.tmp / "home"
        mapp = cls.home / "ansokningar" / "2026-10-01-region-kommunikator"
        mapp.mkdir(parents=True)
        shutil.copy(FIX / "cv-lang-sv.json", mapp / "cv.json")
        shutil.copy(FIX / "brev-sv.json", mapp / "brev.json")
        shutil.copy(FIX / "foto.svg", mapp / "foto.svg")
        cls.mapp = mapp
        cls.bilder = Path(os.environ["JOBBSOK_TEST_BILDER"]) if os.environ.get("JOBBSOK_TEST_BILDER") else cls.tmp / "bilder"
        cls.bilder.mkdir(parents=True, exist_ok=True)
        (cls.home / "design").mkdir(parents=True)
        (cls.home / "design" / "brief.md").write_text("- Läsare: offentlig sektor\n- Känsla: lugn, saklig, varm\n", "utf-8")
        cls.export = design_export.exportera(None, cls.home)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------ export
    def test_1_exportpaket(self):
        e = self.export
        ut = Path(e["mapp"])
        self.assertFalse(e["exempelinnehall"])
        self.assertFalse(e["brief_saknas"])
        for f in ("cv-exempel.html", "brev-exempel.html", "tokens.css", "mall.css", "README-for-claude-design.md"):
            self.assertTrue((ut / f).exists(), f)
        self.assertEqual(set(e["komponenter"]), {f"{k}.html" for k in (
            "sidhuvud", "sektion", "post", "punktlista", "kompetenslista", "sidokolumn", "brevhuvud")})
        for k in (ut / "komponenter").glob("*.html"):
            self.assertTrue(k.read_text("utf-8").startswith('<!-- @dsCard group="CV" -->'), k.name)
        cv = (ut / "cv-exempel.html").read_text("utf-8")
        self.assertIn('data-slot="person.namn"', cv)
        self.assertIn("Maja Lindqvist", cv)
        self.assertIn('data-repeat="punkter"', cv)
        self.assertNotIn("<link", cv)  # fristående: stilen är inbäddad
        readme = (ut / "README-for-claude-design.md").read_text("utf-8")
        for ord_ in ("data-slot", "A4", "9 pt", "tabeller", "bilder av text", "lugn, saklig, varm"):
            self.assertIn(ord_, readme)
        with zipfile.ZipFile(e["zip"]) as z:
            self.assertIn("README-for-claude-design.md", z.namelist())
            self.assertIn("komponenter/post.html", z.namelist())

    # ------------------------------------------------------------ redigerad tur och retur
    def test_2_redigerad_import_och_rendering(self):
        ut = Path(self.export["mapp"])
        red = redigera_som_claude_design((ut / "cv-exempel.html").read_text("utf-8"))
        self.assertNotIn('data-slot="period"', red)
        zip_p = self.tmp / "fran-claude-design.zip"
        with zipfile.ZipFile(zip_p, "w") as z:
            z.writestr("Mitt CV.html", red)
            for f in (ut / "fonts").glob("*.ttf"):
                z.write(f, f"fonts/{f.name}")
        res = design_import.importera(zip_p, self.home, namn="lugn")
        self.assertEqual(res["typ"], "cv")
        self.assertEqual(res["tokens_fran_design"].get("farg_accent"), "#7a3b2e")
        design = render.las_json(self.home / "design" / "design.json")
        self.assertEqual(design["layout"], "egen:lugn")
        self.assertEqual(design["tokens"]["farg_accent"], "#7a3b2e")
        self.assertLess(design["sektioner"].index("utbildning"), design["sektioner"].index("erfarenhet"))
        mall = (self.home / "design" / "mallar" / "lugn" / "mall.html").read_text("utf-8")
        self.assertIn('data-sektion="utbildning"', mall)  # återfunnen
        self.assertIn('data-slot="period"', mall)
        erf = mall.split('data-sektion="erfarenhet"', 1)[1].split("</section>", 1)[0]
        self.assertEqual(erf.count('data-repeat="punkter"'), 1)  # återfunnen punktmall
        self.assertEqual(erf.count('data-repeat="poster"'), 1)
        self.assertIn("cd-ram", mall)
        css = (self.home / "design" / "mallar" / "lugn" / "mall.css").read_text("utf-8")
        self.assertIn("@page", css)
        self.assertIn("break-inside: avoid", css)
        self.assertTrue((self.home / "design" / "mallar" / "lugn" / "versioner" / "v1" / "mall.html").exists())
        subprocess.run([sys.executable, str(PLUGIN / "scripts" / "validate.py"),
                        str(self.home / "design" / "design.json")], check=True, capture_output=True)

        for fil in ("cv-kort-sv.json", "cv-lang-sv.json", "cv-kort-en.json", "cv-lang-en.json"):
            with self.subTest(fil=fil):
                cv = render.las_json(FIX / fil)
                r = render.rendera("cv", cv, design, self.tmp / "ut", [FIX, self.home], stam=fil[:-5], pdf=False)
                self.assertEqual(r["layout"], "egen:lugn")
                h = Path(r["html"]).read_text("utf-8")
                ctx, _ = render.bygg_kontext(cv, design, [FIX], "cv")
                alla, _ = mall_kontroll.forvantat(ctx, "cv")
                self.assertEqual(mall_kontroll.tappat(alla, html_text(h)), [])
                if "kort" in fil:  # inget kvar från exemplets innehåll
                    self.assertNotIn("Senior kommunikationsstrateg", h)
                rub = ("Utbildning", "Erfarenhet") if cv["sprak"] == "sv" else ("Education", "Experience")
                self.assertLess(h.find(f"data-slot-rubrik>{rub[0]}<"), h.find(f"data-slot-rubrik>{rub[1]}<"),
                                "utbildning ska komma före erfarenhet")
                self.assertGreater(h.find(f"data-slot-rubrik>{rub[0]}<"), 0)
                self.assertIn("#7a3b2e", h)

    @unittest.skipUnless(har_pdf(), "ingen PDF-motor")
    def test_3_kontroll_och_bilder(self):
        if not (self.home / "design" / "mallar" / "lugn").exists():
            self.test_2_redigerad_import_och_rendering()
        # före: exemplet som det såg ut i paketet
        fore = self.bilder / "fore-claude-design.png"
        render.gor_bild(None, Path(self.export["cv_exempel"]), fore)
        k = mall_kontroll.kontrollera("lugn", self.home, self.bilder / "kontroll-lugn")
        self.assertFalse(k["blockerar"], k["rapport"])
        for f in k["fall"]:
            self.assertEqual(f["tappat"], [], f["id"])
            self.assertEqual(f["lasordning"], [], f["id"])
            if f["id"].startswith("cv-kort"):
                self.assertEqual(f["sidor"], 1, f["id"])
            self.assertLessEqual(f["sidor"], 3, f["id"])
        self.assertTrue(any(f.get("bild") for f in k["fall"]))
        self.assertIn("Allt innehåll kommer med", k["rapport"])
        # efter: hennes ansökan med den importerade mallen
        r = render.rendera("cv", render.las_json(self.mapp / "cv.json"),
                           render.las_json(self.home / "design" / "design.json"),
                           self.bilder, [self.mapp, self.home], stam="efter-import", bild=True)
        self.assertTrue(r["textlager"]["finns"])
        self.assertTrue(Path(r["bild"]).exists())

    # ------------------------------------------------------------ helt omärkt
    def test_4_omarkt_html_heuristik(self):
        ut = Path(self.export["mapp"])
        h = (ut / "cv-exempel.html").read_text("utf-8")
        omarkt = re.sub(r'\s(data-[\w-]+)(="[^"]*")?', "", h)
        omarkt = omarkt.replace('class="', 'class="x-')  # andra klassnamn, som från ett annat verktyg
        self.assertNotIn(" data-slot", omarkt)
        self.assertNotIn(" data-repeat", omarkt)
        f = self.tmp / "omarkt.html"
        f.write_text(omarkt, "utf-8")
        res = design_import.importera(f, self.home, namn="omarkt", uppdatera_design=False)
        s = res["slots_efter"]
        self.assertGreaterEqual(s["sektion"], 6)
        self.assertGreaterEqual(s["repeat"], 8)
        self.assertGreaterEqual(s["rubrik"], 6)
        for ord_ in ("namnet", "yrkestiteln", "kontaktraden (upprepas per uppgift)", "rollerna i Erfarenhet (upprepas)",
                     "punkterna i Erfarenhet", "listan i Kompetenser"):
            self.assertIn(ord_, res["hittat"])
        self.assertLessEqual(len(res["osakert"]), 2, res["osakert"])
        design = {**render.las_json(render.forval_path("konservativ")), "layout": "egen:omarkt"}
        for fil in ("cv-kort-en.json", "cv-lang-sv.json"):
            cv = render.las_json(FIX / fil)
            r = render.rendera("cv", cv, design, self.tmp / "ut-omarkt", [FIX, self.home], stam=fil[:-5], pdf=False)
            h = Path(r["html"]).read_text("utf-8")
            ctx, _ = render.bygg_kontext(cv, design, [FIX], "cv")
            alla, kedjor = mall_kontroll.forvantat(ctx, "cv")
            self.assertEqual(mall_kontroll.tappat(alla, html_text(h)), [], fil)
            self.assertEqual(mall_kontroll.lasordning(kedjor, html_text(h)), [], fil)
            if "kort" in fil:  # inget kvar från exemplets innehåll
                self.assertNotIn("Senior kommunikationsstrateg", h)

    def test_5_brev(self):
        ut = Path(self.export["mapp"])
        h = re.sub(r'\s(data-[\w-]+)(="[^"]*")?', "", (ut / "brev-exempel.html").read_text("utf-8"))
        f = self.tmp / "brev.html"
        f.write_text(h, "utf-8")
        res = design_import.importera(f, self.home, namn="omarkt", brev=True, uppdatera_design=False)
        self.assertEqual(res["typ"], "brev")
        self.assertEqual([x for x in res["osakert"] if x.startswith("Hittade")], [])
        design = {**render.las_json(render.forval_path("konservativ")), "layout": "egen:omarkt"}
        brev = render.las_json(FIX / "brev-en.json")
        r = render.rendera("brev", brev, design, self.tmp / "ut-brev", [FIX, self.home], pdf=False)
        h = Path(r["html"]).read_text("utf-8")
        ctx, _ = render.bygg_kontext(brev, design, [FIX], "brev")
        alla, _ = mall_kontroll.forvantat(ctx, "brev")
        self.assertEqual(mall_kontroll.tappat(alla, html_text(h)), [])
        kropp = html_text(h.split("<body", 1)[1])
        self.assertEqual(kropp.count(brev["person"]["namn"]), 2)  # huvud + underskrift

    # ------------------------------------------------------------ varianter
    def test_6_varianter(self):
        if not (self.home / "design" / "mallar" / "lugn").exists():
            self.test_2_redigerad_import_och_rendering()
        import design_tool
        h = ["--home", str(self.home)]
        for args in (["variant", "stram", "layout=klassisk", "farg_accent=#333333",
                      "sektioner=profil,erfarenhet,utbildning,kompetenser,sprak", "beskrivning=myndighet"],
                     ["variant", "kreativ", "layout=egen:lugn", "visa_foto=ja", "farg_accent=#9a4a2f"],
                     ["variant", "standard", "layout=egen:lugn", "--standard"]):
            with open(os.devnull, "w") as dn:
                stdout, sys.stdout = sys.stdout, dn
                try:
                    design_tool.main([*args, *h])
                finally:
                    sys.stdout = stdout
        design = render.las_json(self.home / "design" / "design.json")
        self.assertEqual(design["standardvariant"], "standard")
        self.assertEqual(set(design["varianter"]), {"stram", "kreativ", "standard"})
        r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "validate.py"), str(self.home / "design" / "design.json")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        cv = render.las_json(self.mapp / "cv.json")
        ut = self.tmp / "ut-var"
        # standard (ingen design_variant): egen mall
        r = render.rendera("cv", cv, design, ut, [self.mapp, self.home], stam="standard", pdf=False)
        self.assertEqual(r["layout"], "egen:lugn")
        # stram: inbyggd klassisk med grafit och utan kurser/ideellt i ordningen
        r = render.rendera("cv", {**cv, "design_variant": "stram"}, design, ut, [self.mapp, self.home], stam="stram", pdf=False)
        hs = Path(r["html"]).read_text("utf-8")
        self.assertEqual(r["layout"], "klassisk")
        self.assertIn("--farg-accent:#333333", hs)
        self.assertIn("Styrelseledamot", hs)  # sektioner utanför ordningen läggs sist, inget tappas
        # kreativ: egen mall med foto och terrakotta
        r = render.rendera("cv", {**cv, "design_variant": "kreativ"}, design, ut, [self.mapp, self.home], stam="kreativ", pdf=False)
        hk = Path(r["html"]).read_text("utf-8")
        self.assertIn("--farg-accent:#9a4a2f", hk)
        self.assertNotIn("Senior kommunikationsstrateg</h3>", hk.split("Senior kommunikationsstrateg", 1)[0])
        # okänd variant faller tillbaka på standard
        r = render.rendera("cv", {**cv, "design_variant": "finns-inte"}, design, ut, [self.mapp, self.home], stam="x", pdf=False)
        self.assertEqual(r["layout"], "egen:lugn")
        # cv.json med design_variant validerar
        p = self.tmp / "cv.json"
        p.write_text(json.dumps({**cv, "design_variant": "stram"}, ensure_ascii=False), "utf-8")
        r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "validate.py"), str(p)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


class Slotmotor(unittest.TestCase):
    def ctx(self, **andra):
        cv = render.las_json(FIX / "cv-kort-sv.json")
        cv.update(andra)
        return render.bygg_kontext(cv, render.las_json(render.forval_path("konservativ")), [FIX], "cv")[0], cv

    def test_escaping_och_lankar(self):
        ctx, _ = self.ctx()
        ctx["person"]["namn"] = 'Eva <img src=x onerror="alert(1)">'
        ctx["person"]["kontakt"].append({"text": "x", "url": None, "etikett": ""})
        mall = ('<h1 data-slot="person.namn"></h1><ul><li data-repeat="person.kontakt"><a data-slot="text" '
                'href="javascript:alert(1)">k</a></li></ul>')
        ut = mall_slots.fyll_mall(mall, ctx)
        self.assertIn("Eva &lt;img src=x onerror=&quot;alert(1)&quot;&gt;", ut)
        self.assertNotIn("javascript:", ut)
        self.assertIn('href="mailto:maja.lindqvist@example.se"', ut)

    def test_reservdelar_tappar_inget(self):
        ctx, cv = self.ctx()
        mall = '<main><h1 data-slot="person.namn"></h1><section data-sektion="erfarenhet"><div data-repeat="poster"><b data-slot="titel"></b></div></section></main>'
        ut = mall_kontroll.html_text(mall_slots.fyll_mall(mall, ctx))
        alla, _ = mall_kontroll.forvantat(ctx, "cv")
        self.assertEqual(mall_kontroll.tappat(alla, ut), [])

    def test_if_och_tomma_slots(self):
        ctx, _ = self.ctx()
        ut = mall_slots.fyll_mall('<img data-if="person.foto" data-slot="person.foto"><p data-slot="person.finns_ej">x</p>'
                                  '<p data-if="not person.foto">utan foto</p>', ctx)
        self.assertNotIn("<img", ut)
        self.assertNotIn("<p>x", ut)
        self.assertIn("utan foto", ut)


if __name__ == "__main__":
    unittest.main()
