#!/usr/bin/env python3
"""Run on the Pi - inserts only the panel HTML markup, CSS already landed."""
import re

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    content = f.read()

if 'class="alerts-panel"' in content:
    print("Panel HTML already present - nothing to do")
else:
    panel_html = '''    <div class="alerts-panel">
      <canvas id="alert-matrix-canvas"></canvas>
      <div class="alerts-scanlines"></div>
      <div class="alerts-content">
        <div class="alerts-header">
          <div class="alerts-label">
            <span>ALERTS</span>
            <span class="alert-count zero" id="alert-count">0</span>
          </div>
        </div>
        <div class="alerts-scroll" id="alerts-list">
          <div class="alerts-empty">no alerts // cluster quiet</div>
        </div>
      </div>
    </div>
'''
    # Match the exact block visible in the file: textarea close, send-btn,
    # then 4 closing divs, then <script> - using a regex that tolerates
    # whitespace variation instead of an exact string match.
    pattern = re.compile(
        r'(<button class="send-btn" id="send-btn" onclick="sendMessage\(\)">EXEC</button>\s*'
        r'</div>\s*</div>\s*</div>\s*)(</div>\s*<script>)',
        re.DOTALL
    )

    new_content, count = pattern.subn(r'\1' + panel_html + r'\2', content, count=1)

    if count == 1:
        with open(path, "w") as f:
            f.write(new_content)
        print("SUCCESS - panel HTML inserted")
    else:
        print(f"ERROR - regex matched {count} times, expected 1. No changes written.")
        idx = content.find('id="send-btn"')
        print("Context:")
        print(repr(content[idx:idx+400]))
