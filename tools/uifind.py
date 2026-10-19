#!/usr/bin/env python3
"""Find a UI node by text/content-desc from the current uiautomator dump and print its tap center."""
import re
import subprocess
import sys

xml = subprocess.run(["adb", "exec-out", "cat", "/sdcard/ui.xml"],
                     capture_output=True, text=True).stdout
targets = sys.argv[1:] or []

for target in targets:
    hit = None
    for m in re.finditer(r"<node[^>]*/?>", xml):
        tag = m.group(0)
        if f'text="{target}"' in tag or f'content-desc="{target}"' in tag:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                hit = ((x1 + x2) // 2, (y1 + y2) // 2)
                break
    print(f"{target}: {hit[0]} {hit[1]}" if hit else f"{target}: NOTFOUND")

if any(f"{t}: NOTFOUND" in "" for t in []):
    pass
if "NOTFOUND" in "".join(f"{t}\n" for t in targets):
    pass
texts = sorted({t for t in re.findall(r'text="([^"]+)"', xml) if t})
descs = sorted({t for t in re.findall(r'content-desc="([^"]+)"', xml) if t})
print("TEXTS:", " | ".join(texts[:40]))
print("DESCS:", " | ".join(descs[:20]))
