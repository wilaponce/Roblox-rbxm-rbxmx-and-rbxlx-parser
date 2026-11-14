#!/usr/bin/env bash

set -euo pipefail

REGISTRY="pipeline_steps.json"
mkdir -p downloads copy converted fixed published

select_file() {
    local prompt_title="$1"
    shift
    local exts=("$@")
    local files=()

    for ext in "${exts[@]}"; do
        while IFS= read -r -d '' f; do
            files+=("${f#./}")
        done < <(find . ./downloads ./converted ./copy ./repaired ./fixed ./published -maxdepth 1 -type f -name "*.${ext}" -print0 2>/dev/null)
    done

    IFS=$'\n' files=($(sort -u <<<"${files[*]:-}"))
    unset IFS

    if [ ${#files[@]} -eq 0 ]; then
        echo -e "\n[ERROR] No matching files found (${exts[*]})." >&2
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
        i=$((i + 1))
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

# Copy selected file into fixed/ without modifying original
stage_in_fixed() {
    local src="$1"
    local base
    base=$(basename "$src")
    local dst="fixed/$base"
    if [ "$src" != "$dst" ]; then
        cp "$src" "$dst"
        echo "[STAGED] Copied original -> $dst (original untouched)" >&2
    fi
    echo "$dst"
}

invoke_script() {
    local script="$1"
    shift
    case "$script" in
        *.py)   python3 "$script" "$@" ;;
        *.sh)   bash "$script" "$@" ;;
        *.luau) lune run "$script" "$@" ;;
        *.js)   node "$script" "$@" ;;
        *)      "./$script" "$@" ;;
    esac
}

run_step_json() {
    local step_json="$1"
    local preset_target="${2:-}"

    local id label script mode log_file default_out prompt_txt
    id=$(echo "$step_json" | jq -r '.id // empty')
    label=$(echo "$step_json" | jq -r '.label')
    script=$(echo "$step_json" | jq -r '.script // empty')
    mode=$(echo "$step_json" | jq -r '.mode')
    log_file=$(echo "$step_json" | jq -r '.log_file // empty')
    default_out=$(echo "$step_json" | jq -r '.default_out // "merged_place.rbxlx"')
    prompt_txt=$(echo "$step_json" | jq -r '.prompt // "Enter Asset ID: "')

    if [ "$mode" = "submenu" ]; then
        local skey
        skey=$(echo "$step_json" | jq -r '.submenu_key')
        open_submenu "$skey" "$label"
        return
    fi

    if [ "$mode" = "prompt_asset_id" ]; then
        read -rp "$prompt_txt" asset_id </dev/tty
        if [ -n "$asset_id" ]; then
            invoke_script "$script" "$asset_id"
        fi
        return
    fi

    mapfile -t exts < <(echo "$step_json" | jq -r '.exts[]? // empty')
    mapfile -t exts2 < <(echo "$step_json" | jq -r '.exts2[]? // empty')

    # Special handling: Convert .rbxm -> converted/<name>.rbxmx
    if [ "$id" = "convert_rbxm" ]; then
        select_file "Select binary .rbxm to convert:" "${exts[@]}" || return
        local src="$SELECTED_FILE"
        local base
        base=$(basename "$src" .rbxm)
        local dst="converted/${base}.rbxmx"
        set +e
        out=$(invoke_script "$script" "$src" "$dst" 2>&1)
        rc=$?
        set -e
        echo "$out"
        if [ $rc -eq 0 ] && [ -f "$dst" ]; then
            python3 state_manager.py mark_converted "$src" "$dst"
            python3 state_manager.py update_xml_status "$dst" "NONE"
        else
            python3 state_manager.py update_xml_status "$src" "$out"
        fi
        return
    fi

    # Special handling: Publish -> copy to published/ and upload
    if [ "$script" = "BUILTIN_PUBLISH" ]; then
        select_file "Select place file to publish:" "${exts[@]}" || return
        local src="$SELECTED_FILE"
        local base
        base=$(basename "$src")
        local pub_copy="published/$base"
        [ "$src" != "$pub_copy" ] && cp "$src" "$pub_copy"
        if [ -f "publish_config.json" ]; then
            tmp_cfg=$(mktemp)
            jq --arg f "$pub_copy" '.rbxlx_file = $f' publish_config.json > "$tmp_cfg" && mv "$tmp_cfg" publish_config.json
        fi
        set +e
        out=$(./roblox_publish.sh publish 2>&1)
        rc=$?
        set -e
        echo "$out"
        if [ $rc -eq 0 ]; then
            python3 state_manager.py mark_published "$src"
        else
            python3 state_manager.py update_xml_status "$src" "$out"
        fi
        return
    fi

    if [ "$mode" = "single" ]; then
        local target="$preset_target"
        if [ -z "$target" ]; then
            select_file "Select file for [$label] ($script):" "${exts[@]}" || return
            target="$SELECTED_FILE"
        fi
        # Read-only checks run directly; repair scripts stage into fixed/ first
        if [[ "$id" == check_* ]] || [[ "$id" == verify_* ]] || [[ "$id" == audit_merge* ]] || [[ "$id" == diagnose_* ]]; then
            set +e
            out=$(invoke_script "$script" "$target" 2>&1)
            rc=$?
            set -e
            echo "$out"
            if [[ "$target" == *.rbxlx ]] || [[ "$target" == *.rbxmx ]]; then
                if [ $rc -eq 0 ] && ! echo "$out" | grep -qE '\[FAIL\]|\[NOT READY\]|\[ISSUES FOUND\]'; then
                    python3 state_manager.py update_xml_status "$target" "NONE"
                else
                    python3 state_manager.py update_xml_status "$target" "$out"
                fi
            fi
        else
            local staged
            staged=$(stage_in_fixed "$target")
            set +e
            if [ -n "$log_file" ]; then
                out=$(invoke_script "$script" "$staged" 2>&1 | tee "$log_file")
                rc=${PIPESTATUS}
            else
                out=$(invoke_script "$script" "$staged" 2>&1)
                rc=$?
            fi
            set -e
            echo "$out"
            if [ $rc -eq 0 ]; then
                python3 state_manager.py update_xml_status "$staged" "NONE"
            else
                python3 state_manager.py update_xml_status "$staged" "$out"
            fi
        fi

    elif [ "$mode" = "pair" ]; then
        select_file "Select FIRST / REFERENCE file for [$label]:" "${exts[@]}" || return
        local f1="$SELECTED_FILE"
        select_file "Select SECOND / TARGET file for [$label]:" "${exts2[@]}" || return
        local f2="$SELECTED_FILE"
        if [[ "$id" == diff_* ]]; then
            invoke_script "$script" "$f1" "$f2"
        else
            local staged
            staged=$(stage_in_fixed "$f2")
            invoke_script "$script" "$f1" "$staged"
            python3 state_manager.py update_xml_status "$staged" "NONE"
        fi

    elif [ "$mode" = "merge_to_output" ]; then
        select_file "Select BASE Place file for [$label]:" "${exts[@]}" || return
        local f1="$SELECTED_FILE"
        select_file "Select MODEL file to install:" "${exts2[@]}" || return
        local f2="$SELECTED_FILE"
        read -rp "Output filename inside fixed/ [default: $default_out]: " out_name </dev/tty
        out_name=$(basename "${out_name:-$default_out}")
        local out_f="fixed/$out_name"
        set +e
        out=$(invoke_script "$script" "$f1" "$f2" "$out_f" 2>&1)
        rc=$?
        set -e
        echo "$out"
        if [ $rc -eq 0 ] && [ -f "$out_f" ]; then
            python3 state_manager.py update_xml_status "$out_f" "NONE"
        else
            python3 state_manager.py update_xml_status "$f1" "$out"
        fi
    fi
}

open_submenu() {
    local skey="$1"
    local title="$2"
    while true; do
        local count
        count=$(jq ".submenus[\"$skey\"] | length" "$REGISTRY")
        echo -e "\n------------------------------------------------------------"
        echo "  $title"
        echo "------------------------------------------------------------"
        for ((j=0; j<count; j++)); do
            local lbl scr
            lbl=$(jq -r ".submenus[\"$skey\"][$j].label" "$REGISTRY")
            scr=$(jq -r ".submenus[\"$skey\"][$j].script" "$REGISTRY")
            printf "  %2d) %s (%s)\n" "$((j + 1))" "$lbl" "$scr"
        done
        echo "   0) <- Back to Main Menu"
        echo "------------------------------------------------------------"
        read -rp "Select option [0-$count]: " sub_choice </dev/tty
        if [ "$sub_choice" = "0" ]; then
            return
        elif [[ "$sub_choice" =~ ^[0-9]+$ ]] && [ "$sub_choice" -ge 1 ] && [ "$sub_choice" -le "$count" ]; then
            local sjson
            sjson=$(jq -c ".submenus[\"$skey\"][$((sub_choice - 1))]" "$REGISTRY")
            run_step_json "$sjson"
        else
            echo "Invalid selection."
        fi
    done
}

add_new_step() {
    echo -e "\n=== Register New Script in Menu ==="
    read -rp "Script filename (e.g., fix_sounds.py): " new_script </dev/tty
    [ -z "$new_script" ] && return
    read -rp "Menu label: " new_label </dev/tty
    echo "Where should it appear?"
    echo "  1) Main Menu"
    echo "  2) XML Structure & Tag Repairs Submenu"
    echo "  3) Additional Repairs & Lua Audits Submenu"
    read -rp "Choose location [1-3]: " loc </dev/tty
    read -rp "Allowed extensions space-separated [default: rbxlx rbxmx]: " ext_str </dev/tty
    ext_str="${ext_str:-rbxlx rbxmx}"
    read -rp "Include in Full Auto-Pipeline (Option P)? (y/n) [n]: " pipe_ans </dev/tty
    [[ "${pipe_ans:-n}" =~ ^[Yy]$ ]] && new_pipe="true" || new_pipe="false"

    local exts_json new_id
    exts_json=$(printf '%s\n' $ext_str | jq -R . | jq -s .)
    new_id=$(echo "$new_script" | tr -cd 'a-zA-Z0-9_')

    local entry
    entry=$(jq -n \
        --arg id "$new_id" \
        --arg lbl "$new_label" \
        --arg scr "$new_script" \
        --argjson exts "$exts_json" \
        --argjson pip "$new_pipe" \
        '{id:$id, label:$lbl, script:$scr, mode:"single", exts:$exts, backup:true, in_full_pipeline:$pip}')

    tmp_reg=$(mktemp)
    case "$loc" in
        2) jq --argjson e "$entry" '.submenus.xml_repairs += [$e]' "$REGISTRY" > "$tmp_reg" ;;
        3) jq --argjson e "$entry" '.submenus.additional_repairs += [$e]' "$REGISTRY" > "$tmp_reg" ;;
        *) jq --argjson e "$entry" '.main_steps += [$e]' "$REGISTRY" > "$tmp_reg" ;;
    esac
    mv "$tmp_reg" "$REGISTRY"
    echo "[ADDED] '$new_label' registered in $REGISTRY!"
}

while true; do
    echo
    echo "============================================================"
    echo "   MODULAR ROBLOX PIPELINE"
    echo "============================================================"

    total_main=$(jq '.main_steps | length' "$REGISTRY")
    for ((i=0; i<total_main; i++)); do
        lbl=$(jq -r ".main_steps[$i].label" "$REGISTRY")
        scr=$(jq -r ".main_steps[$i].script // empty" "$REGISTRY")
        disp=""
        if [ -n "$scr" ] && [[ "$scr" != BUILTIN_* ]]; then
            disp=" ($scr)"
        fi
        printf "  %2d) %s%s\n" "$((i + 1))" "$lbl" "$disp"
    done

    echo ""
    echo "  --- PIPELINE, CHECKLIST & EXPANSION ---"
    echo "   V) View Checklist of Any File"
    echo "   P) Run Full Auto-Pipeline (all flagged steps in order)"
    echo "   A) Add / Register a New Script to Menu"
    echo "   0) Exit"
    echo "============================================================"
    echo "  --- ACTIVE FILE CHECKLIST ---"
    python3 state_manager.py show
    echo "============================================================"
    read -rp "Choose an option: " opt </dev/tty

    case "${opt^^}" in
        0)
            echo "Exiting."
            exit 0
            ;;
        V)
            if select_file "Select any file to view & activate its checklist:" rbxlx rbxmx rbxl rbxm; then
                python3 state_manager.py set_active "$SELECTED_FILE"
            fi
            ;;
        A)
            add_new_step
            ;;
        P)
            if select_file "Select .rbxlx file to run FULL AUTO-PIPELINE on:" rbxlx; then
                TARGET=$(stage_in_fixed "$SELECTED_FILE")
                while IFS= read -r sjson; do
                    lbl=$(echo "$sjson" | jq -r '.label')
                    echo -e "\n>>> Running Auto-Pipeline Step: $lbl"
                    run_step_json "$sjson" "$TARGET"
                done < <(jq -c '[.submenus.xml_repairs[], .submenus.additional_repairs[], .main_steps[]] | .[] | select(.in_full_pipeline == true)' "$REGISTRY")
                echo -e "\n[PIPELINE COMPLETE] Finished all auto-pipeline steps on $TARGET."
            fi
            ;;
        *)
            if [[ "$opt" =~ ^[0-9]+$ ]] && [ "$opt" -ge 1 ] && [ "$opt" -le "$total_main" ]; then
                sjson=$(jq -c ".main_steps[$((opt - 1))]" "$REGISTRY")
                run_step_json "$sjson"
            else
                echo "Invalid selection."
            fi
            ;;
    esac
done
