#!/usr/bin/env python3
import sys
from collections import Counter
import xml.etree.ElementTree as ET

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"

print(f"=== Diagnosing: {path} ===\n")

try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
except FileNotFoundError:
    print(f"[ERROR] File not found: {path}")
    sys.exit(1)

try:
    root = ET.fromstring(text)
    print("[PASS] XML Well-Formedness: Valid XML structure.")
except ET.ParseError as e:
    print(f"[FAIL] XML Syntax Error: {e}")
    sys.exit(1)

if root.tag == "roblox":
    print(f"[PASS] Root Tag: <roblox version=\"{root.attrib.get('version', 'missing')}\">")
else:
    print(f"[FAIL] Root Tag: Expected <roblox>, found <{root.tag}>")

EXPECTED_ORDERS = {
    "Vector3": ["X", "Y", "Z"],
    "Vector2": ["X", "Y"],
    "Vector3int16": ["X", "Y", "Z"],
    "Vector2int16": ["X", "Y"],
    "CoordinateFrame": ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"],
    "Color3": ["R", "G", "B"],
    "UDim2": ["XS", "XO", "YS", "YO"],
    "PhysicalProperties": ["CustomPhysics", "Density", "Friction", "Elasticity", "FrictionWeight", "ElasticityWeight"],
    "Font": ["Family", "Weight", "Style", "CachedFaceId"],
}

counts = {k: 0 for k in EXPECTED_ORDERS}
counts["Rect2D"] = 0

grouped_errors = Counter()
issue_totals = Counter()

def get_item_label(item_elem):
    cls = item_elem.attrib.get("class", "UnknownClass")
    props = item_elem.find("Properties")
    if props is not None:
        for child in props:
            if child.attrib.get("name") == "Name" and child.text:
                return f'{cls} "{child.text}"'
    return cls

for item in root.iter("Item"):
    parent_label = get_item_label(item)
    props = item.find("Properties")
    if props is None:
        continue

    seen_prop_names = set()
    for prop in props:
        tag = prop.tag
        prop_name = prop.attrib.get("name", "")

        if prop_name:
            key = (tag, prop_name)
            if key in seen_prop_names:
                issue = f'Duplicate <{tag} name="{prop_name}">'
                grouped_errors[(issue, parent_label)] += 1
                issue_totals[issue] += 1
            seen_prop_names.add(key)

        if tag == "Color3uint8":
            issue = f'Unsupported <Color3uint8 name="{prop_name}">'
            grouped_errors[(issue, parent_label)] += 1
            issue_totals[issue] += 1

        elif tag == "Rect2D":
            counts["Rect2D"] += 1
            children = [c.tag for c in prop]
            if children != ["min", "max"]:
                issue = f'Invalid <Rect2D name="{prop_name}"> structure {children}'
                grouped_errors[(issue, parent_label)] += 1
                issue_totals[issue] += 1
            else:
                for sub in prop:
                    sub_children = [c.tag for c in sub]
                    if sub_children != ["X", "Y"]:
                        issue = f'Invalid <{sub.tag}> in <Rect2D name="{prop_name}"> {sub_children}'
                        grouped_errors[(issue, parent_label)] += 1
                        issue_totals[issue] += 1

        elif tag in EXPECTED_ORDERS:
            counts[tag] += 1
            children = [c.tag for c in prop]
            expected = EXPECTED_ORDERS[tag]

            if tag == "PhysicalProperties" and children == ["CustomPhysics"]:
                continue
            if tag == "Font":
                expected = [k for k in expected if k in children]

            if children != expected:
                issue = f'Out-of-order <{tag} name="{prop_name}"> {children}'
                grouped_errors[(issue, parent_label)] += 1
                issue_totals[issue] += 1

print("\n=== Element Summary ===")
for k, v in counts.items():
    print(f"  {k}: {v} checked")

total_issues = sum(issue_totals.values())
print("\n=== Grouped Diagnostic Results ===")
if total_issues == 0:
    print("[SUCCESS] 0 issues found! All vectors, CFrames, Rect2Ds, Fonts, and properties match Roblox's XML schema.")
else:
    print(f"[ISSUES FOUND] {total_issues} total problem(s) across {len(grouped_errors)} parent node group(s):\n")
    print("--- Summary by Issue Type ---")
    for issue, count in issue_totals.most_common():
        print(f"  [{count}x] {issue}")

    print("\n--- Breakdown by Parent Node ---")
    for (issue, parent_label), count in grouped_errors.most_common():
        print(f"  [{count}x] in {parent_label} -> {issue}")
