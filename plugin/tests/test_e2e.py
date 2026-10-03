"""E2E-genomkörning utan nät: från tom mapp till färdig ansökan och översikt.

Kör skripten som skillsen anropar dem (subprocess, samma flaggor som i SKILL.md),
med testpersonan i fixtures/home. Texterna i cv.json, brev.json och mejl.md är
skrivna som Claude skulle skriva dem enligt skillen ansokan.

    JOBBSOK_OFFLINE=1 python3 -m unittest discover plugin/tests -p 'test_e2e.py'
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = HERE.parent / "scripts"
FIX = HERE / "fixtures"


def jobtech_poster():
    """Fixturannonserna från JobTech, omgjorda till ingest-poster (som Claude gör vid nätfel)."""
    d = json.loads((FIX / "sok" / "jobtech_search.json").read_text(encoding="utf-8"))
    ut = []
    for h in d["hits"]:
        ut.append({"titel": h["headline"], "arbetsgivare": h["employer"]["name"],
                   "url": h.get("webpage_url") or f"https://arbetsformedlingen.se/platsbanken/annonser/{h['id']}",
                   "ort": h["workplace_address"].get("municipality"),
                   "deadline": (h.get("application_deadline") or "")[:10] or None,
                   "utdrag": ((h.get("description") or {}).get("text") or "")[:300]})
    return ut


ANNONS_UPPSALA = {
    "titel": "Kommunikatör med inriktning på klarspråk", "arbetsgivare": "Region Uppsala",
    "url": "https://example.org/annons/region-uppsala-kommunikator", "ort": "Uppsala",
    "kommun_id": "otaF_bQY_4ZD", "deadline": "2026-10-20", "anstallningsform": "tillsvidare",
    "omfattning": "heltid", "distans": 1,
    "text": "Vi söker en kommunikatör som skriver begripligt för patienter och invånare. Du leder "
            "kommunikationsprojekt, skriver i klarspråk och arbetar nära verksamheten. Erfarenhet av "
            "intranät och projektledning är meriterande.",
    "utdrag": "Vi söker en kommunikatör som skriver begripligt för patienter och invånare.",
}
ANNONS_VIKARIAT = {  # som Hemköp i testet: vikariat och lång pendling
    "titel": "Kommunikatör, vikariat", "arbetsgivare": "Butikskedjan AB",
    "url": "https://example.org/annons/butikskedjan-vikariat", "ort": "Stockholm", "kommun_id": "AvNB_uwa_6n6",
    "anstallningsform": "vikariat", "omfattning": "heltid", "distans": 0,
    "utdrag": "Vi söker en kommunikatör som skriver nyhetsbrev och intranät för våra butiker.",
}
ANNONS_SALJ = {"titel": "Säljare till mediebyrå", "arbetsgivare": "Annonsbolaget AB",
               "url": "https://example.org/annons/saljare", "ort": "Stockholm", "utdrag": "Säljare med provision."}


class TestE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="jobbsok-e2e-"))
        cls.home = cls.tmp / "Jobbsok"
        cls.env = dict(os.environ, JOBBSOK_OFFLINE="1", JOBBSOK_HOME=str(cls.home))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def kor(self, skript, *args, stdin=None, ok=(0,)):
        r = subprocess.run([sys.executable, str(S / skript), *map(str, args)], input=stdin,
                           capture_output=True, text=True, env=self.env, timeout=300)
        self.assertIn(r.returncode, ok, f"{skript} {args} gav {r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        return r

    def test_hela_kedjan(self):
        home = self.home
        # 1. jobbsok-start: skapa mappen
        self.kor("init_home.py", "--home", home)
        self.assertTrue((home / "README.md").exists())

        # 2. faktabank/karriarcoach: profilen på plats, validerad
        for f in ("fakta.json", "preferenser.json", "rost.json"):
            shutil.copy(FIX / "home" / "profil" / f, home / "profil" / f)
        self.kor("validate.py", home / "profil" / "fakta.json", home / "profil" / "preferenser.json",
                 home / "profil" / "rost.json")

        # 3. cv-design: välj förval
        self.kor("design_tool.py", "init", "--forval", "konservativ", "--home", home)
        design = json.loads((home / "design" / "design.json").read_text(encoding="utf-8"))
        self.kor("validate.py", home / "design" / "design.json")

        # 4. jobbsok: ingest -> dedupe -> score -> lista
        poster = jobtech_poster() + [ANNONS_UPPSALA, ANNONS_SALJ, dict(ANNONS_UPPSALA), ANNONS_VIKARIAT]
        r = self.kor("ingest.py", "--kalla", "webb", "--hittad-via", "e2e", "--home", home,
                     stdin=json.dumps(poster, ensure_ascii=False))
        self.assertTrue(json.loads(r.stdout).get("nya"))
        self.kor("dedupe.py", "--home", home)
        self.kor("score.py", "--jokrar", "2", "--home", home)
        r = self.kor("lista.py", "--json", "--home", home)
        lista = json.loads(r.stdout)
        jobb = lista if isinstance(lista, list) else lista["jobb"]
        uppsala = [j for j in jobb if "Uppsala" in (j.get("arbetsgivare") or "")]
        self.assertEqual(len(uppsala), 1, "dubbletten ska vara borta")
        uid = uppsala[0]["uid"]
        con = sqlite3.connect(home / "sok" / "jobb.sqlite")
        poang = dict(con.execute("select arbetsgivare, poang from jobb where dubblett_av is null").fetchall())
        self.assertGreater(poang["Region Uppsala"], poang["Annonsbolaget AB"])
        self.kor("lista.py", "satt", uid, "intressant", "--orsak", "klarspråk och Uppsala", "--home", home)
        # etikett och gränsbrott: syns i listan, utesluts inte
        self.assertTrue(uppsala[0]["etikett"])
        self.assertFalse(any("%" in (j.get("etikett") or "") for j in jobb))
        vik = [j for j in jobb if j["arbetsgivare"] == "Butikskedjan AB"]
        self.assertEqual(len(vik), 1, "gränsbrott ska visas, inte uteslutas")
        self.assertTrue(vik[0]["etikett"].startswith("Bryter mot din gräns: vikariat"), vik[0]["etikett"])
        self.assertTrue(any("pendling troligen över 45 min" in b for b in vik[0]["granbrott"]), vik[0]["granbrott"])
        r = self.kor("lista.py", "--home", home)
        self.assertIn("! Bryter mot din gräns: vikariat", r.stdout)

        # arbetsgivarkort (offline) och rollkort (fixturer i stället för JobTech/SCB)
        r = self.kor("arbetsgivarkort.py", "bygg", "Region Uppsala", "--typ", "region", "--utan-nat", "--home", home)
        self.kor("validate.py", home / "sok" / "arbetsgivare" / "region-uppsala.json")
        sys.path.insert(0, str(S))
        sys.path.insert(0, str(HERE))
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        import jakt_common as jc
        import rollkort as rk
        import sok_common as sc
        import test_rollkort as trk
        with mock.patch.object(jc, "api", side_effect=trk.falsk_api), \
                mock.patch.object(sc, "http_json", return_value=(200, trk.SCB, {})), redirect_stdout(io.StringIO()):
            self.assertEqual(rk.main(["--home", str(home), "bygg", "--roll", "kommunikatör", "--region", "Uppsala län",
                                      "--ar", "2"]), 0)
            rk.main(["--home", str(home), "glapp", "kommunikatör-uppsala"])
        self.kor("validate.py", home / "sok" / "rollkort" / "kommunikatör-uppsala.json")
        m = rk.jamfor(str(home))
        self.assertTrue(m["rader"][0]["etikett"])
        self.assertFalse(any("%" in r_["etikett"] for r_ in m["rader"]))

        # 5. ansokan: mappen, som skillen beskriver den
        mapp = home / "ansokningar" / "2026-10-01-region-uppsala-kommunikator"
        mapp.mkdir(parents=True)
        (mapp / "annons.md").write_text(
            f"Källa: {ANNONS_UPPSALA['url']}\nSista ansökningsdag: 2026-10-20\n\n# {ANNONS_UPPSALA['titel']}\n\n"
            f"{ANNONS_UPPSALA['text']}\n", encoding="utf-8")
        logg = {"schema_version": 1, "bolag": "Region Uppsala", "roll": "Kommunikatör", "deadline": "2026-10-20",
                "annons_url": ANNONS_UPPSALA["url"], "jobb_uid": uid, "status": "utkast", "skickad": None,
                "kanal": None, "kontakt": "", "foljupp_datum": None, "anteckningar": []}
        (mapp / "logg.json").write_text(json.dumps(logg, ensure_ascii=False, indent=1), encoding="utf-8")
        (mapp / "analys.json").write_text(json.dumps({
            "schema_version": 1, "sprak": "sv", "vinkel": "Hon gör vårdens texter begripliga och har mätt effekten.",
            "krav": [{"krav": "Skriva i klarspråk", "typ": "ska", "matchar": ["r1-m2"], "lucka": False, "kommentar": ""},
                     {"krav": "Projektledning", "typ": "meriterande", "matchar": ["r2-m1"], "lucka": False, "kommentar": ""},
                     {"krav": "Intranät", "typ": "meriterande", "matchar": ["r1-m1"], "lucka": False, "kommentar": ""}],
            "nyckelord": ["klarspråk", "patienter", "intranät"], "fragor_till_arbetsgivaren": []},
            ensure_ascii=False), encoding="utf-8")

        fakta = json.loads((home / "profil" / "fakta.json").read_text(encoding="utf-8"))
        m = {mm["id"]: mm["text"]["sv"] for r in fakta["roller"] for mm in r["meriter"]}
        p = fakta["person"]
        cv = {
            "schema_version": 1, "sprak": "sv", "design_version": design["version"],
            "person": {"namn": p["namn"], "titel": p["titel"]["sv"], "ort": p["ort"], "epost": p["epost"],
                       "telefon": p["telefon"], "lankar": p["lankar"], "foto": None},
            "profil": "Kommunikationsstrateg som skriver så att patienter och invånare förstår. Jag kan leda ett "
                      "projekt från idé till lansering och har skrivit om patientinformationen i Region Exempel.",
            "sektioner": [
                {"id": "erfarenhet", "typ": "erfarenhet", "rubrik": "Erfarenhet", "poster": [
                    {"titel": "Kommunikationsstrateg", "organisation": "Region Exempel", "ort": "Uppsala",
                     "period": "2021 – nu", "punkter": [m["r1-m1"], m["r1-m2"]], "kalla": ["r1-m1", "r1-m2"]},
                    {"titel": "Projektledare", "organisation": "Byrån AB", "period": "2017 – 2021",
                     "punkter": [m["r2-m1"]], "kalla": ["r2-m1"]},
                    {"titel": "Kommunikatör", "organisation": "Föreningen Läsglädje", "period": "2014 – 2017",
                     "punkter": [m["r3-m1"]], "kalla": ["r3-m1"]}]},
                {"id": "utbildning", "typ": "utbildning", "rubrik": "Utbildning", "poster": [
                    {"titel": "Medie- och kommunikationsvetenskap", "organisation": "Uppsala universitet",
                     "period": "2011 – 2014"}]},
                {"id": "kompetenser", "typ": "lista", "rubrik": "Kompetenser", "grupper": [
                    {"etikett": "Kommunikation", "poster": ["Projektledning", "Klarspråk"]}]},
                {"id": "sprak", "typ": "lista", "rubrik": "Språk", "grupper": [
                    {"etikett": "", "poster": ["Svenska (modersmål)", "Engelska (flytande)"]}]},
            ],
        }
        brev = {
            "schema_version": 1, "sprak": "sv",
            "mottagare": {"namn": "", "bolag": "Region Uppsala", "adress": ""}, "datum": "2026-10-01",
            "rubrik": "Kommunikatör som skriver begripligt",
            "stycken": [
                "Ni vill att patienter och invånare ska förstå det de läser. Det har varit mitt jobb de senaste åren.",
                "Som kommunikationsstrateg på Region Exempel skrev jag om patientinformationen i klarspråk "
                "tillsammans med fem vårdenheter. Jag ledde också omläggningen av intranätet, och antalet "
                "supportärenden minskade med 30 %.",
                "Jag kan driva projekt från start till mål. På Byrån AB drev jag tolv kampanjer från brief "
                "till lansering, alla inom budget.",
                "Jag berättar gärna mer när vi ses.",
            ],
            "halsning": "Vänliga hälsningar", "ton": {"personas": [{"namn": "Kim", "vikt": 1.0}]},
            "kalla_per_stycke": [["r1-m2"], ["r1-m2", "r1-m1"], ["r2-m1"], []],
        }
        (mapp / "cv.json").write_text(json.dumps(cv, ensure_ascii=False, indent=1), encoding="utf-8")
        (mapp / "brev.json").write_text(json.dumps(brev, ensure_ascii=False, indent=1), encoding="utf-8")
        (mapp / "mejl.md").write_text(
            "Ämne: Ansökan: Kommunikatör – Lina Testsson\n\nHej!\n\n"
            "Här kommer min ansökan till tjänsten som kommunikatör. CV och brev ligger bifogade.\n"
            "Jag har skrivit om texter till patienter i klarspråk, så att fler förstår dem.\n"
            "Hör gärna av er om ni har frågor.\n\nVänliga hälsningar\nLina Testsson\n070-000 00 00\n",
            encoding="utf-8")

        # 6. Kontrollerna i steg 7, i skillens ordning
        for args in (("cv.json", "--profil", "kim"), ("brev.json",), ("mejl.md",)):
            r = self.kor("antiai.py", mapp / args[0], *args[1:], ok=(0, 2))
            if r.returncode == 2:
                self.fail(f"antiai hittade AI-tics i {args[0]}: {r.stdout[:1500]}")
        r = self.kor("sparbarhet.py", mapp, "--home", home, ok=(0, 2))
        fynd = json.loads(r.stdout)
        fel = [f for f in fynd["fynd"] if f["allvar"] == "fel"]
        self.assertFalse(fel, f"spårbarhetsfel: {r.stdout[:1500]}")
        self.kor("validate.py", mapp / "cv.json", mapp / "brev.json", mapp / "logg.json", mapp / "analys.json")

        for typ in ("cv", "brev"):
            r = self.kor("render.py", typ, mapp, "--home", home)
            res = json.loads(r.stdout)
            self.assertTrue((mapp / f"{typ}.html").exists())
            if res.get("pdf"):
                self.assertTrue((mapp / f"{typ}.pdf").exists())
                self.assertLessEqual(res.get("sidor") or 1, 2 if typ == "cv" else 1)
        html = (mapp / "cv.html").read_text(encoding="utf-8")
        self.assertLess(html.index("Erfarenhet"), html.index("Utbildning"))

        # 7. intervju-och-beslut: kallad på intervju
        logg.update(status="intervju", skickad="2026-10-01")
        (mapp / "logg.json").write_text(json.dumps(logg, ensure_ascii=False, indent=1), encoding="utf-8")
        (mapp / "intervju.json").write_text(json.dumps({
            "schema_version": 1, "bolag": "Region Uppsala", "roll": "Kommunikatör", "skapad": "2026-10-01",
            "omgangar": [{"nr": 1, "datum": "2099-10-12", "tid": "10:00", "format": "plats", "plats": "Uppsala"}],
            "fragor_troliga": [{"id": "f1", "fraga": "Berätta om ett klarspråksprojekt", "typ": "krav",
                                "kalla": ["r1-m2"], "status": "klar"},
                               {"id": "f2", "fraga": "Hur prioriterar du?", "typ": "standard", "status": "ovad"}]},
            ensure_ascii=False), encoding="utf-8")
        (mapp / "intervju.md").write_text("# Inför intervjun\n", encoding="utf-8")
        self.kor("validate.py", mapp / "intervju.json", mapp / "logg.json")

        # 8. Översikten läser logg.json i första hand
        r = self.kor("oversikt.py", "--home", home, "--idag", "2026-10-01")
        self.assertTrue((home / "oversikt.html").exists())
        import oversikt
        d = oversikt.bygg_data(home, "2026-10-01")
        a = d["ansokningar"][0]
        self.assertEqual((a["bolag"], a["roll"], a["deadline"]), ("Region Uppsala", "Kommunikatör", "2026-10-20"))
        self.assertEqual((a["intervju"]["datum"], a["intervju"]["tid"]), ("2099-10-12", "10:00"))
        self.assertEqual(a["intervju"]["forberedelse"], f"ansokningar/{mapp.name}/intervju.md")
        self.assertEqual((a["intervju"]["klara"], a["intervju"]["fragor"]), (1, 2))
        self.assertTrue(any(h["typ"] == "intervju" for h in d["kalender"]))
        jo = {j["bolag"]: j for j in d["jobb"]}
        self.assertTrue(jo["Region Uppsala"]["etikett"])
        self.assertTrue(jo["Region Uppsala"]["motivering"])
        self.assertEqual(jo["Region Uppsala"]["arbetsgivarkort"]["slug"], "region-uppsala")
        self.assertIn("vikariat", jo["Butikskedjan AB"]["granbrott"])
        self.assertTrue(d["riktningar"]["kort"][0]["etikett"])
        html = (home / "oversikt.html").read_text(encoding="utf-8")
        for bit in ("Bryter mot din gräns", "Arbetsgivarkort", "Förberedelse", "etikett"):
            self.assertIn(bit, html)
        self.kor("status.py", "--format", "json", "--home", home)


if __name__ == "__main__":
    unittest.main()
