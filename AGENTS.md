# AGENTS.md

Static site mapping ASN.1 types from IETF RFCs (CMS, X.509, CMP, EST). Python pipeline -> JSON -> plain JS (Cytoscape) in `site/`. No build tooling, no tests, no lint config, no package manifests; Python scripts use stdlib only.

## Pipeline (run in this order)

```
python3 scripts/fetch_rfcs.py    # RFC-source.txt -> rfc/ (cache) -> asn1/*.asn + asn1/sources.json
python3 scripts/build_graph.py   # asn1/*.asn -> site/data/nodes.json + edges.json
python3 scripts/verify.py        # only "test": asserts key edges exist, no dangling edges
python3 -m http.server -d site   # serve locally
```

- `RFC-source.txt` is the single input list: `<rfc> <label> [skip=Mod1,Mod2]`. Label becomes the graph colour/filter; the front end derives both dynamically.
- `fetch_rfcs.py` deletes all `asn1/*.asn` on each run, so never hand-edit them. Needs network (rfc-editor.org); `rfc/` and `.venv/` are gitignored.
- `site/data/*.json` and `asn1/` are generated but committed. Regenerate and commit them with any change to scripts or `RFC-source.txt`. CI (`.github/workflows/pages.yml`) regenerates and runs `verify.py` before deploying `site/`.

## Parser (`scripts/asn1parse.py`)

- Custom, not `asn1tools`: it fails on the 2009-era object-class syntax in RFC 5911/5912/9810. Do not reintroduce it.
- Extracts type assignments only; classes, objects, object sets and values are skipped. Parameterized args are kept as soft refs (`argrefs`, resolved only if they match a known type, never create stubs).
- Assignment boundaries are found by the first token on the line containing a depth-0 `::=`, so a multi-line left-hand side can break it.
- Class-field types such as `CONTENT-TYPE.&id` carry `noref`. `build_graph.py` links them to the same-module alias type (`ContentType ::= CONTENT-TYPE.&id`) via `link_aliases`.

## Extraction quirks (`scripts/fetch_rfcs.py`)

- Finds modules by the `DEFINITIONS ... TAGS ::=` line through `END`, after stripping RFC page headers/footers. An RFC with no such block (RFC 7030 EST has only inline snippets) yields nothing; use RFC 8951 instead.
- Module names must be unique across RFCs (later one wins with a warning). Duplicate modules such as `AlgorithmInformation-2009` (in both 5911 and 5912) must be excluded with `skip=`.
- `build_graph.py` skips (with a warning) any module that fails to parse. Many RFCs ship legacy 88-syntax duplicates and older copies of the same module; `RFC-source.txt` omits or `skip=`s them. Check for new `Module.Type` ids after adding an RFC, since a duplicate changes the plain id that `verify.py` expects (e.g. adding PKCS-9 broke `ContentType`).
- Type names defined in several modules get ids `Module.Type`; unique names use the plain name.

## Graph semantics

- `ContentInfo -> SignedData/EnvelopedData/...` edges are hand-added in `build_graph.py` (flagged `implicit`, rendered dotted) because the content is an open type.
- Unresolved types become `External` stubs. Currently there are none; new stubs usually mean a missing RFC in `RFC-source.txt` or a parser bug.
- When adding RFCs, update the expected edges in `scripts/verify.py` if relevant.
