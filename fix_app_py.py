#!/usr/bin/env python3
"""Run on the Pi - inserts webhook/alerts backend into app.py, anchored precisely."""

path = "/home/smarty/ArgoCD/app/app.py"

with open(path, "r") as f:
    content = f.read()

already_done = "def webhook_alert" in content
if already_done:
    print("Webhook backend already present - nothing to do")
else:
    # ── 1. Insert alerts table + webhook route + API, right after clear_history ──
    anchor = """def clear_history(user_id: int):
    \"\"\"Clear all chat history for a user.\"\"\"
    conn = get_db()
    conn.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
"""

    insertion = '''

def init_alerts_table():
    """Create alerts table if it doesn't exist. Separate from chat_history -
    alerts are system-wide, not per-user."""
    conn = get_db()
    conn.executescript(\'\'\'
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            alertname TEXT NOT NULL,
            severity TEXT DEFAULT 'warning',
            status TEXT DEFAULT 'firing',
            namespace TEXT DEFAULT '',
            pod TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            description TEXT DEFAULT '',
            diagnosis TEXT DEFAULT '',
            tools_used TEXT DEFAULT '',
            created_at REAL NOT NULL,
            resolved_at REAL
        );
    \'\'\')
    conn.commit()
    conn.close()


def save_alert(alertname, severity, status, namespace, pod, summary, description) -> int:
    """Save an incoming alert, return its row id."""
    conn = get_db()
    cur = conn.execute(
        \'\'\'INSERT INTO alerts (alertname, severity, status, namespace, pod, summary, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)\'\'\',
        (alertname, severity, status, namespace, pod, summary, description, datetime.now().timestamp())
    )
    alert_id = cur.lastrowid
    conn.commit()
    conn.close()
    return alert_id


def update_alert_diagnosis(alert_id: int, diagnosis: str, tools_used: list):
    """Save the agent's investigation result back onto the alert row."""
    conn = get_db()
    conn.execute(
        'UPDATE alerts SET diagnosis = ?, tools_used = ? WHERE id = ?',
        (diagnosis, ','.join(tools_used), alert_id)
    )
    conn.commit()
    conn.close()


def resolve_alert(alertname: str, namespace: str, pod: str):
    """Mark matching firing alerts as resolved when Alertmanager sends send_resolved."""
    conn = get_db()
    conn.execute(
        \'\'\'UPDATE alerts SET status = 'resolved', resolved_at = ?
           WHERE alertname = ? AND namespace = ? AND pod = ? AND status = 'firing' \'\'\',
        (datetime.now().timestamp(), alertname, namespace, pod)
    )
    conn.commit()
    conn.close()


def load_alerts(limit: int = 30) -> list:
    """Load recent alerts, newest first."""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route('/webhook/alert', methods=['POST'])
def webhook_alert():
    """
    Receives alerts from Alertmanager. No @login_required - Alertmanager
    can't authenticate as a user. Only reachable from inside the cluster.
    """
    data = request.get_json(force=True, silent=True) or {}
    alerts = data.get('alerts', [])

    if not alerts:
        return jsonify({"received": 0}), 200

    processed = 0

    for alert in alerts:
        status = alert.get('status', 'firing')
        labels = alert.get('labels', {})
        annotations = alert.get('annotations', {})

        alertname = labels.get('alertname', 'UnknownAlert')
        severity = labels.get('severity', 'warning')
        namespace = labels.get('namespace', '')
        pod = labels.get('pod', '')
        summary = annotations.get('summary', '')
        description = annotations.get('description', '')

        if status == 'resolved':
            resolve_alert(alertname, namespace, pod)
            processed += 1
            continue

        alert_id = save_alert(alertname, severity, status, namespace, pod, summary, description)
        processed += 1

        try:
            investigation_prompt = (
                f"An alert just fired: {alertname}. "
                f"Summary: {summary}. Description: {description}. "
                f"Namespace: {namespace or 'unknown'}, Pod: {pod or 'unknown'}. "
                f"Investigate the root cause using available tools and give a concise diagnosis."
            )
            diagnosis, tools_used = run_agent(investigation_prompt, [])
            update_alert_diagnosis(alert_id, diagnosis, tools_used)
        except Exception as e:
            update_alert_diagnosis(alert_id, f"Auto-investigation failed: {e}", [])

    return jsonify({"received": processed}), 200


@app.route('/alerts')
@login_required
def alerts_page_api():
    """Returns recent alerts as JSON for the sidebar panel to poll."""
    return jsonify(load_alerts(limit=30))

'''

    if anchor not in content:
        print("ERROR: clear_history anchor not found exactly - aborting, no changes written")
        import sys
        sys.exit(1)

    content = content.replace(anchor, anchor + insertion, 1)
    print("Webhook/alerts backend inserted after clear_history")

    # ── 2. Update if __name__ block to call init_alerts_table() ──────────────
    old_main = """if __name__ == '__main__':
    init_db()
    init_chat_history()
    app.run(host='0.0.0.0', port=5000)"""

    new_main = """if __name__ == '__main__':
    init_db()
    init_chat_history()
    init_alerts_table()
    app.run(host='0.0.0.0', port=5000)"""

    if old_main in content:
        content = content.replace(old_main, new_main, 1)
        print("if __name__ block updated with init_alerts_table()")
    else:
        print("WARNING: if __name__ block not matched exactly - main init not updated, check manually")

    with open(path, "w") as f:
        f.write(content)

    print("Done writing file")
