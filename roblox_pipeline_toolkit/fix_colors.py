import re
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

def convert_color(m):
    val = int(m.group(1))
    r = ((val >> 16) & 0xFF) / 255.0
    g = ((val >> 8) & 0xFF) / 255.0
    b = (val & 0xFF) / 255.0
    return (
        f'<Color3 name="Color">\n'
        f'  <R>{r:.6f}</R>\n'
        f'  <G>{g:.6f}</G>\n'
        f'  <B>{b:.6f}</B>\n'
        f'</Color3>'
    )

fixed, count = re.subn(r'<Color3uint8\b[^>]*>(\d+)</Color3uint8>', convert_color, text)

with open(path, "w", encoding="utf-8") as f:
    f.write(fixed)

print(f"Converted {count} Color3uint8 tags to Color3")
