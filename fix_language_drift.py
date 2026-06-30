#!/usr/bin/env python3
"""Run on the Pi - strengthens English enforcement and reshapes the
auto-investigation prompt used by webhook_alert()."""

path = "/home/smarty/ArgoCD/app/app.py"

with open(path, "r") as f:
    content = f.read()

# ── 1. Strengthen SYSTEM_PROMPT with repeated, explicit English enforcement ──
old_prompt = '''SYSTEM_PROMPT = """You are a Kubernetes cluster assistant for a k3s cluster on a Raspberry Pi (hostname: smarty).
RULES:
- Always respond in English only.
- Use tool calls to fetch real data. Never write JSON tool calls as markdown text.
- Call at most 3 tools per response, then summarize findings in plain English.
- After fetching data with tools, write your final answer as plain text - do not call more tools.
- Use sensible defaults: namespace=all, lines=50.
- Be direct and technical. Format tables as plain text. Highlight unhealthy items.
- You are talking to Grisho, a senior DevOps/Platform Engineer."""'''

new_prompt = '''SYSTEM_PROMPT = """You are a Kubernetes cluster assistant for a k3s cluster on a Raspberry Pi (hostname: smarty).

LANGUAGE: Respond ONLY in English. Every word of your output must be English.
Do not use Chinese, Thai, or any other language under any circumstances, even
if it seems contextually relevant. This is a strict requirement, not a preference.

RULES:
- Use tool calls to fetch real data. Never write JSON tool calls as markdown text -
  if you need to call a tool, use a proper tool_call, not text describing one.
- Call at most 3 tools per response, then summarize findings in plain English.
- After fetching data with tools, write your final answer as plain English text - do not call more tools.
- Use sensible defaults: namespace=all, lines=50.
- Be direct and technical. Format tables as plain text. Highlight unhealthy items.
- You are talking to Grisho, a senior DevOps/Platform Engineer.

Remember: English only, always."""'''

if old_prompt not in content:
    print("ERROR: SYSTEM_PROMPT anchor not found exactly - aborting, no changes written")
else:
    content = content.replace(old_prompt, new_prompt, 1)
    print("SYSTEM_PROMPT strengthened")

    # ── 2. Reshape the webhook investigation prompt to read more naturally ──
    old_investigation = '''            investigation_prompt = (
                f"An alert just fired: {alertname}. "
                f"Summary: {summary}. Description: {description}. "
                f"Namespace: {namespace or 'unknown'}, Pod: {pod or 'unknown'}. "
                f"Investigate the root cause using available tools and give a concise diagnosis."
            )'''

    new_investigation = '''            target_desc = f"pod {pod} in namespace {namespace}" if pod else f"namespace {namespace}" if namespace else "the cluster"
            investigation_prompt = (
                f"A monitoring alert called '{alertname}' just fired for {target_desc}. "
                f"Here is what triggered it: {summary or description}. "
                f"Please investigate {target_desc} using your tools and explain in plain English "
                f"what is actually happening and what the likely root cause is. "
                f"Respond only in English."
            )'''

    if old_investigation not in content:
        print("WARNING: investigation_prompt anchor not found - SYSTEM_PROMPT was still updated, but the webhook prompt itself was not reshaped. Check manually.")
    else:
        content = content.replace(old_investigation, new_investigation, 1)
        print("Investigation prompt reshaped")

    with open(path, "w") as f:
        f.write(content)
    print("Done writing file")
