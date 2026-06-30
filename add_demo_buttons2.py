#!/usr/bin/env python3
"""Run on the Pi - inserts DEMO CONTROLS section, anchored on a unique
content match (the 'pod metrics' button line) rather than a fixed line
number, to avoid drift issues from prior edits."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

if any('class="sidebar-section demo-controls"' in l for l in lines):
    print("Already present - nothing to do")
else:
    # Find the unique "pod metrics" button line, then the next </div> after it
    anchor_idx = None
    for i, line in enumerate(lines):
        if "pod metrics</button>" in line:
            anchor_idx = i
            break

    if anchor_idx is None:
        print("ERROR: could not find 'pod metrics</button>' anchor line")
    else:
        # The closing </div> for the sidebar-section should be the very next line
        close_idx = anchor_idx + 1
        if lines[close_idx].strip() != '</div>':
            print(f"ERROR: line after anchor is not '</div>' - actual: {lines[close_idx]!r}")
        else:
            demo_section = '''      <div class="sidebar-section demo-controls">
        <div class="sidebar-label demo-label">DEMO CONTROLS</div>
        <button class="tool-btn demo-btn" onclick="startCrashpod()">+ start crashpod</button>
        <button class="tool-btn demo-btn-danger" onclick="deleteCrashpod()">- delete crashpod</button>
        <div id="demo-result" class="demo-result"></div>
      </div>
'''
            new_lines = lines[:close_idx+1] + [demo_section] + lines[close_idx+1:]
            with open(path, "w") as f:
                f.writelines(new_lines)
            print(f"SUCCESS: DEMO CONTROLS inserted after line {close_idx+1}")
