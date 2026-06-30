#!/usr/bin/env python3
"""Run on the Pi - inserts toggle button + collapsed-panel CSS before line 587
(.alert-dismiss-btn rule)."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    lines = f.readlines()

if any(".alerts-toggle-btn {" in l for l in lines):
    print("Toggle CSS already present - nothing to do")
else:
    line_587 = lines[586]  # 0-indexed
    if ".alert-dismiss-btn {" not in line_587:
        print(f"ERROR: line 587 is not the expected anchor - actual: {line_587!r}")
    else:
        toggle_css = '''  .alerts-toggle-btn {
    position: absolute;
    top: 50%;
    left: -22px;
    transform: translateY(-50%);
    width: 22px;
    height: 50px;
    background: var(--red-faint);
    border: 1px solid var(--red-bright);
    border-right: none;
    border-radius: 4px 0 0 4px;
    color: var(--red-bright);
    cursor: pointer;
    font-size: 13px;
    font-family: 'Share Tech Mono', monospace;
    z-index: 3;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
  }

  .alerts-toggle-btn:hover {
    background: rgba(255, 0, 51, 0.15);
  }

  .alerts-panel.collapsed {
    width: 22px;
    min-width: 22px;
  }

  .alerts-panel.collapsed .alerts-content {
    opacity: 0;
    pointer-events: none;
  }

'''
        new_lines = lines[:586] + [toggle_css] + lines[586:]
        with open(path, "w") as f:
            f.writelines(new_lines)
        print("SUCCESS: toggle button + collapsed-state CSS inserted before line 587")
