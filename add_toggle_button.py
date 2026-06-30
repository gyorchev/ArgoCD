#!/usr/bin/env python3
"""Run on the Pi - inserts the toggle button markup after .alerts-header closes (line 752)."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

if any('<button id="alerts-toggle-btn"' in l for l in lines):
    print("Toggle button already present - nothing to do")
else:
    line_752 = lines[751]  # 0-indexed
    if line_752.strip() != '</div>':
        print(f"ERROR: line 752 is not the expected closing div - actual: {line_752!r}")
    else:
        toggle_html = '        <button id="alerts-toggle-btn" class="alerts-toggle-btn" onclick="toggleAlertsPanel()">&gt;</button>\n'
        new_lines = lines[:752] + [toggle_html] + lines[752:]
        with open(path, "w") as f:
            f.writelines(new_lines)
        print("SUCCESS: toggle button markup inserted after line 752")
