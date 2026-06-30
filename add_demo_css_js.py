#!/usr/bin/env python3
"""Run on the Pi - adds CSS for the demo controls (amber palette, distinct
from green query buttons) and the JS functions that call the Flask routes."""

path = "/home/smarty/ArgoCD/app/templates/chat.html"

with open(path, "r") as f:
    content = f.read()

if "startCrashpod" in content:
    print("Already present - nothing to do")
else:
    # ── CSS: anchor on .tool-btn's existing rule, insert right after it ──────
    css_anchor = "  .tool-btn:hover {"

    if css_anchor not in content:
        print("ERROR: CSS anchor .tool-btn:hover not found - aborting")
    else:
        # Find the closing brace of .tool-btn:hover to insert after the whole block
        idx = content.find(css_anchor)
        brace_end = content.find("}", idx) + 1

        demo_css = """

  .demo-controls {
    border-top: 1px dashed var(--text-faint);
    padding-top: 14px;
  }

  .demo-label {
    color: var(--amber) !important;
  }

  .demo-btn {
    border-color: rgba(255, 170, 0, 0.3) !important;
  }

  .demo-btn:hover {
    color: var(--amber) !important;
    border-color: var(--amber) !important;
    background: rgba(255, 170, 0, 0.08) !important;
    text-shadow: 0 0 8px var(--amber) !important;
  }

  .demo-btn-danger {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: 1px solid rgba(255, 0, 64, 0.3);
    color: var(--text-dim);
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    padding: 6px 10px;
    cursor: pointer;
    border-radius: 2px;
    margin-bottom: 4px;
    transition: all 0.15s;
    letter-spacing: 0.5px;
  }

  .demo-btn-danger::before { content: '> '; color: var(--text-faint); }

  .demo-btn-danger:hover {
    color: var(--red);
    border-color: var(--red);
    background: rgba(255, 0, 64, 0.08);
    text-shadow: 0 0 8px var(--red);
  }

  .demo-result {
    margin-top: 8px;
    font-size: 9px;
    color: var(--text-faint);
    line-height: 1.5;
    min-height: 12px;
    word-break: break-word;
  }

  .demo-result.success { color: var(--amber); }
  .demo-result.error { color: var(--red); }
"""
        content = content[:brace_end] + demo_css + content[brace_end:]
        print("Demo CSS inserted")

    # ── JS: anchor on the existing sendQuick function, insert right after ────
    js_anchor = '''function sendQuick(text) {
  inputEl.value = text;
  sendMessage();
}'''

    if js_anchor not in content:
        print("ERROR: JS anchor sendQuick not found - CSS was inserted but JS was not")
    else:
        demo_js = '''

async function startCrashpod() {
  const resultEl = document.getElementById("demo-result");
  resultEl.className = "demo-result";
  resultEl.textContent = "deploying...";
  try {
    const res = await fetch("/demo/crashpod/start", { method: "POST" });
    const data = await res.json();
    resultEl.textContent = data.result;
    resultEl.className = "demo-result success";
  } catch (err) {
    resultEl.textContent = "Error: " + err.message;
    resultEl.className = "demo-result error";
  }
}

async function deleteCrashpod() {
  const resultEl = document.getElementById("demo-result");
  resultEl.className = "demo-result";
  resultEl.textContent = "deleting...";
  try {
    const res = await fetch("/demo/crashpod/delete", { method: "POST" });
    const data = await res.json();
    resultEl.textContent = data.result;
    resultEl.className = "demo-result success";
  } catch (err) {
    resultEl.textContent = "Error: " + err.message;
    resultEl.className = "demo-result error";
  }
}'''
        content = content.replace(js_anchor, js_anchor + demo_js, 1)
        print("Demo JS functions added")

    with open(path, "w") as f:
        f.write(content)
    print("Done writing file")
