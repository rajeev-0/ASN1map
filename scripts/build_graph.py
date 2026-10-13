#!/usr/bin/env python3
"""Parse asn1/*.asn and emit site/data/nodes.json and edges.json."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asn1parse

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = {
    "SEQUENCE", "SET", "CHOICE", "SEQUENCE OF", "SET OF", "ENUMERATED", "INTEGER",
    "OCTET STRING", "BIT STRING", "OBJECT IDENTIFIER", "BOOLEAN", "NULL", "ANY",
    "ANY DEFINED BY", "UTF8String", "PrintableString", "IA5String", "TeletexString",
    "T61String", "UniversalString", "BMPString", "VisibleString", "NumericString",
    "UTCTime", "GeneralizedTime", "GeneralString", "GraphicString", "REAL", "NULL",
    "OpenType", "EXTERNAL", "ObjectDescriptor",
}
ASSIGN_RE = re.compile(r"^\s*([A-Za-z][\w-]*)\s*(\{[^}]*\})?(\s+[A-Z][A-Z -]*)?\s*::=")


def tag_str(t):
    if not t:
        return None
    cls = t.get("class", "")
    s = f"[{cls + ' ' if cls else ''}{t['number']}]"
    if t.get("kind"):
        s += " " + t["kind"]
    return s


def type_label(m):
    t = m["type"]
    if t in ("SEQUENCE OF", "SET OF"):
        el = m["element"]
        return f"{t} {type_label(el)}"
    if t == "ANY DEFINED BY":
        return f"ANY DEFINED BY {m.get('value')}"
    if t in ("SEQUENCE", "SET", "CHOICE", "ENUMERATED"):
        return t
    return t


def collect_refs(d, out):
    """Collect referenced type names in a type definition (recursively)."""
    t = d.get("type")
    if t and t not in BUILTIN and not d.get("noref") and not t.startswith("INSTANCE OF"):
        out.append(t)
    for a in d.get("argrefs", []):
        out.append("?" + a)  # soft ref: only linked if it resolves to a known type
    for m in d.get("members", []) or []:
        if isinstance(m, dict):
            collect_refs(m, out)
    if isinstance(d.get("element"), dict):
        collect_refs(d["element"], out)


def fields_of(d, field_refs):
    t = d["type"]
    res = []
    if t in ("SEQUENCE", "SET", "CHOICE"):
        for m in d.get("members", []):
            if not isinstance(m, dict) or "name" not in m:
                continue  # extension markers
            f = {"name": m["name"], "type": type_label(m), "tag": tag_str(m.get("tag")),
                 "optional": bool(m.get("optional")), "default": None}
            if "default" in m:
                f["default"] = str(m["default"])
            refs = []
            collect_refs(m, refs)
            f["refs"] = refs
            if m["type"] in ("SEQUENCE", "SET", "CHOICE", "ENUMERATED"):
                f["inline"] = fields_of(m, field_refs)
            res.append(f)
    elif t in ("SEQUENCE OF", "SET OF"):
        el = d["element"]
        refs = []
        collect_refs(el, refs)
        res.append({"name": "(element)", "type": type_label(el), "tag": tag_str(el.get("tag")),
                    "optional": False, "default": None, "refs": refs,
                    **({"inline": fields_of(el, field_refs)} if el["type"] in ("SEQUENCE", "SET", "CHOICE") else {})})
    elif t == "ENUMERATED":
        for k, v in (d.get("values") or []):
            res.append({"name": k, "type": f"({v})", "tag": None, "optional": False, "default": None, "refs": []})
    elif t == "INTEGER" and d.get("named-numbers"):
        for k, v in d["named-numbers"].items():
            res.append({"name": k, "type": f"({v})", "tag": None, "optional": False, "default": None, "refs": []})
    return res


def source_spans(text):
    lines = text.split("\n")
    starts = [(i, ASSIGN_RE.match(l).group(1)) for i, l in enumerate(lines) if ASSIGN_RE.match(l)]
    spans = {}
    for n, (i, name) in enumerate(starts):
        j = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        seg = lines[i:j]
        while seg and (not seg[-1].strip() or seg[-1].strip().startswith("--") or seg[-1].strip() == "END"):
            seg.pop()
        spans.setdefault(name, "\n".join(seg))
    return spans


def main():
    manifest = json.loads((ROOT / "asn1" / "sources.json").read_text())
    mods = {}
    for ent in manifest:
        p = ROOT / "asn1" / ent["file"]
        mname, m = asn1parse.parse_module(p.read_text())
        if mname in mods:
            print(f"warning: module {mname} defined twice; keeping {ent['file']}", file=sys.stderr)
        mods[mname] = (m, ent, source_spans(p.read_text()))

    # node ids: plain name unless it collides
    count = {}
    for mname, (m, _, _) in mods.items():
        for t in m["types"]:
            count[t] = count.get(t, 0) + 1
    nid = lambda mod, t: t if count.get(t) == 1 else f"{mod}.{t}"
    by_name = {}
    for mname, (m, _, _) in mods.items():
        for t in m["types"]:
            by_name.setdefault(t, []).append(mname)

    nodes, edges, stubs, warnings = {}, [], {}, []

    def resolve(mod, ref):
        if ref.startswith("?"):
            ref = ref[1:]
            m = mods[mod][0]
            if ref in m["types"]:
                return nid(mod, ref)
            for src, names in m["imports"].items():
                if ref in names and src in mods and ref in mods[src][0]["types"]:
                    return nid(src, ref)
            return None
        m = mods[mod][0]
        if ref in m["types"]:
            return nid(mod, ref)
        for src, names in m["imports"].items():
            if ref in names and src in mods and ref in mods[src][0]["types"]:
                return nid(src, ref)
        if ref in by_name:  # imported from a module we have, but not declared
            return nid(by_name[ref][0], ref)
        stubs[ref] = {"id": ref, "name": ref, "kind": "EXTERNAL", "stub": True, "standard": "External",
                      "module": next((s for s, n in m["imports"].items() if ref in n), None),
                      "rfc": None, "section": None, "fields": [], "source": None}
        return ref

    for mname, (m, ent, spans) in mods.items():
        for tname, d in m["types"].items():
            fr = []
            fields = fields_of(d, fr)
            node = {
                "id": nid(mname, tname), "name": tname, "kind": d["type"] if d["type"] in BUILTIN else f"= {d['type']}",
                "module": mname, "rfc": ent["rfc"], "section": ent["section"],
                "standard": ent["standard"], "tag": tag_str(d.get("tag")),
                "fields": fields, "source": spans.get(tname),
            }
            if d["type"] not in BUILTIN and not d.get("noref"):  # alias to another type
                node["fields"] = [{"name": "(alias)", "type": d["type"], "tag": None, "optional": False,
                                   "default": None, "refs": [d["type"]] + ["?" + a for a in d.get("argrefs", [])]}]
            nodes[node["id"]] = node

    def walk_fields(node_id, mod, fields, prefix=""):
        for f in fields:
            for r in f.get("refs", []):
                tgt = resolve(mod, r)
                if tgt:
                    f.setdefault("targets", []).append(tgt)
            for tgt in f.get("targets", []):
                edges.append({"source": node_id, "target": tgt, "field": prefix + f["name"],
                              "optional": f["optional"] or f["default"] is not None})
            if f.get("inline"):
                # inline refs are already counted via collect_refs on the parent field
                for sub in f["inline"]:
                    sub.setdefault("targets", [x for x in (resolve(mod, r) for r in sub.get("refs", [])) if x])
            f["ref"] = f["targets"][0] if f.get("targets") else None
            f.pop("refs", None)

    for node in list(nodes.values()):
        walk_fields(node["id"], node["module"], node["fields"])
    # strip helper keys from inline fields
    def clean(fs):
        for f in fs:
            f.pop("refs", None)
            f["ref"] = (f.get("targets") or [None])[0]
            if f.get("inline"):
                clean(f["inline"])
    for n in nodes.values():
        clean(n["fields"])

    nodes.update({k: v for k, v in stubs.items() if k not in nodes})
    # semantic edges for ANY DEFINED BY content of ContentInfo (RFC 5652 section 3)
    for t in ("Data", "SignedData", "EnvelopedData", "DigestedData", "EncryptedData", "AuthenticatedData"):
        if t in nodes:
            edges.append({"source": "ContentInfo", "target": t, "field": "content (by contentType)",
                          "optional": False, "implicit": True})
    # dedupe edges
    seen, uniq = set(), []
    for e in edges:
        k = (e["source"], e["target"], e["field"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    used_by = {}
    for e in uniq:
        used_by.setdefault(e["target"], set()).add(e["source"])
    for n in nodes.values():
        n["usedBy"] = sorted(used_by.get(n["id"], set()) - {n["id"]})
    out = ROOT / "site" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "nodes.json").write_text(json.dumps(list(nodes.values()), indent=1))
    (out / "edges.json").write_text(json.dumps(uniq, indent=1))
    print(f"{len(nodes)} nodes ({len(stubs)} external stubs), {len(uniq)} edges")
    if stubs:
        print("external:", ", ".join(sorted(stubs)))


if __name__ == "__main__":
    main()
