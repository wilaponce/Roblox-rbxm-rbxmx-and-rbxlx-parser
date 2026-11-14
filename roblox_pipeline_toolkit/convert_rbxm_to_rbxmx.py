import base64
#!/usr/bin/env python3
import os
import struct
import sys
import xml.etree.ElementTree as ET

try:
    import lz4.block
except ImportError:
    print("[ERROR] Missing 'lz4' library. Install it with: pip install lz4")
    sys.exit(1)

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

if len(sys.argv) < 2:
    print("Usage: ./convert_rbxm_to_rbxmx.py <input.rbxm> [output.rbxmx]")
    sys.exit(1)

_, in_path, *rest = sys.argv
base_name, _ = os.path.splitext(in_path)
out_path = rest.pop(0) if rest else base_name + ".rbxmx"

with open(in_path, "rb") as f:
    data = f.read()

if not data.startswith(b"<roblox!\x89\xff\r\n\x1a\n"):
    print("[ERROR] Not a valid binary Roblox file (.rbxm / .rbxl).")
    sys.exit(1)

pos = 32

def read_chunk(offset):
    name = data[offset:offset+4].decode("ascii", errors="replace")
    comp_len, uncomp_len, _ = struct.unpack_from("<III", data, offset + 4)
    payload = data[offset + 16 : offset + 16 + comp_len]
    next_offset = offset + 16 + comp_len
    if comp_len == 0:
        return name, payload, next_offset
    if payload.startswith(b"\x28\xb5\x2f\xfd"):
        if not HAS_ZSTD:
            raise RuntimeError("Chunk uses Zstd compression. Run: pip install zstandard")
        raw = zstd.ZstdDecompressor().decompress(payload, max_output_size=uncomp_len)
    else:
        raw = lz4.block.decompress(payload, uncompressed_size=uncomp_len)
    return name, raw, next_offset

def read_str(buf, off):
    slen, = struct.unpack_from("<I", buf, off)
    off += 4
    return buf[off:off+slen].decode("utf-8", errors="replace"), off + slen

def read_bytes(buf, off):
    slen, = struct.unpack_from("<I", buf, off)
    off += 4
    return buf[off:off+slen], off + slen

def uninterleave_i32(buf, count):
    vals = []
    for i in range(count):
        b = bytes([buf[i], buf[i + count], buf[i + 2*count], buf[i + 3*count]])
        u, = struct.unpack(">I", b)
        vals.append((u >> 1) ^ -(u & 1))
    return vals

def uninterleave_u32(buf, count):
    vals = []
    for i in range(count):
        b = bytes([buf[i], buf[i + count], buf[i + 2*count], buf[i + 3*count]])
        u, = struct.unpack(">I", b)
        vals.append(u)
    return vals

def uninterleave_f32(buf, count):
    vals = []
    for i in range(count):
        b = bytes([buf[i], buf[i + count], buf[i + 2*count], buf[i + 3*count]])
        u, = struct.unpack(">I", b)
        rot = ((u >> 1) | ((u & 1) << 31)) & 0xFFFFFFFF
        f, = struct.unpack("<f", struct.pack("<I", rot))
        vals.append(f)
    return vals

def decode_ref_array(buf, count):
    deltas = uninterleave_i32(buf, count)
    refs, acc = [], 0
    for d in deltas:
        acc += d
        refs.append(acc)
    return refs

instances = {}
type_map = {}

while pos < len(data):
    cname, raw, pos = read_chunk(pos)
    if cname == "END\x00":
        break

    elif cname == "INST":
        type_id, = struct.unpack_from("<I", raw, 0)
        cls_name, off = read_str(raw, 4)
        off += 1
        inst_cnt, = struct.unpack_from("<I", raw, off)
        off += 4
        ids = decode_ref_array(raw[off:off + 4*inst_cnt], inst_cnt)
        type_map[type_id] = {"class": cls_name, "ids": ids}
        for rid in ids:
            instances[rid] = {"class": cls_name, "props": [], "children": [], "parent": -1}

    elif cname == "PROP":
        type_id, = struct.unpack_from("<I", raw, 0)
        prop_name, off = read_str(raw, 4)
        ptype = raw[off]
        off += 1
        if type_id not in type_map:
            continue
        ids = type_map[type_id]["ids"]
        cnt = len(ids)

        if prop_name in ("Tags", "SecurityCapabilities", "Capabilities") or ptype == 0x1E:
            continue

        if ptype == 0x01:
            for rid in ids:
                sbytes, off = read_bytes(raw, off)
                has_ctrl = any(b < 32 and b not in (9, 10, 13) for b in sbytes)
                if has_ctrl or prop_name in ("AttributesSerialize", "PhysicsGrid", "SmoothGrid", "MaterialColors"):
                    b64 = base64.b64encode(sbytes).decode("ascii")
                    instances[rid]["props"].append(("BinaryString", prop_name, b64))
                else:
                    txt = sbytes.decode("utf-8", errors="replace").replace("\ufffd", "")
                    instances[rid]["props"].append(("string", prop_name, txt))
        elif ptype == 0x02:
            for idx, rid in enumerate(ids):
                instances[rid]["props"].append(("bool", prop_name, "true" if raw[off + idx] != 0 else "false"))
        elif ptype == 0x03:
            for rid, v in zip(ids, uninterleave_i32(raw[off:off + 4*cnt], cnt)):
                instances[rid]["props"].append(("int", prop_name, str(v)))
        elif ptype == 0x04:
            for rid, v in zip(ids, uninterleave_f32(raw[off:off + 4*cnt], cnt)):
                v = 0.0 if (v != v or abs(v) == float("inf")) else v
                instances[rid]["props"].append(("float", prop_name, f"{v:.6g}"))
        elif ptype == 0x05:
            for idx, rid in enumerate(ids):
                v, = struct.unpack_from("<d", raw, off + idx*8)
                v = 0.0 if (v != v or abs(v) == float("inf")) else v
                instances[rid]["props"].append(("double", prop_name, f"{v:.12g}"))
        elif ptype == 0x06:
            sc = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            of = uninterleave_i32(raw[off + 4*cnt:off + 8*cnt], cnt)
            for rid, s, o in zip(ids, sc, of):
                instances[rid]["props"].append(("UDim", prop_name, (s, o)))
        elif ptype == 0x07:
            sx = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            sy = uninterleave_f32(raw[off + 4*cnt:off + 8*cnt], cnt)
            ox = uninterleave_i32(raw[off + 8*cnt:off + 12*cnt], cnt)
            oy = uninterleave_i32(raw[off + 12*cnt:off + 16*cnt], cnt)
            for rid, a, b, c, d in zip(ids, sx, ox, sy, oy):
                instances[rid]["props"].append(("UDim2", prop_name, (a, b, c, d)))
        elif ptype == 0x0B:
            for rid, v in zip(ids, uninterleave_u32(raw[off:off + 4*cnt], cnt)):
                instances[rid]["props"].append(("int", prop_name, str(v)))
        elif ptype == 0x0C:
            rs = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            gs = uninterleave_f32(raw[off + 4*cnt:off + 8*cnt], cnt)
            bs = uninterleave_f32(raw[off + 8*cnt:off + 12*cnt], cnt)
            for rid, r, g, b in zip(ids, rs, gs, bs):
                instances[rid]["props"].append(("Color3", prop_name, (r, g, b)))
        elif ptype == 0x0D:
            xs = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            ys = uninterleave_f32(raw[off + 4*cnt:off + 8*cnt], cnt)
            for rid, x, y in zip(ids, xs, ys):
                instances[rid]["props"].append(("Vector2", prop_name, (x, y)))
        elif ptype == 0x0E:
            xs = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            ys = uninterleave_f32(raw[off + 4*cnt:off + 8*cnt], cnt)
            zs = uninterleave_f32(raw[off + 8*cnt:off + 12*cnt], cnt)
            pname = "size" if prop_name == "Size" else prop_name
            for rid, x, y, z in zip(ids, xs, ys, zs):
                instances[rid]["props"].append(("Vector3", pname, (x, y, z)))
        elif ptype == 0x10:
            mats = []
            for _ in range(cnt):
                orient = raw[off]
                off += 1
                if orient > 0:
                    rot = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
                else:
                    rot = list(struct.unpack_from("<9f", raw, off))
                    off += 36
                mats.append(rot)
            xs = uninterleave_f32(raw[off:off + 4*cnt], cnt)
            ys = uninterleave_f32(raw[off + 4*cnt:off + 8*cnt], cnt)
            zs = uninterleave_f32(raw[off + 8*cnt:off + 12*cnt], cnt)
            for rid, rot, x, y, z in zip(ids, mats, xs, ys, zs):
                instances[rid]["props"].append(("CoordinateFrame", prop_name, (x, y, z, rot)))
        elif ptype == 0x12:
            pname = "shape" if prop_name == "Shape" else prop_name
            for rid, v in zip(ids, uninterleave_u32(raw[off:off + 4*cnt], cnt)):
                instances[rid]["props"].append(("token", pname, str(v)))
        elif ptype == 0x13:
            for rid, tref in zip(ids, decode_ref_array(raw[off:off + 4*cnt], cnt)):
                rstr = f"RBX{tref:032X}" if tref >= 0 else "null"
                instances[rid]["props"].append(("Ref", prop_name, rstr))
        elif ptype == 0x1A:
            for rid, r, g, b in zip(ids, raw[off:off+cnt], raw[off+cnt:off+2*cnt], raw[off+2*cnt:off+3*cnt]):
                packed = (0xFF << 24) | (r << 16) | (g << 8) | b
                instances[rid]["props"].append(("Color3uint8", "Color3uint8", str(packed)))
        elif ptype == 0x1B:
            for rid, v in zip(ids, uninterleave_i32(raw[off:off + 4*cnt], cnt)):
                instances[rid]["props"].append(("int64", prop_name, str(v)))

    elif cname == "PRNT":
        _, pcnt = struct.unpack_from("<BI", raw, 0)
        cids = decode_ref_array(raw[5:5 + 4*pcnt], pcnt)
        pids = decode_ref_array(raw[5 + 4*pcnt:5 + 8*pcnt], pcnt)
        for cid, pid in zip(cids, pids):
            if cid in instances:
                instances[cid]["parent"] = pid
                if pid in instances:
                    instances[pid]["children"].append(cid)

root_xml = ET.Element("roblox", {"version": "4"})

def build_xml_item(rid, parent_xml):
    inst = instances[rid]
    item_el = ET.SubElement(parent_xml, "Item", {"class": inst["class"], "referent": f"RBX{rid:032X}"})
    props_el = ET.SubElement(item_el, "Properties")
    for tag, pname, val in inst["props"]:
        if tag == "Vector3":
            el = ET.SubElement(props_el, "Vector3", {"name": pname})
            for ax, num in zip(("X", "Y", "Z"), val):
                ET.SubElement(el, ax).text = f"{num:.6g}"
        elif tag == "Vector2":
            el = ET.SubElement(props_el, "Vector2", {"name": pname})
            for ax, num in zip(("X", "Y"), val):
                ET.SubElement(el, ax).text = f"{num:.6g}"
        elif tag == "Color3":
            el = ET.SubElement(props_el, "Color3", {"name": pname})
            for ch, num in zip(("R", "G", "B"), val):
                ET.SubElement(el, ch).text = f"{num:.6f}"
        elif tag == "UDim":
            el = ET.SubElement(props_el, "UDim", {"name": pname})
            for k, num in zip(("S", "O"), val):
                ET.SubElement(el, k).text = str(num)
        elif tag == "UDim2":
            el = ET.SubElement(props_el, "UDim2", {"name": pname})
            for k, num in zip(("XS", "XO", "YS", "YO"), val):
                ET.SubElement(el, k).text = str(num)
        elif tag == "CoordinateFrame":
            el = ET.SubElement(props_el, "CoordinateFrame", {"name": pname})
            x, y, z, rot = val
            keys = ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"]
            for k, num in zip(keys, [x, y, z] + list(rot)):
                ET.SubElement(el, k).text = f"{num:.6g}"
        else:
            ET.SubElement(props_el, tag, {"name": pname}).text = str(val)
    for cid in inst["children"]:
        build_xml_item(cid, item_el)

for rid, inst in instances.items():
    if inst["parent"] == -1:
        build_xml_item(rid, root_xml)

tree = ET.ElementTree(root_xml)
ET.indent(tree, space="  ")
tree.write(out_path, encoding="utf-8", xml_declaration=False)
print(f"[DONE] Converted {len(instances)} instances from {in_path} -> {out_path}")
