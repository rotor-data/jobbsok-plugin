#!/usr/bin/env python3
"""Markerar dubbletter i sok/jobb.sqlite.

  python3 dedupe.py [--home DIR] [--troskel 0.8]

Tre steg, som slås ihop till grupper:
 1. källa+id (uid) och identisk URL
 2. normaliserad nyckel: (orgnr, och separat arbetsgivare i gemener) + normaliserad titel + ort
 3. textlikhet: 5-ords-shingles, Jaccard >= tröskeln (fulltext ur cache/text, annars titel+utdrag)
I varje grupp behålls posten med mest information; övriga får dubblett_av = dess uid.
Körs om från grunden varje gång, så resultatet är deterministiskt.
"""
import argparse
import json
import re

import sok_common as sc

FALT_INFO = ("url", "titel", "arbetsgivare", "orgnr", "ort", "kommun_id", "distans", "publicerad", "deadline",
             "anstallningsform", "omfattning")


def shingles(t, k=5):
    w = re.findall(r"[\wåäö]+", (t or "").lower())
    if len(w) < k:
        return {" ".join(w)} if w else set()
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def info(r, textlen):
    n = sum(1 for f in FALT_INFO if r[f] not in (None, ""))
    n += min(len(json.loads(r["kompetenser_json"] or "[]")), 10) * 0.3
    return (n + min(textlen, 5000) / 1000, -len(r["uid"]), r["uid"])


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def dedupe(home, troskel=0.8):
    c = sc.db(home)
    rows = c.execute("SELECT * FROM jobb").fetchall()
    uf = UF()
    texter = {}
    for r in rows:
        uf.find(r["uid"])
        texter[r["uid"]] = sc.las_text(home, r["text_hash"]) or ""
    steg = {1: 0, 2: 0, 3: 0}

    def slå(grupper, s):
        for g in grupper.values():
            for u in g[1:]:
                if uf.find(u) != uf.find(g[0]):
                    uf.union(u, g[0])
                    steg[s] += 1

    # 1. identisk URL (uid är redan unik per källa+id)
    g = {}
    for r in rows:
        if r["url"]:
            g.setdefault(r["url"].split("?")[0].rstrip("/").lower(), []).append(r["uid"])
    slå(g, 1)
    # 2. normaliserad nyckel
    g = {}
    for r in rows:
        if not r["titel"]:
            continue
        for arb in {r["orgnr"], sc.norm(r["arbetsgivare"])} - {None, ""}:
            g.setdefault((arb, sc.norm(r["titel"]), sc.norm(r["ort"])), []).append(r["uid"])
    slå(g, 2)
    # 3. textlikhet inom block (samma titel, samma första titelord eller samma första ord i arbetsgivaren)
    sh = {r["uid"]: shingles(texter[r["uid"]] or f"{r['titel']} {r['utdrag']}") for r in rows}
    block = {}
    for r in rows:
        block.setdefault(("t", sc.norm(r["titel"])), []).append(r["uid"])
        block.setdefault(("t1", (sc.norm(r["titel"]).split() or [""])[0]), []).append(r["uid"])
        f = (sc.norm(r["arbetsgivare"]).split() or [""])[0]
        if f:
            block.setdefault(("a", f), []).append(r["uid"])
    sett = set()
    for uids in block.values():
        if len(uids) < 2 or len(uids) > 400:
            continue
        for i, a in enumerate(uids):
            for b in uids[i + 1:]:
                if (a, b) in sett or uf.find(a) == uf.find(b):
                    continue
                sett.add((a, b))
                if len(sh[a]) >= 3 and len(sh[b]) >= 3 and jaccard(sh[a], sh[b]) >= troskel:
                    uf.union(a, b)
                    steg[3] += 1
    # välj bästa post per grupp
    per = {r["uid"]: r for r in rows}
    grupper = {}
    for u in per:
        grupper.setdefault(uf.find(u), []).append(u)
    c.execute("UPDATE jobb SET dubblett_av=NULL")
    markerade = 0
    for uids in grupper.values():
        if len(uids) < 2:
            continue
        bast = max(uids, key=lambda u: info(per[u], len(texter[u])))
        for u in uids:
            if u != bast:
                c.execute("UPDATE jobb SET dubblett_av=? WHERE uid=?", (bast, u))
                markerade += 1
    c.commit()
    return {"poster": len(rows), "dubbletter": markerade, "per_steg": steg}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--troskel", type=float, default=0.8)
    sc.add_home_arg(ap)
    a = ap.parse_args()
    print(json.dumps(dedupe(sc.hem(a.home), a.troskel), ensure_ascii=False))


if __name__ == "__main__":
    main()
