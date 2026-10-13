# ASN.1 Map

**Tagline:** An interactive map of the ASN.1 type definitions used in internet security standards. Explore how CMS, X.509 and CMP structures connect, from the top-level type down to each field.

## Description

ASN.1 Map turns the ASN.1 modules published in IETF RFCs into a browsable, cross-linked graph. Standards like CMS (RFC 5652), X.509 (RFC 5280) and CMP (RFC 4210) define dozens of nested types. They are normally read as long blocks of text. This site shows them as a map.

## Features

- **Type relationship graph:** click a type such as `ContentInfo` to see what it contains and what uses it. For example, `ContentInfo -> SignedData -> SignerInfo -> SignerIdentifier`.
- **Field details:** each node shows its ASN.1 kind (SEQUENCE, CHOICE, SET OF, ...), its fields, tags, and OPTIONAL or DEFAULT markers.
- **Cross-references:** jump from a field to the type it references, or find every place a type is used ("used by").
- **Search and filter:** find types by name, RFC or module. Filter the graph by standard.
- **Source links:** every type links back to its RFC section and the original ASN.1 module text.
- **Static and fast:** generated from the RFC modules into JSON and rendered in the browser. No backend is needed, and it can be hosted on GitHub Pages.

## Audience

Developers and security engineers who implement or debug CMS, S/MIME, PKI and certificate management code, and learners who want to understand how the structures fit together.

## Scope (v1)

- RFC 5652 (CMS)
- RFC 5280 (X.509)
- RFC 4210 (CMP)
- Their imported dependencies

## Tech Notes

- Source: `.asn` modules extracted from the RFCs.
- Parsing: `asn1tools` or a similar parser.
- Output: `nodes.json` and `edges.json`.
- Front end: Cytoscape.js or D3, plain static HTML and JS.

## Pipeline

1. Collect the `.asn` modules from the RFCs.
2. Parse them into a dict of types and their members.
3. Emit nodes (types) and edges (references) as JSON.
4. Render the JSON as a static site.
