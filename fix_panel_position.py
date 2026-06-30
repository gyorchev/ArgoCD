#!/usr/bin/env python3
"""Run on the Pi - moves the alerts-panel block to be a child of .main, not a sibling."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

# Find the alerts-panel block boundaries: starts at the <div class="alerts-panel">
# line, ends at its matching </div> (tracked by depth).
start_idx = None
for i, line in enumerate(lines):
    if 'class="alerts-panel"' in line:
        start_idx = i
        break

if start_idx is None:
    print("ERROR: alerts-panel div not found")
else:
    depth = lines[start_idx].count('<div') - lines[start_idx].count('</div>')
    end_idx = start_idx
    for i in range(start_idx + 1, len(lines)):
        depth += lines[i].count('<div') - lines[i].count('</div>')
        if depth == 0:
            end_idx = i
            break

    panel_block = lines[start_idx:end_idx + 1]
    print(f"Panel block spans lines {start_idx+1}-{end_idx+1} ({len(panel_block)} lines)")

    # Remove the panel block from its current (wrong) location
    remaining = lines[:start_idx] + lines[end_idx + 1:]

    # Find .main's closing </div> in the NEW line numbering (after removal)
    depth = 0
    main_start = None
    main_close_idx = None
    for i, line in enumerate(remaining):
        if 'class="main"' in line and main_start is None:
            main_start = i
            depth = line.count('<div') - line.count('</div>')
            continue
        if main_start is not None:
            depth += line.count('<div') - line.count('</div>')
            if depth == 0:
                main_close_idx = i
                break

    if main_close_idx is None:
        print("ERROR: could not relocate .main's closing div after removal - aborting")
    else:
        # Insert panel block right before .main's closing </div>
        new_lines = remaining[:main_close_idx] + panel_block + remaining[main_close_idx:]
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"SUCCESS: panel moved to before .main's close (was sibling, now child)")
