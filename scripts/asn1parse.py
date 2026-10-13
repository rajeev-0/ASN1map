"""Tolerant ASN.1 type-assignment parser.

Handles the RFC modules, including the 2009-era syntax with information object
classes, parameterized types and constraints. It extracts type assignments only;
classes, objects, object sets and values are skipped. Output mirrors the
asn1tools dict shape: {module: {"imports": {...}, "types": {...}}}.
"""
import re

TOKEN_RE = re.compile(r'''
    (?P<str>"[^"]*")
  | (?P<assign>::=)
  | (?P<dots>\.\.\.|\.\.)
  | (?P<ident>&?[A-Za-z][A-Za-z0-9_-]*)
  | (?P<num>-?\d+)
  | (?P<punct>[{}()\[\],;|.:<@^!])
''', re.X)

BUILTIN_TYPES = {
    "BOOLEAN", "NULL", "REAL", "UTF8String", "PrintableString", "IA5String", "TeletexString",
    "T61String", "UniversalString", "BMPString", "VisibleString", "NumericString", "UTCTime",
    "GeneralizedTime", "GeneralString", "GraphicString", "ObjectDescriptor", "EXTERNAL",
}


def strip_comments(text):
    out = []
    for line in text.split("\n"):
        i = line.find("--")
        while i != -1:
            j = line.find("--", i + 2)
            line = line[:i] + (line[j + 2:] if j != -1 else "")
            i = line.find("--")
        out.append(line)
    return "\n".join(out)


def tokenize(text):
    """Return (tokens, line_numbers)."""
    text = strip_comments(text)
    toks, lines = [], []
    for m in TOKEN_RE.finditer(text):
        toks.append(m.group())
        lines.append(text.count("\n", 0, m.start()))
    return toks, lines


def balanced(toks, i):
    """toks[i] is an opener; return index after its matching closer."""
    pairs = {"{": "}", "(": ")", "[": "]"}
    stack = []
    n = len(toks)
    while i < n:
        t = toks[i]
        if t in pairs:
            stack.append(pairs[t])
        elif stack and t == stack[-1]:
            stack.pop()
            if not stack:
                return i + 1
        i += 1
    return n


def split_commas(toks):
    out, cur, depth = [], [], 0
    for t in toks:
        if t in "{([":
            depth += 1
        elif t in "})]":
            depth -= 1
        if t == "," and depth == 0:
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


class Parser:
    def __init__(self, params=()):
        self.params = set(params)

    # ---- type parsing; returns (def, next_index)
    def parse_type(self, t, i):
        tag = None
        while i < len(t) and t[i] == "[":
            j = balanced(t, i)
            inner = t[i + 1:j - 1]
            cls = None
            if inner and inner[0] in ("UNIVERSAL", "APPLICATION", "PRIVATE"):
                cls, inner = inner[0], inner[1:]
            tag = {"number": inner[0] if inner else "?"}
            if tag["number"].lstrip("-").isdigit():
                tag["number"] = int(tag["number"])
            if cls:
                tag["class"] = cls
            i = j
            if i < len(t) and t[i] in ("IMPLICIT", "EXPLICIT"):
                tag["kind"] = t[i]
                i += 1
        d, i = self.parse_untagged(t, i)
        if tag:
            d["tag"] = tag
        # constraints / trailing parens
        while i < len(t) and t[i] == "(":
            i = balanced(t, i)
        return d, i

    def parse_untagged(self, t, i):
        if i >= len(t):
            return {"type": "?"}, i
        w = t[i]
        nxt = t[i + 1] if i + 1 < len(t) else None
        if w in ("SEQUENCE", "SET"):
            j = i + 1
            if j < len(t) and t[j] == "SIZE":
                j += 1
            if j < len(t) and t[j] == "(":  # SIZE constraint
                j = balanced(t, j)
            if j < len(t) and t[j] == "OF":
                j += 1
                # optional element name
                if j + 1 < len(t) and t[j][0].islower() and t[j + 1] not in ("(", ")", ",", "}"):
                    j += 1
                el, j = self.parse_type(t, j)
                return {"type": w + " OF", "element": el}, j
            if j < len(t) and t[j] == "{":
                k = balanced(t, j)
                return {"type": w, "members": self.parse_members(t[j + 1:k - 1])}, k
            return {"type": w}, j
        if w == "CHOICE":
            k = balanced(t, i + 1)
            return {"type": "CHOICE", "members": self.parse_members(t[i + 2:k - 1])}, k
        if w == "ENUMERATED":
            k = balanced(t, i + 1)
            vals, n = [], 0
            for item in split_commas(t[i + 2:k - 1]):
                if not item or item[0] == "...":
                    continue
                if len(item) >= 4 and item[1] == "(":
                    n = int(item[2]) if item[2].lstrip("-").isdigit() else n
                vals.append((item[0], n))
                n += 1
            return {"type": "ENUMERATED", "values": vals}, k
        if w == "INTEGER":
            j = i + 1
            d = {"type": "INTEGER"}
            if j < len(t) and t[j] == "{":
                k = balanced(t, j)
                nums = {}
                for item in split_commas(t[j + 1:k - 1]):
                    if len(item) >= 4 and item[1] == "(":
                        nums[item[0]] = int(item[2]) if item[2].lstrip("-").isdigit() else item[2]
                d["named-numbers"] = nums
                j = k
            return d, j
        if w == "BIT" and nxt == "STRING":
            j = i + 2
            d = {"type": "BIT STRING"}
            if j < len(t) and t[j] == "{":
                k = balanced(t, j)
                bits = {}
                for item in split_commas(t[j + 1:k - 1]):
                    if len(item) >= 4 and item[1] == "(":
                        bits[item[0]] = item[2]
                d["named-bits"] = bits
                j = k
            return d, j
        if w == "OCTET" and nxt == "STRING":
            return {"type": "OCTET STRING"}, i + 2
        if w == "OBJECT" and nxt == "IDENTIFIER":
            return {"type": "OBJECT IDENTIFIER"}, i + 2
        if w == "ANY":
            if nxt == "DEFINED":
                return {"type": "ANY DEFINED BY", "value": t[i + 3] if i + 3 < len(t) else None}, i + 4
            return {"type": "ANY"}, i + 1
        if w == "INSTANCE" and nxt == "OF":
            cls = t[i + 2] if i + 2 < len(t) else "?"
            return {"type": f"INSTANCE OF {cls}", "noref": True}, i + 3
        if w == "CLASS":
            return {"type": "CLASS", "noref": True}, balanced(t, i + 1) if nxt == "{" else i + 1
        if w in BUILTIN_TYPES:
            return {"type": w}, i + 1
        # reference: Ident, Module.Ident, Class.&field, optionally parameterized
        name, j = w, i + 1
        noref = False
        while j + 1 < len(t) and t[j] == "." and re.match(r"&?[A-Za-z]", t[j + 1]):
            name = t[j + 1] if not t[j + 1].startswith("&") else name + "." + t[j + 1]
            noref = noref or t[j + 1].startswith("&")
            j += 2
        argrefs = []
        if j < len(t) and t[j] == "{":  # parameterized actual args
            k = balanced(t, j)
            for a, tok in enumerate(t[j + 1:k - 1]):
                if re.match(r"[A-Z]", tok) and re.search(r"[a-z]", tok) and tok not in self.params:
                    argrefs.append(tok)
            j = k
        if name in self.params:
            noref = True
        d = {"type": name}
        if argrefs:
            d["argrefs"] = argrefs
        if noref:
            d["noref"] = True
        return d, j

    def parse_members(self, toks):
        members = []
        # drop extension version brackets: [[ 3: a T, b T ]]
        flat, k = [], 0
        while k < len(toks):
            if toks[k] == "[" and k + 1 < len(toks) and toks[k + 1] == "[":
                k += 2
                if k + 1 < len(toks) and toks[k + 1] == ":":
                    k += 2
                continue
            if toks[k] == "]" and k + 1 < len(toks) and toks[k + 1] == "]":
                k += 2
                continue
            flat.append(toks[k])
            k += 1
        for item in split_commas(flat):
            if not item or item[0] in ("...", "!"):
                continue
            if item[0] == "COMPONENTS":
                continue
            if item[0] == "[" and item[1] == "[":  # version brackets
                continue
            name = None
            if item[0][0].islower() or item[0].startswith("&"):
                name, item = item[0], item[1:]
            d, j = self.parse_type(item, 0)
            m = {"name": name or d["type"], **d}
            rest = item[j:]
            if "OPTIONAL" in rest:
                m["optional"] = True
            if "DEFAULT" in rest:
                k = rest.index("DEFAULT")
                m["default"] = " ".join(rest[k + 1:])
            members.append(m)
        return members


def parse_module(text):
    toks, tlines = tokenize(text)
    # header: Name [oid] DEFINITIONS ... ::= BEGIN
    try:
        di = toks.index("DEFINITIONS")
        bi = toks.index("BEGIN", di)
    except ValueError:
        raise ValueError("no DEFINITIONS/BEGIN found")
    name = toks[0]
    body = toks[bi + 1:]
    blines = tlines[bi + 1:]
    # strip END
    if "END" in body:
        cut = len(body) - 1 - body[::-1].index("END")
        body, blines = body[:cut], blines[:cut]
    i = 0
    imports, exports = {}, None
    if i < len(body) and body[i] == "EXPORTS":
        while body[i] != ";":
            i += 1
        i += 1
    if i < len(body) and body[i] == "IMPORTS":
        i += 1
        pend = []
        while body[i] != ";":
            t = body[i]
            if t == "FROM":
                mod = body[i + 1]
                imports.setdefault(mod, []).extend(x for x in pend if x not in (",",))
                pend = []
                i += 2
                if body[i] == "{":
                    i = balanced(body, i)
                elif body[i] == "WITH":
                    i += 2
                continue
            if t == "{":  # parameterized import marker e.g. Foo{}
                i = balanced(body, i)
                continue
            if t != ",":
                pend.append(t)
            i += 1
        i += 1
    # split into assignments: find '::=' tokens, assignment lhs begins after
    # previous assignment's rhs. Boundaries are found by scanning depth-0 for
    # "<Ident-ish lhs> ::=" patterns.
    types = {}
    rest = body[i:]
    rlines = blines[i:]
    # positions of depth-0 ::=
    depth, pos = 0, []
    for k, t in enumerate(rest):
        if t in "{([":
            depth += 1
        elif t in "})]":
            depth -= 1
        elif t == "::=" and depth == 0:
            pos.append(k)
    bounds = []
    for k in pos:
        s0 = k
        while s0 > 0 and rlines[s0 - 1] == rlines[k]:
            s0 -= 1
        if s0 == k:  # '::=' starts its line; lhs on previous line(s)
            s0 = k - 1
            while s0 > 0 and rlines[s0 - 1] == rlines[k - 1]:
                s0 -= 1
        bounds.append(s0)
    for n, k in enumerate(pos):
        s = bounds[n]
        e = bounds[n + 1] if n + 1 < len(pos) else len(rest)
        lhs = rest[s:k]
        rhs = rest[k + 1:e]
        if not lhs or not lhs[0][0].isupper() or lhs[0].startswith("&"):
            continue
        params = ()
        if len(lhs) > 1:
            if lhs[1] == "{":
                params = [x for x in lhs[2:-1] if re.match(r"[A-Za-z]", x)]
            else:
                continue  # object set / information object
        if rhs and rhs[0] in ("CLASS", "TYPE-IDENTIFIER", "ABSTRACT-SYNTAX"):
            continue
        if rhs and rhs[0] == "{":  # object set etc.
            continue
        d, _ = Parser(params).parse_type(rhs, 0)
        types[lhs[0]] = d
    return name, {"imports": imports, "types": types}
