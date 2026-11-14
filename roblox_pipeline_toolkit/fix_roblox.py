import re
import sys

if len(sys.argv) < 2:
    print("Usage: python3 fix_roblox.py your_file.rbxlx")
    sys.exit(1)

path = sys.argv[1]
with open(path, "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

SCHEMAS = {
    "CoordinateFrame": ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"],
    "Vector3": ["X", "Y", "Z"],
    "Vector2": ["X", "Y"],
    "Color3": ["R", "G", "B"],
    "UDim2": ["XS", "XO", "YS", "YO"],
}

counts = {k: 0 for k in SCHEMAS}

for tag_name, order in SCHEMAS.items():
    pattern = re.compile(rf"(<{tag_name}\b[^>]*>)(.*?)(</{tag_name}>)", re.DOTALL)
    child_pattern = re.compile(r"<([A-Za-z0-9_]+)>\s*([^<]*?)\s*</\1>")

    def replacer(m, order=order, tag_name=tag_name):
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        pairs = child_pattern.findall(body)
        found = dict(pairs)
        if len(found) != len(order) or not all(k in found for k in order):
            return m.group(0)
        current_order = [k for k, _ in pairs]
        if current_order != order:
            counts[tag_name] += 1
        indent_match = re.search(r"\n([ \t]*)<", body)
        indent = indent_match.group(1) if indent_match else ""
        close_indent = indent[:-2] if len(indent) >= 2 else ""
        sorted_lines = "\n".join(f"{indent}<{k}>{found[k]}</{k}>" for k in order)
        return f"{open_tag}\n{sorted_lines}\n{close_indent}{close_tag}"

    text = pattern.sub(replacer, text)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

for k, v in counts.items():
    print(f"Fixed {v} {k} blocks")
