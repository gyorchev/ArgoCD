#!/usr/bin/env python3
"""Run on the Pi - adds two Flask routes for the demo crashpod buttons,
anchored on the confirmed dismiss_alert_api function ending at line 905."""

path = "/home/smarty/ArgoCD/app/app.py"

with open(path, "r") as f:
    lines = f.readlines()

if any("def demo_start_crashpod" in l for l in lines):
    print("Already present - nothing to do")
else:
    # Line 907 (1-indexed) = index 906, should be the return jsonify line
    target_line = lines[906]
    if "return jsonify" not in target_line or "id\": alert_id" not in target_line:
        print(f"ERROR: line 907 is not the expected return statement - actual: {target_line!r}")
    else:
        new_routes = '''

@app.route('/demo/crashpod/start', methods=['POST'])
@login_required
def demo_start_crashpod():
    """Deploy the hardcoded demo crash-loop pod via MCP. No parameters accepted
    from the request - this only ever calls the fixed start_crashpod tool."""
    result = mcp_call('start_crashpod')
    return jsonify({"result": result})


@app.route('/demo/crashpod/delete', methods=['POST'])
@login_required
def demo_delete_crashpod():
    """Delete the hardcoded demo crash-loop pod via MCP. No parameters accepted
    from the request - this only ever calls the fixed delete_crashpod tool."""
    result = mcp_call('delete_crashpod')
    return jsonify({"result": result})
'''
        new_lines = lines[:907] + [new_routes] + lines[907:]
        with open(path, "w") as f:
            f.writelines(new_lines)
        print("SUCCESS: demo crashpod routes added")
