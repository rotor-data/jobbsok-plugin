"""Kärntester för jobbsok: validate, init_home, status, common.

Kör från repo-roten:  python3 -m unittest discover plugin/tests -p 'test_core.py'
"""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import init_home  # noqa: E402
import jobbsok_common as jc  # noqa: E402
import status  # noqa: E402
import validate  # noqa: E402

FIX = HERE / "fixtures" / "home"


def schema(name):
    return validate.load_schema(name)


class TestCommon(unittest.TestCase):
    def test_resolve_home_order(self):
        old = os.environ.get("JOBBSOK_HOME")
        try:
            os.environ["JOBBSOK_HOME"] = "/tmp/envhome"
            self.assertEqual(jc.resolve_home("/tmp/cli"), Path("/tmp/cli").resolve())
            self.assertEqual(jc.resolve_home(), Path("/tmp/envhome").resolve())
            del os.environ["JOBBSOK_HOME"]
            self.assertEqual(jc.resolve_home(), Path(os.path.expanduser("~/Jobbsok")).resolve())
        finally:
            if old is not None:
                os.environ["JOBBSOK_HOME"] = old

    def test_slugify_och_mapp(self):
        self.assertEqual(jc.slugify("Region Uppsala – Kommunikatör"), "region-uppsala-kommunikator")
        self.assertEqual(jc.slugify("!!!"), "okand")
        self.assertEqual(jc.ansokningsmapp("Åre Kommun", "Projektledare (vik.)", "2026-10-01"),
                         "2026-10-01-are-kommun-projektledare-vik")

    def test_write_json_backup(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a" / "x.json"
            jc.write_json(p, {"v": 1})
            self.assertFalse(p.with_name("x.json.bak").exists())
            jc.write_json(p, {"v": 2})
            self.assertEqual(jc.read_json(p)["v"], 2)
            self.assertEqual(jc.read_json(p.with_name("x.json.bak"))["v"], 1)
            self.assertEqual([f.name for f in p.parent.iterdir() if f.name.endswith(".tmp")], [])


class TestValidate(unittest.TestCase):
    def test_fixtures_valid(self):
        for f in ["fakta", "preferenser", "rost"]:
            name, errs = validate.validate_file(str(FIX / "profil" / f"{f}.json"))
            self.assertEqual(name, f)
            self.assertEqual(errs, [], f"{f}: {errs}")

    def test_fixture_has_three_roles_bilingual(self):
        f = jc.read_json(FIX / "profil" / "fakta.json")
        self.assertEqual(len(f["roller"]), 3)
        self.assertTrue(any(m["text"].get("en") for r in f["roller"] for m in r["meriter"]))

    def test_invalid_fakta(self):
        f = jc.read_json(FIX / "profil" / "fakta.json")
        bad = copy.deepcopy(f)
        del bad["person"]["namn"]
        bad["roller"][0]["start"] = "2021"
        bad["roller"][0]["meriter"][0]["belagg"] = "kanske"
        bad["roller"][0]["meriter"][0]["text"] = {"de": "x"}
        bad["personnummer"] = "19800101-1234"
        errs = validate.validate(bad, schema("fakta"))
        msgs = {validate._fmt(p): m for p, m in errs}
        self.assertIn("person", msgs)
        self.assertIn("saknar obligatoriskt fält \"namn\"", msgs["person"])
        self.assertIn("roller[0].start", msgs)
        self.assertIn("roller[0].meriter[0].belagg", msgs)
        self.assertIn("roller[0].meriter[0].text", msgs)
        self.assertTrue(any("personnummer" in m for m in msgs.values()))

    def test_minimum_maximum(self):
        sch = {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 10},
                                                "y": {"type": "number", "minimum": 0.5}}}
        self.assertEqual(validate.validate({"x": 0, "y": 0.5}, sch), [])
        self.assertEqual(validate.validate({"x": 10}, sch), [])
        msgs = {validate._fmt(p): m for p, m in validate.validate({"x": 11, "y": 0.1}, sch)}
        self.assertIn("högst 10", msgs["x"])
        self.assertIn("minst 0.5", msgs["y"])
        self.assertIn("minst 0", validate.validate({"x": -1}, sch)[0][1])
        # coach.json använder 0–10-skalor; fixturen ska fortfarande vara giltig
        name, errs = validate.validate_file(str(FIX / "profil" / "coach.json"))
        self.assertEqual(errs, [], errs)

    def test_duplicate_merit_id(self):
        f = jc.read_json(FIX / "profil" / "fakta.json")
        f["roller"][0]["meriter"][1]["id"] = "r1-m1"
        self.assertTrue(validate.extra_checks("fakta", f))

    def test_cv_oneof_sections(self):
        cv = {"schema_version": 1, "sprak": "sv", "design_version": 1, "person": {"namn": "L"},
              "profil": "x", "sektioner": [
                  {"typ": "erfarenhet", "rubrik": "Erfarenhet", "poster": [{"titel": "a", "punkter": ["p"], "kalla": ["r1-m1"]}]},
                  {"typ": "lista", "rubrik": "Kompetenser", "grupper": [{"etikett": "", "poster": ["a"]}]},
                  {"typ": "text", "rubrik": "Övrigt", "text": "t"}]}
        self.assertEqual(validate.validate(cv, schema("cv")), [])
        cv["sektioner"].append({"typ": "lista", "rubrik": "X"})
        self.assertTrue(validate.validate(cv, schema("cv")))

    def test_other_schemas(self):
        ok = {
            "logg": {"schema_version": 1, "status": "skickad", "skickad": "2026-09-01", "kanal": "formular",
                     "kontakt": "", "foljupp_datum": "2026-09-15", "anteckningar": []},
            "kallor": {"schema_version": 1, "kallor": [{"id": "af", "typ": "jobtech", "namn": "Platsbanken", "url": "",
                                                       "aktiv": True, "senast_hamtad": None, "etag": None, "hash": None}]},
            "recept": {"schema_version": 1, "namn": "uppsala", "kallor": ["af"], "jobtech": {"q": "kommunikatör", "remote": None},
                       "filter": {"min_poang": 50}, "senast_kord": None},
            "analys": {"schema_version": 1, "krav": [{"krav": "Klarspråk", "typ": "ska", "matchar": ["r1-m2"], "lucka": False}],
                       "nyckelord": [], "vinkel": "", "fragor_till_arbetsgivaren": [], "sprak": "sv"},
            "brev": {"schema_version": 1, "sprak": "sv", "stycken": ["Hej"], "kalla_per_stycke": [["r1-m1"]]},
            "design": {"schema_version": 1, "version": 1, "namn": "Lugn", "layout": "klassisk",
                       "tokens": {"farg_text": "#1d1d1f", "storlek_brod_pt": 10.5}, "sektioner": ["profil", "erfarenhet"], "historik": []},
            "coach": {"schema_version": 1, "faser": {"intake": {"vad_som_helst": [1, 2]}}, "status": {"aktuell_fas": "identity", "senast": None}},
        }
        for n, d in ok.items():
            self.assertEqual(validate.validate(d, schema(n)), [], n)
        bad = {"logg": dict(ok["logg"], status="väntar"), "kallor": {"schema_version": 1, "kallor": [{"id": "Af X", "typ": "rss", "namn": ""}]},
               "design": dict(ok["design"], tokens={"farg_text": "svart"}), "coach": dict(ok["coach"], schema_version=2)}
        for n, d in bad.items():
            self.assertTrue(validate.validate(d, schema(n)), n)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            good = FIX / "profil" / "fakta.json"
            bad = Path(t) / "rost.json"
            bad.write_text('{"schema_version": 1, "aldrig_ord": "inte en lista"}', encoding="utf-8")
            broken = Path(t) / "preferenser.json"
            broken.write_text("{", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(validate.main([str(good)]), 0)
                self.assertEqual(validate.main([str(bad)]), 1)
                self.assertEqual(validate.main([str(broken)]), 1)
                self.assertEqual(validate.main([str(Path(t) / "okand.json")]), 1)
            self.assertEqual(validate.schema_for_path("/x/sok/recept/morgon.json"), "recept")


class TestInitHome(unittest.TestCase):
    def test_creates_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t) / "Jobbsok"
            r1 = init_home.init_home(home)
            self.assertIn("README.md", r1["skapade"])
            for rel in init_home.STARTFILER:
                name, errs = validate.validate_file(str(home / rel))
                self.assertEqual(errs, [], f"{rel}: {errs}")
            # hennes ändring får aldrig skrivas över
            fakta = home / "profil" / "fakta.json"
            d = jc.read_json(fakta)
            d["person"]["namn"] = "Lina"
            jc.write_json(fakta, d)
            r2 = init_home.init_home(home)
            self.assertEqual(r2["skapade"], [])
            self.assertEqual(jc.read_json(fakta)["person"]["namn"], "Lina")
            self.assertTrue((home / "ansokningar").is_dir())


class TestStatus(unittest.TestCase):
    def test_missing_home(self):
        with tempfile.TemporaryDirectory() as t:
            r = status.build(Path(t) / "finnsinte")
            self.assertFalse(r["finns"])
            self.assertEqual(r["nasta_steg"]["skill"], "jobbsok-start")
            self.assertIn("inte påbörjad", status.text(r))

    def test_empty_home(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t) / "h"
            init_home.init_home(home)
            r = status.build(home)
            self.assertEqual(r["faktabank"]["fyllnadsgrad"], 0)
            self.assertFalse(r["design"]["finns"])
            self.assertEqual(r["ansokningar"]["totalt"], 0)
            self.assertEqual(r["nasta_steg"]["skill"], "karriarcoach")
            json.dumps(r)

    def test_filled_home(self):
        import shutil
        import sqlite3
        with tempfile.TemporaryDirectory() as t:
            home = Path(t) / "h"
            shutil.copytree(FIX, home)
            init_home.init_home(home)
            jc.write_json(home / "design" / "design.json", {"schema_version": 1, "version": 2, "namn": "Lugn", "layout": "klassisk",
                                                              "tokens": {}, "sektioner": ["profil"], "historik": []})
            jc.write_json(home / "sok" / "kallor.json", {"schema_version": 1, "kallor": [{"id": "af", "typ": "jobtech", "namn": "AF"}]})
            jc.write_json(home / "sok" / "recept" / "uppsala.json", {"schema_version": 1, "namn": "uppsala", "kallor": ["af"]})
            con = sqlite3.connect(home / "sok" / "jobb.sqlite")
            con.execute("CREATE TABLE jobb(uid TEXT PRIMARY KEY, status TEXT DEFAULT 'ny', dubblett_av TEXT)")
            con.executemany("INSERT INTO jobb VALUES (?,?,?)", [("a", "ny", None), ("b", "ny", None), ("c", "ny", "a"), ("d", "sokt", None)])
            con.commit(); con.close()
            a = home / "ansokningar"
            jc.write_json(a / "2026-09-01-byran-x" / "logg.json", {"schema_version": 1, "status": "skickad", "skickad": "2026-09-01",
                                                                   "kanal": "mejl", "kontakt": "Eva", "foljupp_datum": "2026-09-15", "anteckningar": []})
            jc.write_json(a / "2026-09-20-region-y" / "logg.json", {"schema_version": 1, "status": "skickad", "skickad": "2026-09-20",
                                                                    "kanal": "formular", "kontakt": "", "foljupp_datum": "2026-10-20", "anteckningar": []})
            (a / "2026-09-30-utkast-z").mkdir()
            r = status.build(home, idag="2026-10-01")
            self.assertEqual(r["faktabank"]["roller"], 3)
            self.assertGreaterEqual(r["faktabank"]["fyllnadsgrad"], 90)
            self.assertTrue(r["design"]["finns"])
            self.assertEqual(r["kallor"]["recept"], ["uppsala"])
            self.assertEqual(r["jobb"]["ny"], 2)
            self.assertEqual(r["ansokningar"]["per_status"]["skickad"], 2)
            self.assertEqual(r["ansokningar"]["per_status"]["utkast"], 1)
            self.assertEqual([u["mapp"] for u in r["uppfoljning_forfallen"]], ["2026-09-01-byran-x"])
            self.assertEqual(r["nasta_steg"]["skill"], "jobbsok-start")
            self.assertIn("Följ upp", status.text(r))


if __name__ == "__main__":
    unittest.main()


class TestNatkoll(unittest.TestCase):
    def test_reservlage_nar_jobtech_blockeras(self):
        import natkoll
        fake = lambda url, timeout: ("blockerad", "proxy") if "jobtechdev" in url else ("ok", "HTTP 200")
        with mock.patch.dict(os.environ, {"JOBBSOK_OFFLINE": "0"}):
            r = natkoll.kolla(prova_fn=fake)
        self.assertEqual(r["lage"], "reserv")
        self.assertIn("jobsearch.api.jobtechdev.se", r["nodvandiga_blockerade"])
        self.assertNotIn("api.scb.se", r["blockerade"])
        self.assertIn("forsta", r["pdf"])
        with mock.patch.dict(os.environ, {"JOBBSOK_OFFLINE": "0"}):
            self.assertEqual(natkoll.kolla(prova_fn=lambda u, t: ("ok", "HTTP 404"))["lage"], "fullt")

    def test_spara_offline(self):
        import natkoll
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"JOBBSOK_OFFLINE": "1"}), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(natkoll.main(["--home", t, "--spara"]), 0)
            d = json.loads(Path(t, "profil", "miljo.json").read_text("utf-8"))
        self.assertEqual(d["lage"], "ej testad")
        self.assertTrue(all(r["status"] == "ej testad" for r in d["domaner"]))
