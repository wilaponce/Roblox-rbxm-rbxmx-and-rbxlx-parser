#!/usr/bin/env python3
import ast
import shutil
import sys
import xml.etree.ElementTree as ET

path = sys.argv[-1] if len(sys.argv) > 1 else "16089886249_with_MartialCombat.rbxlx"
shutil.copyfile(path, path + ".pre_unwrap.bak")

tree = ET.parse(path)
root = tree.getroot()

fixed_count = 0
for el in root.iter():
    if el.text and el.text.startswith('String("') and el.text.endswith('")'):
        inner_literal = el.text[len("String("):-1]
        try:
            # Safely decode the escaped string literal back into clean multi-line text
            el.text = ast.literal_eval(inner_literal)
            fixed_count += 1
        except Exception as e:
            print(f"[WARN] Could not decode {el.tag} ({el.attrib}): {e}")

ET.indent(tree, space="  ")
tree.write(path, encoding="utf-8", xml_declaration=False)
print(f"[DONE] Unwrapped and decoded {fixed_count} String(\"...\") tag(s) in {path}")
