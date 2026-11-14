#!/usr/bin/env python3
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) < 3:
    print("Usage: ./sync_rbxlx_schema.py <working_reference.rbxlx> <target_to_fix.rbxlx> [optional_output.rbxlx]")
    sys.exit(1)

ref_path = sys.argv[1]
target_path = sys.argv[2]
out_path = sys.argv[3] if len(sys.argv) > 3 else target_path

for p in (ref_path, target_path):
    if not os.path.isfile(p):
        print(f"[ERROR] File not found: {p}")
        sys.exit(1)

if out_path == target_path:
    bak_path = target_path + ".bak"
    shutil.copyfile(target_path, bak_path)
    print(f"[BACKUP] Saved original to {bak_path}")

with open(ref_path, "r", encoding="utf-8", errors="replace") as f:
    ref_text = f.read()

with open(target_path, "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

ref_root = ET.fromstring(ref_text)

# 1. Detect reference schema conventions dynamically
ref_root_tag_match = re.search(r"<roblox\b[^>]*>", ref_text)
ref_root_tag = ref_root_tag_match.group(0) if ref_root_tag_match else '<roblox version="4">'
ref_has_external = bool(re.search(r"<External>(?:null|nil)</External>", ref_text))

ref_prop_types = set()
ref_prop_names = set()
for props in ref_root.iter("Properties"):
    for p in props:
        ref_prop_types.add(p.tag)
        pname = p.attrib.get("name")
        if pname:
            ref_prop_names.add((p.tag, pname))

uses_string_source = ("string", "Source") in ref_prop_names and ("ProtectedString", "Source") not in ref_prop_names
uses_lower_size = ("Vector3", "size") in ref_prop_names and ("Vector3", "Size") not in ref_prop_names
uses_lower_shape = ("token", "shape") in ref_prop_names and ("token", "Shape") not in ref_prop_names
uses_color3uint8 = "Color3uint8" in ref_prop_types

print(f"=== Syncing Schema: {target_path} -> matching {ref_path} ===")
print(f"  Root Header       : {ref_root_tag}")
print(f"  Keep <External>   : {ref_has_external}")
print(f"  Script Source Tag : {'<string>' if uses_string_source else '<ProtectedString>'}")
print(f"  Size/Shape Casing : {'lowercase (size/shape)' if uses_lower_size else 'PascalCase (Size/Shape)'}")
print(f"  Part Color Format : {'<Color3uint8>' if uses_color3uint8 else '<Color3>'}")

# 2. Match <roblox> header and <External> tags
text = re.sub(r"<roblox\b[^>]*>", ref_root_tag, text, count=1)
if not ref_has_external:
    text = re.sub(r"\s*<External>(?:null|nil)</External>", "", text)

# 3. Match Source tag format
if uses_string_source:
    text = re.sub(r'<ProtectedString(\s+name="Source"[^>]*)>', r"<string\1>", text)
    text = text.replace("</ProtectedString>", "</string>")

# 4. Match size / shape casing
if uses_lower_size:
    text = text.replace('<Vector3 name="Size">', '<Vector3 name="size">')
if uses_lower_shape:
    text = text.replace('<token name="Shape">', '<token name="shape">')

# 5. Match Color3uint8 vs Color3 if reference uses Color3uint8
if uses_color3uint8:
    def color3_to_uint8(m):
        r_m = re.search(r"<R>([^<]+)</R>", m.group(1))
        g_m = re.search(r"<G>([^<]+)</G>", m.group(1))
        b_m = re.search(r"<B>([^<]+)</B>", m.group(1))
        if not (r_m and g_m and b_m):
            return m.group(0)
        r = max(0, min(255, round(float(r_m.group(1)) * 255)))
        g = max(0, min(255, round(float(g_m.group(1)) * 255)))
        b = max(0, min(255, round(float(b_m.group(1)) * 255)))
        packed = (0xFF << 24) | (r << 16) | (g << 8) | b
        return f'<Color3uint8 name="Color3uint8">{packed}</Color3uint8>'

    def fix_item_colors(im):
        item_xml = im.group(0)
        cls_m = re.search(r'<Item\s+class="([^"]+)"', item_xml)
        cls = cls_m.group(1) if cls_m else ""
        if cls in ("Part", "SpawnLocation", "WedgePart", "CornerWedgePart", "TrussPart", "VehicleSeat", "Seat", "MeshPart", "UnionOperation"):
            item_xml = re.sub(r'<Color3 name="Color">(.*?)</Color3>', color3_to_uint8, item_xml, flags=re.DOTALL)
        return item_xml

    text = re.sub(r'<Item\b[^>]*>.*?</Item>', fix_item_colors, text, flags=re.DOTALL)

# 6. Strip newer/unsupported properties not present in the reference file
KNOWN_UNSUPPORTED = [
    "BottomLeftRadius",
    "BottomRightRadius",
    "TopLeftRadius",
    "TopRightRadius",
    "FormFactorRaw",
    "HasSeenDeprecationDialog",
    "IsLegacyChatDisabled",
    "ThrottlePhysicsToRealtime",
    "AvatarJointUpgrade_SerializedRollout",
    "PlatformIntegratedChat",
    "TextChannelDisplayMode",
]
removed_count = 0
for prop in KNOWN_UNSUPPORTED:
    if not any(pname == prop for _, pname in ref_prop_names):
        text, n = re.subn(rf'\s*<[A-Za-z0-9_]+ name="{prop}">.*?</[A-Za-z0-9_]+>', "", text, flags=re.DOTALL)
        removed_count += n

# 7. Clean any NaN / Inf floats
text, nan_count = re.subn(
    r'(<(?:float|double)\b[^>]*>)\s*(?:[+-]?(?:nan|inf|1\.#inf|1\.#ind))\s*(</(?:float|double)>)',
    r"\g<1>0\g<2>",
    text,
    flags=re.IGNORECASE,
)

with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)

print(f"  Stripped Unsupported Props : {removed_count}")
print(f"  Cleaned NaN/Inf Floats     : {nan_count}")
print(f"[DONE] Written to {out_path}")
