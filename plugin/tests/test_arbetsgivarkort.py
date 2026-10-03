"""Tester för arbetsgivarkort.py och arbetsgivar-/matchningsdelarna i score.py.

Kör från repo-roten:  JOBBSOK_OFFLINE=1 python3 -m unittest plugin/tests/test_arbetsgivarkort.py
Offline med fixturer (riktiga Kolada-svar för Uppsala kommun, ett riktigt Cision-nyhetsrum och ett utdrag
ur IVO:s årsredovisning 2025). Live-testerna skippas utan nät eller när JOBBSOK_OFFLINE=1.
"""
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "arbetsgivarkort"
sys.path.insert(0, str(HERE.parent / "scripts"))

import arbetsgivarkort as ak  # noqa: E402
import score  # noqa: E402
import sok_common as sc  # noqa: E402
import validate  # noqa: E402

KOLADA = json.loads((FIX / "kolada_uppsala.json").read_text(encoding="utf-8"))

PRESTATION = ("Vi söker dig som är resultatorienterad, ambitiös och driven. Du trivs i högt tempo i en dynamisk "
              "och föränderlig miljö där vi tävlar om att vara bäst och leverera framgång.")
OMSORG = ("Hos oss arbetar vi tillsammans i ett stöttande team med fina kollegor. Vi värnar om gemenskap, "
          "omtanke och samarbete, och du får stort eget ansvar och möjlighet att påverka.")


class TestTyp(unittest.TestCase):
    def test_orgnr_och_namn(self):
        self.assertEqual(ak.avgor_typ("Uppsala kommun", "212000-3005")[0], "kommun")
        self.assertEqual(ak.avgor_typ("Region Uppsala", "232100-0024")[0], "region")
        self.assertEqual(ak.avgor_typ("Inspektionen för vård och omsorg", "2021006537")[0], "stat")
        self.assertEqual(ak.avgor_typ("Hemköpskedjan AB", "5561138826")[0], "privat")
        self.assertEqual(ak.avgor_typ("Svenska kyrkan", "8020000000")[0], "ideell")
        self.assertEqual(ak.avgor_typ("Sveriges lantbruksuniversitet", None)[0], "stat")
        self.assertEqual(ak.avgor_typ("Knivsta kommun", None)[0], "kommun")
        self.assertEqual(ak.norm_orgnr("556113-8826"), "5561138826")


class TestKolada(unittest.TestCase):
    def test_kommun_ur_fixtur(self):
        with mock.patch.object(ak, "hamta_json", side_effect=lambda u, **k: KOLADA[u]):
            k = ak.kolada("Uppsala kommun", "kommun")
        self.assertEqual(k["status"], "auto")
        self.assertEqual(k["kolada_id"], "0380")
        led = k["matt"]["ledarskap"]
        self.assertIsNotNone(led["senaste"])
        self.assertIn(led["trend_3_matningar"], ("upp", "ner", "stabil"))
        sj = k["matt"]["sjukfranvaro_pct"]
        self.assertIsNotNone(sj["riket_samma_ar"])  # rikssnitt finns för sjukfrånvaro
        self.assertEqual(sj["kalla"]["typ"], "kolada")
        self.assertIn("N00090", sj["kalla"]["url"])

    def test_privat_har_ingen_kolada(self):
        self.assertEqual(ak.kolada("Hemköp", "privat")["status"], "ej_tillampligt")


class TestKallor(unittest.TestCase):
    def test_arsredovisning_tabell(self):
        v, rad = ak.sjukfranvaro_ur_text((FIX / "ivo_sjukfranvaro.txt").read_text(encoding="utf-8"))
        self.assertEqual(v, 3.76)
        self.assertIn("2025", rad)

    def test_arsredovisning_utan_pdf_ar_manuell(self):
        r = ak.stat_arsredovisning("IVO")
        self.assertEqual(r["status"], "manuellt")
        self.assertIn("2000:605", r["anteckning"])

    def test_ixbrl(self):
        html = ('<xbrli:context id="period0"><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate>'
                '<xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
                '<xbrli:context id="period1"><xbrli:period><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
                '<ix:nonFraction name="se-gen-base:MedelantaletAnstallda" contextRef="period0" unitRef="antal">42</ix:nonFraction>'
                '<ix:nonFraction name="se-gen-base:MedelantaletAnstallda" contextRef="period1" unitRef="antal">38</ix:nonFraction>'
                '<ix:nonFraction name="se-gen-base:Nettoomsattning" contextRef="period0" scale="3" unitRef="SEK">12 345</ix:nonFraction>'
                '<ix:nonFraction name="se-gen-base:AretsResultat" contextRef="period0" sign="-" unitRef="SEK">1 000</ix:nonFraction>')
        v, per = ak.ixbrl_varden(html)
        self.assertEqual(v["anstallda"], {"period0": 42, "period1": 38})
        self.assertEqual(v["omsattning"]["period0"], 12345000)
        self.assertEqual(v["resultat"]["period0"], -1000)
        self.assertEqual(per["period0"], "2024-12-31")

    def test_ekonomi_utan_nyckel(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JOBBSOK_BOLAGSVERKET_ID", None)
            self.assertEqual(ak.ekonomi("5561138826", "privat")["status"], "kraver_nyckel")
        self.assertEqual(ak.ekonomi("2120003005", "kommun")["status"], "ej_tillampligt")

    def test_cision_ur_fixtur(self):
        html = (FIX / "cision_axfood.html").read_text(encoding="utf-8")
        with mock.patch.object(ak, "hamta_text", return_value=html), \
                mock.patch.object(sc, "robots_tillater", return_value=True), \
                mock.patch.object(ak.jc, "ar_sedan", return_value="2000-01-01"):
            p = ak.press("Axfood AB")
        self.assertEqual(p["status"], "auto")
        self.assertEqual(p["kalla"]["url"], "https://news.cision.com/se/axfood")
        self.assertGreater(p["antal_pressmeddelanden"], 5)
        for s in p["signaler"]:
            self.assertTrue(set(s["kategorier"]) <= set(ak.PRESS))

    def test_cision_saknas(self):
        with mock.patch.object(ak, "hamta_text", side_effect=sc.HttpFel(404, "x")), \
                mock.patch.object(sc, "robots_tillater", return_value=True):
            self.assertEqual(ak.press("Okänt Bolag AB")["status"], "saknas")


class TestAnnonssprak(unittest.TestCase):
    def test_axlar_och_sjalvbeskrivning(self):
        with mock.patch.object(ak, "QSORT", "/finns/inte"):
            a = ak.annonssprak([PRESTATION])
            b = ak.annonssprak([OMSORG])
        self.assertTrue(a["sjalvbeskrivning"])
        self.assertIn("självbeskrivning", a["varning"])
        self.assertEqual(a["axlar"][0]["lasning"], "lutar mot prestation_tavling")
        self.assertEqual(b["axlar"][0]["lasning"], "lutar mot samarbete_omsorg")
        self.assertEqual(a["mappning"]["mot"], "ocp")
        self.assertEqual(len(a["mappning"]["dimensioner"]), 6)

    def test_qsort_om_filen_finns(self):
        d = tempfile.mkdtemp()
        try:
            f = os.path.join(d, "kultur-qsort.md")
            Path(f).write_text("| s1 | Vi samarbetar och stöttar varandra |\n| s2 | Resultat mäts och tävling uppmuntras |\n",
                               encoding="utf-8")
            with mock.patch.object(ak, "QSORT", f):
                r = ak.annonssprak([OMSORG])
        finally:
            shutil.rmtree(d)
        self.assertEqual(r["mappning"]["mot"], "kultur-qsort")
        self.assertIn("s1", r["mappning"]["antyder_topp"])


class TestMatchningOchFragor(unittest.TestCase):
    KORT = {"annonssprak": None, "press": {"signaler": [{"datum": "2026-03-01", "titel": "Bolaget varslar 40 tjänster",
                                                        "url": "u", "kategorier": ["varsel"]}]},
            "rekrytering": {"upprepade_roller": [{"titel": "kommunikatör", "annonser": 7, "forsta": "2023-02-01"}]},
            "typ": {"varde": "privat"}, "ekonomi": {"status": "kraver_nyckel"}}

    def kort(self):
        k = json.loads(json.dumps(self.KORT))
        with mock.patch.object(ak, "QSORT", "/finns/inte"):
            k["annonssprak"] = ak.annonssprak([OMSORG])
        return k

    def test_tolerant_och_utan_totalpoang(self):
        pref = {"kultur_ideal": {"topp": ["samarbete och omtanke"], "botten": ["tävling"]},
                "ledarskap_krav": [{"text": "chef som ger frihet"}], "varningssignaler": ["varsel", "mikrostyrning"]}
        m = ak.matchning(pref, self.kort(), satser={})
        self.assertEqual(m["stammer"][0]["onskemal"], "samarbete och omtanke")
        self.assertTrue(any("varsel" in f["signal"] for f in m["varningsflaggor"]))
        self.assertTrue(any("mikrostyrning" in o["onskemal"] for o in m["okant"]))
        self.assertTrue(any("frihet" in o["onskemal"] for o in m["okant"]))
        self.assertNotIn("poang", json.dumps(m))
        self.assertEqual(ak.matchning({}, self.kort())["stammer"], [])
        ak.matchning({"kultur_ideal": "bara en sträng", "varningssignaler": None}, self.kort())

    def test_coachens_format(self):
        pref = {"kultur_ideal": {"instrument": "kultur-qsort-18-v1", "topp": ["s12", "s16"], "botten": ["s15"]},
                "ledarskap_krav": {"ansvar": "sak", "chefsegenskaper_topp3": ["ger_frihet"], "avstamning_frekvens": "veckovis",
                                   "krav": ["säger som det är"]},
                "varningssignaler": ["mikrostyrning"]}
        satser = {"s12": "Man bryr sig om varandra [stödjande]", "s16": "Stort eget ansvar [autonomi]",
                  "s15": "Man tävlar internt [konkurrens]"}
        m = ak.matchning(pref, self.kort(), satser=satser)
        alla = json.dumps(m, ensure_ascii=False)
        self.assertNotIn("kultur-qsort-18-v1", alla)
        self.assertEqual([x["onskemal"] for x in m["stammer"]][:1], ["s12"])
        self.assertIn("en chef som ger frihet", alla)
        self.assertIn("avstämning med chefen veckovis", alla)
        self.assertNotIn('"sak"', alla)

    def test_fragor_starka(self):
        k = self.kort()
        k["matchning"] = ak.matchning({"varningssignaler": ["mikrostyrning"]}, k, satser={})
        f = ak.fragor(k, {})
        text = " ".join(x["fraga"] for x in f)
        self.assertIn("7 gånger", text)
        self.assertIn("varslar", text)
        self.assertIn("mikrostyrning", text)
        self.assertTrue(all(x["till"] for x in f))


class TestBygg(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        sc.skriv_json(os.path.join(self.home, "profil", "preferenser.json"),
                      {"schema_version": 1, "varningssignaler": ["varsel"], "kultur_ideal": ["samarbete"]})

    def tearDown(self):
        sc.stang_db()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_utan_nat_validerar_och_bevarar_manuellt(self):
        vag, kort = ak.bygg(self.home, "Hemköpskedjan AB", orgnr="556113-8826", utan_nat=True)
        self.assertTrue(vag.endswith("sok/arbetsgivare/hemkopskedjan-ab.json"))
        self.assertEqual(kort["typ"]["varde"], "privat")
        self.assertEqual(validate.validate_file(vag)[1], [])
        self.assertEqual(validate.schema_for_path(vag), "arbetsgivarkort")
        self.assertTrue(kort["okant"])
        ak.main(["satt", "hemkopskedjan-ab", "--falt", "egna_intryck", "--text", "Trevlig chef", "--home", self.home])
        ak.main(["satt", "hemkopskedjan-ab", "--falt", "personer_att_fraga", "--text", "Anna; Bo", "--home", self.home])
        _, kort2 = ak.bygg(self.home, "Hemköpskedjan AB", orgnr="5561138826", utan_nat=True)
        self.assertEqual(kort2["manuellt"]["egna_intryck"]["varde"], "Trevlig chef")
        self.assertEqual(kort2["manuellt"]["personer_att_fraga"]["varde"], ["Anna", "Bo"])
        self.assertEqual(validate.validate_file(vag)[1], [])


# ---------------------------------------------------------------- score.py

class TestScoreMatchning(unittest.TestCase):
    PREF = {"schema_version": 1,
            "riktningar": [{"namn": "K", "yrkes_id": ["Y1"], "sokord": ["kommunikatör"]}],
            "orter": [{"namn": "Uppsala", "kommun_id": "K1"}],
            "hårda_gränser": {"anstallningsform": ["tillsvidare"], "omfattning": ["heltid"]},
            "kompetens_id": ["webbpublicering", "intranät"]}
    FAKTA = {"schema_version": 1, "person": {"namn": "X", "korkort": None},
             "roller": [{"id": "r1", "arbetsgivare": "A", "titel": {"sv": "Kommunikatör"}, "start": "2019-01", "slut": None,
                         "meriter": []}],
             "sprak": [{"sprak": "Svenska", "niva": "modersmål"}, {"sprak": "Engelska", "niva": "flytande"}]}

    def setUp(self):
        self.home = tempfile.mkdtemp()
        sc.skriv_json(os.path.join(self.home, "profil", "preferenser.json"), self.PREF)
        sc.skriv_json(os.path.join(self.home, "profil", "fakta.json"), self.FAKTA)
        self.p = [mock.patch.object(score, n, return_value=r) for n, r in
                  (("etikett_for_id", None), ("kommuner_i_region", set()), ("yrkesgrupp_for", set()))]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        sc.stang_db()
        shutil.rmtree(self.home, ignore_errors=True)

    def jobb(self, kid, titel="Kommunikatör", text="", arbetsgivare="Bra AB", orgnr=None, komp=None):
        komp = komp if komp is not None else ["Webbpublicering", "Intranät", "Grafisk design", "Videoredigering"]
        post = {"kalla_id": kid, "titel": titel, "arbetsgivare": arbetsgivare, "orgnr": orgnr, "ort": "Uppsala",
                "kommun_id": "K1", "anstallningsform": "tillsvidare", "omfattning": "heltid", "text": text,
                "kompetenser": [{"id": "Y1", "namn": titel, "typ": "yrke"}] +
                               [{"id": None, "namn": k, "typ": "nice"} for k in komp]}
        return sc.normalisera(post, "t")

    def kor(self, *jobb, **kw):
        sc.upsert(sc.db(self.home), self.home, list(jobb))
        score.score(self.home, **kw)
        return {r["uid"].split("-", 1)[1]: (r["poang"], json.loads(r["poang_skal_json"]))
                for r in sc.db(self.home).execute("SELECT * FROM jobb").fetchall()}

    def test_halva_onskelistan_ar_bra_matchning(self):
        r = self.kor(self.jobb("halv"))
        p, sk = r["halv"]
        self.assertEqual(sk["matchning_etikett"], "Bra matchning – värd att söka")
        self.assertGreaterEqual(p, 70)
        self.assertIn("Webbpublicering", sk["matchning_motivering"])
        self.assertNotIn("%", sk["matchning_motivering"])

    def test_stark_nar_nastan_allt_finns(self):
        p, sk = self.kor(self.jobb("allt", komp=["Webbpublicering", "Intranät"]))["allt"]
        self.assertEqual(sk["matchning_etikett"], "Stark matchning")

    def test_erfarenhetskrav_ar_onskelista_men_ger_strackjobb(self):
        p, sk = self.kor(self.jobb("ar", text="Du har minst 15 års erfarenhet av kommunikation."))["ar"]
        self.assertNotIn("hart_krav_saknas", sk)
        self.assertEqual(sk["matchning_etikett"], "Sträckjobb – sök!")
        self.assertIn("15", sk["strackjobb"])

    def test_senior_titel_ar_strackjobb(self):
        p, sk = self.kor(self.jobb("sen", titel="Senior kommunikatör"))["sen"]
        self.assertEqual(sk["matchning_etikett"], "Sträckjobb – sök!")
        self.assertFalse(sk["uteslutet"])

    def test_hart_krav_flaggas_utesluter_inte(self):
        r = self.kor(self.jobb("leg", text="Krav på legitimerad sjuksköterska."),
                     self.jobb("kk", text="B-körkort är ett krav i tjänsten."),
                     self.jobb("sv", text="Du talar och skriver flytande svenska och engelska."))
        p, sk = r["leg"]
        self.assertEqual(sk["hart_krav_saknas"], ["legitimation"])
        self.assertTrue(sk["matchning_etikett"].startswith("Möjlig – kolla legitimation"))
        self.assertGreater(p, 0)
        self.assertFalse(sk["uteslutet"])
        self.assertEqual(r["kk"][1]["hart_krav_saknas"], ["körkort"])
        self.assertNotIn("hart_krav_saknas", r["sv"][1])  # språken finns i faktabanken

    def test_arbetsgivarkort_flagga_och_vikt(self):
        sc.skriv_json(sc.sokv(self.home, "arbetsgivare", "bra-ab.json"),
                      {"slug": "bra-ab", "arbetsgivare": "Bra AB", "orgnr": "5560000000",
                       "matchning": {"stammer": [{}], "skaver": [{}, {}, {}],
                                     "varningsflaggor": [{"signal": "varsel", "belagg": ["press 2026-03: varslar"]}]}})
        p0, sk0 = self.kor(self.jobb("a", orgnr="556000-0000"), arbetsgivarkort=True)["a"]
        self.assertNotIn("arbetsgivare", sk0["delar"])  # vikt 0 som standard
        self.assertTrue(any("varsel" in f for f in sk0["flaggor"]))
        self.assertFalse(sk0["uteslutet"])
        p1, sk1 = self.kor(arbetsgivare_vikt=10)["a"]
        self.assertEqual(sk1["delar"]["arbetsgivare"], round(10 * 1 / 4))
        self.assertLess(p1, p0)


# ---------------------------------------------------------------- live

def natet_finns():
    if os.environ.get("JOBBSOK_OFFLINE") == "1":
        return False
    try:
        socket.create_connection(("api.kolada.se", 443), timeout=5).close()
        return True
    except OSError:
        return False


@unittest.skipUnless(natet_finns(), "inget nät (eller JOBBSOK_OFFLINE=1)")
class TestLive(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        sc.stang_db()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_uppsala_kommun(self):
        _, k = ak.bygg(self.home, "Uppsala kommun", antal_ar=2)
        self.assertEqual(k["orgnr"], "2120003005")
        self.assertEqual(k["typ"]["varde"], "kommun")
        self.assertIsNotNone(k["offentligt"]["kolada"]["matt"]["ledarskap"]["senaste"])
        self.assertGreater(sum(p["annonser"] for p in k["rekrytering"]["per_ar"]), 100)

    def test_region_uppsala_kolada(self):
        k = ak.kolada("Region Uppsala", "region")
        self.assertEqual(k["kolada_id"], "0003")
        self.assertIsNotNone(k["matt"]["sjukfranvaro_pct"]["senaste"])

    def test_privat_hemkop(self):
        vag, k = ak.bygg(self.home, "Hemköpskedjan AB", orgnr="5561138826", antal_ar=2)
        self.assertEqual(k["typ"]["varde"], "privat")
        self.assertTrue(k["rekrytering"]["upprepade_roller"])
        self.assertEqual(validate.validate_file(vag)[1], [])


if __name__ == "__main__":
    unittest.main()
