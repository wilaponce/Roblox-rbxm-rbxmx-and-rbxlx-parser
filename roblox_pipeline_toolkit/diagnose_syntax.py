#!/usr/bin/env python3
import re
import sys

log_path = sys.argv[-1] if len(sys.argv) > 1 else "lua_audit_report.txt"

with open(log_path, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

blocks = re.split(r"\n\s*\[ERROR\]\s+", content)
if len(blocks) <= 1:
    print("No [ERROR] blocks found in", log_path)
    sys.exit(0)

print(f"=== Exact Syntax Root-Cause Diagnosis ({len(blocks) - 1} scripts) ===\n")

for blk in blocks[1:]:
    lines = blk.strip().splitlines()
    header = lines[0]
    script_name, _, err_msg = header.partition(":")
    code_lines = [ln for ln in lines[1:] if "|" in ln and "(end of file)" not in ln]

    target_line = ""
    for cl in code_lines:
        if ">>>" in cl:
            target_line = cl.split("|", 1)[1]
            break

    diagnosis = []

    if "Unclosed" in err_msg and "string" in err_msg:
        if target_line.count('"') % 2 != 0 or target_line.count("'") % 2 != 0:
            diagnosis.append("Odd number of quotes on this line—likely an unescaped quote inside a string (e.g., \"foo \"bar\"\" instead of \"foo \\\"bar\\\"\") or a stripped backslash from Rust unescaping.")
        if target_line.rstrip().endswith("\\"):
            diagnosis.append("Trailing backslash at end of line escaped the closing quote or newline.")

    elif "Unexpected ')'" in err_msg or "Unexpected ']'" in err_msg or "Unexpected '}'" in err_msg:
        if "--[[" in "\n".join(code_lines) and "]]" not in "\n".join(code_lines):
            diagnosis.append("A multi-line block comment (--[[ ... ]]) opened earlier without a closing ]], causing the lexer to misread brackets.")
        elif target_line.count("(") < target_line.count(")"):
            diagnosis.append("Extra closing ')' on this line—check for a missing opening '(' or an unclosed string on the line directly above.")
        else:
            diagnosis.append("Mismatched delimiter caused by an unclosed block comment (--[[) or unescaped bracket earlier in the script.")

    elif "Unclosed '{'" in err_msg:
        diagnosis.append("A table constructor '{' opened near the top of the file was never closed with '}' before EOF, or a closing '}' was swallowed inside a broken string/comment.")

    if not diagnosis:
        diagnosis.append("Check the highlighted >>> line and the 2 lines immediately above it for missing commas, quotes, or block comment closures.")

    print(f"Script : {script_name.strip()}")
    print(f"Error  : {err_msg.strip()}")
    if target_line:
        print(f"Code   : {target_line.strip()}")
    for d in diagnosis:
        print(f"Cause  : {d}")
    print("-" * 60)
