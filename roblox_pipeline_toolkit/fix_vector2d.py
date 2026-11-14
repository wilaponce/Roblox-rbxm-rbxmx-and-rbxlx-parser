#!/usr/bin/env python3
import re, sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

def fix_v3(m):
    open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
    tags = dict(re.findall(r"<([XYZ])>(.*?)</\1>", body, re.DOTALL))
    if len(tags) != 3:
        return m.group(0)
    indent_match = re.search(r"\n([ \t]*)<", body)
    indent = indent_match.group(1) if indent_match else ""
    sorted_lines = "\n".join(f"{indent}<{k}>{tags[k]}</{k}>" for k in ["X", "Y", "Z"])
    return f"{open_tag}\n{sorted_lines}\n{indent[:-2] if len(indent) >= 2 else indent}{close_tag}"

fixed = re.sub(r"(<Vector3\b[^>]*>)(.*?)(</Vector3>)", fix_v3, text, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(fixed)

print("Fixed all Vector3 blocks!")
 

