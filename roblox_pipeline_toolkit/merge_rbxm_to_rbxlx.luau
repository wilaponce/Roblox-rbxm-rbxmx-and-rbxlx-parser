local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")

local args = process.args
if #args < 3 then
    print("Usage: lune run merge_rbxm_to_rbxlx.luau <base_place.rbxlx> <model.rbxm> <output_file.rbxlx_or_rbxl>")
    process.exit(1)
end

local placePath = args[1]
local modelPath = args[2]
local outPath = args[3]

print("=== Lune Binary Model (.rbxm) -> Place Merger ===")
print("  Base Place : " .. placePath)
print("  RBXM Model : " .. modelPath)
print("  Output     : " .. outPath .. "\n")

local game = roblox.deserializePlace(fs.readFile(placePath))
local rootInstances = roblox.deserializeModel(fs.readFile(modelPath))

local repStorage = game:GetService("ReplicatedStorage")
local serverScriptService = game:GetService("ServerScriptService")
local serverStorage = game:GetService("ServerStorage")
local starterGui = game:GetService("StarterGui")
local starterPack = game:GetService("StarterPack")
local lighting = game:GetService("Lighting")
local starterPlayer = game:GetService("StarterPlayer")

local starterPlayerScripts = starterPlayer:FindFirstChildOfClass("StarterPlayerScripts")
if not starterPlayerScripts then
    starterPlayerScripts = roblox.Instance.new("StarterPlayerScripts")
    starterPlayerScripts.Parent = starterPlayer
end

local starterCharacterScripts = starterPlayer:FindFirstChildOfClass("StarterCharacterScripts")
if not starterCharacterScripts then
    starterCharacterScripts = roblox.Instance.new("StarterCharacterScripts")
    starterCharacterScripts.Parent = starterPlayer
end

-- Exact service routing for Martial Combat & standard service containers
local namedDestinations = {
    MartialCombatSystem = repStorage,
    MartialCombatServer = serverScriptService,
    OptionalDamageNumbers = serverScriptService,
    MartialCombatClient = starterPlayerScripts,
}

local serviceContainers = {
    ReplicatedStorage = repStorage,
    ServerScriptService = serverScriptService,
    ServerStorage = serverStorage,
    StarterGui = starterGui,
    StarterPack = starterPack,
    Lighting = lighting,
    StarterPlayerScripts = starterPlayerScripts,
    StarterCharacterScripts = starterCharacterScripts,
    Workspace = game:GetService("Workspace"),
}

local installedCount = 0

local function installNode(inst)
    -- 1. If the .rbxm contains a service folder (e.g., Folder named "ReplicatedStorage"), unpack its children into that service
    if serviceContainers[inst.Name] and (inst:IsA("Folder") or inst:IsA("Model") or inst:IsA("Configuration")) then
        local targetService = serviceContainers[inst.Name]
        for _, child in ipairs(inst:GetChildren()) do
            installNode(child)
        end
        return
    end

    -- 2. If the instance matches a known system component, route it directly
    local dest = namedDestinations[inst.Name]
    if dest then
        local existing = dest:FindFirstChild(inst.Name)
        if existing then
            existing:Destroy()
        end
        inst.Parent = dest
        installedCount += 1
        print(string.format("  [INSTALLED] %s (%s) -> %s", inst.Name, inst.ClassName, dest.Name))
        return
    end

    -- 3. If it is a wrapper Model/Folder holding named components, recurse inside it
    local hasNamedChild = false
    for _, child in ipairs(inst:GetChildren()) do
        if namedDestinations[child.Name] or serviceContainers[child.Name] then
            hasNamedChild = true
            break
        end
    end

    if hasNamedChild then
        for _, child in ipairs(inst:GetChildren()) do
            installNode(child)
        end
    else
        -- Default fallback: place standalone models/parts into Workspace
        local ws = game:GetService("Workspace")
        local existing = ws:FindFirstChild(inst.Name)
        if existing then
            existing:Destroy()
        end
        inst.Parent = ws
        installedCount += 1
        print(string.format("  [INSTALLED] %s (%s) -> Workspace", inst.Name, inst.ClassName))
    end
end

for _, topInst in ipairs(rootInstances) do
    installNode(topInst)
end

-- Serialize as XML (.rbxlx) or Binary (.rbxl) based on output filename extension
local isXml = string.lower(string.sub(outPath, -6)) == ".rbxlx"
local serialized = roblox.serializePlace(game, isXml)
fs.writeFile(outPath, serialized)

print(string.format("\n[DONE] Installed %d component(s) and wrote %s (%s format)", installedCount, outPath, isXml and "XML .rbxlx" or "Binary .rbxl"))
