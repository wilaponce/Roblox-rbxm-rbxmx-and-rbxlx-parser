#!/usr/bin/env python3
import re
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) < 3:
    print("Usage: ./install_martial_combat.py <working_place.rbxlx> <martial_combat.rbxmx> [output.rbxlx]")
    sys.exit(1)

_, place_path, model_path, *rest = sys.argv
out_path = rest.pop(0) if rest else "16089886249_with_MartialCombat.rbxlx"

place_tree = ET.parse(place_path)
place_root = place_tree.getroot()

model_tree = ET.parse(model_path)
model_root = model_tree.getroot()

# 1. Detect schema conventions from working place
uses_string_source = False
uses_lower_size = False
uses_lower_shape = False
uses_color3uint8 = False
max_ref_num = 100000

for item in place_root.iter("Item"):
    ref = item.attrib.get("referent", "")
    m = re.search(r"(\d+)$", ref)
    if m:
        max_ref_num = max(max_ref_num, int(m.group(1)))
    props = item.find("Properties")
    if props is None:
        continue
    for p in props:
        tag = p.tag
        pname = p.attrib.get("name", "")
        if (tag, pname) == ("string", "Source"):
            uses_string_source = True
        elif (tag, pname) == ("Vector3", "size"):
            uses_lower_size = True
        elif (tag, pname) == ("token", "shape"):
            uses_lower_shape = True
        elif tag == "Color3uint8":
            uses_color3uint8 = True

# 2. Helper to find or create target services in the place
def get_or_create_service(parent, class_name, name_val=None):
    for child in parent.findall("Item"):
        if child.attrib.get("class") == class_name:
            return child
    global max_ref_num
    max_ref_num += 1
    svc = ET.SubElement(parent, "Item", {"class": class_name, "referent": f"RBX{max_ref_num:032X}"})
    props = ET.SubElement(svc, "Properties")
    name_el = ET.SubElement(props, "string", {"name": "Name"})
    name_el.text = name_val or class_name
    return svc

rep_storage = get_or_create_service(place_root, "ReplicatedStorage")
server_scripts = get_or_create_service(place_root, "ServerScriptService")
starter_player = get_or_create_service(place_root, "StarterPlayer")
starter_player_scripts = get_or_create_service(starter_player, "StarterPlayerScripts")

# Map item names from the ReadMe to their exact destination service
DESTINATIONS = {
    "MartialCombatSystem": ("ReplicatedStorage", rep_storage),
    "MartialCombatServer": ("ServerScriptService", server_scripts),
    "OptionalDamageNumbers": ("ServerScriptService", server_scripts),
    "MartialCombatClient": ("StarterPlayerScripts", starter_player_scripts),
}

# Remove any previous copies of these 4 items if re-running
for _, container in DESTINATIONS.values():
    for existing in list(container.findall("Item")):
        props = existing.find("Properties")
        if props is not None:
            for p in props:
                if p.attrib.get("name") == "Name" and p.text in DESTINATIONS:
                    container.remove(existing)
                    break

# 3. Remap referents and normalize XML schema ONLY on the imported .rbxmx items
ref_map = {}
for item in model_root.iter("Item"):
    old_ref = item.attrib.get("referent")
    if old_ref:
        max_ref_num += 1
        new_ref = f"RBX{max_ref_num:032X}"
        ref_map[old_ref] = new_ref
        item.set("referent", new_ref)

UNSUPPORTED_PROPS = {
    "UniqueId", "FormFactorRaw", "BottomLeftRadius", "BottomRightRadius",
    "TopLeftRadius", "TopRightRadius", "HasSeenDeprecationDialog",
    "IsLegacyChatDisabled", "ThrottlePhysicsToRealtime",
    "AvatarJointUpgrade_SerializedRollout", "PlatformIntegratedChat",
    "TextChannelDisplayMode",
}

for item in model_root.iter("Item"):
    cls = item.attrib.get("class", "")
    props = item.find("Properties")
    if props is None:
        continue

    to_remove = []
    for p in list(props):
        pname = p.attrib.get("name", "")

        # Update internal <Ref> pointers to match remapped referents
        if p.tag == "Ref" and p.text and p.text in ref_map:
            p.text = ref_map[p.text]

        # Strip UniqueId or unsupported newer tags
        if p.tag == "UniqueId" or pname in UNSUPPORTED_PROPS:
            to_remove.append(p)
            continue

        # Normalize Source tag
        if uses_string_source and p.tag == "ProtectedString" and pname == "Source":
            p.tag = "string"

        # Normalize size / shape casing
        if uses_lower_size and p.tag == "Vector3" and pname == "Size":
            p.set("name", "size")
        if uses_lower_shape and p.tag == "token" and pname == "Shape":
            p.set("name", "shape")

        # Normalize Color3 -> Color3uint8 on BaseParts
        if uses_color3uint8 and p.tag == "Color3" and pname == "Color":
            if cls in ("Part", "SpawnLocation", "WedgePart", "CornerWedgePart", "TrussPart", "VehicleSeat", "Seat", "MeshPart", "UnionOperation"):
                r_el, g_el, b_el = p.find("R"), p.find("G"), p.find("B")
                if r_el is not None and g_el is not None and b_el is not None:
                    r = max(0, min(255, round(float(r_el.text or 0) * 255)))
                    g = max(0, min(255, round(float(g_el.text or 0) * 255)))
                    b = max(0, min(255, round(float(b_el.text or 0) * 255)))
                    packed = (0xFF << 24) | (r << 16) | (g << 8) | b
                    p.clear()
                    p.tag = "Color3uint8"
                    p.set("name", "Color3uint8")
                    p.text = str(packed)

        # Clean NaN/Inf floats
        if p.tag in ("float", "double") and p.text:
            if p.text.strip().lower() in ("nan", "inf", "-inf", "1.#inf", "-1.#inf", "1.#ind"):
                p.text = "0"

    for p in to_remove:
        props.remove(p)

# 4. Find the 4 Martial Combat items anywhere in the .rbxmx and route them to their exact services
installed = []
for item in list(model_root.iter("Item")):
    props = item.find("Properties")
    item_name = ""
    if props is not None:
        for p in props:
            if p.attrib.get("name") == "Name" and p.text:
                item_name = p.text.strip()
                break

    if item_name in DESTINATIONS:
        dest_label, dest_container = DESTINATIONS[item_name]
        dest_container.append(item)
        installed.append((item_name, item.attrib.get("class", ""), dest_label))

print("=== Martial Combat Installation Summary ===")
if not installed:
    print("[WARN] None of the 4 expected items (MartialCombatSystem, MartialCombatServer, MartialCombatClient, OptionalDamageNumbers) were found in the .rbxmx!")
    sys.exit(1)

for name, cls, dest in installed:
    print(f"  Installed: {name} ({cls}) -> {dest}")

ET.indent(place_tree, space="  ")
place_tree.write(out_path, encoding="utf-8", xml_declaration=False)
print(f"\n[DONE] Saved merged place to: {out_path}")
