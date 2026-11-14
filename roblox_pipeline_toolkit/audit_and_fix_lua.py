#!/usr/bin/env python3
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"
if not os.path.isfile(path):
    print(f"[ERROR] File not found: {path}")
    sys.exit(1)

shutil.copyfile(path, path + ".pre_lua_fix.bak")

def unescape_rust_string(s):
    out, i, n = [], 0, len(s)
    emap = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0"}
    while i < n:
        if s[i] == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt in emap:
                out.append(emap[nxt])
                i += 2
                continue
            out.append(nxt)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)

def repair_lua_source(src):
    if not src:
        return src, []
    fixes, orig = [], src
    if "\ufeff" in src or "\x00" in src:
        src = src.replace("\ufeff", "").replace("\x00", "")
        fixes.append("stripped BOM/nulls")
    st = src.strip()
    for pfx in ('String("', 'ProtectedString("'):
        if st.startswith(pfx) and st.endswith('")'):
            src = unescape_rust_string(st[len(pfx):-2])
            fixes.append(f"unwrapped {pfx}...)")
            break
    if "\n" not in src and ("\\n" in src or '\\"' in src):
        src = unescape_rust_string(src)
        fixes.append("unescaped single-line source")
    if "\\\n" in src:
        src = src.replace("\\\n", "\n")
        fixes.append("cleaned line-continuation backslashes")
    src = src.replace("\r\n", "\n")
    return src, (fixes if src != orig else [])

def check_syntax(src):
    if not src or not src.strip():
        return None, None
    i, n, line, stack = 0, len(src), 1, []
    pairs = {")": "(", "]": "[", "}": "{"}
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch == "-" and i + 1 < n and src[i + 1] == "-":
            nl = src.find("\n", i)
            if nl == -1:
                break
            line += 1
            i = nl + 1
            continue
        if ch in ('"', "'", "`"):
            q, sline, i, closed = ch, line, i + 1, False
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "\n" and q != "`":
                    return f"Unclosed {q} string at line {sline}", sline
                if src[i] == "\n":
                    line += 1
                if src[i] == q:
                    closed = True
                    i += 1
                    break
                i += 1
            if not closed:
                return f"Unterminated {q} string at line {sline}", sline
            continue
        if ch in "([{":
            stack.append((ch, line))
        elif ch in ")]}":
            if not stack or stack[-1][0] != pairs[ch]:
                return f"Unexpected '{ch}' at line {line}", line
            stack.pop()
        i += 1
    if stack:
        return f"Unclosed '{stack[-1][0]}' opened at line {stack[-1][1]}", stack[-1][1]
    return None, None

def show_context(src, eline, r=3):
    lines = src.splitlines()
    tot = len(lines)
    if not tot:
        return "    (empty)"
    eline = eline if (eline and 1 <= eline <= tot) else tot
    s, e = max(1, eline - r), min(tot, eline + r)
    out = [f"    {'>>>' if ln == eline else '   '} {ln:4d} | {lines[ln - 1]}" for ln in range(s, e + 1)]
    if eline <= 5 and tot > e:
        out.append("        ...  | (end of file)")
        for ln in range(max(e + 1, tot - 4), tot + 1):
            out.append(f"        {ln:4d} | {lines[ln - 1]}")
    return "\n".join(out)

tree = ET.parse(path)
root = tree.getroot()
pmap = {c: p for p in root.iter() for c in p}

def get_name(it):
    res, cur = [], it
    while cur in pmap:
        if cur.tag == "Item":
            pr = cur.find("Properties")
            nm = cur.attrib.get("class", "Item")
            if pr is not None:
                for p in pr:
                    if p.attrib.get("name") == "Name" and p.text:
                        nm = p.text
                        break
            res.append(nm)
        cur = pmap[cur]
    return ".".join(reversed(res))

repaired, broken = [], []
for it in root.iter("Item"):
    if it.attrib.get("class") not in {"Script", "LocalScript", "ModuleScript"}:
        continue
    pr = it.find("Properties")
    if pr is None:
        continue
    src_el = next((p for p in pr if p.attrib.get("name") == "Source"), None)
    if src_el is None:
        continue
    fixed, fxs = repair_lua_source(src_el.text or "")
    if fxs:
        src_el.text = fixed
        repaired.append((get_name(it), ", ".join(fxs)))
    err, eln = check_syntax(fixed)
    if err:
        broken.append((get_name(it), err, eln, fixed))

if repaired:
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=False)

print(f"Repaired: {len(repaired)} | Remaining Errors: {len(broken)}")
for nm, rsn in repaired:
    print(f"  [FIXED] {nm} -> {rsn}")
for nm, err, eln, code in broken:
    print(f"\n  [ERROR] {nm}: {err}\n{show_context(code, eln)}")
