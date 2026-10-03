#!/usr/bin/env python3
"""Validera jobbsok-JSON mot plugin/schemas. Endast stdlib.

Användning:
    python3 validate.py <fil.json> [fler filer ...] [--schema namn] [--json]

Schemat väljs efter filnamnet (fakta.json -> fakta, sok/recept/x.json -> recept,
sok/webbrecept/x.json -> webbrecept, sok/rollkort/x.json -> rollkort,
sok/arbetsgivare/x.json -> arbetsgivarkort).
Exit 0 = allt giltigt, 1 = minst ett fel (även oläslig fil eller okänt schema).

Stöder: type, required, properties, additionalProperties, items, enum, const,
pattern, anyOf, oneOf, minItems, maxItems, minimum, maximum, $ref (#/$defs/...).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobbsok_common as jc  # noqa: E402

NAMN = ["fakta", "coach", "preferenser", "rost", "design", "cv", "brev", "analys", "logg", "kallor", "recept", "hypoteser", "webbrecept", "rollkort", "intervju", "beslut", "arbetsgivarkort"]
TYPNAMN = {"object": "ett objekt", "array": "en lista", "string": "en text", "integer": "ett heltal",
           "number": "ett tal", "boolean": "sant/falskt", "null": "tomt (null)"}


def schema_for_path(path):
    base = os.path.basename(path)
    stem = base[:-5] if base.endswith(".json") else base
    if stem in NAMN:
        return stem
    mapp = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if mapp in ("recept", "webbrecept", "rollkort") and not stem.startswith("_"):
        return mapp
    if mapp == "arbetsgivare" and not stem.startswith("_"):
        return "arbetsgivarkort"
    return None


def load_schema(name):
    with open(jc.SCHEMA_DIR / f"{name}.schema.json", encoding="utf-8") as f:
        return json.load(f)


def _is_type(v, t):
    if t == "object": return isinstance(v, dict)
    if t == "array": return isinstance(v, list)
    if t == "string": return isinstance(v, str)
    if t == "boolean": return isinstance(v, bool)
    if t == "integer": return isinstance(v, int) and not isinstance(v, bool)
    if t == "number": return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "null": return v is None
    return True


def _fmt(path):
    out = ""
    for p in path:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else p)
    return out or "(roten)"


def validate(data, schema, root=None, path=()):
    """Returnerar lista med (sökväg, meddelande)."""
    root = root or schema
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        node = root
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        errs += validate(data, node, root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(data, t) for t in types):
            want = " eller ".join(TYPNAMN.get(t, t) for t in types)
            return errs + [(path, f"ska vara {want}, men är {json.dumps(data, ensure_ascii=False)[:60]}")]
    if "const" in schema and data != schema["const"]:
        errs.append((path, f"ska vara exakt {json.dumps(schema['const'], ensure_ascii=False)}"))
    if "enum" in schema and data not in schema["enum"]:
        val = ", ".join(json.dumps(e, ensure_ascii=False) for e in schema["enum"])
        errs.append((path, f"ogiltigt värde {json.dumps(data, ensure_ascii=False)}; tillåtna: {val}"))
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errs.append((path, f"{data} är för lågt; minst {schema['minimum']}"))
        if "maximum" in schema and data > schema["maximum"]:
            errs.append((path, f"{data} är för högt; högst {schema['maximum']}"))
    if isinstance(data, str) and "pattern" in schema and not re.search(schema["pattern"], data):
        errs.append((path, f"\"{data}\" har fel format (mönster {schema['pattern']})"))
    if isinstance(data, dict):
        for r in schema.get("required", []):
            if r not in data:
                errs.append((path, f"saknar obligatoriskt fält \"{r}\""))
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in data.items():
            if k in props:
                errs += validate(v, props[k], root, path + (k,))
            elif addl is False:
                errs.append((path, f"okänt fält \"{k}\" (stavfel?)"))
            elif isinstance(addl, dict):
                errs += validate(v, addl, root, path + (k,))
    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errs.append((path, f"ska ha minst {schema['minItems']} poster"))
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errs.append((path, f"får ha högst {schema['maxItems']} poster, har {len(data)}"))
        if "items" in schema:
            for i, v in enumerate(data):
                errs += validate(v, schema["items"], root, path + (i,))
    if "anyOf" in schema:
        if not any(not validate(data, s, root, path) for s in schema["anyOf"]):
            errs.append((path, "matchar inget av de tillåtna formaten"))
    if "oneOf" in schema:
        results = [validate(data, s, root, path) for s in schema["oneOf"]]
        ok = sum(1 for r in results if not r)
        if ok == 0:
            best = min(results, key=len)
            errs += best if len(best) <= 3 else [(path, "matchar inget av de tillåtna formaten")]
        elif ok > 1:
            errs.append((path, "matchar flera format samtidigt (tvetydigt)"))
    return errs


def extra_checks(name, data):
    """Kontrakt som inte uttrycks i schemat."""
    errs = []
    if name == "fakta" and isinstance(data, dict):
        seen = set()
        for i, r in enumerate(data.get("roller", []) or []):
            for j, m in enumerate(r.get("meriter", []) or []):
                mid = m.get("id")
                if mid in seen:
                    errs.append((("roller", i, "meriter", j, "id"), f"merit-id \"{mid}\" används flera gånger"))
                seen.add(mid)
                if mid and r.get("id") and not str(mid).startswith(r["id"] + "-"):
                    errs.append((("roller", i, "meriter", j, "id"), f"merit-id \"{mid}\" ska börja med rollens id \"{r['id']}-\""))
    return errs


def validate_file(path, name=None):
    name = name or schema_for_path(path)
    if not name:
        return None, [((), f"vet inte vilket schema som gäller för {os.path.basename(path)}")]
    try:
        data = jc.read_json(path)
    except json.JSONDecodeError as e:
        return name, [((), f"filen är inte giltig JSON (rad {e.lineno}, kolumn {e.colno}): {e.msg}")]
    if data is None:
        return name, [((), "filen finns inte")]
    return name, validate(data, load_schema(name)) + extra_checks(name, data)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validera jobbsok-JSON-filer.")
    ap.add_argument("filer", nargs="+")
    ap.add_argument("--schema", choices=NAMN, help="tvinga ett visst schema")
    ap.add_argument("--json", action="store_true", help="skriv resultatet som JSON")
    a = ap.parse_args(argv)
    rapport, fel = [], False
    for f in a.filer:
        name, errs = validate_file(f, a.schema)
        fel = fel or bool(errs)
        rapport.append({"fil": f, "schema": name, "giltig": not errs,
                        "fel": [{"sokvag": _fmt(p), "meddelande": m} for p, m in errs]})
    if a.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
    else:
        for r in rapport:
            if r["giltig"]:
                print(f"OK   {r['fil']} ({r['schema']})")
            else:
                print(f"FEL  {r['fil']} ({r['schema'] or 'okänt schema'}): {len(r['fel'])} fel")
                for e in r["fel"]:
                    print(f"     - {e['sokvag']}: {e['meddelande']}")
    return 1 if fel else 0


if __name__ == "__main__":
    sys.exit(main())
