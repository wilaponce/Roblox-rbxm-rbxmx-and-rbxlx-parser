#!/usr/bin/env python3
import re, sys, shutil

path = sys.argv[1]
shutil.copyfile(path, path + ".bak")

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

order = ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"]

def fix_cf(m):
    open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
    tags = dict(re.findall(r"<([XYZ]|R[0-2]{2})>(.*?)</\1>", body, re.DOTALL))
    if len(tags) != 12:
        return m.group(0)
    indent_match = re.search(r"\n([ \t]*)<", body)
    indent = indent_match.group(1) if indent_match else ""
    sorted_lines = "\n".join(f"{indent}<{k}>{tags[k]}</{k}>" for k in order)
    return f"{open_tag}\n{sorted_lines}\n{indent[:-2] if len(indent) >= 2 else indent}{close_tag}"

fixed = re.sub(r"(<CoordinateFrame\b[^>]*>)(.*?)(</CoordinateFrame>)", fix_cf, text, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(fixed)

print("Done! Backup saved to " + path + ".bak")

