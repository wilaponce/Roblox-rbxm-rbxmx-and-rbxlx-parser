#!/usr/bin/env python3
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"

print(f"=== Open Cloud Place Upload Readiness Check: {path} ===\n")

blockers = []
warnings = []

# 1. File existence, extension, and size checks
if not os.path.isfile(path):
    print(f"[FAIL] File not found: {path}")
    sys.exit(1)

ext = os.path.splitext(path)[-1].lower()
if ext not in (".rbxl", ".rbxlx"):
    blockers.append(f"Invalid extension '{ext}': Open Cloud Places API only accepts .rbxl (binary) or .rbxlx (XML).")

size_bytes = os.path.getsize(path)
size_mb = size_bytes / (1024 * 1024)
if size_bytes == 0:
    blockers.append("File is 0 bytes (empty).")
elif size_mb > 100:
    blockers.append(f"File size ({size_mb:.2f} MB) exceeds the 100 MB Open Cloud Place upload limit.")

# 2. Raw text / binary & encoding checks
with open(path, "rb") as f:
    raw = f.read()

if b"\x00" in raw:
    blockers.append("File contains null bytes (\\x00), indicating a truncated or corrupted save.")

try:
    text = raw.decode("utf-8")
except UnicodeDecodeError as e:
    blockers.append(f"Invalid UTF-8 encoding at byte {e.start}: Open Cloud XML parser requires valid UTF-8.")
    text = raw.decode("utf-8", errors="replace")

# 3. XML well-formedness & root schema check
root = None
try:
    root = ET.fromstring(text)
except ET.ParseError as e:
    blockers.append(f"Malformed XML syntax (will trigger HTTP 400 Bad Request): {e}")

if root is not None:
    if root.tag != "roblox":
        blockers.append(f"Invalid root element <{root.tag}>: Must be <roblox>.")
    elif root.attrib.get("version") != "4":
        warnings.append(f"Root <roblox version=\"{root.attrib.get('version')}\"> is not '4' (standard Roblox place version).")

    # 4. Place vs. Model check (must contain top-level Workspace, not just standalone Parts/Models)
    top_items = root.findall("Item")
    top_classes = [item.attrib.get("class", "") for item in top_items]

    if not top_items:
        blockers.append("File contains 0 top-level <Item> nodes (empty place).")
    elif "Workspace" not in top_classes:
        blockers.append(
            f"Not a valid Place file: Missing top-level <Item class=\"Workspace\"> "
            f"(found top-level classes: {top_classes[:5]}). This looks like a Model (.rbxmx) rather than a Place (.rbxlx)."
        )

    # Check for duplicate Referent IDs (breaks internal instance linking on upload)
    referents = [item.attrib.get("referent") for item in root.iter("Item") if item.attrib.get("referent")]
    dup_refs = [ref for ref, cnt in Counter(referents).items() if cnt > 1]
    if dup_refs:
        blockers.append(f"Found {len(dup_refs)} duplicate referent ID(s) (e.g., '{dup_refs[-1]}'), which corrupts instance hierarchy on import.")

    # 5. Strict Roblox XML property schema checks
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

    schema_errors = Counter()
    for props in root.iter("Properties"):
        seen = set()
        for prop in props:
            tag = prop.tag
            pname = prop.attrib.get("name", "")
            if pname:
                if (tag, pname) in seen:
                    schema_errors[f"Duplicate property <{tag} name=\"{pname}\"> in same item"] += 1
                seen.add((tag, pname))
            if tag == "Color3uint8":
                schema_errors["Unsupported <Color3uint8> tag"] += 1
            elif tag == "Rect2D":
                if [c.tag for c in prop] != ["min", "max"]:
                    schema_errors[f"Invalid <Rect2D> children {[c.tag for c in prop]}"] += 1
            elif tag in ORDERS:
                ch = [c.tag for c in prop]
                exp = ORDERS[tag]
                if tag == "PhysicalProperties" and ch == ["CustomPhysics"]:
                    continue
                if tag == "Font":
                    exp = [k for k in exp if k in ch]
                if ch != exp:
                    schema_errors[f"Out-of-order <{tag} name=\"{pname}\"> {ch}"] += 1

    for err_desc, count in schema_errors.items():
        blockers.append(f"Schema violation ({count}x): {err_desc}")

# 6. Print Verdict
print(f"File Size: {size_mb:.2f} MB / 100.00 MB limit")
if root is not None:
    print(f"Total Instances: {len(list(root.iter('Item')))}")

print("\n=== Verdict ===")
if not blockers:
    print("[READY] PASS: File is a valid .rbxlx Place and meets Roblox Open Cloud upload requirements.")
    print("  -> Required HTTP Header: Content-Type: application/xml")
    print("  -> Required Query Param: ?versionType=Saved (or Published)")
else:
    print(f"[NOT READY] FAIL: {len(blockers)} upload blocker(s) found:\n")
    for i, b in enumerate(blockers, 1):
        print(f"  {i}. {b}")

if warnings:
    print("\n--- Warnings (Non-blocking) ---")
    for w in warnings:
        print(f"  - {w}")
