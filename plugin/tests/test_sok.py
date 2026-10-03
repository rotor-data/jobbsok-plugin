"""Tester för sökskripten (fetch, ingest, dedupe, score, lista, utbyte, upptack_ats, kalla_lagg_till).

Kör: python3 -m unittest discover plugin/tests -p 'test_sok.py'
Fixturer i fixtures/sok/ är riktiga, avkortade svar från JobTech, Lever och Teamtailor (2026-10-01).
Live-testet skippas utan nät.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import warnings
from unittest import mock

warnings.simplefilter("ignore", ResourceWarning)  # sqlite-anslutningar stängs vid processens slut

HIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIT, "..", "scripts"))

import dedupe  # noqa: E402
import fetch  # noqa: E402
import kalla_lagg_till  # noqa: E402
import lista  # noqa: E402
import score  # noqa: E402
import sok_common as sc  # noqa: E402
import upptack_ats  # noqa: E402
import utbyte  # noqa: E402

FIX = os.path.join(HIT, "fixtures", "sok")


def fix(namn):
    with open(os.path.join(FIX, namn), encoding="utf-8") as f:
        return f.read()


class FalskHttp:
    """Ersätter sc.http: svarar per URL-prefix och loggar anropen."""

    def __init__(self, svar):
        self.svar = svar
        self.anrop = []

    def __call__(self, url, **kw):
        self.anrop.append(url)
        for prefix, text in self.svar.items():
            if url.startswith(prefix):
                if isinstance(text, Exception):
                    raise text
                return 200, text() if callable(text) else text, {}
        raise sc.HttpFel(404, url)


class Bas(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="jobbsok-test-")
        os.makedirs(os.path.join(self.home, "sok", "recept"))
        sc._robots.clear()
        self.robots = mock.patch.object(sc, "robots_tillater", return_value=True)
        self.robots.start()

    def tearDown(self):
        sc.stang_db()
        self.robots.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def kallor(self, *k):
        sc.skriv_json(sc.sokv(self.home, "kallor.json"), {"schema_version": 1, "kallor": list(k)})

    def recept(self, namn, kallor, jobtech=None, senast=None):
        sc.skriv_json(sc.sokv(self.home, "recept", namn + ".json"), {
            "schema_version": 1, "namn": namn, "kallor": kallor, "jobtech": jobtech or {"q": "kommunikatör"},
            "filter": {"exkludera_ord": [], "exkludera_arbetsgivare": [], "min_poang": 0}, "senast_kord": senast})

    def rader(self):
        return {r["uid"]: r for r in sc.db(self.home).execute("SELECT * FROM jobb").fetchall()}


class TestAdaptrar(Bas):
    def test_jobtech_normalisering(self):
        d = json.loads(fix("jobtech_search.json"))
        p = fetch.jobtech_post(d["hits"][0])
        self.assertEqual(p["kalla_id"], "31531156")
        self.assertEqual(p["ort"], "Kalmar")
        self.assertEqual(p["kommun_id"], "Pnmg_SgP_uHQ")
        self.assertEqual(p["omfattning"], "heltid")
        self.assertIn(p["anstallningsform"], ("tillsvidare", "visstid"))
        self.assertTrue(p["deadline"].startswith("2026-10-11"))
        self.assertTrue(any(k["typ"] == "yrke" for k in p["kompetenser"]))

    def test_teamtailor(self):
        fh = FalskHttp({"https://career.teamtailor.com/jobs.rss": fix("teamtailor_jobs.rss")})
        with mock.patch.object(sc, "http", fh):
            poster, full = fetch.ad_teamtailor({"url": "https://career.teamtailor.com/jobs.rss", "namn": "TT"},
                                               {}, self.home, None)
        self.assertTrue(full)
        self.assertEqual(len(poster), 2)
        self.assertEqual(poster[0]["ort"], "London")
        self.assertEqual(poster[0]["distans"], 1)
        r = sc.normalisera(poster[0], "tt")
        self.assertTrue(r["utdrag"])
        self.assertLessEqual(len(r["utdrag"]), 300)

    def test_lever(self):
        fh = FalskHttp({"https://api.lever.co/v0/postings/leverdemo": fix("lever_postings.json")})
        with mock.patch.object(sc, "http", fh):
            poster, _ = fetch.ad_lever({"url": "https://jobs.lever.co/leverdemo", "namn": "Lever"}, {}, self.home, None)
        self.assertEqual(len(poster), 2)
        self.assertIn("mode=json", fh.anrop[0])
        self.assertEqual(poster[0]["distans"], 2)
        self.assertEqual(poster[0]["ort"], "Baltimore, MD")

    def test_rss_atom_och_wwr_titel(self):
        atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x1</id><title>Acme: Writer</title>'
                '<link href="https://e.org/1"/><updated>2026-09-30T10:00:00Z</updated><summary>Hej</summary>'
                '</entry></feed>')
        with mock.patch.object(sc, "http", FalskHttp({"https://e.org/feed": atom})):
            p, _ = fetch.ad_rss({"url": "https://e.org/feed", "namn": "X", "arbetsgivare_ur_titel": True},
                                {}, self.home, None)
        self.assertEqual((p[0]["arbetsgivare"], p[0]["titel"], p[0]["url"]), ("Acme", "Writer", "https://e.org/1"))

    def test_json_api_faltmappning(self):
        data = json.dumps([{"legal": "x"}, {"id": 7, "position": "Editor", "company": "Co", "url": "https://r/7",
                                            "date": "2026-09-30T00:00:00", "description": "<p>Text</p>"}])
        k = {"url": "https://r/api", "falt": {"id": "id", "titel": "position", "url": "url", "arbetsgivare": "company",
                                              "publicerad": "date", "text": "description"}, "distans": 2}
        with mock.patch.object(sc, "http", FalskHttp({"https://r/api": data})):
            p, _ = fetch.ad_json_api(k, {}, self.home, None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["titel"], "Editor")
        self.assertEqual(sc.normalisera(p[0], "r")["utdrag"], "Text")

    def test_sitemap_bara_nya_hamtas(self):
        sm = "<urlset><url><loc>https://h.io/jobs/aaa111</loc></url><url><loc>https://h.io/jobs/bbb222</loc></url></urlset>"
        sida = ('<script type="application/ld+json">{"@type":"JobPosting","title":"PM","hiringOrganization":'
                '{"name":"Start"},"jobLocation":{"address":{"addressLocality":"Stockholm","addressCountry":"Sweden"}},'
                '"description":"Bra jobb"}</script>')
        k = {"id": "hub", "typ": "sitemap", "namn": "Hub", "url": "https://h.io/sitemap.xml", "aktiv": True,
             "monster": r"/jobs/\w+$", "krav": "Sweden"}
        self.kallor(k)
        fh = FalskHttp({"https://h.io/sitemap.xml": sm, "https://h.io/jobs/": sida})
        with mock.patch.object(sc, "http", fh):
            r1 = fetch.kor_bevakade(self.home)
            n1 = len(fh.anrop)
            r2 = fetch.kor_bevakade(self.home)
        self.assertEqual(r1["kallor"][0]["nya"], 2)
        self.assertEqual(n1, 3)
        self.assertEqual(len(fh.anrop) - n1, 1, "andra körningen ska bara läsa sitemapen")
        self.assertEqual(r2["kallor"][0]["stangda"], 0)
        self.assertEqual({r["status"] for r in self.rader().values()}, {"ny"})


class TestInkrementellt(Bas):
    def test_published_after_och_senast_kord(self):
        self.kallor({"id": "af", "typ": "jobtech", "namn": "PB", "url": "", "aktiv": True})
        self.recept("r", ["af"])
        fh = FalskHttp({fetch.JOBTECH: fix("jobtech_search.json")})
        with mock.patch.object(sc, "http", fh):
            r1 = fetch.kor_recept(self.home, "r")
            self.assertNotIn("published-after", fh.anrop[0])
            rec = sc.las_json(sc.sokv(self.home, "recept", "r.json"))
            self.assertTrue(rec["senast_kord"])
            fetch.kor_recept(self.home, "r")
        self.assertIn("published-after", fh.anrop[-1])
        self.assertEqual(r1["kallor"][0]["nya"], 2)
        rows = self.rader()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["hittad_via"] == "r" for r in rows.values()))

    def test_natfel_ger_ingen_senast_kord(self):
        self.kallor({"id": "af", "typ": "jobtech", "namn": "PB", "url": "", "aktiv": True})
        self.recept("r", ["af"])
        with mock.patch.object(sc, "http", FalskHttp({fetch.JOBTECH: sc.NatFel("x")})):
            r = fetch.kor_recept(self.home, "r")
        self.assertFalse(r["ok"])
        self.assertTrue(r["natfel"])
        self.assertIsNone(sc.las_json(sc.sokv(self.home, "recept", "r.json"))["senast_kord"])

    def test_forsvunna_och_utgangna_stangs(self):
        self.kallor({"id": "tt", "typ": "teamtailor_rss", "namn": "TT", "url": "https://x.teamtailor.com/jobs.rss",
                     "aktiv": True})
        self.recept("r", ["tt"])
        full = fix("teamtailor_jobs.rss")
        en = full.split("<item>")[0] + "<item>" + full.split("<item>")[1].split("</item>")[0] + "</item></channel></rss>"
        aktuell = {"t": full}
        with mock.patch.object(sc, "http", FalskHttp({"https://x.teamtailor.com": lambda: aktuell["t"]})):
            fetch.kor_recept(self.home, "r")
            aktuell["t"] = en
            r = fetch.kor_recept(self.home, "r")
        self.assertEqual(r["kallor"][0]["stangda"], 1)
        c = sc.db(self.home)
        c.execute("UPDATE jobb SET deadline='2020-01-01' WHERE status='ny'")
        self.assertEqual(sc.stang_utgangna(c), 1)

    def test_status_bevaras_vid_upsert(self):
        c = sc.db(self.home)
        r = sc.normalisera({"kalla_id": "1", "titel": "A", "url": "u"}, "x")
        sc.upsert(c, self.home, [dict(r)])
        lista.satt(self.home, r["uid"], "intressant", "bra team", "kul,nära")
        sc.upsert(c, self.home, [sc.normalisera({"kalla_id": "1", "titel": "A2"}, "x")])
        rad = self.rader()[r["uid"]]
        self.assertEqual(rad["status"], "intressant")
        self.assertEqual(rad["titel"], "A2")
        self.assertEqual(rad["url"], "u")
        b = json.loads(rad["bedomning_json"])
        self.assertEqual((b["orsak"], b["taggar"]), ("bra team", ["kul", "nära"]))

    def test_migrering_av_gammal_tabell(self):
        p = sc.sokv(self.home, "jobb.sqlite")
        c = sqlite3.connect(p)
        c.execute(sc.SCHEMA.replace(", bedomning_json TEXT, hittad_via TEXT", ""))
        c.execute("INSERT INTO jobb(uid, titel) VALUES('x-1', 'Gammal')")
        c.commit()
        c.close()
        kol = {r[1] for r in sc.db(self.home).execute("PRAGMA table_info(jobb)")}
        self.assertTrue({"bedomning_json", "hittad_via"} <= kol)
        self.assertEqual(self.rader()["x-1"]["titel"], "Gammal")


class TestDedupe(Bas):
    def lagg(self, *poster):
        sc.upsert(sc.db(self.home), self.home, [sc.normalisera(p, p.pop("_k")) for p in poster])

    def test_tre_steg(self):
        lang = ("Vi söker en kommunikatör som vill driva vår interna och externa kommunikation framåt. "
                "Du skriver texter, ansvarar för webben och sociala medier och stöttar chefer i förändringsarbete. "
                "Tjänsten är placerad i Uppsala och du rapporterar till kommunikationschefen.")
        self.lagg(
            {"_k": "af", "kalla_id": "1", "titel": "Kommunikatör", "arbetsgivare": "Region Uppsala", "ort": "Uppsala",
             "url": "https://a/1", "text": lang, "deadline": "2026-12-01", "orgnr": "2321000255"},
            {"_k": "tt", "kalla_id": "x", "titel": "Kommunikatör", "arbetsgivare": "REGION UPPSALA", "ort": "Uppsala",
             "url": "https://b/x"},
            {"_k": "web", "kalla_id": "y", "titel": "Kommunikatör till regionen", "arbetsgivare": "Regionen",
             "url": "https://c/y", "text": lang + " Välkommen!"},
            {"_k": "web", "kalla_id": "z", "titel": "Annat", "url": "https://a/1/"},
            {"_k": "af", "kalla_id": "2", "titel": "Ekonom", "arbetsgivare": "Region Uppsala", "ort": "Uppsala",
             "text": "Helt annan annons om budget och redovisning."},
        )
        res = dedupe.dedupe(self.home)
        rows = self.rader()
        self.assertEqual(res["dubbletter"], 3)
        self.assertGreaterEqual(res["per_steg"][1], 1)
        self.assertGreaterEqual(res["per_steg"][2], 1)
        self.assertGreaterEqual(res["per_steg"][3], 1)
        self.assertIsNone(rows["af-1"]["dubblett_av"], "posten med mest info ska behållas")
        self.assertEqual(rows["tt-x"]["dubblett_av"], "af-1")
        self.assertIsNone(rows["af-2"]["dubblett_av"])

    def test_jaccard(self):
        a = dedupe.shingles("ett två tre fyra fem sex sju åtta nio tio")
        self.assertEqual(dedupe.jaccard(a, a), 1.0)
        self.assertLess(dedupe.jaccard(a, dedupe.shingles("helt andra ord i en annan mening här nu")), 0.1)


class TestScore(Bas):
    PREF = {"schema_version": 1,
            "riktningar": [{"namn": "K", "yrkes_id": ["Y1"], "sokord": ["kommunikatör"], "exkludera_ord": ["säljare"]}],
            "orter": [{"namn": "Uppsala", "kommun_id": "K1"}],
            "hårda_gränser": {"distans_dagar": {"min": 0, "max": 5}, "anstallningsform": ["tillsvidare"],
                              "omfattning": ["heltid"]},
            "varden_topp5": ["hållbarhet"], "arbetsdag": {"energigivare": ["skriva texter"]},
            "kompetens_id": ["webbpublicering"], "exkludera_arbetsgivare": ["Dåligt AB"]}

    def setUp(self):
        super().setUp()
        sc.skriv_json(os.path.join(self.home, "profil", "preferenser.json"), self.PREF)
        self.tax = [mock.patch.object(score, "etikett_for_id", return_value=None),
                    mock.patch.object(score, "kommuner_i_region", return_value=set()),
                    mock.patch.object(score, "yrkesgrupp_for", return_value=set())]
        for t in self.tax:
            t.start()

    def tearDown(self):
        for t in self.tax:
            t.stop()
        super().tearDown()

    def post(self, kid, **kw):
        base = {"kalla_id": kid, "titel": "Kommunikatör", "arbetsgivare": "Bra AB", "ort": "Uppsala",
                "kommun_id": "K1", "anstallningsform": "tillsvidare", "omfattning": "heltid",
                "kompetenser": [{"id": "Y1", "namn": "Kommunikatör", "typ": "yrke"},
                                {"id": None, "namn": "Webbpublicering", "typ": "must"}]}
        base.update(kw)
        return sc.normalisera(base, "t")

    def test_poang_och_uteslutning(self):
        sc.upsert(sc.db(self.home), self.home, [
            self.post("bast"),
            self.post("deltid", omfattning="deltid"),
            self.post("annan_ort", ort="Kiruna", kommun_id="K9"),
            self.post("distans_annan_ort", ort="Kiruna", kommun_id="K9", distans=2),
            self.post("arb", arbetsgivare="Dåligt AB"),
            self.post("saljare", titel="Säljare och kommunikatör"),
            self.post("svag", titel="Ekonom", kompetenser=[{"id": "Y9", "namn": "Ekonom", "typ": "yrke"}],
                      text="Du gillar att skriva texter om hållbarhet."),
        ])
        res = score.score(self.home, jokrar=1, min_poang=50)
        r = {k.split("-", 1)[1]: v for k, v in self.rader().items()}
        self.assertEqual(r["bast"]["poang"], 100)
        self.assertEqual(r["arb"]["poang"], 0)
        self.assertTrue(json.loads(r["arb"]["poang_skal_json"])["uteslutet"])
        # gränsbrott flaggas men utesluts inte
        for k, ord_ in (("deltid", "deltid"), ("annan_ort", "Kiruna")):
            sk = json.loads(r[k]["poang_skal_json"])
            self.assertFalse(sk["uteslutet"], k)
            self.assertTrue(any(ord_ in b for b in sk["granbrott"]), k)
            self.assertTrue(sk["matchning_etikett"].startswith("Bryter mot din gräns"), k)
            self.assertIn("Bryter mot din gräns", sk["matchning_motivering"])
            self.assertLess(r[k]["poang"], r["bast"]["poang"])
        self.assertGreater(r["distans_annan_ort"]["poang"], 50)
        self.assertLess(r["saljare"]["poang"], r["bast"]["poang"])
        self.assertEqual([j["uid"] for j in res["jokrar"]], ["t-svag"])
        self.assertTrue(json.loads(r["svag"]["poang_skal_json"])["joker"])
        # lista: uteslutna visas inte, bästa först, ≤300 tecken utdrag
        rs = lista.rader(self.home)
        self.assertEqual(rs[0]["uid"], "t-bast")
        self.assertNotIn("t-arb", [x["uid"] for x in rs])
        dt = next(x for x in rs if x["uid"] == "t-deltid")
        self.assertIn("bryter mot din gräns: deltid", dt["flaggor"])
        self.assertIn("! Bryter mot din gräns: deltid", lista.formatera(dt, detalj=True))
        self.assertIn("t-svag", [j["uid"] for j in lista.jokrar(self.home)])
        rad = lista.formatera(rs[0])
        self.assertEqual(rad.count(" | "), 9)  # + matchning_etikett

    def test_deterministisk(self):
        sc.upsert(sc.db(self.home), self.home, [self.post("a")])
        score.score(self.home)
        p1 = self.rader()["t-a"]["poang_skal_json"]
        score.score(self.home)
        self.assertEqual(p1, self.rader()["t-a"]["poang_skal_json"])


class TestUtbyteOchKallor(Bas):
    def test_utbyte(self):
        c = sc.db(self.home)
        sc.upsert(c, self.home, [sc.normalisera({"kalla_id": str(i), "titel": f"J{i}", "hittad_via": "h1"}, "af")
                                 for i in range(3)])
        lista.satt(self.home, "af-0", "nej", "fel nivå")
        lista.satt(self.home, "af-1", "sokt")
        u = utbyte.utbyte(self.home)
        self.assertEqual(u["per_kalla"]["af"]["nej"], 1)
        self.assertEqual(u["per_hittad_via"]["h1"]["sokt"], 1)
        self.assertTrue(os.path.exists(sc.sokv(self.home, "utbyte.json")))

    def test_lankmonster_och_kalla_lagg_till(self):
        html_ = "<html><body>" + "".join(
            f'<a href="/lediga-jobb/annons/{1000 + i}">Kommunikatör nummer {i}</a>' for i in range(4)) + \
            '<a href="/om-oss">Om oss</a><a href="/lediga-jobb/">Alla jobb</a></body></html>'
        fh = FalskHttp({"https://bolag.se/lediga-jobb": html_})
        with mock.patch.object(sc, "http", fh):
            r = kalla_lagg_till.lagg_till(self.home, "https://bolag.se/lediga-jobb/", "Bolaget")
            self.assertEqual(r["kalla"]["typ"], "pagehash")
            self.assertTrue(r["kalla"]["lankmonster"])
            self.assertEqual(r["kalla"]["tillagd_av"], "anvandare")
            rap = fetch.kor_bevakade(self.home)
        self.assertEqual(rap["kallor"][0]["nya"], 4)
        self.assertEqual(kalla_lagg_till.lagg_till(self.home, "https://bolag.se/lediga-jobb/")["atgard"], "fanns_redan")
        kalla_lagg_till.satt_aktiv(self.home, r["kalla"]["id"], False)
        self.assertEqual(fetch.kor_bevakade(self.home)["kallor"], [])
        kalla_lagg_till.ta_bort(self.home, r["kalla"]["id"])
        self.assertEqual(kalla_lagg_till.las(self.home)["kallor"], [])
        self.assertEqual(len(sc.las_json(sc.sokv(self.home, "kallor_borttagna.json"))["kallor"]), 1)

    def test_upptack_ats_i_html(self):
        k = upptack_ats.kandidater_ur('<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme">'
                                      '</script><a href="https://jobs.lever.co/foo">x</a> https://uu.varbi.com/se/')
        typer = {t: u for t, u in k}
        self.assertEqual(typer["greenhouse"], "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true")
        self.assertEqual(typer["lever"], "https://api.lever.co/v0/postings/foo?mode=json")
        self.assertEqual(typer["rss"], "https://uu.varbi.com/what:rssfeed/")
        r = upptack_ats.upptack("https://www.linkedin.com/jobs/search?keywords=x", self.home)
        self.assertEqual(r["forslag"]["typ"], "mejl")


class TestLive(unittest.TestCase):
    def test_jobtech_live(self):
        try:
            _, d, _ = sc.http_json(fetch.JOBTECH + "/search?q=kommunikat%C3%B6r&limit=1", timeout=10)
        except sc.NatFel as e:
            self.skipTest(f"inget nät: {e}")
        self.assertIn("total", d)
        if d["hits"]:
            p = fetch.jobtech_post(d["hits"][0])
            self.assertTrue(p["kalla_id"] and p["titel"])


if __name__ == "__main__":
    unittest.main()
