"""Tester för render.py och design_tool.py.

Kör: python3 -m unittest discover plugin/tests -p 'test_render.py'
HTML byggs alltid. PDF-testerna skippas om ingen PDF-motor finns.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN / "scripts"))
import render  # noqa: E402

FIX = PLUGIN / "tests" / "fixtures" / "cv-exempel"
FORVAL = sorted(p.stem for p in (PLUGIN / "templates" / "design-forval").glob("*.json"))


def las(n):
    return render.las_json(FIX / n)


def design(layout, **tokens):
    d = render.las_json(render.forval_path("konservativ"))
    d["layout"] = layout
    d["tokens"].update(tokens)
    return d


def har_pdf_motor():
    return bool(render._chrome()) or any(fn.__name__ != "pdf_chrome" and _importerbar(n) for n, fn in render.MOTORER)


def _importerbar(namn):
    try:
        __import__({"playwright": "playwright", "weasyprint": "weasyprint"}.get(namn, "__nope__"))
        return True
    except Exception:
        return False


def text_ur_html(h):
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


class Mallmotor(unittest.TestCase):
    def test_escaping(self):
        ut = render.fyll("<p>{{ x }}</p><p>{{ y|raw }}</p>", {"x": '<script>alert("a")</script>&', "y": "<b>ok</b>"})
        self.assertIn("&lt;script&gt;alert(&quot;a&quot;)&lt;/script&gt;&amp;", ut)
        self.assertNotIn("<script>", ut)
        self.assertIn("<b>ok</b>", ut)

    def test_if_for_include_loop(self):
        ut = render.fyll("{% for a in l %}{{ a.n }}{% if not loop.last %},{% endif %}{% endfor %}"
                         "{% if tom %}X{% else %}Y{% endif %}", {"l": [{"n": 1}, {"n": 2}], "tom": []})
        self.assertEqual(ut, "1,2Y")

    def test_saknade_varden_ger_tomt(self):
        self.assertEqual(render.fyll("[{{ a.b.c }}]", {}), "[]")

    def test_trasig_mall(self):
        with self.assertRaises(render.MallFel):
            render.fyll("{% if x %}utan slut", {})

    def test_cv_escapar_innehall_och_farliga_lankar(self):
        cv = las("cv-kort-sv.json")
        cv["person"]["namn"] = 'Eva <img src=x onerror="alert(1)">'
        cv["person"]["lankar"] = [{"etikett": "x", "url": "javascript:alert(1)"}]
        cv["sektioner"][0]["poster"][0]["punkter"] = ["Ökade <b>allt</b> & mer"]
        with tempfile.TemporaryDirectory() as t:
            r = render.rendera("cv", cv, design("klassisk"), Path(t), [FIX], pdf=False)
            h = Path(r["html"]).read_text("utf-8")
        self.assertNotIn("<img src=x", h)
        self.assertNotIn("javascript:", h)
        self.assertIn("Ökade &lt;b&gt;allt&lt;/b&gt; &amp; mer", h)


class HtmlAllaLayouter(unittest.TestCase):
    """HTML byggs alltid: alla layouter × kort/lång × sv/en."""

    def test_matris(self):
        with tempfile.TemporaryDirectory() as t:
            for layout in render.LAYOUTER:
                for fil in ("cv-kort-sv.json", "cv-kort-en.json", "cv-lang-sv.json", "cv-lang-en.json"):
                    with self.subTest(layout=layout, fil=fil):
                        cv = las(fil)
                        r = render.rendera("cv", cv, design(layout), Path(t), [FIX], stam=f"{layout}-{fil}", pdf=False)
                        h = Path(r["html"]).read_text("utf-8")
                        txt = text_ur_html(h)
                        self.assertIn(f'lang="{cv["sprak"]}"', h)
                        self.assertIn(cv["person"]["namn"], txt)
                        for s in cv["sektioner"]:
                            for p in s.get("poster", []):
                                if isinstance(p, dict):
                                    self.assertIn(render.html.escape(p["titel"], quote=True), h)
                        rub = "Erfarenhet" if cv["sprak"] == "sv" else "Experience"
                        self.assertIn(rub, txt)
                        self.assertNotIn("{{", h)
                        self.assertNotIn("{%", h)
                        self.assertIn("@page{size:A4", h)

    def test_rubriker_foljer_sprak(self):
        cv = las("cv-kort-en.json")  # rubriker saknas i fixturen och fylls i efter sprak
        ctx, _ = render.bygg_kontext(cv, design("klassisk"), [FIX], "cv")
        self.assertEqual([s["rubrik"] for s in ctx["sektioner"]][:3], ["Profile", "Experience", "Education"])

    def test_sektionsordning_och_okanda_sist(self):
        cv = las("cv-kort-sv.json")
        cv["sektioner"].append({"typ": "text", "rubrik": "Hobbyer", "text": "Rodd"})
        d = design("klassisk")
        d["sektioner"] = ["utbildning", "erfarenhet"]
        ctx, varn = render.bygg_kontext(cv, d, [FIX], "cv")
        nycklar = [s["nyckel"] for s in ctx["sektioner"]]
        self.assertEqual(nycklar[:2], ["utbildning", "erfarenhet"])
        self.assertIn("Hobbyer", [s["rubrik"] for s in ctx["sektioner"]])
        self.assertTrue(any("lades sist" in v for v in varn))

    def test_sidokolumn_delar_upp(self):
        ctx, _ = render.bygg_kontext(las("cv-kort-sv.json"), design("sidokolumn"), [FIX], "cv")
        self.assertEqual({s["nyckel"] for s in ctx["sida"]}, {"kompetenser", "sprak"})
        self.assertNotIn("kompetenser", {s["nyckel"] for s in ctx["huvud"]})

    def test_foto_valfritt(self):
        cv = las("cv-kort-sv.json")
        ctx, _ = render.bygg_kontext(cv, design("portratt"), [FIX], "cv")
        self.assertTrue(ctx["person"]["foto"].startswith("data:image/svg+xml"))
        cv["person"]["foto"] = None
        with tempfile.TemporaryDirectory() as t:
            r = render.rendera("cv", cv, design("portratt"), Path(t), [FIX], pdf=False)
            self.assertNotIn('class="foto"', Path(r["html"]).read_text("utf-8"))
        ctx, _ = render.bygg_kontext(las("cv-kort-sv.json"), design("klassisk", visa_foto=False), [FIX], "cv")
        self.assertIsNone(ctx["person"]["foto"])

    def test_trasiga_tokens_klampas(self):
        d = design("okand", storlek_brod_pt="stor", farg_accent="röd", marginal_mm=99)
        varn = render.granska_design(d)
        self.assertTrue(varn)
        with tempfile.TemporaryDirectory() as t:
            r = render.rendera("cv", las("cv-kort-sv.json"), d, Path(t), [FIX], pdf=False)
            h = Path(r["html"]).read_text("utf-8")
        self.assertIn("--marginal:30.0mm", h)
        self.assertEqual(r["layout"], "klassisk")

    def test_lag_kontrast_varnas(self):
        self.assertTrue(any("kontrast" in v for v in render.granska_design(design("klassisk", farg_text="#bbbbbb"))))

    def test_forval_ar_rena(self):
        for namn in FORVAL:
            with self.subTest(forval=namn):
                self.assertEqual(render.granska_design(render.las_json(render.forval_path(namn))), [])

    def test_brev_html(self):
        with tempfile.TemporaryDirectory() as t:
            for fil in ("brev-sv.json", "brev-en.json"):
                b = las(fil)
                r = render.rendera("brev", b, design("klassisk"), Path(t), [FIX], stam=fil, pdf=False)
                txt = text_ur_html(Path(r["html"]).read_text("utf-8"))
                self.assertIn(b["stycken"][0][:40], txt)
                self.assertIn(b["halsning"], txt)


@unittest.skipUnless(har_pdf_motor(), "ingen PDF-motor (Chrome/Playwright/WeasyPrint) finns")
class Pdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def rendera(self, typ, fil, d, stam):
        return render.rendera(typ, las(fil), d, Path(self.tmp), [FIX], stam=stam)

    def test_kort_cv_en_sida_alla_layouter(self):
        for layout in render.LAYOUTER:
            for fil in ("cv-kort-sv.json", "cv-kort-en.json"):
                with self.subTest(layout=layout, fil=fil):
                    r = self.rendera("cv", fil, design(layout), f"k-{layout}-{fil}")
                    self.assertNotEqual(r["motor"], "html")
                    self.assertEqual(r["sidor"], 1)
                    self.assertFalse(r["overflow"])
                    self.assertTrue(r["textlager"]["finns"])

    def test_langt_cv_max_tva_sidor_klassisk_och_kompakt(self):
        for layout in ("klassisk", "kompakt"):
            for fil in ("cv-lang-sv.json", "cv-lang-en.json"):
                with self.subTest(layout=layout, fil=fil):
                    r = self.rendera("cv", fil, render.las_json(render.forval_path(
                        "konservativ" if layout == "klassisk" else "kompakt")), f"l-{layout}-{fil}")
                    self.assertIn(r["sidor"], (1, 2))

    def test_overflow_flaggas(self):
        cv = las("cv-lang-sv.json")
        cv["sektioner"][0]["poster"] *= 3
        r = render.rendera("cv", cv, design("klassisk"), Path(self.tmp), [FIX], stam="overflow")
        self.assertGreater(r["sidor"], 2)
        self.assertTrue(r["overflow"])
        self.assertTrue(any("sidor" in v for v in r["varningar"]))

    def test_brev_en_sida(self):
        for fil in ("brev-sv.json", "brev-en.json"):
            r = self.rendera("brev", fil, design("klassisk"), f"b-{fil}")
            self.assertEqual(r["sidor"], 1)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext saknas")
    def test_lasordning_sidokolumn(self):
        r = self.rendera("cv", "cv-kort-sv.json", design("sidokolumn"), "ordning")
        txt = subprocess.run(["pdftotext", r["pdf"], "-"], capture_output=True, text=True).stdout
        self.assertLess(txt.index("Maja Lindqvist"), txt.index("Kommunikationsstrateg"))
        self.assertLess(txt.index("Kommunikationsstrateg"), txt.index("Kommunikatör"))
        self.assertIn("Region Uppsala", txt)

    def test_sidantal_utan_pdftotext(self):
        r = self.rendera("cv", "cv-kort-sv.json", design("klassisk"), "sid")
        self.assertEqual(render.sidantal(Path(r["pdf"])), 1)

    def test_forslag_och_jamforelse(self):
        ut = Path(self.tmp) / "forslag"
        res = render.kor_forslag(str(FIX / "cv-kort-sv.json"), ["konservativ", "modern", "varm"], ut,
                                 Path(self.tmp), bild=False)
        self.assertEqual(len(res["forslag"]), 3)
        sida = Path(res["jamforelse"]).read_text("utf-8")
        self.assertEqual(sida.count('class="kort"'), 3)


class Weasy(unittest.TestCase):
    def test_weasy_html_blandar_farg_och_lagger_till_css(self):
        h = ('<html><head><style>:root{--farg-accent: #2f5d62;} .x{border:1pt solid color-mix(in srgb, '
             'var(--farg-accent) 50%, #fff)}</style></head><body></body></html>')
        ut = render.weasy_html(h)
        self.assertNotIn("color-mix", ut)
        self.assertIn("#97aeb0", ut)  # 50 % av #2f5d62 mot vitt
        self.assertIn(".lay-kompakt .post", ut)

    def test_tvingad_motor(self):
        with tempfile.TemporaryDirectory() as t, unittest.mock.patch.dict(os.environ, {"JOBBSOK_PDF_MOTOR": "finnsinte"}):
            r = render.rendera("cv", las("cv-kort-sv.json"), design("klassisk"), Path(t), [FIX], stam="x")
            self.assertEqual(r["motor"], "html")

    @unittest.skipUnless(_importerbar("weasyprint"), "WeasyPrint saknas")
    def test_weasyprint_sidor_och_text(self):
        with tempfile.TemporaryDirectory() as t, unittest.mock.patch.dict(os.environ, {"JOBBSOK_PDF_MOTOR": "weasyprint"}):
            for layout in render.LAYOUTER:
                r = render.rendera("cv", las("cv-kort-sv.json"), design(layout), Path(t), [FIX], stam=layout)
                self.assertEqual((r["motor"], r["sidor"], r["overflow"]), ("weasyprint", 1, False), layout)
                self.assertTrue(r["textlager"]["finns"])
            cv = las("cv-lang-sv.json")
            cv["sektioner"][0]["poster"] *= 3
            r = render.rendera("cv", cv, design("klassisk"), Path(t), [FIX], stam="lang")
            self.assertTrue(r["overflow"])


class Cli(unittest.TestCase):
    def test_html_fallback_utan_motor(self):
        with tempfile.TemporaryDirectory() as t:
            env = {**os.environ, "JOBBSOK_PDF_MOTOR": "ingen", "JOBBSOK_HOME": t}
            out = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "render.py"), "cv",
                                  str(FIX / "cv-kort-sv.json"), "--out", t], capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            r = json.loads(out.stdout)
            self.assertEqual(r["motor"], "html")
            self.assertIn("Skriv ut", r["instruktion"])
            self.assertTrue(Path(r["html"]).exists())

    def test_design_tool_versioner(self):
        tool = [sys.executable, str(PLUGIN / "scripts" / "design_tool.py")]
        with tempfile.TemporaryDirectory() as t:
            env = {**os.environ, "JOBBSOK_HOME": t}
            kor = lambda *a: subprocess.run(tool + list(a), capture_output=True, text=True, env=env)  # noqa: E731
            self.assertEqual(kor("init", "--forval", "konservativ").returncode, 0)
            r = json.loads(kor("set", "farg_accent=#9a4a2f", "storlek_brod_pt=10,5").stdout)
            self.assertEqual(r["version"], 2)
            self.assertEqual(r["tokens"]["storlek_brod_pt"], 10.5)
            self.assertNotEqual(kor("set", "hittepa=1").returncode, 0)
            self.assertNotEqual(kor("layout", "fyrkantig").returncode, 0)
            r = json.loads(kor("aterstall", "1").stdout)
            self.assertEqual(r["tokens"]["farg_accent"], "#2f5d62")
            self.assertEqual(r["version"], 3)
            v = Path(t) / "design" / "versioner"
            self.assertEqual(sorted(p.name for p in v.iterdir()), ["design-v1.json", "design-v2.json", "design-v3.json"])
            self.assertEqual(len(json.loads(kor("historik").stdout)["historik"]), 3)


if __name__ == "__main__":
    unittest.main()
