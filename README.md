# ASN.1 Map

Interactive map of the ASN.1 types in RFC 5652 (CMS), RFC 5280 (X.509) and RFC 4210 (CMP),
plus imported dependencies (RFC 4211 CRMF). See `ASN1map.md` for the project description.

## Pipeline

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_rfcs.py    # RFC text -> asn1/*.asn + sources.json
.venv/bin/python scripts/build_graph.py   # asn1tools -> site/data/nodes.json, edges.json
.venv/bin/python scripts/verify.py        # sanity checks
python3 -m http.server -d site            # open http://localhost:8000
```

The site in `site/` is static (Cytoscape.js, vendored) and can be hosted on GitHub Pages.
Types not defined in scope (e.g. PKCS#10 `CertificationRequest`, RFC 5755 attribute certificates)
appear as grey "External" stubs. Dotted red edges are the `ContentInfo` content types, which
ASN.1 expresses only as `ANY DEFINED BY`.
