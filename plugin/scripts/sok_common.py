"""Gemensamma hjälpfunktioner för sökskripten (fetch, ingest, dedupe, score, lista, kor m.fl.).

Bara Python 3 stdlib. Användardata ligger i $JOBBSOK_HOME (standard ~/Jobbsok).

Nätfel ger NatFel. Skripten fångar det, skriver ett tydligt meddelande på stderr
och avslutar med kod 3, så att skillen kan falla tillbaka på Claudes webbverktyg
och mata in resultatet via ingest.py.
"""
import datetime as _dt
import email.utils
import hashlib
import html
import html.parser
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "jobbsok-plugin/0.1 (personlig jobbsokning)"
TIMEOUT = 20
MIN_INTERVALL_S = 1.0
STATUSAR = ("ny", "intressant", "nej", "sokt", "stangd")
NATFEL_KOD = 3

_senaste_anrop = {}


class NatFel(Exception):
    """Nätet går inte att nå (sandlåda, offline, DNS, timeout)."""


class HttpFel(Exception):
    def __init__(self, status, url, text=""):
        super().__init__(f"HTTP {status} från {url}")
        self.status = status
        self.url = url
        self.text = text


# ---------------------------------------------------------------- hem & filer

def hem(arg=None):
    p = arg or os.environ.get("JOBBSOK_HOME") or os.path.join(os.path.expanduser("~"), "Jobbsok")
    return os.path.abspath(os.path.expanduser(p))


def sokv(home, *delar):
    return os.path.join(home, "sok", *delar)


def cachev(home, *delar):
    return os.path.join(home, "cache", *delar)


def las_json(sokvag, standard=None):
    try:
        with open(sokvag, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return standard


def skriv_json(sokvag, data):
    os.makedirs(os.path.dirname(sokvag), exist_ok=True)
    tmp = sokvag + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, sokvag)


def nu_iso():
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def idag():
    return _dt.date.today().isoformat()


def add_home_arg(parser):
    parser.add_argument("--home", help="datarot (standard $JOBBSOK_HOME eller ~/Jobbsok)")


def natfel_avslut(fel):
    sys.stderr.write(
        "NÄTFEL: kunde inte nå källan (%s).\n"
        "Nätet verkar vara begränsat här. Hämta i stället annonserna med webbsök/webbhämtning "
        "och mata in dem som JSON via: python3 scripts/ingest.py --kalla webb < poster.json\n" % fel)
    sys.exit(NATFEL_KOD)


# ---------------------------------------------------------------- HTTP

def _vanta_vard(url):
    vard = urllib.parse.urlsplit(url).netloc
    sist = _senaste_anrop.get(vard)
    if sist is not None:
        d = time.monotonic() - sist
        if d < MIN_INTERVALL_S:
            time.sleep(MIN_INTERVALL_S - d)
    _senaste_anrop[vard] = time.monotonic()


def http(url, *, method="GET", data=None, headers=None, home=None, cache=False, timeout=TIMEOUT):
    """Gör ett anrop. Returnerar (status, text, svarshuvuden).

    cache=True: villkorligt anrop med ETag/If-Modified-Since mot cache/http.
    Vid 304 returneras den cachade texten och status 304.
    """
    h = {"User-Agent": USER_AGENT, "Accept-Language": "sv,en;q=0.8"}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    cfil = None
    cpost = None
    if cache and home and method == "GET":
        cfil = cachev(home, "http", hashlib.sha1(url.encode()).hexdigest() + ".json")
        cpost = las_json(cfil)
        if cpost:
            if cpost.get("etag"):
                h["If-None-Match"] = cpost["etag"]
            if cpost.get("last_modified"):
                h["If-Modified-Since"] = cpost["last_modified"]
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    _vanta_vard(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
            hdr = {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        if e.code == 304 and cpost:
            return 304, cpost.get("text", ""), {}
        txt = ""
        try:
            txt = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        raise HttpFel(e.code, url, txt)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise NatFel(f"{urllib.parse.urlsplit(url).netloc}: {getattr(e, 'reason', e)}")
    cs = "utf-8"
    m = re.search(r"charset=([\w-]+)", hdr.get("content-type", ""))
    if m:
        cs = m.group(1)
    text = raw.decode(cs, "replace")
    if cfil:
        skriv_json(cfil, {"url": url, "etag": hdr.get("etag"), "last_modified": hdr.get("last-modified"),
                          "hamtad": nu_iso(), "text": text})
    return status, text, hdr


def http_json(url, **kw):
    hd = kw.pop("headers", {}) or {}
    hd.setdefault("Accept", "application/json")
    status, text, hdr = http(url, headers=hd, **kw)
    return status, (json.loads(text) if text.strip() else None), hdr


_robots = {}


def robots_tillater(url):
    """Följer robots.txt för vanliga webbsidor (inte API:er). Går robots.txt inte att läsa tillåts anropet."""
    import urllib.robotparser
    u = urllib.parse.urlsplit(url)
    bas = f"{u.scheme}://{u.netloc}"
    if bas not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _, t, _ = http(bas + "/robots.txt", timeout=10)
            rp.parse(t.splitlines())
        except (HttpFel, NatFel):
            rp = None
        _robots[bas] = rp
    rp = _robots[bas]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


class _Lankar(html.parser.HTMLParser):
    def __init__(self, bas):
        super().__init__(convert_charrefs=True)
        self.bas, self.ut, self._a = bas, [], None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("mailto:", "tel:", "javascript:", "#")):
                self._a = [urllib.parse.urljoin(self.bas, href).split("#")[0], []]

    def handle_data(self, d):
        if self._a is not None:
            self._a[1].append(d)

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.ut.append((self._a[0], re.sub(r"\s+", " ", "".join(self._a[1])).strip()))
            self._a = None


def lankar(html_text, bas):
    """Alla <a href> som (absolut url, länktext)."""
    p = _Lankar(bas)
    try:
        p.feed(html_text)
    except Exception:
        pass
    return p.ut


JOBBLANK = re.compile(r"/(jobs?|jobb|lediga[-_]?(jobb|tjanster)|ledig[-_]tjanst|annonser?|platsannons(er)?|career|"
                      r"careers|karriar|vacanc(y|ies)|positions?|tjanster|job-?postings?|opening|rekrytering)/",
                      re.I)


def jsonld_jobb(html_text):
    """Första JobPosting i sidans JSON-LD, normaliserad till ingest-form (eller None)."""
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html_text, re.S | re.I):
        try:
            d = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = d if isinstance(d, list) else [d]
        while stack:
            x = stack.pop(0)
            if not isinstance(x, dict):
                continue
            stack += x.get("@graph") or []
            t = x.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                org = x.get("hiringOrganization") or {}
                loc = x.get("jobLocation") or {}
                loc = loc[0] if isinstance(loc, list) and loc else loc
                adr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
                adr = adr if isinstance(adr, dict) else {"addressLocality": str(adr)}
                return {"titel": x.get("title"), "arbetsgivare": org.get("name") if isinstance(org, dict) else org,
                        "ort": adr.get("addressLocality") or adr.get("addressRegion"),
                        "land": adr.get("addressCountry") if isinstance(adr.get("addressCountry"), str)
                        else (adr.get("addressCountry") or {}).get("name"),
                        "publicerad": x.get("datePosted"), "deadline": x.get("validThrough"),
                        "distans": 2 if x.get("jobLocationType") == "TELECOMMUTE" else None,
                        "text": html_till_text(x.get("description") or "")}
    return None


def hamta_sokvag(obj, vag):
    """Punkt-sökväg i JSON: 'a.b.0.c'."""
    for d in str(vag).split("."):
        if isinstance(obj, list):
            try:
                obj = obj[int(d)]
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(d)
        else:
            return None
    return obj


# ---------------------------------------------------------------- text

class _Txt(html.parser.HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "ul", "ol"}
    SKIP = {"script", "style", "noscript", "svg", "head", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        if tag == "li":
            self.out.append("- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def html_till_text(s):
    if not s:
        return ""
    p = _Txt()
    try:
        p.feed(s)
        p.close()
        t = "".join(p.out)
    except Exception:
        t = re.sub(r"<[^>]+>", " ", html.unescape(s))
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b(ab|aktiebolag|ltd|inc|gmbh|as|oy|publ)\b", " ", s)
    s = re.sub(r"[^\wåäöéü]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def text_hash(t):
    return hashlib.sha1(norm(t).encode("utf-8")).hexdigest()[:20]


def utdrag(t, n=300):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def iso_datum(v):
    """Tolkar ISO, RFC 822 eller epok-ms till ISO-sträng (sekunder)."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        x = float(v)
        if x > 1e11:
            x /= 1000
        return _dt.datetime.fromtimestamp(x).replace(microsecond=0).isoformat()
    s = str(v).strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d.replace(tzinfo=None, microsecond=0).isoformat()
    except Exception:
        pass
    m = re.match(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?", s)
    return m.group(0) if m else None


# ---------------------------------------------------------------- databas

FALT = ["uid", "kalla", "kalla_id", "url", "titel", "arbetsgivare", "orgnr", "ort", "kommun_id", "distans",
        "publicerad", "deadline", "anstallningsform", "omfattning", "kompetenser_json", "utdrag", "text_hash",
        "dubblett_av", "poang", "poang_skal_json", "status", "forst_sedd", "senast_sedd", "bedomning_json", "hittad_via"]

SCHEMA = """CREATE TABLE IF NOT EXISTS jobb(
 uid TEXT PRIMARY KEY, kalla TEXT, kalla_id TEXT, url TEXT, titel TEXT, arbetsgivare TEXT, orgnr TEXT,
 ort TEXT, kommun_id TEXT, distans INT, publicerad TEXT, deadline TEXT, anstallningsform TEXT, omfattning TEXT,
 kompetenser_json TEXT, utdrag TEXT, text_hash TEXT, dubblett_av TEXT, poang INT, poang_skal_json TEXT,
 status TEXT DEFAULT 'ny', forst_sedd TEXT, senast_sedd TEXT, bedomning_json TEXT, hittad_via TEXT)"""
# Tillägg utöver datakontraktet: bedomning_json (orsak/taggar från lista.py satt) och
# hittad_via (recept-, webbrecept- eller hypotes-id). Läggs till med ALTER TABLE i befintliga databaser.
MIGRERING = {"bedomning_json": "TEXT", "hittad_via": "TEXT"}


_conns = {}


def stang_db():
    for c in _conns.values():
        c.close()
    _conns.clear()


def db(home):
    """En delad anslutning per databasfil i processen."""
    p = sokv(home, "jobb.sqlite")
    if p in _conns:
        return _conns[p]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    c = sqlite3.connect(p)
    _conns[p] = c
    c.row_factory = sqlite3.Row
    c.execute(SCHEMA)
    finns = {r[1] for r in c.execute("PRAGMA table_info(jobb)")}
    for kol, typ in MIGRERING.items():
        if kol not in finns:
            c.execute(f"ALTER TABLE jobb ADD COLUMN {kol} {typ}")
    c.commit()
    return c


def gor_uid(kalla, kalla_id):
    kid = str(kalla_id)
    if re.fullmatch(r"[\w.-]{1,40}", kid):
        return f"{kalla}-{kid}"
    return f"{kalla}-{hashlib.sha1(kid.encode()).hexdigest()[:12]}"


def spara_text(home, th, text):
    if th and text:
        p = cachev(home, "text", th + ".txt")
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)


def las_text(home, th):
    if not th:
        return None
    try:
        with open(cachev(home, "text", th + ".txt"), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def normalisera(post, kalla):
    """Gör en inkommande post (dict) till en jobb-rad. 'text' (fulltext) är valfri och sparas i cache/text."""
    kid = post.get("kalla_id") or post.get("id") or post.get("url")
    if not kid:
        kid = hashlib.sha1((str(post.get("titel")) + str(post.get("arbetsgivare"))).encode()).hexdigest()[:12]
    kalla = post.get("kalla") or kalla
    text = post.get("text") or ""
    if not text and post.get("html"):
        text = html_till_text(post["html"])
    komp = post.get("kompetenser")
    if komp is None and post.get("kompetenser_json"):
        komp = json.loads(post["kompetenser_json"])
    komp = [k if isinstance(k, dict) else {"id": None, "namn": str(k), "typ": "must"} for k in (komp or [])]
    distans = post.get("distans")
    if isinstance(distans, str):
        distans = {"plats": 0, "på plats": 0, "onsite": 0, "hybrid": 1, "distans": 2, "remote": 2,
                   "fully": 2, "helt": 2}.get(distans.lower())
    r = {
        "uid": post.get("uid") or gor_uid(kalla, kid),
        "kalla": kalla, "kalla_id": str(kid),
        "url": post.get("url"), "titel": (post.get("titel") or "").strip() or None,
        "arbetsgivare": (post.get("arbetsgivare") or "").strip() or None,
        "orgnr": (re.sub(r"\D", "", str(post["orgnr"])) or None) if post.get("orgnr") else None,
        "ort": post.get("ort"), "kommun_id": post.get("kommun_id"), "distans": distans,
        "publicerad": iso_datum(post.get("publicerad")), "deadline": iso_datum(post.get("deadline")),
        "anstallningsform": post.get("anstallningsform"), "omfattning": post.get("omfattning"),
        "kompetenser_json": json.dumps(komp, ensure_ascii=False),
        "utdrag": utdrag(post.get("utdrag") or text),
        "hittad_via": post.get("hittad_via"),
    }
    full = " ".join(x for x in (r["titel"], r["arbetsgivare"], text or r["utdrag"]) if x)
    r["text_hash"] = text_hash(full)
    r["_text"] = text
    return r


def upsert(c, home, rader, nar=None):
    """Lägger in/uppdaterar rader. Returnerar (nya, uppdaterade). Status bevaras, men 'stangd' öppnas igen."""
    nar = nar or nu_iso()
    nya = upd = 0
    for r in rader:
        text = r.pop("_text", None)
        spara_text(home, r.get("text_hash"), text)
        old = c.execute("SELECT status FROM jobb WHERE uid=?", (r["uid"],)).fetchone()
        falt = [k for k in r if k in FALT and k not in ("status", "forst_sedd", "senast_sedd", "poang",
                                                        "poang_skal_json", "dubblett_av", "bedomning_json")]
        if old is None:
            cols = falt + ["status", "forst_sedd", "senast_sedd"]
            c.execute(f"INSERT INTO jobb({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                      [r[k] for k in falt] + ["ny", nar, nar])
            nya += 1
        else:
            # skriv inte över befintliga värden med None
            # hittad_via behåller första värdet (där jobbet först hittades)
            satt = [k for k in falt if r[k] is not None and k not in ("uid", "hittad_via")]
            if r.get("hittad_via"):
                c.execute("UPDATE jobb SET hittad_via=COALESCE(hittad_via,?) WHERE uid=?", (r["hittad_via"], r["uid"]))
            ny_status = "ny" if old["status"] == "stangd" else old["status"]
            c.execute(f"UPDATE jobb SET {','.join(k + '=?' for k in satt)}{',' if satt else ''} status=?, senast_sedd=? "
                      "WHERE uid=?", [r[k] for k in satt] + [ny_status, nar, r["uid"]])
            upd += 1
    c.commit()
    return nya, upd


def stang_utgangna(c):
    n = c.execute("UPDATE jobb SET status='stangd' WHERE status IN ('ny','intressant') AND deadline IS NOT NULL "
                  "AND substr(deadline,1,10) < ?", (idag(),)).rowcount
    c.commit()
    return n


def stang_forsvunna(c, kalla, sedda_uid):
    """Efter en fullständig hämtning av en källa: stäng öppna jobb som inte längre finns."""
    rows = c.execute("SELECT uid FROM jobb WHERE kalla=? AND status IN ('ny','intressant')", (kalla,)).fetchall()
    sedda = set(sedda_uid)
    borta = [r["uid"] for r in rows if r["uid"] not in sedda]
    c.executemany("UPDATE jobb SET status='stangd' WHERE uid=?", [(u,) for u in borta])
    c.commit()
    return len(borta)


def korning_logg(home):
    return las_json(sokv(home, "senaste_korning.json"), {}) or {}
