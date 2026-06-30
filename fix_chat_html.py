#!/usr/bin/env python3
"""Run this ON THE PI to insert the missing alerts panel CSS and HTML markup."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    content = f.read()

# ── 1. Insert CSS before </style> ─────────────────────────────────────────
css_block = """
  :root {
    --red-bright: #ff0033;
    --red-dim: #cc0029;
    --red-dark: #3b0008;
    --red-faint: #1a0003;
  }

  .alerts-panel {
    width: 300px;
    flex-shrink: 0;
    border-left: 1px solid var(--red-bright);
    background: var(--red-faint);
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
    position: relative;
  }

  #alert-matrix-canvas {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    opacity: 0.06;
    pointer-events: none;
  }

  .alerts-scanlines {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 1;
    pointer-events: none;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px,
      rgba(255,0,51,0.02) 2px, rgba(255,0,51,0.02) 4px
    );
  }

  .alerts-content {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .alerts-header {
    padding: 10px 16px;
    border-bottom: 1px solid var(--red-bright);
    background: rgba(255, 0, 51, 0.04);
    flex-shrink: 0;
  }

  .alerts-label {
    font-family: 'Orbitron', monospace;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 3px;
    color: var(--red-bright);
    text-shadow: 0 0 12px var(--red-bright);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .alerts-label::before { content: '\\26A0 '; }

  .alert-count {
    background: var(--red-bright);
    color: var(--black);
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    padding: 1px 8px;
    border-radius: 9px;
    font-weight: 700;
  }

  .alert-count.zero {
    background: transparent;
    border: 1px solid var(--red-dark);
    color: var(--red-dim);
  }

  .alert-count.pulse { animation: alertPulse 1s infinite; }

  .alerts-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 14px 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--red-dark) transparent;
  }

  .alerts-scroll::-webkit-scrollbar { width: 4px; }
  .alerts-scroll::-webkit-scrollbar-thumb { background: var(--red-dark); }

  .alert-card {
    margin-bottom: 12px;
    padding: 11px;
    border: 1px solid var(--red-bright);
    background: rgba(255, 0, 51, 0.05);
    border-radius: 2px;
    font-size: 10px;
    font-family: 'Share Tech Mono', monospace;
    animation: fadeInUp 0.3s ease;
    box-shadow: 0 0 14px rgba(255, 0, 51, 0.08);
  }

  .alert-card.resolved {
    border-color: var(--red-dark);
    background: rgba(255, 0, 51, 0.015);
    opacity: 0.55;
    box-shadow: none;
  }

  .alert-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 7px;
  }

  .alert-name {
    color: var(--red-bright);
    font-weight: 700;
    letter-spacing: 0.5px;
    text-shadow: 0 0 8px rgba(255, 0, 51, 0.5);
  }

  .alert-card.resolved .alert-name { color: var(--red-dim); text-shadow: none; }
  .alert-card.resolved .alert-name::after { content: ' [RESOLVED]'; font-size: 8px; opacity: 0.7; }

  .alert-time { color: var(--red-dim); opacity: 0.6; font-size: 9px; }

  .alert-target { color: var(--red-dim); margin-bottom: 7px; font-size: 9px; letter-spacing: 0.5px; }
  .alert-target::before { content: '\\2B21 '; }

  .alert-summary { color: #ffaaaa; line-height: 1.6; margin-bottom: 7px; }

  .alert-diagnosis {
    color: #ffcccc;
    opacity: 0.85;
    border-top: 1px solid var(--red-dark);
    padding-top: 7px;
    margin-top: 7px;
    line-height: 1.6;
    white-space: pre-wrap;
    max-height: 180px;
    overflow-y: auto;
  }

  .alert-diagnosis::-webkit-scrollbar { width: 3px; }
  .alert-diagnosis::-webkit-scrollbar-thumb { background: var(--red-dark); }

  .alert-pending { color: var(--amber); font-size: 9px; letter-spacing: 0.5px; animation: blink 1.2s infinite; }
  .alert-pending::before { content: '\\2B21 '; }

  .alerts-empty { padding: 30px 10px; text-align: center; color: var(--red-dark); font-size: 10px; letter-spacing: 1px; }
  .alerts-empty::before { content: '\\2014 '; }
  .alerts-empty::after { content: ' \\2014'; }

  @keyframes alertPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255,0,51,0.5); }
    50% { box-shadow: 0 0 0 5px rgba(255,0,51,0); }
  }
"""

marker_css = "</style>"
if marker_css in content and "alerts-panel {" not in content:
    content = content.replace(marker_css, css_block + marker_css, 1)
    print("CSS inserted")
else:
    print("CSS already present or marker not found - skipped")

# ── 2. Insert HTML markup after .chat-area closing div ────────────────────
panel_html = """
    <div class="alerts-panel">
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
"""

# Find the specific closing pattern: chat-area's last </div> followed by .main's </div>
old_close = """      </div>
    </div>
  </div>
</div>
<script>"""

new_close = """      </div>
    </div>""" + panel_html + """  </div>
</div>
<script>"""

if old_close in content and 'class="alerts-panel"' not in content:
    content = content.replace(old_close, new_close, 1)
    print("Panel HTML inserted")
elif 'class="alerts-panel"' in content:
    print("Panel HTML already present - skipped")
else:
    print("ERROR: closing pattern not found - manual fix needed")
    idx = content.find('<script>')
    print("Context around <script>:")
    print(content[max(0,idx-200):idx+20])

with open(path, "w") as f:
    f.write(content)

print("Done writing file")
