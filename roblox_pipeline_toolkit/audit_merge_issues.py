#!/usr/bin/env python3
import base64
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"

print(f"=== Deep Merge & Stream Audit: {path} ===\n")

try:
    with open(path, "rb") as f:
        raw = f.read()
except FileNotFoundError:
    print(f"[ERROR] File not found: {path}")
    sys.exit(1)

# 1. Header & XML Declaration check
header_preview = raw[:250].decode("utf-8", errors="replace")
if not header_preview.lstrip().startswith("<"):
    print("[FAIL] File does not start with '<' (corrupted leading bytes).")
elif "version=\"4\"" not in header_preview:
    print("[WARN] <roblox version=\"4\"> attribute not found in top 250 bytes.")

root = ET.fromstring(raw.decode("utf-8"))

# Standard property tags recognized by Roblox's Open Cloud XML deserializer
VALID_PROP_TAGS = {
    "string", "ProtectedString", "Content", "BinaryString", "SharedString",
    "bool", "int", "int64", "float", "double",
    "UDim", "UDim2", "Ray", "Faces", "Axes", "BrickColor",
    "Color3", "Color3uint8", "Vector2", "Vector3", "Vector2int16", "Vector3int16",
    "CFrame", "CoordinateFrame", "Quaternion", "Enum", "Ref",
    "PhysicalProperties", "ColorSequence", "NumberSequence", "NumberRange",
    "Rect2D", "Font", "UniqueId", "SecurityCapabilities", "OptionalCoordinateFrame"
}

# Tags that commonly break Open Cloud XML stream parsing if malformed or from newer/older Studio builds
SUSPICIOUS_TAGS = {
    "SharedString", "OptionalCoordinateFrame", "SecurityCapabilities",
    "UniqueId", "Color3uint8", "Quaternion", "Capabilities"
}

invalid_props = Counter()
sample_locations = defaultdict(list)

def item_label(el):
    cls = el.attrib.get("class", "Unknown")
    props = el.find("Properties")
    if props is not None:
        for p in props:
            if p.attrib.get("name") == "Name" and p.text:
                return f'{cls} "{p.text}"'
    return cls

# 2. Check Referents & Ref Pointers
referent_counts = Counter()
for el in root.iter("Item"):
    ref = el.attrib.get("referent")
    if not ref:
        invalid_props["Missing referent attribute on <Item>"] += 1
    else:
        referent_counts[ref] += 1

dup_refs = {r: c for r, c in referent_counts.items() if c > 1}
valid_ref_set = set(referent_counts.keys())

# Check <SharedString md5="..."> registry at root/bottom
shared_md5s = set()
for ss in root.findall("SharedStrings/SharedString"):
    md5 = ss.attrib.get("md5", "")
    if md5:
        shared_md5s.add(md5)
    b64 = (ss.text or "").strip()
    if b64:
        try:
            base64.b64decode(b64, validate=True)
        except Exception:
            invalid_props["Invalid Base64 in <SharedStrings><SharedString>"] += 1

# 3. Walk all <Item> -> <Properties>
for el in root.iter("Item"):
    lbl = item_label(el)
    props = el.find("Properties")
    if props is None:
        continue

    for prop in props:
        tag = prop.tag
        pname = prop.attrib.get("name", "<unnamed>")
        val_text = (prop.text or "").strip()

        # A. Completely unknown XML property tag
        if tag not in VALID_PROP_TAGS:
            reason = f'Unrecognized property tag <{tag} name="{pname}">'
            invalid_props[reason] += 1
            if len(sample_locations[reason]) < 3:
                sample_locations[reason].append(lbl)

        # B. Suspicious / merge-incompatible tags
        if tag in SUSPICIOUS_TAGS:
            reason = f'Potentially unsupported tag <{tag} name="{pname}">'
            invalid_props[reason] += 1
            if len(sample_locations[reason]) < 3:
                sample_locations[reason].append(lbl)

        # C. Validate BinaryString Base64 encoding
        if tag == "BinaryString" and val_text:
            clean_b64 = re.sub(r"\s+", "", val_text)
            try:
                base64.b64decode(clean_b64, validate=True)
            except Exception:
                reason = f'Corrupted Base64 in <BinaryString name="{pname}">'
                invalid_props[reason] += 1
                if len(sample_locations[reason]) < 3:
                    sample_locations[reason].append(lbl)

        # D. Validate SharedString md5 reference
        if tag == "SharedString":
            if val_text and val_text not in shared_md5s:
                reason = f'Dangling <SharedString name="{pname}"> (md5 "{val_text}" not in <SharedStrings>)'
                invalid_props[reason] += 1
                if len(sample_locations[reason]) < 3:
                    sample_locations[reason].append(lbl)

        # E. Validate <Ref> pointers
        if tag == "Ref":
            if val_text and val_text != "null" and val_text not in valid_ref_set:
                reason = f'Dangling <Ref name="{pname}"> pointing to missing referent "{val_text}"'
                invalid_props[reason] += 1
                if len(sample_locations[reason]) < 3:
                    sample_locations[reason].append(lbl)

        # F. Validate numeric fields (float, double, int, int64, token)
        if tag in ("float", "double"):
            if val_text.lower() in ("nan", "inf", "-inf", "1.#inf", "-1.#inf", "1.#ind"):
                reason = f'Invalid NaN/Inf float in <{tag} name="{pname}"> ({val_text})'
                invalid_props[reason] += 1
                if len(sample_locations[reason]) < 3:
                    sample_locations[reason].append(lbl)

        # G. Validate OptionalCoordinateFrame
        if tag == "OptionalCoordinateFrame":
            children = [c.tag for c in prop]
            if children not in ([], ["CFrame"]):
                reason = f'Invalid <OptionalCoordinateFrame name="{pname}"> children {children}'
                invalid_props[reason] += 1
                if len(sample_locations[reason]) < 3:
                    sample_locations[reason].append(lbl)

# 4. Print Concise Report
print("--- Root & Referent Summary ---")
print(f"  Root Attributes   : {root.attrib}")
print(f"  Total <Item>s     : {sum(referent_counts.values())}")
print(f"  Duplicate Refs    : {len(dup_refs)}")
if dup_refs:
    for r, c in list(dup_refs.items())[:5]:
        print(f"    - {r} (appears {c} times)")

print("\n--- Invalid / Suspicious Properties Found ---")
if not invalid_props and not dup_refs:
    print("  [PASS] 0 invalid properties, dangling refs, or duplicate referents found.")
else:
    for reason, cnt in invalid_props.most_common():
        locs = ", ".join(sample_locations[reason])
        loc_str = f" (e.g., {locs})" if locs else ""
        print(f"  [{cnt}x] {reason}{loc_str}")
