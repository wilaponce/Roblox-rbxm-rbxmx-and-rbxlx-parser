const fs = require("fs");
const { execFileSync } = require("child_process");

const CONFIG_FILE = "publish_config.json";

if (!fs.existsSync(CONFIG_FILE)) {
    console.error(`ERROR: Missing config file: ${CONFIG_FILE}`);
    process.exit(1);
}

let config;
try {
    config = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf8"));
} catch (err) {
    console.error(`ERROR: Failed to parse ${CONFIG_FILE}: ${err.message}`);
    process.exit(1);
}

const API_KEY = (config.api_key || process.env.ROBLOX_API_KEY || "").trim();
const ASSET_ID = String(process.argv.slice(2).pop() || "").trim();

if (!API_KEY || API_KEY === "YOUR_ROBLOX_OPEN_CLOUD_API_KEY") {
    console.error("ERROR: Valid api_key not found in publish_config.json");
    process.exit(1);
}

if (!ASSET_ID || ASSET_ID === "0") {
    console.error("Usage: node download_model_rbxm.js <modelAssetId>");
    process.exit(1);
}

(async () => {
    console.log(`=== Downloading Model ID: ${ASSET_ID} ===`);

    const response = await fetch(
        `https://apis.roblox.com/asset-delivery-api/v1/assetId/${ASSET_ID}`,
        {
            headers: {
                "x-api-key": API_KEY
            }
        }
    );

    if (!response.ok) {
        const errText = await response.text();
        console.error(`HTTP ${response.status}: ${errText}`);
        process.exit(1);
    }

    const json = await response.json();

    if (!json.location) {
        console.error(JSON.stringify(json, null, 2));
        process.exit(1);
    }

    const asset = await fetch(json.location);
    const buffer = Buffer.from(await asset.arrayBuffer());

    // Detect binary (.rbxm) vs XML (.rbxmx) from file header
    const isBinary = buffer.subarray(0, 8).toString("latin1") === "<roblox!";
    const ext = isBinary ? "rbxm" : "rbxmx";

    fs.mkdirSync("downloads", { recursive: true });
    const outfile = `downloads/${ASSET_ID}.${ext}`;
    fs.writeFileSync(outfile, buffer);

    console.log("[DOWNLOADED]");
    console.log(`  File   : ${outfile}`);
    console.log(`  Format : ${isBinary ? "Binary (.rbxm)" : "XML (.rbxmx)"}`);
    console.log(`  Bytes  : ${buffer.length}`);

    if (fs.existsSync("state_manager.py")) {
        if (isBinary) {
            execFileSync("python3", ["state_manager.py", "register", outfile], { stdio: "inherit" });
        } else {
            execFileSync("python3", ["state_manager.py", "update_xml_status", outfile, "NONE"], { stdio: "inherit" });
        }
    }
})();
