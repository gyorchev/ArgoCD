#!/usr/bin/env python3
"""Run on the Pi - moves the toggle button out of .alerts-content, making it
a direct sibling of the canvas/scanlines/content divs inside .alerts-panel,
so it floats above the scrollable content correctly instead of competing
with it inside the same stacking context."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

# Find the exact lines: toggle button line, and the alerts-panel opening line
button_idx = None
panel_idx = None
for i, line in enumerate(lines):
    if 'id="alerts-toggle-btn"' in line and button_idx is None:
        button_idx = i
    if 'class="alerts-panel"' in line and panel_idx is None:
        panel_idx = i

if button_idx is None or panel_idx is None:
    print(f"ERROR: could not find anchors - button_idx={button_idx}, panel_idx={panel_idx}")
else:
    button_line = lines[button_idx]
    print(f"Found button at line {button_idx+1}: {button_line.strip()}")
    print(f"Found panel opening at line {panel_idx+1}")

    # Remove the button from its current location
    remaining = lines[:button_idx] + lines[button_idx+1:]

    # Re-find panel_idx in the new (shorter) list - should be unchanged since
    # panel_idx < button_idx in the original
    insert_at = panel_idx + 1  # insert right after <div class="alerts-panel">

    new_lines = remaining[:insert_at] + [button_line] + remaining[insert_at:]

    with open(path, "w") as f:
        f.writelines(new_lines)

    print(f"SUCCESS: button moved to be a direct child of .alerts-panel (line {insert_at+1})")
