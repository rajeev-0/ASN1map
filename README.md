# ASN.1 Map

Live site: https://rajeev-0.github.io/ASN1map/

Interactive map of the ASN.1 types in the CMS, X.509/PKIX and CMP RFCs listed in `RFC-source.txt`
(currently RFC 5911, 3274, 6211, 5753, 5912 and 9810). See `ASN1map.md` for the project description.

## Pipeline

The RFCs to import are listed in `RFC-source.txt` (one `<number> <label>` per line). Add a line to include a new RFC.

```
python3 scripts/fetch_rfcs.py    # RFC text -> asn1/*.asn + sources.json
python3 scripts/build_graph.py   # built-in parser (scripts/asn1parse.py) -> site/data/nodes.json, edges.json
python3 scripts/verify.py        # sanity checks
python3 -m http.server -d site            # open http://localhost:8000
```

The site in `site/` is static (Cytoscape.js, vendored) and can be hosted on GitHub Pages.
Types not defined in any listed RFC appear as grey "External" stubs. The parser (`scripts/asn1parse.py`) is a tolerant, dependency-free parser for type assignments, including the
2009-era information-object-class syntax. Dotted red edges are the `ContentInfo` content types, which
ASN.1 expresses only as `ANY DEFINED BY`.
