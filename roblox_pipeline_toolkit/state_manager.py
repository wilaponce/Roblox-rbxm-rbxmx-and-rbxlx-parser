#!/usr/bin/env python3
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

STATE_FILE = "file_checklists.json"
FOLDERS = [".", "downloads", "copy", "converted", "fixed", "published"]

def load_state():
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "files" in data:
                    return data
        except Exception:
            pass
    return {"active_file": "", "files": {}}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def norm_path(p):
    return p.lstrip("./") if p.startswith("./") else p

def init_entry(state, filepath):
    fp = norm_path(filepath)
    ext = os.path.splitext(fp)[-1].lower()
    if fp not in state["files"]:
        if ext == ".rbxm":
            state["files"][fp] = {
                "type": "binary_model",
                "Fixed": {
                    "converted": False,
                    "convertedto": ""
                },
                "last_error": "None"
            }
        elif ext == ".rbxl":
            state["files"][fp] = {
                "type": "binary_place",
                "Fixed": {
                    "copied_to_copy_folder": fp.startswith("copy/"),
                    "copy_path": fp if fp.startswith("copy/") else "",
                    "published": fp.startswith("published/")
                },
                "last_error": "None"
            }
        else:
            state["files"][fp] = {
                "type": "xml_asset",
                "Fixed": {
                    "ValidXML": False,
                    "CoordinateFrame": False,
                    "Vector3": False,
                    "Vector2": False,
                    "Color3": False,
                    "UDim2": False,
                    "Rect2D": False,
                    "Font": False,
                    "PhysicalProperties": False,
                    "LuaScriptsFixed": False,
                    "OpenCloudReady": False
                },
                "last_error": "None"
            }
    state["active_file"] = fp
    return fp

def format_clean_error(raw_err):
    if not raw_err or raw_err.strip() in ("", "NONE"):
        return "None"
    clean_lines = []
    for line in raw_err.splitlines():
        line = line.strip()
        if not line or len(line) > 140:
            continue
        if any(k in line for k in ("Error", "FAIL", "Invalid", "Exception", "ParseError", "Unclosed", "Unexpected")):
            clean_lines.append(line)
    if not clean_lines:
        first = raw_err.strip().splitlines()
        first_line = first.pop(0) if first else ""
        return first_line[:120] + ("..." if len(first_line) > 120 else "")
    return " | ".join(clean_lines[-2:])

def calc_percentage(fixed_dict):
    bools = [v for v in fixed_dict.values() if isinstance(v, bool)]
    if not bools:
        return 0
    done = sum(1 for v in bools if v)
    return round((done / len(bools)) * 100)

def render_checklist(filepath, entry):
    pct = calc_percentage(entry.get("Fixed", {}))
    display_obj = {
        filepath: {
            "Progress": f"{pct}%",
            "Fixed": entry.get("Fixed", {}),
            "LastError": entry.get("last_error", "None")
        }
    }
    print(json.dumps(display_obj, indent=2))

def inspect_xml(state, fp, err_msg=""):
    fp = init_entry(state, fp)
    fixed = state["files"][fp]["Fixed"]
    if err_msg and err_msg != "NONE":
        state["files"][fp]["last_error"] = format_clean_error(err_msg)
    else:
        state["files"][fp]["last_error"] = "None"

    if not os.path.isfile(fp):
        return

    try:
        root = ET.parse(fp).getroot()
        fixed["ValidXML"] = True
        checks = {
            "CoordinateFrame": True, "Vector3": True, "Vector2": True,
            "Color3": True, "UDim2": True, "Rect2D": True,
            "Font": True, "PhysicalProperties": True, "LuaScriptsFixed": True
        }
        for props in root.iter("Properties"):
            for p in props:
                t = p.tag
                pn = p.attrib.get("name", "")
                ch = [c.tag for c in p]
                if t == "CoordinateFrame" and ch != ["X","Y","Z","R00","R01","R02","R10","R11","R12","R20","R21","R22"]:
                    checks["CoordinateFrame"] = False
                elif t == "Vector3" and ch != ["X","Y","Z"]:
                    checks["Vector3"] = False
                elif t == "Vector2" and ch != ["X","Y"]:
                    checks["Vector2"] = False
                elif t == "Color3" and ch != ["R","G","B"]:
                    checks["Color3"] = False
                elif t == "Color3uint8":
                    checks["Color3"] = False
                elif t == "UDim2" and ch != ["XS","XO","YS","YO"]:
                    checks["UDim2"] = False
                elif t == "Rect2D" and ch != ["min","max"]:
                    checks["Rect2D"] = False
                elif t == "Font":
                    exp = [k for k in ["Family","Weight","Style","CachedFaceId"] if k in ch]
                    if ch != exp:
                        checks["Font"] = False
                elif t == "PhysicalProperties" and ch not in (["CustomPhysics"], ["CustomPhysics","Density","Friction","Elasticity","FrictionWeight","ElasticityWeight"]):
                    checks["PhysicalProperties"] = False
                elif pn == "Source" and p.text and p.text.strip().startswith('String("'):
                    checks["LuaScriptsFixed"] = False

        for k, v in checks.items():
            fixed[k] = v
        has_ws = any(el.attrib.get("class") == "Workspace" for el in root.findall("Item"))
        fixed["OpenCloudReady"] = all(checks.values()) and has_ws
    except Exception as e:
        fixed["ValidXML"] = False
        state["files"][fp]["last_error"] = format_clean_error(str(e))

def scan_workspace(state):
    found = []
    for folder in FOLDERS:
        if not os.path.isdir(folder):
            continue
        for ext in ("*.rbxlx", "*.rbxmx", "*.rbxl", "*.rbxm"):
            for match in glob.glob(os.path.join(folder, ext)):
                fp = norm_path(match)
                found.append(fp)
                if fp not in state["files"]:
                    if fp.endswith((".rbxlx", ".rbxmx")):
                        inspect_xml(state, fp, "NONE")
                    else:
                        init_entry(state, fp)
    if found and (not state.get("active_file") or not os.path.isfile(state["active_file"])):
        newest = max(found, key=os.path.getmtime)
        state["active_file"] = newest

if __name__ == "__main__":
    _, *args = sys.argv
    if not args:
        sys.exit(0)

    cmd = args.pop(0)
    state = load_state()

    if cmd == "register" and args:
        fp = init_entry(state, args.pop(0))
        save_state(state)

    elif cmd == "set_active" and args:
        fp = norm_path(args.pop(0))
        if fp.endswith((".rbxlx", ".rbxmx")):
            inspect_xml(state, fp, "NONE")
        else:
            init_entry(state, fp)
        save_state(state)
        render_checklist(fp, state["files"][fp])

    elif cmd == "mark_converted" and len(args) >= 2:
        src_rbxm = norm_path(args.pop(0))
        dst_rbxmx = norm_path(args.pop(0))
        init_entry(state, src_rbxm)
        state["files"][src_rbxm]["Fixed"]["converted"] = True
        state["files"][src_rbxm]["Fixed"]["convertedto"] = dst_rbxmx
        state["files"][src_rbxm]["last_error"] = "None"
        inspect_xml(state, dst_rbxmx, "NONE")
        save_state(state)

    elif cmd == "update_xml_status" and args:
        fp = norm_path(args.pop(0))
        err_msg = args.pop(0) if args else ""
        inspect_xml(state, fp, err_msg)
        save_state(state)

    elif cmd == "mark_published" and args:
        fp = norm_path(args.pop(0))
        init_entry(state, fp)
        if "published" in state["files"][fp]["Fixed"]:
            state["files"][fp]["Fixed"]["published"] = True
        state["files"][fp]["last_error"] = "None"
        save_state(state)

    elif cmd == "show":
        scan_workspace(state)
        save_state(state)
        fp = norm_path(args.pop(0)) if args else state.get("active_file", "")
        if not fp or fp not in state["files"]:
            print('{\n  "status": "No files found yet. Download a place or model to begin."\n}')
        else:
            render_checklist(fp, state["files"][fp])
