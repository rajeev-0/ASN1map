#!/usr/bin/env python3
"""Sanity checks on the generated graph."""
import json, sys
from pathlib import Path
d = Path(__file__).resolve().parent.parent / "site" / "data"
nodes = {n["id"]: n for n in json.loads((d / "nodes.json").read_text())}
edges = json.loads((d / "edges.json").read_text())
ok = True
for a, b in [("ContentInfo", "SignedData"), ("ContentInfo", "ContentType"), ("CsrAttrs", "AttrOrOID"), ("SignedData", "SignerInfos"), ("SignerInfos", "SignerInfo"),
             ("SignerInfo", "SignerIdentifier"), ("Certificate", "TBSCertificate"), ("PKIMessage", "PKIBody")]:
    if not any(e["source"] == a and e["target"] == b for e in edges):
        print("MISSING edge", a, "->", b); ok = False
for e in edges:
    if e["source"] not in nodes or e["target"] not in nodes:
        print("DANGLING", e); ok = False
print("OK" if ok else "FAILED"); sys.exit(0 if ok else 1)
