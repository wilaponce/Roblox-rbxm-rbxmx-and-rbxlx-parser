# Roblox RBXLX / RBXM Repair, Merge & Open Cloud Pipeline

A modular, menu-driven CLI toolkit built for **Termux (Android), Linux, macOS, and Windows (WSL / Git Bash)** to download Roblox places and models, repair corrupted Roblox XML schemas, convert binary `.rbxm` models to `.rbxmx`, inject systems into `.rbxlx` place files, repair escaped or corrupted Luau scripts, track repair checklists, and publish directly via the **Roblox Open Cloud Places API**.

> Built entirely on a mobile phone without access to a laptop or Roblox Studio—designed to run anywhere Python 3 and Node.js are available.

---

## Features

* **Interactive JSON-Driven Menu (`roblox_pipeline.sh`):** Dynamically loads steps from `pipeline_steps.json`, includes numbered file pickers with byte sizes, creates timestamped backups automatically, and lets you register new custom scripts directly from the menu (`Option A`).
* **Per-File Repair Checklist (`file_checklists.json` & `status_checklist.py`):** Tracks which repair and audit steps (`Vector3`, `Color3`, `CFrame`, Lua syntax, Open Cloud check, etc.) have already been applied to each `.rbxlx` or `.rbxmx` file.
* **One-Click Auto-Pipeline (`Option P`):** Chains XML schema repair, Lua script unwrapping/repair, split-quote fixing, and Open Cloud readiness verification in order on any `.rbxlx` file.
* **Open Cloud Place & Model Downloaders (`download_place_rbxl.js` & `download_model_rbxm.js`):** Fetches `.rbxlx` places and `.rbxm` models directly by Asset ID using your Open Cloud API key—no Roblox Studio required.
* **Binary `.rbxm` to `.rbxmx` Converter (`convert_rbxm_to_rbxmx.py`):** Parses Roblox binary chunk formats (`INST`, `PROP`, `PRNT`) directly in Python—bypassing reflection mismatches and safely Base64-encoding binary attributes.
* **System & Service Installer (`install_martial_combat.py` & `merge_rbxm_to_rbxlx.luau`):** Automatically routes models, folders, and scripts into `ReplicatedStorage`, `ServerScriptService`, and `StarterPlayerScripts` while remapping `referent` IDs to prevent collisions.
* **Strict Roblox XML Schema Repair (`repair_rbxlx.py` & `sync_rbxlx_schema.py`):** Fixes out-of-order `CoordinateFrame`, `Vector3`, `Vector2`, `Color3`, `UDim2`, `PhysicalProperties`, `Font`, and `Rect2D` tags, cleans `NaN`/`Inf` floats, and syncs schema conventions to a working reference place.
* **Luau Script Unwrapper & Syntax Auditor (`audit_and_fix_lua.py` & `fix_split_lua_strings.py`):** Unwraps `String("...")` debug wrappers, decodes escape sequences, rejoins split multi-line string literals, and validates delimiter and string balance across every script in the place.
* **Open Cloud Validation & Publishing (`verify_opencloud_place.py`, `diff_rbxlx.py`, `roblox_publish.sh`):** Audits place files against Open Cloud upload rules before publishing via the Roblox Open Cloud Places API.

---

## Prerequisites

* **Environment:** Termux (Android), Linux, macOS, or Windows (WSL / Git Bash)
* **Required Tools:** `python3` (3.9+ with `venv`), `node` (18+), `curl`, `git`, `zip`
* **Python Libraries:** `lz4`, `zstandard` (automatically installed into `.venv` by `build.sh`)
* **Optional:** `lune` (for Luau-based `.rbxm` merging) and `jq` (for CLI JSON inspection)

---

## Installation & Setup

1. **Extract the zip archive and enter the project folder:**
   ```bash
   unzip roblox_pipeline_toolkit.zip
   cd roblox_pipeline_toolkit
   ```

2. **Run the cross-platform build script:**
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
   **What `build.sh` does automatically:**
   * Detects your OS package manager (`pkg`, `brew`, `apt-get`, `dnf`, or `pacman`) and installs `python3`, `node`, `curl`, `git`, and `zip`.
   * Creates an isolated Python virtual environment (`.venv`) and installs `lz4` and `zstandard` from `requirements.txt`.
   * Creates working folders (`downloads/`, `converted/`, `fixed/`, `published/`) and includes `samples/sample_baseplate.rbxlx` for safe testing.
   * Marks all `.sh` and `.py` scripts executable and generates `publish_config.json` from `publish_config.example.json`.

3. **Activate the Python virtual environment before running tools:**
   ```bash
   source .venv/bin/activate
   ```
   *(On Windows Git Bash, run `source .venv/Scripts/activate`.)*

## Usage

Launch the interactive console from the toolkit folder:
```
./roblox_pipeline.sh
```
*(The script automatically activates `.venv` in the background if present.)*

---

## API Key & Configuration

### 1. Create a Roblox Open Cloud API Key
1. Open the **Roblox Creator Dashboard** -> **Open Cloud** -> **API Keys**.
2. Create a new key and add permissions for:
   * **Place Publishing** (`universe-places:write`) — required for `roblox_publish.sh`
   * **Asset Delivery / Creator Assets** (read access) — required for `download_place_rbxl.js` and `download_model_rbxm.js`
3. Select your target **Experience (Universe)** and set your IP restriction (`0.0.0.0/0` if using mobile data).

### 2. Configure `publish_config.json` & Environment Variables
Edit `publish_config.json` with your Universe ID, Place ID, and API Key:
```
json
{
  "universe_id": 1234567890,
  "place_id": 9876543210,
  "api_key": "YOUR_ROBLOX_OPEN_CLOUD_API_KEY",
  "rbxlx_file": "samples/sample_baseplate.rbxlx",
  "publish_endpoint": "https://roblox.com"
}
```
Export `ROBLOX_API_KEY` in your shell if using the Node.js downloader scripts directly:
```bash
export ROBLOX_API_KEY="YOUR_ROBLOX_OPEN_CLOUD_API_KEY"
```
* **Security:** `publish_config.json` is listed in `.gitignore` so your API key is never committed to Git.

---

## Usage

Activate your virtual environment and launch the interactive console:
```
source .venv/bin/activate
./roblox_pipeline.sh

## Usage

Launch the interactive console from the toolkit folder:
```bash
./roblox_pipeline.sh
```
*(The script automatically activates `.venv` in the background if present.)*


### End-to-End Workflow Example
1. **Download Assets (Optional):** Run `node download_place_rbxl.js <placeId>` or `node download_model_rbxm.js <assetId>` to save files into `downloads/`.
2. **Repair Base Place:** Run **Full XML Tag & Schema Repair (`repair_rbxlx.py`)** on your `.rbxlx` file (or test first on `samples/sample_baseplate.rbxlx`).
3. **Convert Binary Model:** Run **Convert Binary `.rbxm` to `.rbxmx` (`convert_rbxm_to_rbxmx.py`)** on your `.rbxm` model.
4. **Merge into Place:** Run **Install `.rbxmx` Model into Place (`install_martial_combat.py`)** to inject the converted `.rbxmx` into your `.rbxlx`.
5. **Auto-Repair & Verify (`Option P`):** Run the **Full Auto-Pipeline** on the merged `.rbxlx` file to unwrap/repair Lua scripts and verify Open Cloud compatibility.
6. **Publish (`roblox_publish.sh`):** Upload the verified `.rbxlx` to Roblox Open Cloud (`Published` pushes live immediately; `Saved` saves a version without overwriting the live game) and record the new version in `latest_version.txt`.

---

## How the Status Checklist Works (`file_checklists.json`)

The toolkit tracks per-file repair and audit progress in **`file_checklists.json`** (managed by `state_manager.py` and `status_checklist.py`) and displays a live checklist below the console menu.

* **Automatic Tracking:** Each time you run a repair, schema fix, Lua audit, or Open Cloud check on a file, its status flags are updated in `file_checklists.json`:
  ```
  json
  {
    "your_place.rbxlx": {
      "Vector3": true,
      "Color3": true,
      "CFrame": true,
      "LuaAudit": true,
      "OpenCloudVerified": true
    }
  }
  ```
* **Why It Helps:** When working across multiple `.rbxlx` variants or after merging new `.rbxmx` models, the checklist immediately shows which fixes have already been applied to your active file and which steps still need to run before publishing.

---

## Adding & Customizing Pipeline Steps

You can expand the console menu in two ways:

### Method 1: Register Directly from the Menu (`Option A`)
1. Launch `./roblox_pipeline.sh` and select **`A` (Add / Register a New Script to Menu)**.
2. Enter the script filename (e.g., `my_custom_fixer.py`), menu label, category, target file extensions (`.rbxlx`, `.rbxmx`, `.rbxm`), and whether it should run during **`Option P` (Full Auto-Pipeline)**.
3. The menu automatically saves the entry to `pipeline_steps.json`.

### Method 2: Edit `pipeline_steps.json` Manually
Add a new object to the `steps` array in `pipeline_steps.json`:
```
json
{
  "id": "custom_fix",
  "name": "My Custom Schema Fixer",
  "category": "1. XML & SCHEMA REPAIR",
  "script": "my_custom_fixer.py",
  "mode": "single",
  "extensions": [".rbxlx", ".rbxmx"],
  "backup": true,
  "auto_pipeline": true
}
```
* **`mode` options:**
  * `"single"` — Prompts for 1 input file (`script <file>`).
  * `"pair"` — Prompts for 2 files, such as a target file and a reference/diff file (`script <file1> <file2>`).
  * `"merge_to_output"` — Prompts for a base place, a model to inject, and an output filename.
* **`backup` (`true`/`false`):** Creates a timestamped `.bak` copy before modifying the target file.
* **`auto_pipeline` (`true`/`false`):** Includes the script when running **`Option P` (Full Auto-Pipeline)**.

---

## Script Reference

### Core Orchestration, State & Downloading
* **`roblox_pipeline.sh`**: Main interactive CLI menu. Reads `pipeline_steps.json`, displays numbered file pickers with byte sizes, creates timestamped backups, and invokes Python, Bash, Node.js, or Lune scripts.
* **`pipeline_steps.json`**: JSON registry controlling all menu items, categories, execution modes, and auto-pipeline steps.
* **`state_manager.py` & `status_checklist.py`**: Manages active workspace file selection and renders the per-file repair checklist stored in `file_checklists.json`.
* **`download_place_rbxl.js` & `download_model_rbxm.js`**: Node.js scripts that fetch `.rbxlx` places and `.rbxm` models via the Roblox Asset Delivery API into `downloads/`.
