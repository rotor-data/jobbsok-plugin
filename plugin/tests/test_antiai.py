"""Tester för antiai.py och sparbarhet.py. Kör:
python3 -m unittest discover plugin/tests -p 'test_antiai.py'
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import antiai  # noqa: E402
import sparbarhet  # noqa: E402


def _skriv(p, data):
    with open(p, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))


def regler(text, sprak="sv", profil="standard", typ="text"):
    traffar, _ = antiai.analysera([antiai.Segment(None, text)], sprak, profil, typ)
    return {t["regel"] for t in traffar}


class TicFlaggas(unittest.TestCase):
    def test_sv(self):
        fall = [
            ("Det handlar inte om snabbhet, utan om precision.", "antites_pivot"),
            ("Inte bara ett verktyg — utan en partner.", "antites_pivot"),
            ("Vi bygger inte det enkla. Men det rätta.", "antites_pivot"),
            ("Det viktiga är att jag sätter kunden först.", "metadiskurs"),
            ("Det är där förklaringen brukar börja.", "metadiskurs"),
            ("Det är värt att notera att jag har körkort.", "metadiskurs"),
            ("I dagens arbetsliv behövs struktur.", "stark_klyscha"),
            ("Jag erbjuder en sömlös upplevelse för kunderna.", "stark_klyscha"),
            ("Sammanfattningsvis passar jag för rollen.", "stark_klyscha"),
            ("Jag vill navigera, optimera och effektivisera med en robust och innovativ metod.", "ai_ord_kluster"),
        ]
        for text, regel in fall:
            with self.subTest(text=text):
                self.assertIn(regel, regler(text, "sv"))

    def test_en(self):
        fall = [
            ("It's not just a job, but a calling.", "antites_pivot"),
            ("It's not about speed. It's about care.", "antites_pivot"),
            ("That's where the explanation usually begins.", "metadiskurs"),
            ("It's worth noting that I hold a forklift licence.", "metadiskurs"),
            ("I am passionate about logistics.", "stark_klyscha"),
            ("I have a proven track record in sales.", "stark_klyscha"),
            ("In today's market, speed counts.", "stark_klyscha"),
            ("I leverage robust, seamless and holistic tools to foster synergy.", "ai_ord_kluster"),
        ]
        for text, regel in fall:
            with self.subTest(text=text):
                self.assertIn(regel, regler(text, "en"))

    def test_kim_noll_garderingar(self):
        for text in ["Det kan komma att påverka leveransen.", "Jag skulle kunna leda team.",
                     "Förändringen kan möjligen ge effekt.", "Det kan vara svårt att mäta."]:
            with self.subTest(text=text):
                self.assertIn("gardering", regler(text, "sv", "kim"))
                self.assertNotIn("gardering", regler(text, "sv", "standard"))

    def test_kan_som_formaga_ar_ingen_gardering(self):
        for text in ["Jag kan leda team.", "Kan ta ansvar för en hel lansering.",
                     "Jag kan vara på plats i januari.", "Vi kan bli fler till hösten."]:
            with self.subTest(text=text):
                self.assertNotIn("gardering", regler(text, "sv", "kim"))

    def test_tre_pivoter_ar_tic(self):
        text = ("Det är inte tempo, utan omsorg. Jag mäter inte timmar, utan resultat. "
                "Vi säljer inte varor, utan trygghet.")
        tr, _ = antiai.analysera([antiai.Segment(None, text)], "sv")
        piv = [t for t in tr if t["regel"] == "antites_pivot"]
        self.assertEqual(len(piv), 3)
        self.assertTrue(all(t["allvar"] == "maste_fixas" for t in piv))


class RentFlaggasInte(unittest.TestCase):
    def test_sv_rent(self):
        for text in [
            "Jag ledde ett lager med sex anställda i Uppsala.",
            "Priset steg 14 procent på ett kvartal.",
            "Det är där vi bygger den nya hallen.",
            "Vi mätte om det. Det är poängen.",
            "Vi hann inte med mötet, men det löste sig.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(regler(text, "sv"), set())

    def test_motsatt_kontrollfall_utan_att(self):
        # "utan att" är ett villkor, inte en antites – får inte flaggas.
        for text in ["Det går inte att förenkla ytterligare utan att bli missvisande.",
                     "Jag kan inte lämna lagret utan att någon tar över."]:
            with self.subTest(text=text):
                self.assertNotIn("antites_pivot", regler(text, "sv"))

    def test_nominalisering_bara_riktiga_avledningar(self):
        # Ord som bara slutar likadant ("region", "ring", "pension", "Jönköping") räknas inte.
        text = ("Region Uppsala, ring, ting, pension, station, religion, version, vision, mission, "
                "Jönköping, universitet, erfarenhet, vårdenheter, ordförande, nuvarande, fortfarande. ") * 3
        _, sig = antiai.analysera([antiai.Segment(None, text)], "sv")
        self.assertEqual(sig["nominal_per100"], 0)
        _, sig = antiai.analysera([antiai.Segment(None, "Planering, samordning, uppföljning och tydlighet.")], "sv")
        self.assertGreater(sig["nominal_per100"], 50)

    def test_nominaliseringskedja_i_kort_falt(self):
        self.assertIn("nominalisering", regler(
            "Möjliggjorde en effektivisering genom digitalisering, automatisering och standardisering.", "sv", typ="cv"))

    def test_bojda_klyschor(self):
        for text in ["Banade väg för en ny kultur.", "Spelade en avgörande roll i bytet.",
                     "Utnyttjade kraften i data."]:
            with self.subTest(text=text):
                self.assertIn("stark_klyscha", regler(text, "sv"))
        self.assertNotIn("stark_klyscha", regler("Gjutningen krävde betong.", "sv"))

    def test_en_not_but_kontrollfall(self):
        for text in ["I could not attend your open house last week, but I read the notes.",
                     "It was not cheap, but it paid off in a year.",
                     "I did not finish the course, but I am taking the last module."]:
            with self.subTest(text=text):
                self.assertNotIn("antites_pivot", regler(text, "en"))
        for text in ["It's not just a job, but a calling.", "Warehouses are not just buildings. They are the heart."]:
            with self.subTest(text=text):
                self.assertIn("antites_pivot", regler(text, "en"))

    def test_sv_inte_i_vanlig_berattelse(self):
        for text in ["Det kom inte av någon stor reform. Vi flyttade artiklarna närmare packningen.",
                     "Det var inte min idé från början. En mamma frågade, och vi provade."]:
            with self.subTest(text=text):
                self.assertNotIn("antites_pivot", regler(text, "sv"))
        self.assertIn("antites_pivot", regler("Jag är inte bara undersköterska – jag är en trygg hand.", "sv"))

    def test_en_rent(self):
        for text in [
            "I ran a warehouse team of six in Uppsala.",
            "I sent the notes after the meeting.",
            "Sales grew 14 percent in one quarter.",
        ]:
            with self.subTest(text=text):
                self.assertNotIn("antites_pivot", regler(text, "en"))
                self.assertNotIn("stark_klyscha", regler(text, "en"))
                self.assertNotIn("metadiskurs", regler(text, "en"))


FIXT = os.path.join(HERE, "fixtures", "antiai")


def _korpus(namn):
    with open(os.path.join(FIXT, namn), encoding="utf-8") as f:
        return json.load(f)["texter"]


def _flaggade(texter, profil):
    ut = []
    for t in texter:
        if profil == "kim" and t["typ"] != "cv":
            continue
        tr, _ = antiai.analysera([antiai.Segment(None, t["text"])], t["sprak"], profil, t["typ"])
        ut.append((t["id"], sorted({x["regel"] for x in tr})))
    return ut


class Korpus(unittest.TestCase):
    """Kalibreringskorpus (korpus.json) och kontrollkorpus skriven efteråt (kontroll.json).
    Mål: under 5 % falska positiva på rena texter, minst 90 % fångade smutsiga."""

    MAX_FP = 0.05
    MIN_TRAFF = 0.90

    def matt(self, namn):
        texter = _korpus(namn)
        for profil in ("standard", "kim"):
            rena = _flaggade([t for t in texter if t["ren"]], profil)
            smutsiga = _flaggade([t for t in texter if not t["ren"]], profil)
            fp = [x for x in rena if x[1]]
            missade = [x[0] for x in smutsiga if not x[1]]
            with self.subTest(korpus=namn, profil=profil):
                self.assertLess(len(fp) / len(rena), self.MAX_FP, f"falska positiva: {fp}")
                self.assertGreaterEqual(1 - len(missade) / len(smutsiga), self.MIN_TRAFF, f"missade: {missade}")

    def test_kalibrering(self):
        texter = _korpus("korpus.json")
        self.assertGreaterEqual(sum(1 for t in texter if t["ren"] and t["typ"] == "cv"), 30)
        self.matt("korpus.json")

    def test_kontroll(self):
        self.matt("kontroll.json")

    def test_hela_cv_sammanslaget(self):
        # cv.json mäts som ett sammanslaget CV: rena punkter ska inte ge täthetsbrus.
        for ren in (True, False):
            punkter = [t["text"] for t in _korpus("korpus.json") if t["ren"] == ren and t["typ"] == "cv"]
            for i in range(0, len(punkter), 8):
                for profil in ("standard", "kim"):
                    tr, _ = antiai.analysera([antiai.Segment(f"p{j}", p) for j, p in enumerate(punkter[i:i + 8])],
                                             "sv", profil, "cv")
                    with self.subTest(ren=ren, i=i, profil=profil):
                        (self.assertFalse if ren else self.assertTrue)(tr, tr)


class Antites(unittest.TestCase):
    """Bred upptäckt, graderad allvarsnivå: en antites = flagga, två eller fler = maste_fixas."""

    def kor(self, namn):
        for t in _korpus(namn):
            with self.subTest(text=t["text"]):
                (self.assertIn if t["tic"] else self.assertNotIn)("antites_pivot", regler(t["text"], t["sprak"]))

    def test_fixturer(self):
        self.kor("antites.json")

    def test_kontroll_skriven_efterat(self):
        self.kor("antites_kontroll.json")

    def test_en_ar_flagga_tva_ar_maste_fixas(self):
        for text, sprak in [("Det var inte lätt, men det var värt det.", "sv"),
                            ("We don't just build products, we build trust.", "en")]:
            tr, _ = antiai.analysera([antiai.Segment(None, text)], sprak)
            self.assertEqual([t["allvar"] for t in tr if t["regel"] == "antites_pivot"], ["flagga"])
        tr, _ = antiai.analysera([antiai.Segment(None, "Jag söker inte ett jobb, men ett sammanhang. "
                                                 "Mindre prat, mer verkstad.")], "sv")
        piv = [t["allvar"] for t in tr if t["regel"] == "antites_pivot"]
        self.assertEqual(piv, ["maste_fixas", "maste_fixas"])


class CliOchJson(unittest.TestCase):
    def kor(self, args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            kod = antiai.main(args)
        return kod, json.loads(buf.getvalue())

    def test_brev_json_faltvis(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "brev.json")
            _skriv(p, {"schema_version": 1, "sprak": "sv", "stycken": [
                "Jag har lett lagret i fyra år.", "Sammanfattningsvis passar jag bra."]})
            kod, ut = self.kor([p])
        self.assertEqual(kod, 2)
        t = [x for x in ut["traffar"] if x["regel"] == "stark_klyscha"][0]
        self.assertEqual(t["position"]["falt"], "stycken[1]")
        self.assertEqual(t["position"]["start"], 0)

    def test_rent_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt")
            _skriv(p, "Jag ledde ett lager med sex anställda.")
            kod, ut = self.kor([p, "--sprak", "sv"])
        self.assertEqual(kod, 0)
        self.assertTrue(ut["rent"])


FAKTA = {
    "schema_version": 1,
    "roller": [{"id": "r1", "arbetsgivare": "Lagret AB", "meriter": [
        {"id": "r1-m1", "text": {"sv": "Minskade ledtiden med 30 %"},
         "siffror": [{"varde": "30 %", "betydelse": "kortare ledtid"}], "omfattning": "team 6 pers"}]}],
    "utbildning": [{"id": "u1"}],
    "aldrig_pastaa": ["budgetansvar", "Har aldrig varit \"chef\" formellt"],
}


class Sparbarhet(unittest.TestCase):
    def kor(self, cv=None, brev=None, rost=None):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "fakta.json")
            _skriv(fp, FAKTA)
            rp = os.path.join(d, "rost.json")
            _skriv(rp, rost or {"aldrig_ord": []})
            mapp = os.path.join(d, "ans")
            os.mkdir(mapp)
            if cv:
                _skriv(os.path.join(mapp, "cv.json"), cv)
            if brev:
                _skriv(os.path.join(mapp, "brev.json"), brev)
            buf = io.StringIO()
            with redirect_stdout(buf):
                kod = sparbarhet.main([mapp, "--fakta", fp, "--rost", rp])
            return kod, json.loads(buf.getvalue())

    def cv(self, punkt, kalla):
        return {"schema_version": 1, "sprak": "sv", "profil": "Lagerledare.",
                "sektioner": [{"typ": "erfarenhet", "poster": [{"titel": "Lagerledare", "punkter": [punkt], "kalla": kalla}]}]}

    def test_ren(self):
        kod, ut = self.kor(cv=self.cv("Minskade ledtiden med 30 %.", ["r1-m1"]))
        self.assertEqual(kod, 0, ut)

    def test_saknad_och_okand_kalla(self):
        _, ut = self.kor(cv=self.cv("Minskade ledtiden.", []))
        self.assertIn("saknar_kalla", {f["regel"] for f in ut["fynd"]})
        _, ut = self.kor(cv=self.cv("Minskade ledtiden.", ["r9-m9"]))
        self.assertIn("okand_kalla", {f["regel"] for f in ut["fynd"]})

    def test_siffror(self):
        _, ut = self.kor(cv=self.cv("Minskade ledtiden med 45 %.", ["r1-m1"]))
        self.assertIn("siffra_saknas_i_fakta", {f["regel"] for f in ut["fynd"]})
        _, ut = self.kor(cv=self.cv("Ledde 6 personer.", ["r1-m1"]))
        self.assertEqual({f["regel"] for f in ut["fynd"]}, {"siffra_utanfor_siffror"})

    def test_aldrig_pastaa_och_aldrig_ord(self):
        brev = {"schema_version": 1, "sprak": "sv",
                "stycken": ["Jag hade budgetansvar.", "Som chef var jag grym."],
                "kalla_per_stycke": [["r1-m1"], ["r1"]]}
        _, ut = self.kor(brev=brev, rost={"aldrig_ord": ["grym"]})
        regl = [f["regel"] for f in ut["fynd"]]
        self.assertEqual(regl.count("aldrig_pastaa"), 2)
        self.assertIn("aldrig_ord", regl)

    def test_brev_kalla_per_stycke_langd(self):
        brev = {"schema_version": 1, "sprak": "sv", "stycken": ["A b c.", "D e f."], "kalla_per_stycke": [["r1-m1"]]}
        _, ut = self.kor(brev=brev)
        regl = {f["regel"] for f in ut["fynd"]}
        self.assertIn("kalla_per_stycke_langd", regl)
        self.assertIn("saknar_kalla", regl)

    def test_tomt_brevstycke_ar_varning(self):
        brev = {"schema_version": 1, "sprak": "sv", "stycken": ["Jag ledde lagret.", "Hör gärna av er."],
                "kalla_per_stycke": [["r1-m1"], []]}
        _, ut = self.kor(brev=brev)
        self.assertEqual([(f["regel"], f["allvar"]) for f in ut["fynd"]], [("stycke_utan_kalla", "varning")])


if __name__ == "__main__":
    unittest.main()
