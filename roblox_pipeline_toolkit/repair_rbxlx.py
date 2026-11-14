#!/usr/bin/env python3
import re
import sys
import shutil
import xml.etree.ElementTree as ET
from collections import Counter

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"
bak_path = path + ".bak"

try:
    shutil.copyfile(path, bak_path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
except FileNotFoundError:
    print(f"[ERROR] File not found: {path}")
    sys.exit(1)

fixed_counts = Counter()

# 1. Reorder standard multi-child tags
ORDERS = {
    "CoordinateFrame": ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"],
    "Vector3": ["X", "Y", "Z"],
    "Vector2": ["X", "Y"],
    "Vector3int16": ["X", "Y", "Z"],
    "Vector2int16": ["X", "Y"],
    "Color3": ["R", "G", "B"],
    "UDim2": ["XS", "XO", "YS", "YO"],
    "PhysicalProperties": ["CustomPhysics", "Density", "Friction", "Elasticity", "FrictionWeight", "ElasticityWeight"],
    "Font": ["Family", "Weight", "Style", "CachedFaceId"],
}

for tag_name, order in ORDERS.items():
    pat = re.compile(rf"(<{tag_name}\b[^>]*>)(.*?)(</{tag_name}>)", re.DOTALL)

    def fix_order(m, tag_name=tag_name, order=order):
        open_t, body, close_t = m.group(1), m.group(2), m.group(3)
        if tag_name == "Font":
            tags = {}
            found_seq = []
            for k in order:
                tm = re.search(rf"(<{k}>.*?</{k}>)", body, re.DOTALL)
                if tm:
                    tags[k] = tm.group(1).strip()
            for fm in re.finditer(r"<([A-Za-z0-9_]+)>", body):
                if fm.group(1) in order and fm.group(1) not in found_seq:
                    found_seq.append(fm.group(1))
            req = [k for k in order if k in tags]
            if not req or found_seq == req:
                return m.group(0)
            indent_m = re.search(r"\n([ \t]*)<", body)
            ind = indent_m.group(1) if indent_m else ""
            c_ind = ind[:-2] if len(ind) >= 2 else ""
            lines = "\n".join(f"{ind}{tags[k]}" for k in req)
            fixed_counts[tag_name] += 1
            return f"{open_t}\n{lines}\n{c_ind}{close_t}"

        pairs = re.findall(r"<([A-Za-z0-9_]+)>\s*([^<]*?)\s*</\1>", body)
        found = dict(pairs)
        if len(found) != len(order) or not all(k in found for k in order):
            return m.group(0)
        if [k for k, _ in pairs] == order:
            return m.group(0)
        indent_m = re.search(r"\n([ \t]*)<", body)
        ind = indent_m.group(1) if indent_m else ""
        c_ind = ind[:-2] if len(ind) >= 2 else ""
        lines = "\n".join(f"{ind}<{k}>{found[k]}</{k}>" for k in order)
        fixed_counts[tag_name] += 1
        return f"{open_t}\n{lines}\n{c_ind}{close_t}"

    text = pat.sub(fix_order, text)

# 2. Fix Rect2D (<Min>/<Max> or <MinX>/<minX> -> lowercase <min>/<max> with <X>/<Y>)
def fix_rect2d(m):
    open_t, body, close_t = m.group(1), m.group(2), m.group(3)
    indent_m = re.search(r"\n([ \t]*)<", body)
    ind = indent_m.group(1) if indent_m else ""
    c_ind = ind[:-2] if len(ind) >= 2 else ""
    in_ind = ind + "  "

    # Case A: <Min>/<Max> uppercase
    min_m = re.search(r"<Min>(.*?)</Min>", body, re.DOTALL)
    max_m = re.search(r"<Max>(.*?)</Max>", body, re.DOTALL)
    if min_m and max_m:
        min_xy = dict(re.findall(r"<([XY])>\s*([^<]*?)\s*</\1>", min_m.group(1)))
        max_xy = dict(re.findall(r"<([XY])>\s*([^<]*?)\s*</\1>", max_m.group(1)))
        if "X" in min_xy and "Y" in min_xy and "X" in max_xy and "Y" in max_xy:
            minx, miny = min_xy["X"], min_xy["Y"]
            maxx, maxy = max_xy["X"], max_xy["Y"]
            fixed_counts["Rect2D"] += 1
            return (
                f"{open_t}\n{ind}<min>\n{in_ind}<X>{minx}</X>\n{in_ind}<Y>{miny}</Y>\n{ind}</min>\n"
                f"{ind}<max>\n{in_ind}<X>{maxx}</X>\n{in_ind}<Y>{maxy}</Y>\n{ind}</max>\n{c_ind}{close_t}"
            )

    # Case B: <MinX>/<minX> flat tags
    vals = dict(re.findall(r"<(MinX|MinY|MaxX|MaxY)>\s*([^<]*?)\s*</\1>", body, re.IGNORECASE))
    if len(vals) == 4:
        v = {k.lower(): val for k, val in vals.items()}
        minx, miny = v["minx"], v["miny"]
        maxx, maxy = v["maxx"], v["maxy"]
        fixed_counts["Rect2D"] += 1
        return (
            f"{open_t}\n{ind}<min>\n{in_ind}<X>{minx}</X>\n{in_ind}<Y>{miny}</Y>\n{ind}</min>\n"
            f"{ind}<max>\n{in_ind}<X>{maxx}</X>\n{in_ind}<Y>{maxy}</Y>\n{ind}</max>\n{c_ind}{close_t}"
        )
    return m.group(0)

text = re.sub(r"(<Rect2D\b[^>]*>)(.*?)(</Rect2D>)", fix_rect2d, text, flags=re.DOTALL)

# 3. Clean <Properties> blocks: handle Color3uint8 and remove duplicate property names
def fix_properties(m):
    open_t, body, close_t = m.group(1), m.group(2), m.group(3)
    has_color3 = bool(re.search(r'<Color3\b[^>]*name="Color"', body))

    def replace_c3u8(cm):
        fixed_counts["Color3uint8"] += 1
        if has_color3:
            return ""
        val = int(cm.group(1))
        r = ((val >> 16) & 0xFF) / 255.0
        g = ((val >> 8) & 0xFF) / 255.0
        b = (val & 0xFF) / 255.0
        return (
            f'<Color3 name="Color">\n'
            f'  <R>{r:.6f}</R>\n'
            f'  <G>{g:.6f}</G>\n'
            f'  <B>{b:.6f}</B>\n'
            f'</Color3>'
        )

    body = re.sub(r'\s*<Color3uint8\b[^>]*>(\d+)</Color3uint8>', replace_c3u8, body)

    # Deduplicate properties with identical tag + name inside the same <Properties> block
    seen = set()
    def dedup(pm):
        tag, name = pm.group(1), pm.group(2)
        key = (tag, name)
        if key in seen:
            fixed_counts["DuplicateProps"] += 1
            return ""
        seen.add(key)
        return pm.group(0)

    body = re.sub(r'\s*<([A-Za-z0-9_]+)\b[^>]*\bname="([^"]+)"[^>]*>.*?</\1>', dedup, body, flags=re.DOTALL)
    return f"{open_t}{body}{close_t}"

text = re.sub(r"(<Properties>)(.*?)(</Properties>)", fix_properties, text, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

# 4. Concise Post-Fix Diagnostic Check
print(f"=== Repair & Diagnostic Summary: {path} ===")
print(f"Backup saved: {bak_path}\n")

print("--- Fixes Applied ---")
if not fixed_counts:
    print("  None needed (0 changes made).")
else:
    for k, v in fixed_counts.items():
        print(f"  {k}: {v} fixed")

print("\n--- Post-Fix Validation ---")
try:
    root = ET.fromstring(text)
    print("  XML Structure: PASS (Valid XML)")
except ET.ParseError as e:
    print(f"  XML Structure: FAIL ({e})")
    sys.exit(1)

remaining = Counter()
for props in root.iter("Properties"):
    seen = set()
    for prop in props:
        tag = prop.tag
        pname = prop.attrib.get("name", "")
        if pname:
            if (tag, pname) in seen:
                remaining[f"Duplicate <{tag} name='{pname}'>"] += 1
            seen.add((tag, pname))
        if tag == "Color3uint8":
            remaining["Remaining <Color3uint8>"] += 1
        elif tag == "Rect2D":
            if [c.tag for c in prop] != ["min", "max"]:
                remaining["Invalid <Rect2D>"] += 1
        elif tag in ORDERS:
            ch = [c.tag for c in prop]
            exp = ORDERS[tag]
            if tag == "PhysicalProperties" and ch == ["CustomPhysics"]:
                continue
            if tag == "Font":
                exp = [k for k in exp if k in ch]
            if ch != exp:
                remaining[f"Out-of-order <{tag}>"] += 1

if not remaining:
    print("  Schema Check:  PASS (0 remaining issues)")
else:
    print("  Schema Check:  FAIL")
    for issue, cnt in remaining.items():
        print(f"    [{cnt}x] {issue}")
