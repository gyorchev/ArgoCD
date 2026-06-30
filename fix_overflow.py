#!/usr/bin/env python3
"""Run on the Pi - changes .alerts-panel overflow:hidden to visible so the
toggle tab (positioned outside the panel's left edge) is no longer clipped."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

# Line 439 (1-indexed) = index 438
target = lines[438]
if "overflow: hidden;" not in target:
    print(f"ERROR: line 439 doesn't contain expected text - actual: {target!r}")
else:
    lines[438] = target.replace("overflow: hidden;", "overflow: visible;")
    with open(path, "w") as f:
        f.writelines(lines)
    print("SUCCESS: .alerts-panel overflow changed to visible")
