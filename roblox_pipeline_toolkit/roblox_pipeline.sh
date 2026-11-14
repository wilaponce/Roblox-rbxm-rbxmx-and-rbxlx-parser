#!/data/data/com.termux/files/usr/bin/bash

set -euo pipefail

REGISTRY="pipeline_steps.json"

if [ ! -f "$REGISTRY" ]; then
    echo "[ERROR] Missing $REGISTRY. Please create it first."
    exit 1
fi

select_file() {
    local prompt_title="$1"
    shift
    local exts=("$@")
    local files=()

    for ext in "${exts[@]}"; do
        while IFS= read -r -d '' f; do
            files+=("${f#./}")
        done < <(find . -maxdepth 1 -type f -name "*.${ext}" -print0 2>/dev/null)
    done

    IFS=$'\n' files=($(sort -u <<<"${files[*]:-}"))
    unset IFS

    if [ ${#files[@]} -eq 0 ]; then
        echo -e "\n[ERROR] No matching files found (${exts[*]}) in current directory." >&2
        return 1
    fi

    echo -e "\n------------------------------------" >&2
    echo "$prompt_title" >&2
    echo "------------------------------------" >&2
    local i=1
    for f in "${files[@]}"; do
        local sz
        sz=$(wc -c < "$f" | tr -d ' ')
        printf "  %2d) %s (%s bytes)\n" "$i" "$f" "$sz" >&2
        ((i++))
    done
    echo "   0) Cancel" >&2
    echo "" >&2

    while true; do
        read -rp "Select file number: " choice </dev/tty
        if [[ "$choice" == "0" ]]; then
            return 1
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#files[@]} ]; then
            SELECTED_FILE="${files[$((choice - 1))]}"
            return 0
        else
            echo "Invalid selection. Enter 0-${#files[@]}." >&2
        fi
    done
}

backup_file() {
    local target="$1"
    local ts
    ts=$(date +%Y%m%d_%H%M%S)
    local bak="${target}.${ts}.bak"
    cp "$target" "$bak"
    echo "[BACKUP] Created: $bak"
}

invoke_script() {
    local script="$1"
    shift
    if [ ! -f "$script" ]; then
        echo "[ERROR] Script not found in workspace: $script"
        return 1
    fi
    case "$script" in
        *.py)   python3 "$script" "$@" ;;
        *.sh)   bash "$script" "$@" ;;
        *.luau) lune run "$script" "$@" ;;
        *)      "./$script" "$@" ;;
    esac
}

execute_step_index() {
    local idx="$1"
    local preset_target="${2:-}"

    local label script mode backup log_file default_out
    label=$(jq -r ".steps[$idx].label" "$REGISTRY")
    script=$(jq -r ".steps[$idx].script" "$REGISTRY")
    mode=$(jq -r ".steps[$idx].mode" "$REGISTRY")
    backup=$(jq -r ".steps[$idx].backup" "$REGISTRY")
    log_file=$(jq -r ".steps[$idx].log_file // empty" "$REGISTRY")
    default_out=$(jq -r ".steps[$idx].default_out // \"merged_output.rbxlx\"" "$REGISTRY")

    mapfile -t exts < <(jq -r ".steps[$idx].exts[]" "$REGISTRY")
    mapfile -t exts2 < <(jq -r ".steps[$idx].exts2[]? // empty" "$REGISTRY")

    if [ "$script" = "BUILTIN_BACKUP" ]; then
        if select_file "Select file to back up:" "${exts[@]}"; then
            backup_file "$SELECTED_FILE"
        fi
        return
    fi

    if [ "$script" = "BUILTIN_PUBLISH" ]; then
        if select_file "Select place file to publish:" "${exts[@]}"; then
            if [ -f "publish_config.json" ]; then
                tmp_cfg=$(mktemp)
                jq --arg f "$SELECTED_FILE" '.rbxlx_file = $f' publish_config.json > "$tmp_cfg" && mv "$tmp_cfg" publish_config.json
                echo "[CONFIG] Updated publish_config.json -> rbxlx_file = \"$SELECTED_FILE\""
            fi
            ./roblox_publish.sh publish
        fi
        return
    fi

    if [ "$mode" = "single" ]; then
        local target="$preset_target"
        if [ -z "$target" ]; then
            select_file "Select file for [$label] ($script):" "${exts[@]}" || return
            target="$SELECTED_FILE"
        fi
        [ "$backup" = "true" ] && [ -z "$preset_target" ] && backup_file "$target"
        if [ -n "$log_file" ]; then
            invoke_script "$script" "$target" | tee "$log_file"
        else
            invoke_script "$script" "$target"
        fi

    elif [ "$mode" = "pair" ]; then
        select_file "Select FIRST / REFERENCE file for [$label]:" "${exts[@]}" || return
        local f1="$SELECTED_FILE"
        select_file "Select SECOND / TARGET file for [$label]:" "${exts2[@]}" || return
        local f2="$SELECTED_FILE"
        [ "$backup" = "true" ] && backup_file "$f2"
        invoke_script "$script" "$f1" "$f2"

    elif [ "$mode" = "merge_to_output" ]; then
        select_file "Select BASE file for [$label]:" "${exts[@]}" || return
        local f1="$SELECTED_FILE"
        select_file "Select MODEL / SOURCE file to merge:" "${exts2[@]}" || return
        local f2="$SELECTED_FILE"
        read -rp "Output filename [default: $default_out]: " out_f
        out_f="${out_f:-$default_out}"
        invoke_script "$script" "$f1" "$f2" "$out_f"
    fi
}

add_new_step() {
    echo -e "\n=== Register New Script in Pipeline ==="
    read -rp "Script filename (e.g., fix_sounds.py or custom.luau): " new_script
    if [ -z "$new_script" ]; then return; fi
    read -rp "Menu label (e.g., Fix Broken Sound IDs): " new_label
    echo "Categories:"
    echo "  1) 1. BACKUP & XML STRUCTURE REPAIR"
    echo "  2) 2. MODEL MERGE & SCHEMA SYNC"
    echo "  3) 3. LUA SCRIPT REPAIR & SYNTAX AUDIT"
    echo "  4) 4. VERIFICATION, DIFF & PUBLISH"
    read -rp "Choose category [1-4]: " cat_num
    case "$cat_num" in
        1) new_cat="1. BACKUP & XML STRUCTURE REPAIR" ;;
        2) new_cat="2. MODEL MERGE & SCHEMA SYNC" ;;
        3) new_cat="3. LUA SCRIPT REPAIR & SYNTAX AUDIT" ;;
        *) new_cat="4. VERIFICATION, DIFF & PUBLISH" ;;
    esac
    echo "Execution mode:"
    echo "  1) single (takes 1 file)"
    echo "  2) pair (takes 2 files: reference + target)"
    echo "  3) merge_to_output (takes 2 files + output filename)"
    read -rp "Choose mode [1-3]: " mode_num
    case "$mode_num" in
        2) new_mode="pair" ;;
        3) new_mode="merge_to_output" ;;
        *) new_mode="single" ;;
    esac
    read -rp "Allowed extensions space-separated [default: rbxlx rbxmx]: " ext_str
    ext_str="${ext_str:-rbxlx rbxmx}"
    read -rp "Create automatic backup before running? (y/n) [y]: " bak_ans
    [[ "${bak_ans:-y}" =~ ^[Yy]$ ]] && new_bak="true" || new_bak="false"
    read -rp "Include in Full Repair Pipeline (Option P)? (y/n) [n]: " pipe_ans
    [[ "${pipe_ans:-n}" =~ ^[Yy]$ ]] && new_pipe="true" || new_pipe="false"

    local exts_json
    exts_json=$(printf '%s\n' $ext_str | jq -R . | jq -s .)
    local new_id
    new_id=$(echo "$new_script" | tr -cd 'a-zA-Z0-9_')

    tmp_reg=$(mktemp)
    jq --arg id "$new_id" \
       --arg cat "$new_cat" \
       --arg lbl "$new_label" \
       --arg scr "$new_script" \
       --arg mod "$new_mode" \
       --argjson exts "$exts_json" \
       --argjson bak "$new_bak" \
       --argjson pip "$new_pipe" \
       '.steps += [{
         "id": $id,
         "category": $cat,
         "label": $lbl,
         "script": $scr,
         "mode": $mod,
         "exts": $exts,
         "exts2": $exts,
         "backup": $bak,
         "in_full_pipeline": $pip
       }] | sort_by(.category)' "$REGISTRY" > "$tmp_reg" && mv "$tmp_reg" "$REGISTRY"

    echo "[ADDED] '$new_label' ($new_script) saved to $REGISTRY!"
}

while true; do
    echo
    echo "============================================================"
    echo "   MODULAR ROBLOX PIPELINE (Powered by $REGISTRY)"
    echo "============================================================"

    total_steps=$(jq '.steps | length' "$REGISTRY")
    last_cat=""

    for ((i=0; i<total_steps; i++)); do
        cat=$(jq -r ".steps[$i].category" "$REGISTRY")
        lbl=$(jq -r ".steps[$i].label" "$REGISTRY")
        scr=$(jq -r ".steps[$i].script" "$REGISTRY")
        if [ "$cat" != "$last_cat" ]; then
            echo "  --- $cat ---"
            last_cat="$cat"
        fi
        display_scr=""
        [[ "$scr" != BUILTIN_* ]] && display_scr=" ($scr)"
        printf "  %2d) %s%s\n" "$((i + 1))" "$lbl" "$display_scr"
    done

    echo ""
    echo "  --- PIPELINE & EXPANSION ---"
    echo "   P) Run Full Auto-Pipeline (all flagged steps in order)"
    echo "   A) Add / Register a New Script to Menu"
    echo "   0) Exit"
    echo "============================================================"
    read -rp "Choose an option: " opt

    case "${opt^^}" in
        0)
            echo "Exiting."
            exit 0
            ;;
        A)
            add_new_step
            ;;
        P)
            if select_file "Select .rbxlx file to run FULL AUTO-PIPELINE on:" rbxlx; then
                TARGET="$SELECTED_FILE"
                backup_file "$TARGET"
                for ((i=0; i<total_steps; i++)); do
                    in_pipe=$(jq -r ".steps[$i].in_full_pipeline" "$REGISTRY")
                    if [ "$in_pipe" = "true" ]; then
                        lbl=$(jq -r ".steps[$i].label" "$REGISTRY")
                        echo -e "\n>>> Running Pipeline Step: $lbl"
                        execute_step_index "$i" "$TARGET"
                    fi
                done
                echo -e "\n[PIPELINE COMPLETE] Finished all enabled steps on $TARGET."
            fi
            ;;
        *)
            if [[ "$opt" =~ ^[0-9]+$ ]] && [ "$opt" -ge 1 ] && [ "$opt" -le "$total_steps" ]; then
                execute_step_index "$((opt - 1))"
            else
                echo "Invalid selection."
            fi
            ;;
    esac
done
