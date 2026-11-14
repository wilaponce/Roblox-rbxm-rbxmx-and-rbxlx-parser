#!/usr/bin/env python3
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

if len(sys.argv) != 3:
    print("Usage: ./diff_rbxlx.py <file_1.rbxlx> <file_2.rbxlx>")
    sys.exit(1)

_, orig_path, work_path = sys.argv

print("=== Comparing RBXLX Files ===")
print(f"  File 1 : {orig_path}")
print(f"  File 2 : {work_path}\n")

with open(orig_path, "rb") as f:
    orig_raw = f.read()
with open(work_path, "rb") as f:
    work_raw = f.read()

orig_text = orig_raw.decode("utf-8", errors="replace")
work_text = work_raw.decode("utf-8", errors="replace")

# 1. File Size & Header Comparison
print("--- 1. File & Header Differences ---")
print(f"  Size (bytes) : {len(orig_raw):,} -> {len(work_raw):,} (diff: {len(work_raw) - len(orig_raw):+,})")

orig_top = orig_text.splitlines()[:3]
work_top = work_text.splitlines()[:3]
if orig_top != work_top:
    print("  Top lines changed:")
    print(f"    File 1 : {orig_top}")
    print(f"    File 2 : {work_top}")
else:
    print("  Top 3 lines  : Identical")

orig_root = ET.fromstring(orig_text)
work_root = ET.fromstring(work_text)

if orig_root.attrib != work_root.attrib:
    print(f"  Root Attribs : {orig_root.attrib} -> {work_root.attrib}")

# 2. Instance (<Item>) Count Comparison
orig_items = Counter(el.attrib.get("class", "Unknown") for el in orig_root.iter("Item"))
work_items = Counter(el.attrib.get("class", "Unknown") for el in work_root.iter("Item"))

print("\n--- 2. Instance (<Item>) Count Differences ---")
all_classes = sorted(set(orig_items) | set(work_items))
item_diffs = [(c, orig_items[c], work_items[c]) for c in all_classes if orig_items[c] != work_items[c]]
if not item_diffs:
    print(f"  Identical instance counts ({sum(work_items.values())} total items).")
else:
    for cls, c1, c2 in item_diffs:
        print(f"  {cls}: {c1} -> {c2} ({c2 - c1:+})")

# 3. Property Tag Type Differences
def get_prop_stats(root):
    tag_counts = Counter()
    prop_name_counts = Counter()
    child_orders = defaultdict(Counter)
    val_examples = defaultdict(set)

    for props in root.iter("Properties"):
        for p in props:
            tag = p.tag
            pname = p.attrib.get("name", "<unnamed>")
            tag_counts[tag] += 1
            prop_name_counts[(tag, pname)] += 1
            children = tuple(c.tag for c in p)
            if children:
                child_orders[(tag, pname)][children] += 1
            txt = (p.text or "").strip()
            if txt and len(txt) < 40:
                val_examples[(tag, pname)].add(txt)
    return tag_counts, prop_name_counts, child_orders, val_examples

o_tags, o_names, o_orders, o_vals = get_prop_stats(orig_root)
w_tags, w_names, w_orders, w_vals = get_prop_stats(work_root)

print("\n--- 3. Property Tag Count Differences ---")
all_tags = sorted(set(o_tags) | set(w_tags))
tag_diffs = [(t, o_tags[t], w_tags[t]) for t in all_tags if o_tags[t] != w_tags[t]]
if not tag_diffs:
    print("  No property tag count changes.")
else:
    for t, c1, c2 in tag_diffs:
        print(f"  <{t}>: {c1} -> {c2} ({c2 - c1:+})")

print("\n--- 4. Specific Property Names Added / Removed ---")
all_pnames = sorted(set(o_names) | set(w_names))
pname_diffs = [(tp, o_names[tp], w_names[tp]) for tp in all_pnames if o_names[tp] != w_names[tp]]
if not pname_diffs:
    print("  No specific property name counts changed.")
else:
    for (tag, pname), c1, c2 in pname_diffs:
        print(f'  <{tag} name="{pname}">: {c1} -> {c2} ({c2 - c1:+})')

# 5. Child Element Reordering
print("\n--- 5. Child Element Structure / Order Changes ---")
order_changes = []
for tp in sorted(set(o_orders) | set(w_orders)):
    if o_orders[tp] != w_orders[tp]:
        order_changes.append((tp, dict(o_orders[tp]), dict(w_orders[tp])))

if not order_changes:
    print("  No child element order or structure changes.")
else:
    for (tag, pname), ord1, ord2 in order_changes:
        print(f'  <{tag} name="{pname}">:')
        print(f"    File 1 shapes : {ord1}")
        print(f"    File 2 shapes : {ord2}")

# 6. Value Transformations
print("\n--- 6. Notable Value Replacements ---")
val_changes = []
for tp in sorted(set(o_vals) & set(w_vals)):
    removed_vals = o_vals[tp] - w_vals[tp]
    added_vals = w_vals[tp] - o_vals[tp]
    special_removed = [v for v in removed_vals if v.upper() in ("NAN", "INF", "-INF")]
    if special_removed:
        val_changes.append((tp, special_removed, list(added_vals)[:5]))

if not val_changes:
    print("  No special value replacements (like NAN/INF) detected.")
else:
    for (tag, pname), rem, add in val_changes:
        print(f'  <{tag} name="{pname}">: removed {rem} -> now contains {add}')
