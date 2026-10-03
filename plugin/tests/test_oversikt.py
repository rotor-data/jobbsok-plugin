"""Tester för oversikt.py: tom och fylld home.

    python3 -m unittest discover plugin/tests -p 'test_oversikt.py'

Kör som skript för att bygga en fylld exempelmapp: python3 test_oversikt.py --bygg DIR
"""
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import oversikt  # noqa: E402

FIXTUR = HERE / "fixtures" / "home"
IDAG = "2026-10-01"

KOLUMNER = ("uid TEXT PRIMARY KEY, kalla TEXT, kalla_id TEXT, url TEXT, titel TEXT, arbetsgivare TEXT, orgnr TEXT, ort TEXT, "
            "kommun_id TEXT, distans INT, publicerad TEXT, deadline TEXT, anstallningsform TEXT, omfattning TEXT, "
            "kompetenser_json TEXT, utdrag TEXT, text_hash TEXT, dubblett_av TEXT, poang INT, poang_skal_json TEXT, "
            "status TEXT DEFAULT 'ny', forst_sedd TEXT, senast_sedd TEXT, bedomning_json TEXT, hittad_via TEXT")

JOBB = [
    ("af-1", "Kommunikatör", "Region Uppsala", "Uppsala", 1, "2026-10-12", 86, "ny", {"kompetens_traff": ["klarspråk", "webb"], "delar": {"ort": 20}}),
    ("af-2", "Kommunikationsstrateg", "Uppsala kommun", "Uppsala", 0, "2026-10-04", 78, "intressant", {"kompetens_traff": ["strategi"]}),
    ("tt-3", "Content lead", "Fyrtorn AB", "Stockholm", 2, None, 61, "ny", {}),
    ("af-4", "Verksamhetsutvecklare", "SLU", "Uppsala", 1, "2026-10-20", 44, "ny",
     {"joker": True, "joker_traff": ["skriva klart en text", "samhällsnytta"]}),
    ("af-5", "Säljare <b>", "Bolaget", "Enköping", 0, None, 20, "nej", {}),
    ("af-6", "Dubblett", "Region Uppsala", "Uppsala", 1, None, 80, "ny", {}),
    ("af-7", "Utesluten", "X", "Malmö", 0, None, 0, "ny", {"uteslutet": ["ort"]}),
]


def bygg_fylld(home):
    home = Path(home)
    shutil.copytree(FIXTUR, home, dirs_exist_ok=True)
    (home / "profil" / "det-har-vet-vi.md").write_text("# Det här vet vi\n\nDu vill skriva och göra skillnad.\n", encoding="utf-8")
    (home / "profil" / "coach.json").write_text(json.dumps({"schema_version": 1, "faser": {"intake": {"x": 1}},
                                                            "status": {"aktuell_fas": "identity"}}), encoding="utf-8")
    (home / "design").mkdir(exist_ok=True)
    (home / "design" / "design.json").write_text(json.dumps({"schema_version": 1, "version": 2, "namn": "Lugn klassisk"}), encoding="utf-8")
    sok = home / "sok"
    (sok / "recept").mkdir(parents=True, exist_ok=True)
    (sok / "kallor.json").write_text(json.dumps({"schema_version": 1, "kallor": [
        {"id": "af", "typ": "jobtech", "namn": "Platsbanken", "aktiv": True, "senast_hamtad": "2026-09-30T08:00:00"},
        {"id": "fyrtorn", "typ": "teamtailor_rss", "namn": "Fyrtorn AB", "aktiv": True, "tillagd_av": "anvandare"},
        {"id": "slu", "typ": "pagehash", "namn": "SLU lediga jobb", "aktiv": False}]}), encoding="utf-8")
    (sok / "recept" / "kommunikation-uppsala.json").write_text(json.dumps(
        {"schema_version": 1, "namn": "Kommunikation i Uppsala", "kallor": ["af"], "jobtech": {"q": "kommunikatör"}}), encoding="utf-8")
    (sok / "utbyte.json").write_text(json.dumps({"schema_version": 1, "per_kalla": {"af": {"totalt": 10, "intressant": 3, "sokt": 1}},
                                                 "per_recept": {"kommunikation-uppsala": {"totalt": 10, "intressant": 3}},
                                                 "per_hittad_via": {"h1": {"totalt": 4, "intressant": 1}}}), encoding="utf-8")
    (sok / "hypoteser.json").write_text(json.dumps({"schema_version": 1, "hypoteser": [
        {"id": "h1", "typ": "alternativ_titel", "beskrivning": "Myndigheter kallar rollen verksamhetsutvecklare", "metod": "jakt_titlar", "status": "aktiv", "korningar": [{"datum": "2026-09-01T08:00:00", "fynd": 4}], "utbyte": {"fynd": 4, "andel": 0.25}}]}),
        encoding="utf-8")
    con = sqlite3.connect(sok / "jobb.sqlite")
    con.execute(f"CREATE TABLE jobb({KOLUMNER})")
    for uid, titel, bolag, ort, dist, dl, p, st, sk in JOBB:
        con.execute("INSERT INTO jobb(uid,kalla,url,titel,arbetsgivare,ort,distans,deadline,poang,status,poang_skal_json,dubblett_av,utdrag,forst_sedd)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (uid, uid.split("-")[0], f"https://example.org/{uid}", titel, bolag, ort, dist, dl, p, st,
                     json.dumps(sk, ensure_ascii=False), "af-1" if uid == "af-6" else None, "Kort utdrag ur annonsen.", "2026-09-29"))
    con.commit()
    con.close()
    for mapp, logg, pdf in [
        ("2026-09-20-region-uppsala-kommunikator", {"status": "skickad", "skickad": "2026-09-20", "foljupp_datum": "2026-09-28", "bolag": "Region Uppsala", "roll": "Kommunikatör"}, True),
        ("2026-09-28-uppsala-kommun-kommunikationsstrateg", {"status": "utkast"}, False),
        ("2026-09-01-fyrtorn-content-lead", {"status": "intervju", "skickad": "2026-09-02", "foljupp_datum": "2026-10-08"}, True),
    ]:
        d = home / "ansokningar" / mapp
        d.mkdir(parents=True)
        (d / "logg.json").write_text(json.dumps(dict(schema_version=1, **logg)), encoding="utf-8")
        (d / "annons.md").write_text(f"# {mapp.split('-', 3)[3].replace('-', ' ').capitalize()}\n\nDeadline: 2026-10-10\n", encoding="utf-8")
        if pdf:
            (d / "cv.pdf").write_bytes(b"%PDF-1.4\n")
    return home


def data_ur(html):
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


class TestOversikt(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def kor(self, home):
        out = self.tmp / "ut.html"
        self.assertEqual(oversikt.main(["--home", str(home), "--out", str(out), "--idag", IDAG]), 0)
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("/*__", html)
        return html, data_ur(html)

    def test_tom_home(self):
        html, d = self.kor(self.tmp / "finns-inte")
        self.assertEqual(d["jobb"], [])
        self.assertEqual(d["ansokningar"], [])
        self.assertEqual(len(d["resa"]), 6)
        self.assertTrue(all(s["status"] == "ej" for s in d["resa"]))
        self.assertTrue(d["nasta"]["fras"])

    def test_standard_out_i_home(self):
        home = self.tmp / "h"
        home.mkdir()
        oversikt.main(["--home", str(home), "--idag", IDAG])
        self.assertTrue((home / "oversikt.html").exists())

    def test_fylld_home(self):
        home = bygg_fylld(self.tmp / "h")
        html, d = self.kor(home)
        uids = [j["uid"] for j in d["jobb"]]
        self.assertEqual(uids, ["af-1", "af-2", "tt-3", "af-4"])  # nej, dubblett och utesluten bort, sorterat på poäng
        self.assertTrue(next(j for j in d["jobb"] if j["uid"] == "af-4")["joker"])
        self.assertIn("klarspråk", d["jobb"][0]["motivering"])
        st = {a["status"] for a in d["ansokningar"]}
        self.assertEqual(st, {"skickad", "utkast", "intervju"})
        self.assertEqual(d["forfallna"], ["2026-09-20-region-uppsala-kommunikator"])
        a = next(a for a in d["ansokningar"] if a["status"] == "skickad")
        self.assertEqual(a["filer"]["cv.pdf"], "ansokningar/2026-09-20-region-uppsala-kommunikator/cv.pdf")
        self.assertEqual(a["deadline"], "2026-10-10")
        self.assertEqual((a["bolag"], a["roll"]), ("Region Uppsala", "Kommunikatör"))
        self.assertIn("4 fynd", d["bevakning"]["hypoteser"][0]["utfall"])
        self.assertEqual(d["profil"]["varden"][0], "samhällsnytta")
        self.assertTrue(any(k["egen"] for k in d["bevakning"]["kallor"]))
        self.assertEqual(d["bevakning"]["hypoteser"][0]["utbyte"], {"totalt": 4, "bra": 1})
        typer = {k["typ"] for k in d["kalender"]}
        self.assertTrue({"folj", "jobb", "deadline"} <= typer)
        self.assertEqual(d["kalender"], sorted(d["kalender"], key=lambda x: x["datum"]))
        self.assertEqual({s["id"]: s["status"] for s in d["resa"]}["design"], "klar")

    def test_html_escapas_i_data(self):
        home = bygg_fylld(self.tmp / "h")
        con = sqlite3.connect(home / "sok" / "jobb.sqlite")
        con.execute("UPDATE jobb SET titel='</script><script>alert(1)</script>' WHERE uid='af-1'")
        con.commit()
        con.close()
        html, d = self.kor(home)
        self.assertEqual(html.count("</script>"), 2)
        self.assertTrue(d["jobb"][0]["titel"].startswith("</script>"))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--bygg":
        print(bygg_fylld(sys.argv[2]))
    else:
        unittest.main()
