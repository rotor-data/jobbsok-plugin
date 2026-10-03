#!/usr/bin/env python3
"""antiai.py – deterministisk kontroll av typiska AI-maner i svensk och engelsk text.

Inga beroenden, ingen modell, inget nätverk. Reglerna är skrivna för jobbansökningar:
CV-punkter, personliga brev och korta mejl.

Användning:
  python3 antiai.py <fil>            # .md, .txt, .json (cv.json/brev.json läses fältvis)
  python3 antiai.py - < text.txt     # stdin
  Flaggor: --sprak sv|en|auto  --profil standard|kim  --typ auto|cv|brev|text

Utdata: JSON på stdout med träffar (regel, citat, position, forslag, allvar) och en kort
svensk sammanfattning. Exit 0 = rent, 2 = något flaggat, 1 = fel i indata.

Regler
  stark_klyscha    Fraser som nästan bara förekommer i genererad eller mallskriven text:
                   klyschiga ingresser, tomma avslutningar, hype-ord och jobbansöknings-
                   klyschor. En träff räcker. Allvar: maste_fixas.
  metadiskurs      Text som talar om sig själv i stället för om saken ("det är värt att
                   notera", "det viktiga är att"). Allvar: flagga.
  ai_ord_kluster   Ord som språkmodeller överanvänder. Listan för engelska utgår från
                   Kobak m.fl. 2024 ("Delving into ChatGPT usage in academic writing
                   through excess vocabulary"), som visade att ord som delve, showcase,
                   underscore, pivotal och intricate ökade kraftigt efter 2022. Den
                   svenska listan är skriven för projektet efter samma princip. Ett ord är
                   normalt; tre olika i samma mening är ett kluster. Allvar: maste_fixas.
  antites_pivot    Kontrastfiguren "inte X, utan Y" i alla former. Kräver en kontrastram:
                   att det efter negationen kommer en parallell, kort motbild ("men ett
                   sammanhang", "– det är kvalitet", "Vi bygger relationer."). Vanlig
                   berättelse ("Bussen kom inte, men en kollega körde mig") har ett nytt
                   subjekt och en ny handling och flaggas inte. En antites i hela texten =
                   flagga; två eller fler = maste_fixas på alla.
  trippellista     "A, B och C" där alla tre är enstaka abstrakta ord eller egenskaps-
                   adjektiv ("strukturerad, driven och engagerad"). Allvar: flagga.
  nominalisering   Substantivtung text: verb gjorda till substantiv (planering,
                   uppföljning, tydlighet). Mäts per mening (kedjor) och per text (täthet).
                   CV-punkter är fragment och får en mildare gräns. Allvar: flagga.
  gardering        Bara garderande konstruktioner ("kan komma att", "skulle kunna",
                   "möjligen", "det kan vara"). "Jag kan leda" är förmåga, inte gardering.
                   Standard: flaggas vid två i samma fält eller hög täthet. Profil kim
                   (klarspråk): varje gardering måste bort.
  bindeord         Tunga, formella bindeord (dessutom, vidare, därtill, moreover). Ett är
                   normalt; täthet flaggas.
  meningsvariation Monoton meningsrytm: alla meningar ungefär lika långa. Mäts bara på
                   brev och löptext med minst sex meningar, aldrig på CV-punkter.

Motivering för täthetsgränserna: en klarspråkstext har sällan mer än en nominalisering
var tjugonde ord (5 per 100) i löptext. CV-punkter saknar subjekt och blir därför tätare
av sig själva, så gränsen är 10 per 100. Garderingar och tunga bindeord är ovanliga i en
kort ansökan; två per 100 ord är redan mycket. Rytmen mäts som variationskoefficienten
(standardavvikelse / medel) för meningslängden; under 0,25 betyder att nästan alla
meningar är lika långa.
"""
import argparse
import json
import re
import statistics
import sys

# ── Ordlistor ────────────────────────────────────────────────────────────

# (mönster, förslag). Mönster är reguljära uttryck; de omges av ordgränser.
KLYSCHOR = {
    "sv": [
        # ingresser
        (r"i dagens (snabbt )?(föränderliga |digitala |moderna )?\w+", "börja med något konkret ur annonsen"),
        (r"i en (ständigt |allt mer |alltmer )?(föränderlig|komplex|digital|snabbrörlig) (värld|omvärld|tid)",
         "stryk inledningen"),
        (r"i en värld där", "stryk inledningen"),
        (r"i en tid då", "stryk inledningen"),
        (r"det är ingen hemlighet att", "stryk"),
        (r"som vi alla vet", "stryk"),
        (r"med (stort|stor) (intresse|entusiasm)", "säg vad i annonsen som fick dig att söka"),
        (r"det är med stor \w+ (jag|som)", "säg vad i annonsen som fick dig att söka"),
        # avslutningar
        (r"sammanfattningsvis", "stryk; avsluta med något konkret"),
        (r"avslutningsvis", "stryk; avsluta med något konkret"),
        (r"för att summera", "stryk"),
        (r"när allt kommer omkring", "stryk"),
        (r"(jag är|är jag) övertygad om att", "säg vad du gjort i stället för vad du tror"),
        (r"ser fram emot möjligheten", "'hör gärna av er' eller föreslå ett möte"),
        (r"(en )?(värdefull )?tillgång för (er|ert|teamet|organisationen)", "visa med en merit"),
        (r"fortsatta framgång", "stryk"),
        # hype och bilder
        (r"sömlös\w*", "beskriv vad som faktiskt fungerade"),
        (r"banbrytande", "säg vad som var nytt"),
        (r"holistisk\w*", "säg vad som ingick"),
        (r"i världsklass", "visa med en siffra"),
        (r"skräddarsydd\w*", "säg för vem och hur"),
        (r"(spelade|spelar|spela) en (avgörande|nyckel|central|viktig) roll", "säg vad du gjorde"),
        (r"nyckelroll\w*", "säg vad du gjorde"),
        (r"banade väg", "säg vad som hände"),
        (r"banar väg", "säg vad som händer"),
        (r"(utnyttjade|utnyttja|utnyttjar) kraften", "säg vad du använde och till vad"),
        (r"kraften i", "säg vad du använde"),
        (r"(den )?fulla potential\w*", "säg vad resultatet blev"),
        (r"ligger i framkant", "säg vad du kan"),
        (r"tänja på gränserna", "säg vad du gjorde"),
        (r"katalysator\w*", "säg vad du gjorde"),
        (r"drivkraft\w*", "stryk eller säg vad du gjorde"),
        (r"mervärde\w*", "säg vilket värde, gärna med en siffra"),
        (r"leverera värde", "säg vilket värde"),
        (r"(underströk|understryka|betonade|betona) vikten", "säg vad du gjorde"),
        (r"en kultur av", "beskriv vad folk gjorde annorlunda"),
        (r"driva tillväxt", "säg hur mycket det växte"),
        # jobbansökningsklyschor
        (r"brinner för", "visa intresset med något du gjort"),
        (r"passion för", "visa intresset med något du gjort"),
        (r"passionerad\w*", "stryk; visa med en merit"),
        (r"gedig\w*", "ange år eller omfattning"),
        (r"beprövad förmåga", "visa med en merit"),
        (r"resultat(inriktad|orienterad|driven)\w*", "visa ett resultat i stället"),
        (r"lösningsorienterad\w*", "visa med ett exempel"),
        (r"lagspelare", "säg vad du gjort tillsammans med andra"),
        (r"dynamisk (miljö|organisation)", "stryk"),
        (r"enastående resultat", "ange resultatet"),
        (r"ett kall", "säg varför du valt yrket, konkret"),
    ],
    "en": [
        (r"in today's (fast-paced |ever-changing |competitive |digital )?\w+", "start with something concrete from the ad"),
        (r"in a world where", "cut the opening"),
        (r"in an (ever-changing|increasingly \w+) (world|landscape)", "cut the opening"),
        (r"fast-paced", "cut"),
        (r"ever-evolving", "cut"),
        (r"competitive landscape", "cut"),
        (r"at the end of the day", "cut"),
        (r"in conclusion", "cut; end with something concrete"),
        (r"to sum up", "cut"),
        (r"needless to say", "cut"),
        (r"i am (excited|thrilled) to apply", "say what in the ad made you apply"),
        (r"i am confident (that )?(i|my)", "show it with a result instead"),
        (r"(great|perfect|ideal) (fit|candidate)", "cut; let the merits speak"),
        (r"welcome the opportunity", "suggest a meeting plainly"),
        (r"passionate about", "show the interest with something you did"),
        (r"passionate", "cut; show it with a result"),
        (r"proven track record", "give the result"),
        (r"results-driven", "give a result instead"),
        (r"team player", "say what you did with others"),
        (r"thrives? in", "say what you did"),
        (r"self-starter", "cut"),
        (r"go-getter", "cut"),
        (r"detail-oriented", "show it with an example"),
        (r"think outside the box", "say what you did"),
        (r"hit the ground running", "say when you can start"),
        (r"plays? a (pivotal|crucial|key|vital) role", "say what it does"),
        (r"played a (pivotal|crucial|key|vital) role", "say what you did"),
        (r"pave the way", "say what happened"),
        (r"harness the power", "say what you used"),
        (r"unlock the (full )?potential", "say what the result was"),
        (r"beating heart", "cut the image"),
        (r"cutting-edge", "name the tool"),
        (r"operational excellence", "give a number"),
        (r"comprehensive skill set", "name the skills"),
        (r"a testament to", "cut"),
        (r"take it to the next level", "say what changes"),
    ],
}

METAPRAT = {
    "sv": [
        (r"det är (värt|viktigt) att (notera|nämna|påpeka|understryka)", "stryk; säg saken direkt"),
        (r"värt att nämna", "stryk; säg saken direkt"),
        (r"det viktiga (här )?är att", "stryk; säg saken direkt"),
        (r"vill jag (understryka|betona|poängtera|lyfta fram)", "stryk"),
        (r"låt (mig|oss) (förklara|utforska|titta)", "stryk"),
        (r"det är (just |precis )?(här|där) (min |mitt |vår |vårt )?\w+ (\w+ )?(ligger|börjar|börja|kommer in)",
         "stryk; texten ska inte peka på sig själv"),
        (r"som (tidigare )?nämnts", "stryk"),
    ],
    "en": [
        (r"it'?s worth (noting|mentioning)", "cut; say it directly"),
        (r"it is (worth|important) (noting|to note)", "cut; say it directly"),
        (r"let me (explain|be clear)", "cut"),
        (r"i want to (emphasi[sz]e|stress|highlight)", "cut"),
        (r"(that's|that is) (exactly )?where (my |the |our )?\w+ (\w+ )?(lies|begins|comes in)",
         "cut; the text should not point at itself"),
        (r"as (previously )?mentioned", "cut"),
    ],
}

AI_ORD = {
    # Ordstammar; matchas som ordbörjan.
    "sv": ["navigera", "optimera", "effektivisera", "robust", "innovativ", "holistisk", "sömlös", "synergi",
           "främja", "möjliggj", "möjliggör", "säkerställ", "strömlinjeform", "dynamisk", "proaktiv",
           "heltäckande", "skalbar", "banbrytande", "mångsidig", "gedig", "tillhandahåll", "underlätta",
           "katalysator", "kundorienterad", "transformation", "helhetssyn", "kostnadseffektiv", "smidig",
           "strategisk", "landskap", "ekosystem", "hörnsten", "kraftfull", "exceptionell", "frigöra",
           "användarvänlig", "framtidssäker", "mångfacetterad", "engagerad", "driven"],
    "en": ["delve", "showcas", "underscor", "pivotal", "intricate", "meticulous", "commendable", "notabl",
           "comprehensive", "crucial", "realm", "tapestry", "invaluable", "noteworthy", "garner", "leverag",
           "foster", "elevat", "streamlin", "robust", "seamless", "holistic", "synerg", "navigat", "landscape",
           "enhanc", "empower", "dynamic", "innovative", "impactful", "scalable", "spearhead", "multifaceted",
           "nuanced", "paramount", "testament", "embark", "endeavo", "vibrant", "unwavering", "cross-functional",
           "dedicated", "excellence"],
}

GARDERINGAR = {
    "sv": [r"kan komma att", r"skulle kunna", r"möjligen", r"eventuellt", r"kanske", r"torde", r"förmodligen",
           r"i viss mån", r"till viss del", r"(det|detta|vilket) kan (vara|bli|ge|innebära|påverka|leda)"],
    "en": [r"might", r"could potentially", r"arguably", r"perhaps", r"to some extent", r"it could be",
           r"(it|this|that) may"],
}

BINDEORD = {
    "sv": [r"dessutom", r"vidare", r"därtill", r"därmed", r"således", r"följaktligen", r"emellertid", r"likaså",
           r"i synnerhet", r"härmed"],
    "en": [r"furthermore", r"moreover", r"additionally", r"consequently", r"thus", r"hence", r"nevertheless",
           r"notably"],
}

# Nominaliseringar: avledningsändelser med minsta stamlängd, böjda former ingår.
# "-ion", "-het" i allmänhet och "-ande" räknas inte: där finns för många vanliga ord
# (region, pension, erfarenhet, ordförande) som inte gör texten tyngre.
NOMIN = {
    "sv": re.compile(r"^(\w{3,}ering|\w{5,}(?:ning|ling|ring)|\w{3,}[li]ghet)(en|ar|arna|er|erna)?$"),
    "en": re.compile(r"^(\w{4,}(isation|ization|ation|ment))s?$"),
}
NOMIN_UNDANTAG = {"sv": {"tidning", "tidningen", "tidningar"},
                  "en": {"department", "apartment", "government", "station"}}

TRIPPEL_SUFFIX = {
    "sv": r"(ad|ade|ig|iga|isk|iska|ande|ende|bar|sam|lös|iv|iva|ell|het|ning|ing|else|skap|tet)",
    "en": r"(ive|ous|ful|ic|al|ed|ent|ant|ment|tion|ity|ness|ship)",
}

NEG = {"sv": r"\b(inte|ej|aldrig)\b", "en": r"\b(not|never)\b|n't\b"}
PRONOMEN = {"sv": {"jag", "vi", "det", "han", "hon", "de", "den", "man", "ni", "du", "då", "sedan", "ändå", "så"},
            "en": {"i", "we", "it", "he", "she", "they", "you", "this", "that", "then", "so", "still"}}
NP_START = {"sv": {"om", "för", "ett", "en", "i", "på", "snarare", "någon", "något"},
            "en": {"a", "an", "about", "for", "to", "in", "on", "rather"}}
KOPULA = {"sv": r"(är|var|handlar|handlade)", "en": r"('s|’s| is| was| are| were|'re|’re)"}
ATERTAGANDE = {"sv": r"(det|det här|detta|de|jag|vi)", "en": r"(it|that|they|this|we|i)"}

PROFILER = {"standard": {"gardering_varje": False}, "kim": {"gardering_varje": True}}

ALLVAR = {"stark_klyscha": "maste_fixas", "ai_ord_kluster": "maste_fixas", "metadiskurs": "flagga",
          "trippellista": "flagga", "nominalisering": "flagga", "gardering": "flagga", "bindeord": "flagga",
          "meningsvariation": "flagga"}


# ── Textverktyg ──────────────────────────────────────────────────────────

class Segment:
    def __init__(self, falt, text):
        self.falt = falt
        self.text = text or ""


ORD_RX = re.compile(r"[\w'’-]+")


def ord_i(s):
    return [w for w in ORD_RX.findall(s.lower()) if any(c.isalpha() for c in w)]


def stycken(text):
    """(start, text) per stycke."""
    ut, pos = [], 0
    for m in re.finditer(r"\n\s*\n", text):
        ut.append((pos, text[pos:m.start()]))
        pos = m.end()
    ut.append((pos, text[pos:]))
    return [(s, t) for s, t in ut if t.strip()]


def meningar(text):
    """(start, mening) per mening. Radbrytningar och . ! ? … avslutar."""
    ut = []
    for m in re.finditer(r"[^.!?…\n]+[.!?…]*", text):
        s = m.group()
        if any(c.isalpha() for c in s):
            lead = len(s) - len(s.lstrip())
            ut.append((m.start() + lead, s.strip()))
    return ut


def _rx(monster):
    return re.compile(r"(?<![\w'’-])(" + monster + r")(?![\w-])", re.IGNORECASE)


# ── Antites ──────────────────────────────────────────────────────────────

def _antites_i_mening(s, sprak):
    low = s.lower()
    if sprak == "sv":
        if re.search(r"\binte (bara|enbart|endast)\b", low):
            return True
        if re.search(r"^(mindre|färre) [\w-]+( [\w-]+)?, (mer|fler) ", low):
            return True
    else:
        if re.search(r"\b(not (just|only|merely)|n't (just|only)|more than just)\b", low):
            return True
        if re.search(r"^(less|fewer) [\w-]+( [\w-]+)?, more ", low):
            return True
    neg = re.search(NEG[sprak], low)
    if not neg:
        return False
    efter = low[neg.end():]
    if re.search(r"\b(men|but)\b.*\b(värt det|worth it)\b", efter):
        return True
    if sprak == "sv" and re.search(r"\butan\b(?! att\b)", efter):
        return True
    m = re.search(r"\b(men|but)\b\s+(.*)$", efter)
    if m:
        y = ord_i(m.group(2))
        if y and y[0] not in PRONOMEN[sprak] and (
                (y[0] in NP_START[sprak] and len(y) <= 5) or len(y) <= 3):
            return True
    # "inte X – det är Y", "not X, it's Y"
    if re.search(r"[,;:–—-]\s*" + ATERTAGANDE[sprak] + r"\s*" + KOPULA[sprak] + r"\b", efter):
        return True
    # "I don't manage people, I coach them" / "Jag leder inte genom kontroll, jag leder genom tillit"
    forsta = ord_i(low[:neg.start()])
    if forsta and forsta[0] in ("jag", "vi", "i", "we"):
        m = re.search(r",\s*" + re.escape(forsta[0]) + r"\s+(.*)$", efter)
        if m and len(ord_i(m.group(1))) <= 5:
            return True
    return False


def _antites_par(s1, s2, sprak):
    low1, low2 = s1.lower(), s2.lower()
    if not re.search(NEG[sprak], low1):
        return False
    w1, w2 = ord_i(low1), ord_i(low2)
    if len(w1) > 12 or len(w2) > 10 or not w2:
        return False
    if w2[0] in ("men", "utan", "but") and len(w2) <= 4:
        return True
    frame = re.search(r"\b(är|var|handlar|handlade|is|was|are|were)\b|'s\b|’s\b|n't\b", low1)
    if frame and w2[0] in ("det", "detta", "de", "it", "it's", "that", "that's", "they", "this") and \
            re.match(ATERTAGANDE[sprak] + r"\s*" + KOPULA[sprak] + r"\b", low2):
        return True
    if w1[0] == w2[0] and w1[0] in ("jag", "vi", "i", "we", "de", "they"):
        if len(w1) > 1 and len(w2) > 1 and w1[1] == w2[1]:
            return True
        if sprak == "en" and len(w1) > 1 and w1[1] in ("don't", "do", "never", "didn't") and len(w2) <= 6:
            return True
    return False


def hitta_antiteser(segment, sprak):
    ut = []
    for seg in segment:
        for pstart, ptext in stycken(seg.text):
            ms = meningar(ptext)
            anvand = set()
            for i, (st, s) in enumerate(ms):
                if _antites_i_mening(s, sprak):
                    ut.append((seg, pstart + st, s))
                    anvand.add(i)
            for i in range(len(ms) - 1):
                if i in anvand or i + 1 in anvand:
                    continue
                if _antites_par(ms[i][1], ms[i + 1][1], sprak):
                    ut.append((seg, pstart + ms[i][0], ms[i][1] + " " + ms[i + 1][1]))
                    anvand.update({i, i + 1})
    return ut


# ── Analys ───────────────────────────────────────────────────────────────

def _per100(n, antal_ord):
    return round(100 * n / antal_ord, 1) if antal_ord else 0.0


def analysera(segment, sprak="sv", profil="standard", typ="text"):
    sprak = sprak if sprak in ("sv", "en") else "sv"
    prof = PROFILER.get(profil, PROFILER["standard"])
    traffar = []

    def traff(regel, seg, start, citat, forslag, allvar=None):
        traffar.append({"regel": regel, "citat": citat,
                        "position": {"falt": seg.falt, "start": start, "slut": start + len(citat)},
                        "forslag": forslag, "allvar": allvar or ALLVAR[regel]})

    # Frasregler
    for regel, lista in (("stark_klyscha", KLYSCHOR[sprak]), ("metadiskurs", METAPRAT[sprak])):
        for monster, forslag in lista:
            rx = _rx(monster)
            for seg in segment:
                for m in rx.finditer(seg.text):
                    traff(regel, seg, m.start(), m.group(), forslag)

    # AI-ord: kluster per mening
    ai_rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in AI_ORD[sprak]) + r")[\w-]*", re.IGNORECASE)
    ai_totalt, alla_ord = 0, 0
    for seg in segment:
        alla_ord += len(ord_i(seg.text))
        for st, s in meningar(seg.text):
            hits = list(ai_rx.finditer(s))
            ai_totalt += len(hits)
            if len({h.group(1).lower() for h in hits}) >= 3:
                traff("ai_ord_kluster", seg, st, s,
                      "för många modeord i samma mening (" + ", ".join(h.group() for h in hits) +
                      "); säg konkret vad du gjorde")

    # Antiteser
    ant = hitta_antiteser(segment, sprak)
    for seg, st, citat in ant:
        traff("antites_pivot", seg, st, citat, "säg poängen rakt, utan att först säga vad det inte är",
              "maste_fixas" if len(ant) >= 2 else "flagga")

    # Trippellistor av enstaka abstrakta ord
    suf = TRIPPEL_SUFFIX[sprak]
    konj = "och" if sprak == "sv" else "and"
    tri = re.compile(r"(?<![\w-])(\w+" + suf + r"), (\w+" + suf + r"),? " + konj + r" (\w+" + suf + r")(?![\w-])",
                     re.IGNORECASE)
    for seg in segment:
        for m in tri.finditer(seg.text):
            traff("trippellista", seg, m.start(), m.group(), "behåll det viktigaste ordet och visa det med ett exempel")

    # Nominaliseringar
    nrx, undantag = NOMIN[sprak], NOMIN_UNDANTAG[sprak]
    nomin_totalt = 0
    for seg in segment:
        for st, s in meningar(seg.text):
            w = ord_i(s)
            n = sum(1 for x in w if x not in undantag and nrx.match(x))
            nomin_totalt += n
            if n >= 3 and n / max(len(w), 1) >= 0.15:
                traff("nominalisering", seg, st, s,
                      "skriv om med verb: vem gjorde vad (t.ex. 'planerade' i stället för 'planering')")
    nomin_grans = 10 if typ == "cv" else 5
    if alla_ord >= 40 and _per100(nomin_totalt, alla_ord) > nomin_grans and \
            not any(t["regel"] == "nominalisering" for t in traffar):
        traff("nominalisering", segment[0], 0, segment[0].text[:80],
              f"för många substantiverade verb i hela texten ({_per100(nomin_totalt, alla_ord)} per 100 ord)")

    # Garderingar
    g_rx = re.compile(r"(?<![\w-])(" + "|".join(GARDERINGAR[sprak]) + r")(?![\w-])", re.IGNORECASE)
    g_per_seg = [(seg, list(g_rx.finditer(seg.text))) for seg in segment]
    g_totalt = sum(len(h) for _, h in g_per_seg)
    for seg, hits in g_per_seg:
        if prof["gardering_varje"]:
            for h in hits:
                traff("gardering", seg, h.start(), h.group(), "säg det rakt eller stryk", "maste_fixas")
        elif len(hits) >= 2 or (hits and alla_ord >= 40 and _per100(g_totalt, alla_ord) > 2):
            for h in hits:
                traff("gardering", seg, h.start(), h.group(), "säg det rakt eller stryk")

    # Tunga bindeord
    b_rx = re.compile(r"(?<![\w-])(" + "|".join(BINDEORD[sprak]) + r")(?![\w-])", re.IGNORECASE)
    b_hits = [(seg, h) for seg in segment for h in b_rx.finditer(seg.text)]
    if len(b_hits) >= 2 and _per100(len(b_hits), alla_ord) >= 1.5:
        for seg, h in b_hits:
            traff("bindeord", seg, h.start(), h.group(), "stryk bindeordet; ordningen räcker oftast")

    # Meningsrytm (inte CV)
    langder = [len(ord_i(s)) for seg in segment for _, s in meningar(seg.text)]
    rytm = None
    if typ != "cv" and len(langder) >= 6:
        medel = statistics.mean(langder)
        rytm = round(statistics.pstdev(langder) / medel, 2) if medel else None
        if rytm is not None and rytm < 0.25:
            traff("meningsvariation", segment[0], 0, segment[0].text[:80], "blanda korta och långa meningar")

    signaler = {
        "ord": alla_ord,
        "meningar": len(langder),
        "nominal_per100": _per100(nomin_totalt, alla_ord),
        "gardering_per100": _per100(g_totalt, alla_ord),
        "bindeord_per100": _per100(len(b_hits), alla_ord),
        "ai_ord_per100": _per100(ai_totalt, alla_ord),
        "antiteser": len(ant),
        "rytm_variation": rytm,
    }
    traffar.sort(key=lambda t: (str(t["position"]["falt"]), t["position"]["start"]))
    return traffar, signaler


# ── Indata ───────────────────────────────────────────────────────────────

def _txt(v, sprak):
    if isinstance(v, dict):
        return v.get(sprak) or next((x for x in v.values() if isinstance(x, str)), "")
    return v if isinstance(v, str) else ""


def segment_ur_json(data, sprak):
    segs, typ = [], "text"
    if "stycken" in data:
        typ = "brev"
        if data.get("rubrik"):
            segs.append(Segment("rubrik", _txt(data["rubrik"], sprak)))
        for i, s in enumerate(data.get("stycken", [])):
            segs.append(Segment(f"stycken[{i}]", _txt(s, sprak)))
    elif "sektioner" in data or "profil" in data:
        typ = "cv"
        if data.get("profil"):
            segs.append(Segment("profil", _txt(data["profil"], sprak)))
        for si, sek in enumerate(data.get("sektioner", [])):
            base = f"sektioner[{si}]"
            if sek.get("text"):
                segs.append(Segment(f"{base}.text", _txt(sek["text"], sprak)))
            for pi, p in enumerate(sek.get("poster", []) or []):
                if not isinstance(p, dict):
                    continue
                if p.get("text"):
                    segs.append(Segment(f"{base}.poster[{pi}].text", _txt(p["text"], sprak)))
                for ri, r in enumerate(p.get("punkter", []) or []):
                    segs.append(Segment(f"{base}.poster[{pi}].punkter[{ri}]", _txt(r, sprak)))
    else:
        def walk(v, path):
            if isinstance(v, str):
                segs.append(Segment(path, v))
            elif isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{path}.{k}" if path else k)
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{path}[{i}]")
        walk(data, "")
    return [s for s in segs if s.text.strip()], typ


def gissa_sprak(text):
    w = ord_i(text)
    sv = sum(1 for x in w if x in {"och", "att", "det", "som", "jag", "med", "för", "är", "på"}) + \
        len(re.findall(r"[åäö]", text.lower()))
    en = sum(1 for x in w if x in {"the", "and", "to", "of", "i", "with", "for", "is", "on"})
    return "en" if en > sv else "sv"


NAMN = {"stark_klyscha": "klyschor", "ai_ord_kluster": "kluster av modeord", "metadiskurs": "metaprat",
        "antites_pivot": "antites ('inte X, utan Y')", "trippellista": "trippellistor",
        "nominalisering": "substantivtung text", "gardering": "garderingar", "bindeord": "tunga bindeord",
        "meningsvariation": "likformig meningsrytm"}


def sammanfatta(traffar, sprak, profil):
    if not traffar:
        return "Inga AI-maner hittades."
    per = {}
    for t in traffar:
        per[t["regel"]] = per.get(t["regel"], 0) + 1
    s = f"{len(traffar)} saker att titta på: " + ", ".join(f"{NAMN.get(r, r)} ({n})" for r, n in per.items()) + "."
    maste = sum(1 for t in traffar if t["allvar"] == "maste_fixas")
    if maste:
        s += f" {maste} måste skrivas om."
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministisk kontroll av AI-maner i ansökningstexter.")
    ap.add_argument("fil", nargs="?", default="-")
    ap.add_argument("--sprak", default="auto", choices=["auto", "sv", "en"])
    ap.add_argument("--profil", default="standard", choices=sorted(PROFILER))
    ap.add_argument("--typ", default="auto", choices=["auto", "cv", "brev", "text"])
    a = ap.parse_args(argv)
    try:
        if a.fil == "-":
            raw = sys.stdin.read()
        else:
            with open(a.fil, encoding="utf-8") as f:
                raw = f.read()
    except OSError as e:
        print(json.dumps({"fel": f"Kunde inte läsa {a.fil}: {e}"}, ensure_ascii=False))
        return 1
    data = None
    if a.fil.endswith(".json") or raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            if a.fil.endswith(".json"):
                print(json.dumps({"fel": f"Ogiltig JSON: {e}"}, ensure_ascii=False))
                return 1
    sprak = a.sprak
    if isinstance(data, dict):
        if sprak == "auto" and data.get("sprak") in ("sv", "en"):
            sprak = data["sprak"]
        segs, typ = segment_ur_json(data, "sv" if sprak == "auto" else sprak)
    else:
        segs, typ = [Segment(None, raw)], "text"
    if sprak == "auto":
        sprak = gissa_sprak(" ".join(s.text for s in segs))
    if a.typ != "auto":
        typ = a.typ
    if not segs:
        segs = [Segment(None, "")]
    traffar, signaler = analysera(segs, sprak, a.profil, typ)
    ut = {"fil": a.fil, "sprak": sprak, "profil": a.profil, "typ": typ, "rent": not traffar,
          "signaler": signaler, "traffar": traffar, "sammanfattning": sammanfatta(traffar, sprak, a.profil)}
    print(json.dumps(ut, ensure_ascii=False, indent=2))
    return 0 if not traffar else 2


if __name__ == "__main__":
    sys.exit(main())
