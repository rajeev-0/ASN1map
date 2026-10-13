#!/usr/bin/env python3
"""Download RFC text and extract ASN.1 modules into asn1/ plus sources.json."""
import json, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
END_RE = re.compile(r"^\s*END\b\s*(--.*)?$")
HDR_RE = re.compile(r"^RFC \d+\s+.*\d{4}\s*$")
FTR_RE = re.compile(r"\[Page \d+\]\s*$")


def load_rfcs():
    """Read RFC-source.txt: '<number> <label> [skip=Mod1,Mod2]' per line, '#' comments."""
    rfcs = {}
    for line in (ROOT / "RFC-source.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        skip = set()
        for p in [x for x in parts[2:] if x.startswith("skip=")]:
            skip |= set(p[5:].split(","))
        label = parts[1] if len(parts) > 1 and not parts[1].startswith("skip=") else f"RFC {parts[0]}"
        rfcs[int(parts[0])] = (label, skip)
    return rfcs


def fetch(n):
    p = ROOT / "rfc" / f"rfc{n}.txt"
    if not p.exists():
        p.parent.mkdir(exist_ok=True)
        url = f"https://www.rfc-editor.org/rfc/rfc{n}.txt"
        p.write_bytes(urllib.request.urlopen(url).read())
    return p.read_text(encoding="utf-8").replace("\f", "").split("\n")


def clean(lines):
    """Drop page headers/footers; keep (original_line_no, text)."""
    return [(i + 1, l) for i, l in enumerate(lines)
            if not HDR_RE.match(l) and not FTR_RE.search(l)]


def section_at(lines, lineno):
    best = None
    for l in lines[:lineno]:
        m = re.match(r"^(\d+(?:\.\d+)*|Appendix [A-Z]|[A-Z](?:\.\d+)+)\.?\s+[A-Z]", l)
        if m:
            best = m.group(1).replace("Appendix ", "")
    return best


def main():
    (ROOT / "asn1").mkdir(exist_ok=True)
    for old in (ROOT / "asn1").glob("*.asn"):
        old.unlink()
    manifest = []
    for n, (std, skip) in load_rfcs().items():
        raw = fetch(n)
        cl = clean(raw)
        i = 0
        while i < len(cl):
            if re.match(r"^\s*DEFINITIONS\s+(EXPLICIT|IMPLICIT|AUTOMATIC)\s+TAGS\s*::=", cl[i][1]):
                s = i
                while s > 0 and not cl[s - 1][1].strip():
                    s -= 1
                while s > 0 and cl[s - 1][1].strip():
                    s -= 1
                e = i
                while e < len(cl) and not (END_RE.match(cl[e][1]) and e > i + 1):
                    e += 1
                block = [x for x in cl[s:e + 1]]
                while not block[0][1].strip():
                    block = block[1:]
                text = "\n".join(l for _, l in block)
                name = re.match(r"\s*([A-Za-z0-9-]+)", block[0][1]).group(1)
                if name in skip:
                    print("skipped  ", f"rfc{n}_{name}")
                    i = e
                    i += 1
                    continue
                fname = f"rfc{n}_{name}.asn"
                (ROOT / "asn1" / fname).write_text(text + "\n")
                manifest.append({
                    "file": fname, "module": name, "rfc": n, "standard": std,
                    "section": section_at(raw, block[0][0]),
                    "start_line": block[0][0], "end_line": block[-1][0]})
                print("extracted", fname, manifest[-1]["section"])
                i = e
            i += 1
    (ROOT / "asn1" / "sources.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
