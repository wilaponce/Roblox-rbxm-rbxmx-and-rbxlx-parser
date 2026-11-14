# Roblox RBXLX / RBXM Repair, Merge & Open Cloud Pipeline

A modular, menu-driven CLI toolkit built for **Termux** and **Linux** to repair corrupted Roblox XML schemas, convert binary `.rbxm` models to `.rbxmx`, inject systems into `.rbxlx` place files, repair escaped/corrupted Luau scripts, verify Open Cloud stream compatibility, and publish directly via the **Roblox Open Cloud Places API**.

---

## This is sick! All on my mobile phone and originally made for a specific rbxm file but since then it has evolved, especially not having access to a laptop or Roblox Studio.

---

## Features

* **Interactive JSON-Driven Menu (`roblox_pipeline.sh`):** Dynamically loads all steps from `pipeline_steps.json`, includes an interactive file selector with byte sizes, creates timestamped backups automatically, and lets you register new custom scripts directly from the menu (`Option A`).
* **One-Click Auto-Pipeline (`Option P`):** Chains XML schema repair, Lua script unwrapping/repair, split-quote fixing, and Open Cloud readiness verification in order on any `.rbxlx` file.
* **Binary `.rbxm` to `.rbxmx` Converter (`convert_rbxm_to_rbxmx.py`):** Parses Roblox binary chunk formats (`INST`, `PROP`, `PRNT`) directly in Python—bypassing reflection mismatches (such as `Attachment.Tags`) and safely Base64-encoding binary attributes.
* **System & Service Installer (`install_martial_combat.py` & `merge_rbxm_to_rbxlx.luau`):** Automatically routes models, folders, and scripts into `ReplicatedStorage`, `ServerScriptService`, and `StarterPlayerScripts` while remapping `referent` IDs to prevent collisions.
* **Strict Roblox XML Schema Repair (`repair_rbxlx.py` & `sync_rbxlx_schema.py`):** Fixes out-of-order `CoordinateFrame`, `Vector3`, `Vector2`, `Color3`, `UDim2`, `PhysicalProperties`, `Font`, and `Rect2D` tags, cleans `NaN`/`Inf` floats, and syncs schema conventions (`size`/`shape`, `Color3uint8`, `<string name="Source">`) to a working reference place.
* **Luau Script Unwrapper & Syntax Auditor (`audit_and_fix_lua.py` & `fix_split_lua_strings.py`):** Unwraps `String("...")` debug wrappers, decodes Rust/C escape sequences, rejoins split multi-line string literals, and validates delimiter and string balance across every script in the place.
* **Open Cloud Validation & Publishing (`verify_opencloud_place.py`, `diff_rbxlx.py`, `roblox_publish.sh`):** Audits place files against Open Cloud upload rules before publishing via `POST /universes/v1/{universeId}/places/{placeId}/versions`.

---

## Prerequisites

* **Environment:** Termux (Android) or any Linux/macOS Bash shell
* **System Packages:** `python3`, `jq`, `curl`, `git`, `zip`
* **Python Packages:** `lz4`, `zstandard`
* **Optional:** `lune` (for Luau-based binary `.rbxm` merging)

---

## Installation

### Option 1: From the Packaged Zip Archive
1. **Grant storage access (Termux only) and copy the archive into your workspace:**
   ```bash
   termux-setup-storage
   mkdir -p ~/my_roblox_workspace
   cp ~/storage/downloads/roblox_pipeline_toolkit.zip ~/my_roblox_workspace/
   cd ~/my_roblox_workspace
   ```

2. **Extract the archive and enter the toolkit folder:**
   ```bash
   unzip roblox_pipeline_toolkit.zip
   cd roblox_pipeline_toolkit
   ```

3. **Run the automated build script:**
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
   `build.sh` installs required Termux/system packages (`python`, `jq`, `curl`, `git`, `zip`), installs Python compression libraries (`lz4`, `zstandard`), marks all `.sh` and `.py` files executable, sorts `pipeline_steps.json` by category, and generates `publish_config.json` from `publish_config.example.json`.

### Option 2: Manual Installation (Without `build.sh`)
If you are on a Linux or macOS system without Termux's `pkg` manager:
```bash
pip3 install lz4 zstandard
chmod +x *.sh *.py
cp publish_config.example.json publish_config.json
```

---

## Setup & Configuration

### 1. Create a Roblox Open Cloud API Key
1. Go to the **Roblox Creator Dashboard** -> **Open Cloud** -> **API Keys**.
2. Create a new API key and add the **Place Publishing** (`universe-places:write`) API system.
3. Select your target **Experience (Universe)** and set your IP restriction (`0.0.0.0/0` if using mobile data on Termux).
4. Copy the generated API key.

### 2. Configure `publish_config.json`
Open `publish_config.json` and fill in your Universe ID, Place ID, API Key, and target file:
```json
{
  "universe_id": 1234567890,
  "place_id": 9876543210,
  "api_key": "YOUR_ROBLOX_OPEN_CLOUD_API_KEY",
  "rbxlx_file": "your_place.rbxlx",
  "publish_endpoint": "https://roblox.com"
}
```
* **`versionType=Published` vs. `versionType=Saved`:** Use `Published` to push changes live to players immediately, or `Saved` to upload a version to Studio without overwriting the live game.
* **Security:** `publish_config.json` is excluded in `.gitignore` so your API key is never committed to Git.

---

## Usage

Launch the interactive menu from your workspace directory:

```bash
./roblox_pipeline.sh
```

### Typical Workflow: Merging a Binary `.rbxm` into a Place
1. Run **Full XML Tag & Schema Repair (`repair_rbxlx.py`)** on your base `.rbxlx` place if it was exported from an external tool.
2. Run **Convert Binary `.rbxm to .rbxmx` (`convert_rbxm_to_rbxmx.py`)** on your `.rbxm` model file.
3. Run **Install `.rbxmx` Model into Place (`install_martial_combat.py`)** to inject the converted `.rbxmx` into your base `.rbxlx`.
4. Run **Option `P` (Full Auto-Pipeline)** on the merged `.rbxlx` file to repair scripts and verify Open Cloud compatibility.
5. Run **Publish Place to Open Cloud (`roblox_publish.sh`)** to upload the verified place and receive a new `versionNumber`.

### Expanding the Pipeline
* **Add a New Script (`Option A`):** Select `A` in the main menu to register any `.py`, `.sh`, or `.luau` script, specify its target file extensions, and choose whether it runs during the Full Auto-Pipeline.
* **Run Full Auto-Pipeline (`Option P`):** Select `P` to automatically back up, repair XML tags, fix Lua scripts, and verify Open Cloud upload readiness in a single pass.

---

## Script Reference & Explanations

### Core Orchestration & Publishing
* **`roblox_pipeline.sh`**: The main interactive CLI menu. Reads `pipeline_steps.json` dynamically via `jq`, provides numbered file pickers with byte sizes, creates timestamped backups before destructive edits, and executes scripts using the matching interpreter (`python3`, `bash`, or `lune`).
* **`pipeline_steps.json`**: JSON registry defining every menu option, its category header, execution mode (`single`, `pair`, or `merge_to_output`), allowed file extensions, backup flag, and inclusion in the Full Auto-Pipeline (`Option P`).
* **`roblox_publish.sh`**: Reads `publish_config.json`, detects whether the target file is XML (`.rbxlx` -> `Content-Type: application/xml`) or binary (`.rbxl` -> `Content-Type: application/octet-stream`), uploads via `curl --data-binary`, logs the response to `publish_response.json`, and saves the new version number to `latest_version.txt`.
* **`build.sh`**: Environment setup script that installs dependencies, sets executable permissions, initializes `publish_config.json`, and sorts `pipeline_steps.json`.

### Category 1: XML Structure & Schema Repair
* **`repair_rbxlx.py`**: Comprehensive XML fixer that reorders scrambled child tags inside `CoordinateFrame`, `Vector3`, `Vector2`, `Vector3int16`, `Vector2int16`, `Color3`, `UDim2`, `PhysicalProperties`, and `Font` blocks; converts `<Rect2D>` to lowercase `<min>`/`<max>`; converts or removes unsupported `<Color3uint8>` tags; and strips duplicate property names inside the same `<Properties>` block.
* **`fix_cframe.py` / `fix_vector2d.py` / `fix_colors.py` / `fix_roblox.py`**: Standalone single-purpose repair scripts for fixing `CoordinateFrame` rotation matrices, `Rect2D` bounds, `Color3uint8` packing, or standard multi-tag ordering individually.

### Category 2: Model Conversion & Service Merging
* **`convert_rbxm_to_rbxmx.py`**: Custom Python binary parser for Roblox's `<roblox!>` binary format. Decompresses `LZ4` and `Zstd` chunks (`INST`, `PROP`, `PRNT`), skips reflection-incompatible properties (`Tags`, `SecurityCapabilities`), Base64-encodes binary attributes (`AttributesSerialize`), and outputs a clean `.rbxmx` XML file.
* **`install_martial_combat.py`**: Tree-based XML merger that injects system components (`MartialCombatSystem`, `MartialCombatServer`, `MartialCombatClient`, `OptionalDamageNumbers`) into their required Roblox services (`ReplicatedStorage`, `ServerScriptService`, `StarterPlayerScripts`), remaps `referent` IDs to avoid collisions, and aligns property casing (`size`, `shape`, `<string name="Source">`) with the base place.
* **`merge_rbxm_to_rbxlx.luau`**: Lune-based Luau script that deserializes a binary `.rbxm` and `.rbxlx` using `@lune/roblox` and routes instances into their target services.
* **`sync_rbxlx_schema.py`**: Compares a target `.rbxlx` file against a known-working reference `.rbxlx` file and normalizes root headers, `Source` tags, property casing, and `NaN` floats to match the reference.

### Category 3: Lua Script Repair & Syntax Diagnostics
* **`fix_script_strings.py`**: Unwraps scripts accidentally serialized with Rust debug wrappers (`String("...")`) and decodes escaped newlines, tabs, and quotes back into valid Luau source code.
* **`audit_and_fix_lua.py`**: Scans every `Script`, `LocalScript`, and `ModuleScript` in the file, strips BOM/null bytes, unwraps `String("...")` blocks, fixes line-continuation backslashes, checks bracket/string balance, and prints surrounding context lines for any syntax errors (saving output to `lua_audit_report.txt`).
