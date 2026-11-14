#!/usr/bin/env python3
import re
import shutil
import sys
import xml.etree.ElementTree as ET

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"
shutil.copyfile(path, path + ".pre_quote_fix.bak")

def fix_split_quotes(src):
    if not src:
        return src, False
    lines = src.splitlines()
    out = []
    i = 0
    changed = False
    in_block_comment = False

    while i < len(lines):
        line = lines[i]

        # Track --[[ ... ]] block comments so we don't alter comments
        if in_block_comment:
            out.append(line)
            if "]]" in line:
                in_block_comment = False
            i += 1
            continue

        stripped = line.lstrip()
        if stripped.startswith("--[[") and "]]" not in stripped:
            in_block_comment = True
            out.append(line)
            i += 1
            continue

        # Ignore single-line comments when counting quotes
        code_part = line.split("--", 1)

        # Count unescaped double quotes on the code portion
        unescaped_quotes = len(re.findall(r'(?<!\\)"', code_part))
        if unescaped_quotes % 2 == 1 and i + 1 < len(lines):
            # Merge with the following line using \n until the quote closes
            merged = line
            while i + 1 < len(lines):
                i += 1
                next_line = lines[i]
                merged = merged + "\\n" + next_line
                check_part = merged.split("--", 1)
                if len(re.findall(r'(?<!\\)"', check_part)) % 2 == 0:
                    break
            out.append(merged)
            changed = True
        else:
            out.append(line)
        i += 1

    return "\n".join(out), changed

tree = ET.parse(path)
root = tree.getroot()

fixed_scripts = []
for item in root.iter("Item"):
    if item.attrib.get("class") not in {"Script", "LocalScript", "ModuleScript"}:
        continue
    props = item.find("Properties")
    if props is None:
        continue
    name = ""
    src_el = None
    for p in props:
        if p.attrib.get("name") == "Name":
            name = p.text or ""
        elif p.attrib.get("name") == "Source":
            src_el = p

    if src_el is not None and src_el.text:
        new_code, was_fixed = fix_split_quotes(src_el.text)
        if was_fixed:
            src_el.text = new_code
            fixed_scripts.append(name)

ET.indent(tree, space="  ")
tree.write(path, encoding="utf-8", xml_declaration=False)

print(f"Repaired split string literals in {len(fixed_scripts)} script(s): {fixed_scripts}")
