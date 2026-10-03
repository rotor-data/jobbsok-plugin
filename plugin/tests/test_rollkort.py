"""Tester för rollkort.py. Offline med fixturer; TestLive skippas utan nät eller med JOBBSOK_OFFLINE=1.

    JOBBSOK_OFFLINE=1 python3 -m unittest discover plugin/tests -p 'test_rollkort.py'
"""
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import jakt_common as jc  # noqa: E402
import oversikt  # noqa: E402
import rollkort as rk  # noqa: E402
import sok_common as sc  # noqa: E402
import validate  # noqa: E402

PROFIL = HERE / "fixtures" / "home" / "profil"

TEXT = """Vi söker en kommunikatör till vår enhet.
Arbetsuppgifter
- Skriva och publicera innehåll för webb och sociala medier
- Planera kampanjer tillsammans med verksamheten
Du kommer att producera nyhetsbrev och skriva pressmeddelanden.
Kvalifikationer
Du har högskoleutbildning inom kommunikation.
Erfarenhet av sociala medier och webbpublicering.
Det är meriterande med erfarenhet av film och foto.
Vi erbjuder
Friskvårdsbidrag."""


def hit(i, org="2120003005", namn="Uppsala kommun", datum="2025-05-01T10:00:00", text=TEXT):
    return {"id": str(i), "headline": "Kommunikatör till Uppsala kommun", "employer": {"organization_number": org, "name": namn},
            "publication_date": datum, "workplace_address": {"municipality": "Uppsala"},
            "webpage_url": f"https://arbetsformedlingen.se/platsbanken/annonser/{i}",
            "employment_type": {"label": "Vanlig anställning"}, "description": {"text": text},
            "must_have": {"skills": [{"concept_id": "abcd_123_xyz", "label": "Webbpublicering"}]},
            "nice_to_have": {"skills": [{"concept_id": "efgh_123_xyz", "label": "Fotografering"}]}}


HITS = [hit(i) for i in range(6)] + [hit(10, "5560000001", "Acme AB")]


def falsk_api(url, params=None, home=None):
    params = params or {}
    if "autocomplete" in url:
        if params.get("type") == "region":
            return [{"taxonomy/id": "zBon_eET_fFU", "taxonomy/preferred-label": "Uppsala län"}]
        return [{"taxonomy/id": "aRp4_qjZ_tPV", "taxonomy/preferred-label": "Informatör/Kommunikatör",
                 "taxonomy/alternative-labels": ["Kommunikatör"]}]
    if "graphql" in url:
        return {"data": {"concepts": [{"id": "aRp4_qjZ_tPV", "preferred_label": "Informatör/Kommunikatör",
                                       "broader": [{"id": "k1Nx_auG_sNh", "preferred_label": "Informatörer m.fl.",
                                                    "ssyk_code_2012": "2432"}]}]}}
    if params.get("limit") == 0:
        return {"total": {"value": 40 if "historical" in url else 2}, "hits": []}
    off = params.get("offset", 0)
    h = (HITS if "historical" in url else HITS[:2]) if off == 0 else []
    return {"total": {"value": len(h)}, "hits": h}


SCB = {"columns": [{"code": "Region", "type": "d"}, {"code": "Sektor", "type": "d"}, {"code": "Yrke2012", "type": "d"},
                   {"code": "Kon", "type": "d"}, {"code": "Tid", "type": "t"},
                   {"code": "000007AP", "type": "c"}, {"code": "000007AS", "type": "c"}, {"code": "000007AU", "type": "c"}],
       "data": [{"key": ["SE", "0", "2432", "1+2", "2025"], "values": ["22000", "48400", "1290"]},
                {"key": ["SE12", "0", "2432", "1+2", "2025"], "values": ["2100", "45300", ".."]}]}


class Hem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "h")
        shutil.copytree(PROFIL, os.path.join(self.home, "profil"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def kor(self, *args, scb=SCB):
        buf = io.StringIO()
        with mock.patch.object(jc, "api", side_effect=falsk_api), \
             mock.patch.object(sc, "http_json", return_value=(200, scb, {})), redirect_stdout(buf):
            kod = rk.main(["--home", self.home] + list(args))
        return kod, buf.getvalue()

    def kort(self, slug="kommunikatör-uppsala"):
        return json.loads(Path(self.home, "sok", "rollkort", slug + ".json").read_text(encoding="utf-8"))


class TestUtvinning(unittest.TestCase):
    def test_stycken_delar_rubriker(self):
        s = rk.stycken(TEXT)
        uppg = [m for a, m in s if a == "uppg"]
        krav = [m for a, m in s if a == "krav"]
        self.assertTrue(any("sociala medier" in m for m in uppg))
        self.assertTrue(any("högskoleutbildning" in m for m in krav))
        self.assertFalse(any("Friskvård" in m for m in uppg + krav))

    def test_utvinn_teman_med_exempel(self):
        teman, n = rk.utvinn(HITS, "uppg", {"kommunikatör"})
        self.assertEqual(n, len(HITS))
        self.assertTrue(teman)
        self.assertTrue(all(t["exempel"] and t["exempel"][0]["annons_id"] for t in teman))
        self.assertLessEqual(len(teman), 8)


class TestBygg(Hem):
    def test_bygg_falt_har_kallor_och_validerar(self):
        kod, ut = self.kor("bygg", "--roll", "kommunikatör", "--region", "Uppsala län", "--ar", "2")
        self.assertEqual(kod, 0)
        k = self.kort()
        self.assertEqual(k["roll"]["ssyk"], "2432")
        self.assertEqual(k["arbetsgivare"]["varde"][0]["namn"], "Uppsala kommun")
        self.assertEqual(len(k["annonser"]["varde"]), 3)
        self.assertEqual(k["lon"]["varde"]["per_region"]["riket"]["alla"]["manadslon_medel"], 48400)
        self.assertEqual(k["lon"]["kallor"][0]["typ"], "scb")
        for f in ("titlar", "arbetsgivare", "volym", "arbetsuppgifter", "krav", "annonser"):
            self.assertTrue(k[f]["kallor"], f)
        for f in ("kultur", "ledarskap", "arbetsidentitet"):
            self.assertEqual(k[f]["status"], "vantar")
            self.assertIsNone(k[f]["varde"])
        name, errs = validate.validate_file(str(Path(self.home, "sok", "rollkort", "kommunikatör-uppsala.json")))
        self.assertEqual((name, errs), ("rollkort", []))
        self.assertIn("arbetsuppgifter_till_claude", ut)

    def test_scb_fel_ger_todo(self):
        with mock.patch.object(jc, "api", side_effect=falsk_api), \
             mock.patch.object(sc, "http_json", side_effect=sc.NatFel("scb")), redirect_stdout(io.StringIO()):
            rk.main(["--home", self.home, "bygg", "--roll", "kommunikatör"])
        k = self.kort("kommunikatör")
        self.assertIsNone(k["lon"]["varde"])
        self.assertIn("TODO", k["lon"]["todo"])

    def test_natfel_exit_3(self):
        with mock.patch.object(sc, "http_json", side_effect=sc.NatFel("x")), self.assertRaises(SystemExit) as e:
            rk.main(["--home", self.home, "bygg", "--roll", "kommunikatör", "--fraskt"])
        self.assertEqual(e.exception.code, 3)

    def test_cache(self):
        self.kor("bygg", "--roll", "kommunikatör")
        with mock.patch.object(jc, "api", side_effect=AssertionError("ska läsa cache")), \
             mock.patch.object(sc, "http_json", side_effect=AssertionError("scb ska läsa cache")), redirect_stdout(io.StringIO()):
            rk.main(["--home", self.home, "bygg", "--roll", "kommunikatör"])

    def test_stanna_citerar_coach(self):
        self.kor("bygg", "--stanna")
        k = self.kort("stanna")
        self.assertEqual(k["typ"], "stanna")
        self.assertTrue(k["passar_for_att"]["varde"])
        self.assertEqual(rk.kontrollera(k, self.home)[0], [])


class TestCitatGlappKontroll(Hem):
    def setUp(self):
        super().setUp()
        self.kor("bygg", "--roll", "kommunikatör", "--region", "Uppsala län")
        self.slug = "kommunikatör-uppsala"

    def test_citat_maste_finnas(self):
        self.kor("citat", self.slug, "--typ", "passar", "--text", "Skrivande", "--citat",
                 "Skriva klart en text som någon faktiskt förstår", "--fas", "energy_log", "--falt", "patterns.energizers[0]")
        self.assertEqual(len(self.kort()["passar_for_att"]["varde"]), 1)
        with self.assertRaises(SystemExit):
            self.kor("citat", self.slug, "--typ", "skav", "--text", "x", "--citat", "påhittat", "--fas", "identity")

    def test_glapp(self):
        self.kor("glapp", self.slug)
        g = self.kort()["glapp"]["varde"]
        alla = {x["krav"]: s for s in ("har", "saknas", "osakert") for x in g[s]}
        self.assertEqual(alla.get("Fotografering"), "saknas")
        self.assertTrue(self.kort()["glapp"]["kallor"])

    def test_kontrollera_flaggar_falt_utan_kalla(self):
        k = self.kort()
        k["titlar"]["kallor"] = []
        k["skav"]["varde"] = [{"text": "x", "citat": "", "fas": "identity"}]
        fl, _ = rk.kontrollera(k, self.home)
        falt = {f["falt"] for f in fl}
        self.assertIn("titlar", falt)
        self.assertIn("skav[0]", falt)
        sc.skriv_json(rk.kort_sokv(self.home, self.slug), k)
        kod, _ = self.kor("kontrollera", self.slug)
        self.assertEqual(kod, 1)

    def test_tisdag_kraver_uppgifter(self):
        with self.assertRaises(SystemExit):
            self.kor("satt", self.slug, "--falt", "vanlig_tisdag", "--text", "Skriver hela dagen")
        self.kor("satt", self.slug, "--falt", "vanlig_tisdag", "--text", "Skriver", "--uppgift", "0")
        self.assertEqual(self.kort()["vanlig_tisdag"]["kallor"][0]["typ"], "arbetsuppgift")

    def test_krok_kraver_kalla(self):
        with self.assertRaises(SystemExit):
            self.kor("satt", self.slug, "--falt", "kultur", "--text", '{"typiska_kulturer":["s3"]}')
        self.kor("satt", self.slug, "--falt", "kultur", "--text", '{"typiska_kulturer":["s3"]}',
                 "--kalla", '{"typ":"forskning","fil":"docs/research/kultur-ledarskap-evidens.md"}')
        self.assertEqual(self.kort()["kultur"]["varde"]["typiska_kulturer"], ["s3"])

    def test_jamfor_vikter_ur_preferenser(self):
        self.kor("bygg", "--stanna")
        m = rk.jamfor(self.home)
        self.assertEqual(m["vikter"], rk.STANDARD_VIKTER)
        self.assertEqual(m["rader"][0]["slug"], "stanna")
        p = Path(self.home, "profil", "preferenser.json")
        d = json.loads(p.read_text(encoding="utf-8"))
        d["rollkort_vikter"] = {"marknad": 5, "kultur": 0}
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(validate.validate_file(str(p))[1], [])
        m = rk.jamfor(self.home)
        self.assertEqual(m["vikter"]["marknad"], 5)
        self.assertEqual(m["rader"][1]["dimensioner"]["kultur"]["poang"], None)
        kod, ut = self.kor("jamfor", "--md")
        self.assertIn("| Kultur (vikt 0)", ut)

    def test_oversikt_visar_riktningar(self):
        self.kor("bygg", "--stanna")
        d = oversikt.bygg_data(Path(self.home), "2026-10-01")
        self.assertEqual(len(d["riktningar"]["kort"]), 2)
        html = oversikt.rendera(d)
        self.assertIn('id="riktningar"', html)


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
    def test_tre_roller_uppsala(self):
        for roll in ("kommunikatör", "verksamhetsutvecklare", "projektledare"):
            with redirect_stdout(io.StringIO()):
                rk.main(["--home", self.home, "bygg", "--roll", roll, "--region", "Uppsala län", "--max", "150"])
                rk.main(["--home", self.home, "glapp", f"{roll}-uppsala"])
            k = self.kort(f"{roll}-uppsala")
            self.assertTrue(k["roll"]["ssyk"])
            self.assertTrue(k["arbetsgivare"]["varde"])
            self.assertEqual(rk.kontrollera(k, self.home)[0], [])
        self.assertEqual(self.kort()["lon"]["varde"]["per_region"]["riket"]["alla"]["manadslon_medel"] > 30000, True)


class TestHardaKrav(unittest.TestCase):
    def test_klassning(self):
        self.assertTrue(rk.ar_hart("Legitimerad sjuksköterska"))
        self.assertTrue(rk.ar_hart("körkort · b"))
        self.assertTrue(rk.ar_hart("språk", "Du talar och skriver flytande svenska."))
        self.assertFalse(rk.ar_hart("sociala · medier", "Erfarenhet av sociala medier."))

    def test_bara_harda_krav_drar_ner(self):
        def g(saknas):
            return {"typ": "marknad", "glapp": {"varde": {"har": [], "osakert": [], "saknas": saknas}, "kallor": []}}
        onsk = rk.bedom(g([{"krav": "Film", "andel": .5, "hart": False}]), None, [], [], [], {})["glapp"]
        hart = rk.bedom(g([{"krav": "Legitimation", "andel": .5, "hart": True}]), None, [], [], [], {})["glapp"]
        self.assertEqual(onsk["poang"], 1.0)
        self.assertIn("du har 0 av 1", onsk["visa"])
        self.assertLess(hart["poang"], 0.5)
