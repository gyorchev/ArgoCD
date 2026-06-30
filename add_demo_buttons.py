#!/usr/bin/env python3
"""Run on the Pi - inserts a DEMO CONTROLS sidebar section with start/delete
crashpod buttons, anchored on the confirmed line 702 gap between
QUICK COMMANDS and NODE STATUS."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

if any("demo-controls" in l for l in lines):
    print("Already present - nothing to do")
else:
    # Line 702 (1-indexed) = index 701, should be the QUICK COMMANDS section's closing </div>
    target_line = lines[701]
    if target_line.strip() != '</div>':
        print(f"ERROR: line 702 is not the expected closing div - actual: {target_line!r}")
    else:
        demo_section = '''      <div class="sidebar-section demo-controls">
        <div class="sidebar-label demo-label">DEMO CONTROLS</div>
        <button class="tool-btn demo-btn" onclick="startCrashpod()">+ start crashpod</button>
        <button class="tool-btn demo-btn-danger" onclick="deleteCrashpod()">- delete crashpod</button>
        <div id="demo-result" class="demo-result"></div>
      </div>
'''
        new_lines = lines[:702] + [demo_section] + lines[702:]
        with open(path, "w") as f:
            f.writelines(new_lines)
        print("SUCCESS: DEMO CONTROLS section inserted")
