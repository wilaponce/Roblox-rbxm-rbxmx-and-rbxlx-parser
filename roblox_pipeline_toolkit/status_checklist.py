#!/usr/bin/env python3
import glob
import json
import os
import xml.etree.ElementTree as ET

target = ""
if os.path.isfile("publish_config.json"):
    try:
        cfg = json.load(open("publish_config.json", encoding="utf-8"))
        cand = cfg.get("rbxlx_file", "")
        if cand and os.path.isfile(cand):
            target = cand
    except Exception:
        pass

if not target:
    rbxlx_files = sorted(glob.glob("*.rbxlx"), key=os.path.getmtime, reverse=True)
    if rbxlx_files:
        target = rbxlx_files

status = {
    "target_file": target or "none",
    "Fixed": {
        "ValidXML": False,
        "Vector3": False,
        "CoordinateFrame": False,
        "Rect2D": False,
        "Font": False,
        "PhysicalProperties": False,
        "NoColor3uint8": False,
        "NoNaNFloats": False,
        "LuaScriptsUnwrapped": False,
        "OpenCloudReady": False
    }
}

if target and os.path.isfile(target):
    try:
        raw = open(target, "r", encoding="utf-8", errors="replace").read()
        root = ET.fromstring(raw)
        f = status["Fixed"]
        f["ValidXML"] = True

        v3_ok = cf_ok = rect_ok = font_ok = phys_ok = c3_ok = nan_ok = lua_ok = True

        for props in root.iter("Properties"):
            for p in props:
                tag = p.tag
                pname = p.attrib.get("name", "")
                ch = [c.tag for c in p]
                if tag == "Vector3" and ch != ["X", "Y", "Z"]:
                    v3_ok = False
                elif tag == "CoordinateFrame" and ch != ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"]:
                    cf_ok = False
                elif tag == "Rect2D" and ch != ["min", "max"]:
                    rect_ok = False
                elif tag == "Font":
                    exp = [k for k in ["Family", "Weight", "Style", "CachedFaceId"] if k in ch]
                    if ch != exp:
                        font_ok = False
                elif tag == "PhysicalProperties" and ch != ["CustomPhysics"] and ch != ["CustomPhysics", "Density", "Friction", "Elasticity", "FrictionWeight", "ElasticityWeight"]:
                    phys_ok = False
                elif tag == "Color3uint8":
                    c3_ok = False
                elif tag in ("float", "double") and p.text and p.text.strip().lower() in ("nan", "inf", "-inf"):
                    nan_ok = False
                elif pname == "Source" and p.text and p.text.strip().startswith('String("'):
                    lua_ok = False

        has_ws = any(el.attrib.get("class") == "Workspace" for el in root.findall("Item"))

        f["Vector3"] = v3_ok
        f["CoordinateFrame"] = cf_ok
        f["Rect2D"] = rect_ok
        f["Font"] = font_ok
        f["PhysicalProperties"] = phys_ok
        f["NoColor3uint8"] = c3_ok
        f["NoNaNFloats"] = nan_ok
        f["LuaScriptsUnwrapped"] = lua_ok
        f["OpenCloudReady"] = all([v3_ok, cf_ok, rect_ok, font_ok, phys_ok, c3_ok, nan_ok, lua_ok, has_ws])
    except Exception:
        pass

print(json.dumps(status, indent=2))
