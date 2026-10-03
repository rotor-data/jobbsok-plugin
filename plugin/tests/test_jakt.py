"""Tester för skillen jobbjakt (jakt_*.py).

Kör från repo-roten:  python3 -m unittest plugin/tests/test_jakt.py
Offline-testerna använder inbyggda fixturer. Live-testerna (klassen TestLive) skippas utan nät
eller när JOBBSOK_OFFLINE=1.
"""
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SKRIPT = HERE.parent / "scripts"
sys.path.insert(0, str(SKRIPT))

import jakt_arbetsgivare  # noqa: E402
import jakt_common as jc  # noqa: E402
import jakt_signaler  # noqa: E402
import jakt_titlar  # noqa: E402
import jakt_webbrecept as wr  # noqa: E402

PROFIL = HERE / "fixtures" / "home" / "profil"


def hit(rubrik, orgnr, namn, yrke="aRp4_qjZ_tPV", datum="2025-05-01T10:00:00", kommun="Uppsala"):
    return {"headline": rubrik, "employer": {"organization_number": orgnr, "name": namn},
            "occupation": {"concept_id": yrke}, "publication_date": datum,
            "workplace_address": {"municipality": kommun}}


HITS = [hit("Kommunikatör till Region Uppsala", "2321000024", "Region Uppsala"),
        hit("Vi söker en kommunikatör", "2120003005", "Uppsala kommun", datum="2026-08-24T09:00:00"),
        hit("Digital kommunikatör - webb", "2120003005", "Uppsala kommun"),
        hit("Content lead", "5560000001", "Acme AB"),
        hit("Content Lead – Stockholm", "5560000002", "Beta AB"),
        hit("Tomte", "5560000003", "Julmarknad AB")] + [hit("Tomte", "5560000003", "Julmarknad AB")] * 5


def falsk_api(url, params=None, home=None):
    params = params or {}
    if "autocomplete" in url:
        t = params.get("type")
        if t == "region":
            return [{"taxonomy/id": "zBon_eET_fFU", "taxonomy/preferred-label": "Uppsala län"}]
        return [{"taxonomy/id": "64i5_ex4_BP9", "taxonomy/preferred-label": "Kommunikationsstrateg"},
                {"taxonomy/id": "aRp4_qjZ_tPV", "taxonomy/preferred-label": "Informatör/Kommunikatör",
                 "taxonomy/alternative-labels": ["Informatör", "Kommunikatör"]}]
    if "graphql" in url:
        return {"data": {"concepts": [{
            "id": "aRp4_qjZ_tPV", "preferred_label": "Informatör/Kommunikatör",
            "related": [{"id": "x1", "type": "job-title", "preferred_label": "Content lead"},
                        {"id": "x2", "type": "job-title", "preferred_label": "Internkommunikatör"}],
            "substitutes": [{"id": "b3Jk_Gfs_oo9", "type": "occupation-name", "preferred_label": "Webbredaktör"}],
            "broader": [{"id": "k1Nx_auG_sNh", "preferred_label": "Informatörer, kommunikatörer och PR-specialister",
                         "narrower": [{"id": "64i5_ex4_BP9", "preferred_label": "Kommunikationsstrateg"},
                                      {"id": "aRp4_qjZ_tPV", "preferred_label": "Informatör/Kommunikatör"}]}]}]}}
    if params.get("stats"):
        typ = params["stats"]
        if typ == "occupation-group":
            return {"total": {"value": 100}, "stats": [{"type": typ, "values": [
                {"term": "Informatörer", "concept_id": "k1Nx_auG_sNh", "count": 60},
                {"term": "Marknadsförare", "concept_id": "g2", "count": 40}]}]}
        return {"total": {"value": 50}, "stats": [{"type": typ, "values": [
            {"term": "Informatör/Kommunikatör", "concept_id": "aRp4_qjZ_tPV", "count": 40},
            {"term": "Marknadskommunikatör", "concept_id": "jtGy_ZBL_NEP", "count": 10}]}]}
    if params.get("q") and not params.get("occupation-name") and not params.get("occupation-group"):
        # hitta_orgnr för likar
        return {"total": {"value": 2}, "hits": [hit("x", "2120003005", "Uppsala kommun")] * 2}
    off = params.get("offset", 0)
    h = HITS if off == 0 else []
    if "jobsearch" in url:
        h = HITS[1:2] if off == 0 else []
    return {"total": {"value": len(HITS)}, "hits": h}


def lasj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def kor(func, argv):
    buf = io.StringIO()
    with mock.patch.object(jc, "api", side_effect=falsk_api), redirect_stdout(buf):
        func(argv)
    return json.loads(buf.getvalue())


class Hem(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="jakt-")
        shutil.copytree(PROFIL, os.path.join(self.home, "profil"))

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def skript(self, namn, *args, stdin=None):
        r = subprocess.run([sys.executable, str(SKRIPT / namn), "--home", self.home] + list(args),
                           input=stdin, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout


class TestCommon(unittest.TestCase):
    def test_rubrik_till_titel(self):
        f = jc.rubrik_till_titel
        self.assertEqual(f("Vi söker en kommunikatör till Region X"), "kommunikatör")
        self.assertEqual(f("Adeccos kund Swedavia söker en kommunikationskoordinator"), "kommunikationskoordinator")
        self.assertEqual(f("Content Lead – Stockholm"), "content lead")
        self.assertEqual(f("Kommunikatör sökes"), "kommunikatör")
        self.assertEqual(f("Digital kommunikatör, 50%"), "digital kommunikatör")
        self.assertIsNone(f(""))

    def test_basta_traff_foredrar_exakt_alternativ(self):
        k = falsk_api("autocomplete", {"type": "occupation-name"})
        k = [(x["taxonomy/id"], x["taxonomy/preferred-label"], x.get("taxonomy/alternative-labels", [])) for x in k]
        self.assertEqual(jc.basta_traff("kommunikatör", k)[0], "aRp4_qjZ_tPV")

    def test_ar_id(self):
        self.assertTrue(jc.ar_id("aRp4_qjZ_tPV"))
        self.assertFalse(jc.ar_id("kommunikatör"))


class TestTitlar(unittest.TestCase):
    def test_titlar_och_yrken(self):
        ut = kor(jakt_titlar.main, ["--roll", "kommunikatör", "--home", tempfile.gettempdir()])
        titlar = {t["titel"]: t for t in ut["titlar"]}
        self.assertIn("content lead", titlar)
        self.assertEqual(titlar["content lead"]["arbetsgivare"], 2)
        # 6 tomte-annonser från en arbetsgivare rankas under titlar med flera arbetsgivare
        namn = [t["titel"] for t in ut["titlar"]]
        self.assertLess(namn.index("content lead"), namn.index("tomte"))
        self.assertIn("internkommunikatör", titlar)          # från taxonomin
        yrken = {y["namn"]: y for y in ut["yrken"]}
        self.assertIn("Webbredaktör", yrken)
        self.assertIn("utbytbart", yrken["Webbredaktör"]["relation"])
        self.assertIn("samma yrkesgrupp", yrken["Kommunikationsstrateg"]["relation"])
        self.assertIn("content lead", ut["sokord_forslag"])
        self.assertNotIn("tomte", ut["sokord_forslag"])


class TestArbetsgivare(unittest.TestCase):
    def test_region(self):
        ut = kor(jakt_arbetsgivare.main, ["region", "--roll", "kommunikatör", "--region", "Uppsala län",
                                          "--home", tempfile.gettempdir()])
        ag = {a["namn"]: a for a in ut["arbetsgivare"]}
        self.assertEqual(ag["Uppsala kommun"]["annonser"], 2)
        self.assertEqual(ag["Uppsala kommun"]["oppna_nu"], 1)
        self.assertEqual(ag["Uppsala kommun"]["senaste"], "2026-08-24")
        self.assertEqual(ag["Uppsala kommun"]["orgnr"], "2120003005")
        self.assertEqual(ut["arbetsgivare"][0]["namn"], "Julmarknad AB")   # flest annonser

    def test_likar(self):
        ut = kor(jakt_arbetsgivare.main, ["likar", "--bolag", "Uppsala kommun", "--kallor-forslag",
                                          "--home", tempfile.gettempdir()])
        self.assertEqual(ut["orgnr"], "2120003005")
        namn = [x["namn"] for x in ut["likar"]]
        self.assertNotIn("Uppsala kommun", namn)
        self.assertIn("Region Uppsala", namn)
        self.assertTrue(all(0 <= x["likhet"] <= 1 for x in ut["likar"]))
        self.assertIn("kalla_lagg_till.py", ut["kallor_forslag"]["instruktion"])


RSS = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>Cision</title>
<item><title>Acme AB nyanställer 40 personer i Uppsala</title><link>https://news.cision.com/se/acme/r/acme-nyanstaller,c1</link>
<description><![CDATA[<p>Acme <b>expanderar</b> och öppnar nytt kontor.</p>]]></description><pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Beta AB kallar till årsstämma</title><link>https://news.cision.com/se/beta/r/arsstamma,c2</link>
<description>Kallelse</description><pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>Gamma utser ny vd</title><link>https://news.cision.com/se/gamma/r/ny-vd,c3</link>
<description>x</description><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Delta förvärvar Epsilon</title>
<link href="https://delta.se/press/1"/><updated>2026-09-20T08:00:00Z</updated><summary>Förvärv</summary></entry></feed>"""


class TestSignaler(unittest.TestCase):
    def test_tolka_rss_och_atom(self):
        p = jakt_signaler.tolka_flode(RSS)
        self.assertEqual(len(p), 3)
        self.assertEqual(p[0]["url"], "https://news.cision.com/se/acme/r/acme-nyanstaller,c1")
        self.assertNotIn("<b>", p[0]["text"])
        a = jakt_signaler.tolka_flode(ATOM)
        self.assertEqual(a[0]["url"], "https://delta.se/press/1")
        self.assertEqual(jakt_signaler.klassa(a[0]["titel"]), ["förvärv"])

    def test_klassa(self):
        s = jakt_signaler.klassa("Acme nyanställer och öppnar nytt kontor")
        self.assertIn("nyanställer", s)
        self.assertIn("nytt_kontor", s)
        self.assertIn("ny_ledning", jakt_signaler.klassa("Bolaget utser Anna Svensson till ny vd"))
        self.assertEqual(jakt_signaler.klassa("Kallelse till årsstämma"), [])

    def test_main_filtrerar_och_knyter(self):
        home = tempfile.mkdtemp()
        try:
            with mock.patch.object(jakt_signaler, "tillats", return_value=True), \
                 mock.patch.object(jakt_signaler.sc, "http", return_value=(200, RSS, {})):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    jakt_signaler.main(["--cision-slug", "acme", "--bolag", "Acme", "--dagar", "3650",
                                        "--rss", "https://mfn.se/all/a/x.rss", "--home", home])
            ut = json.loads(buf.getvalue())
            titlar = [s["titel"] for s in ut["signaler"]]
            self.assertIn("Acme AB nyanställer 40 personer i Uppsala", titlar)
            self.assertNotIn("Beta AB kallar till årsstämma", titlar)
            self.assertTrue(ut["signaler"][0]["malbolag"])
            self.assertEqual(ut["hoppade"][0]["url"], "https://mfn.se/all/a/x.rss")
            sparat = lasj(os.path.join(home, "sok", "signaler.json"))
            self.assertTrue(sparat["signaler"])
            # --nya: inget nytt andra gången
            with mock.patch.object(jakt_signaler, "tillats", return_value=True), \
                 mock.patch.object(jakt_signaler.sc, "http", return_value=(200, RSS, {})):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    jakt_signaler.main(["--cision-slug", "acme", "--dagar", "3650", "--nya", "--home", home])
            self.assertEqual(json.loads(buf.getvalue())["signaler"], [])
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_robots_blockerar(self):
        jakt_signaler._robots.clear()
        robots = "User-agent: *\nDisallow: *.rss$\nDisallow: /press/\n"
        with mock.patch.object(jakt_signaler.sc, "http", return_value=(200, robots, {})):
            self.assertFalse(jakt_signaler.tillats("https://exempel.se/press/feed"))
            self.assertTrue(jakt_signaler.tillats("https://exempel.se/nyheter/feed"))
        jakt_signaler._robots.clear()


class TestWebbrecept(Hem):
    def test_fragor_ur_profil(self):
        ut = self.skript("jakt_webbrecept.py", "skapa", "komm", "--max-fragor", "30", "--oppen")
        r = lasj(os.path.join(self.home, "sok", "webbrecept", "komm.json"))
        fr = [f["fraga"] for f in r["fragor"]]
        self.assertIn('site:teamtailor.com "kommunikatör" "Uppsala"', fr)
        self.assertTrue(any(f.startswith("site:varbi.com") for f in fr))
        self.assertTrue(any("sverigeskommunikatorer.se" in f for f in fr))   # nisch ur profilen
        self.assertFalse(any("blocket" in f or "stepstone" in f for f in fr))
        self.assertTrue(any("-site:linkedin.com" in f for f in fr))
        self.assertIn("antal_fragor", ut)

    def test_varvning_och_tak(self):
        fr = wr.skapa_fragor(["a", "b"], ["Uppsala", "Stockholm"], ["teamtailor", "lever"], [], False, 3)
        self.assertEqual(len(fr), 3)
        self.assertEqual([f["titel"] for f in fr], ["a", "b", "a"])
        self.assertIn('("Uppsala" OR "Stockholm")', fr[0]["fraga"])

    def test_normalisera(self):
        rec = {"namn": "x", "hypotes": "h-001", "orter": ["Uppsala"]}
        poster, avv = wr.normalisera([
            {"url": "https://acme.teamtailor.com/jobs/123-komm?utm_source=g", "titel": "Kommunikatör - Acme",
             "snippet": "Placering Uppsala"},
            {"url": "https://se.indeed.com/viewjob?jk=1", "titel": "x"},
            {"url": "https://acme.teamtailor.com/jobs", "titel": "Lediga jobb"},
            {"url": "https://jobs.lever.co/beta/0a1b2c3d-1111-2222-3333-444455556666", "titel": "Content Lead",
             "snippet": "Remote"},
            {"url": "https://uu.varbi.com/se/what:job/jobID:123/", "titel": "Kommunikatör"},
        ], rec)
        self.assertEqual(len(poster), 3)
        p = poster[0]
        self.assertEqual(p["url"], "https://acme.teamtailor.com/jobs/123-komm")
        self.assertEqual(p["arbetsgivare"], "Acme")
        self.assertEqual(p["titel"], "Kommunikatör")
        self.assertEqual(p["ort"], "Uppsala")
        self.assertEqual(p["hittad_via"], "h-001")
        self.assertEqual(poster[1]["arbetsgivare"], "Beta")
        self.assertEqual(poster[1]["distans"], "distans")
        self.assertEqual(poster[2]["arbetsgivare"], "Uu")
        self.assertEqual(len(avv), 2)


class TestHypoteser(Hem):
    def test_crud_ingest_utbyte(self):
        ny = json.loads(self.skript("jakt_hypoteser.py", "ny", "--typ", "alternativ_titel", "--beskrivning",
                                    "Content lead i Uppsala", "--metod", "webbrecept", "--param", "titel=content lead",
                                    "--param", "max=5"))
        hid = ny["skapad"]["id"]
        self.assertEqual(hid, "h-001")
        h = json.loads(self.skript("jakt_hypoteser.py", "visa", hid))
        self.assertEqual(h["parametrar"], {"titel": "content lead", "max": 5})
        self.assertEqual(h["status"], "aktiv")
        self.skript("jakt_hypoteser.py", "andra", hid, "--status", "pausad")
        self.assertEqual(json.loads(self.skript("jakt_hypoteser.py", "lista", "--status", "pausad"))[0]["id"], hid)
        self.skript("jakt_hypoteser.py", "andra", hid, "--status", "aktiv")
        poster = [{"titel": "Content lead", "arbetsgivare": "Acme", "url": f"https://acme.teamtailor.com/jobs/{i}"}
                  for i in range(6)]
        ing = json.loads(self.skript("jakt_hypoteser.py", "ingest", hid, stdin=json.dumps(poster)))
        self.assertEqual(ing["nya"], 6)
        c = sqlite3.connect(os.path.join(self.home, "sok", "jobb.sqlite"))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM jobb WHERE hittad_via=?", (hid,)).fetchone()[0], 6)
        for uid in ing["uid"]:
            subprocess.run([sys.executable, str(SKRIPT / "lista.py"), "satt", uid, "nej", "--orsak", "för junior",
                            "--home", self.home], check=True, capture_output=True)
        self.skript("jakt_hypoteser.py", "korning", hid, "--fynd", "0", "--anteckning", "manuell")
        u = json.loads(self.skript("jakt_hypoteser.py", "utbyte"))
        self.assertEqual(u["forslag"][0]["forslag"], "beskär")
        self.assertEqual(u["orsaker"][hid]["nej"], ["för junior"])
        h = json.loads(self.skript("jakt_hypoteser.py", "visa", hid))
        self.assertEqual(h["utbyte"]["nej"], 6)
        self.assertEqual(len(h["korningar"]), 2)
        self.skript("jakt_hypoteser.py", "ta-bort", hid)
        self.assertEqual(json.loads(self.skript("jakt_hypoteser.py", "lista")), [])
        b = lasj(os.path.join(self.home, "sok", "hypoteser_borttagna.json"))
        self.assertEqual(b["hypoteser"][0]["id"], hid)
        ny2 = json.loads(self.skript("jakt_hypoteser.py", "ny", "--typ", "joker", "--beskrivning", "x",
                                     "--metod", "manuell"))
        self.assertEqual(ny2["skapad"]["id"], "h-002")   # id återanvänds inte

    def test_webbrecept_ingest_loggar(self):
        self.skript("jakt_hypoteser.py", "ny", "--typ", "webbjakt", "--beskrivning", "ATS", "--metod", "webbrecept",
                    "--webbrecept", "ats")
        self.skript("jakt_webbrecept.py", "skapa", "ats", "--hypotes", "h-001", "--titel", "kommunikatör",
                    "--ort", "Uppsala")
        res = [{"url": "https://acme.teamtailor.com/jobs/1-k", "titel": "Kommunikatör", "snippet": "Uppsala"}]
        ut = json.loads(self.skript("jakt_webbrecept.py", "normalisera", "ats", "--ingest", stdin=json.dumps(res)))
        self.assertEqual(ut["nya"], 1)
        r = lasj(os.path.join(self.home, "sok", "webbrecept", "ats.json"))
        self.assertEqual(r["korningar"][-1]["nya"], 1)
        h = json.loads(self.skript("jakt_hypoteser.py", "visa", "h-001"))
        self.assertEqual(h["korningar"][-1]["fynd"], 1)


def natet_finns():
    if os.environ.get("JOBBSOK_OFFLINE") == "1":
        return False
    try:
        socket.create_connection(("jobsearch.api.jobtechdev.se", 443), timeout=5).close()
        return True
    except OSError:
        return False


@unittest.skipUnless(natet_finns(), "inget nät (eller JOBBSOK_OFFLINE=1)")
class TestLive(Hem):
    def test_titlar_kommunikator(self):
        ut = json.loads(self.skript("jakt_titlar.py", "--roll", "kommunikatör", "--max", "200", "--antal", "15"))
        self.assertEqual(ut["uppslag"][0]["yrke_id"], "aRp4_qjZ_tPV")
        self.assertTrue(any(t["titel"] == "kommunikatör" for t in ut["titlar"]))
        self.assertGreater(len(ut["yrken"]), 3)

    def test_arbetsgivare_uppsala(self):
        ut = json.loads(self.skript("jakt_arbetsgivare.py", "region", "--roll", "kommunikatör",
                                    "--region", "Uppsala län", "--antal", "10"))
        self.assertGreater(ut["annonser_totalt"], 0)
        self.assertTrue(ut["arbetsgivare"][0]["orgnr"])

    def test_signaler_cision(self):
        ut = json.loads(self.skript("jakt_signaler.py", "--sok", "nyanställer", "--dagar", "365", "--antal", "5"))
        self.assertEqual(ut["fel"], [])


if __name__ == "__main__":
    unittest.main()
