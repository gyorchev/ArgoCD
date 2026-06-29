#!/usr/bin/env python3
"""
MCP Server - Kubernetes stats for Raspberry Pi k3s cluster
Tools: get_pods, get_nodes, get_argocd_apps, get_metrics, describe_pod,
       get_services, get_logs, get_events, get_ingress,
       restart_deployment, argocd_sync
"""

import json
import subprocess
import sys
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_kubectl(args: list[str]) -> dict:
    cmd = ["kubectl"] + args + ["-o", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "kubectl command timed out"}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse kubectl output: {e}"}


def run_kubectl_text(args: list[str], timeout: int = 15) -> str:
    cmd = ["kubectl"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return f"ERROR: {result.stderr.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "ERROR: kubectl command timed out"


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

def get_pods(namespace: str = "all") -> str:
    if namespace == "all":
        data = run_kubectl(["get", "pods", "-A"])
    else:
        data = run_kubectl(["get", "pods", "-n", namespace])

    if "error" in data:
        return f"Error fetching pods: {data['error']}"

    items = data.get("items", [])
    if not items:
        return "No pods found."

    lines = [f"{'NAMESPACE':<20} {'NAME':<55} {'STATUS':<20} {'RESTARTS':<10} {'NODE':<15}"]
    lines.append("-" * 120)

    for pod in items:
        ns = pod["metadata"]["namespace"]
        name = pod["metadata"]["name"]
        node = pod["spec"].get("nodeName", "<none>")
        phase = pod["status"].get("phase", "Unknown")
        container_statuses = pod["status"].get("containerStatuses", [])
        restarts = sum(cs.get("restartCount", 0) for cs in container_statuses)
        for cs in container_statuses:
            state = cs.get("state", {})
            if "waiting" in state:
                phase = state["waiting"].get("reason", phase)
                break
        lines.append(f"{ns:<20} {name:<55} {phase:<20} {str(restarts):<10} {node:<15}")

    return "\n".join(lines)


def get_nodes() -> str:
    data = run_kubectl(["get", "nodes"])
    if "error" in data:
        return f"Error fetching nodes: {data['error']}"

    items = data.get("items", [])
    if not items:
        return "No nodes found."

    top = run_kubectl_text(["top", "nodes", "--no-headers"])

    lines = ["=== NODE STATUS ==="]
    for node in items:
        name = node["metadata"]["name"]
        conditions = node["status"].get("conditions", [])
        ready = next((c["status"] for c in conditions if c["type"] == "Ready"), "Unknown")
        version = node["status"]["nodeInfo"]["kubeletVersion"]
        os_image = node["status"]["nodeInfo"]["osImage"]
        arch = node["status"]["nodeInfo"]["architecture"]
        roles = [
            k.replace("node-role.kubernetes.io/", "")
            for k in node["metadata"].get("labels", {})
            if k.startswith("node-role.kubernetes.io/")
        ]
        lines.append(f"  Name:    {name}")
        lines.append(f"  Ready:   {ready}")
        lines.append(f"  Roles:   {', '.join(roles) or 'worker'}")
        lines.append(f"  Version: {version}")
        lines.append(f"  OS:      {os_image} ({arch})")

    if top and not top.startswith("ERROR"):
        lines.append("\n=== RESOURCE USAGE (metrics-server) ===")
        lines.append(f"{'NODE':<20} {'CPU':<12} {'CPU%':<10} {'MEMORY':<12} {'MEM%':<10}")
        lines.append("-" * 64)
        lines.append(top)

    return "\n".join(lines)


def get_argocd_apps() -> str:
    data = run_kubectl(["get", "applications", "-n", "argocd"])
    if "error" in data:
        return f"Error fetching ArgoCD apps: {data['error']}"

    items = data.get("items", [])
    if not items:
        return "No ArgoCD applications found."

    lines = [f"{'NAME':<30} {'SYNC':<15} {'HEALTH':<15} {'REPO':<50} {'PATH':<20}"]
    lines.append("-" * 130)

    for app in items:
        name = app["metadata"]["name"]
        status = app.get("status", {})
        sync = status.get("sync", {}).get("status", "Unknown")
        health = status.get("health", {}).get("status", "Unknown")
        source = app["spec"].get("source", {})
        repo = source.get("repoURL", "?")
        path = source.get("path", "?")
        lines.append(f"{name:<30} {sync:<15} {health:<15} {repo:<50} {path:<20}")

    return "\n".join(lines)


def get_metrics() -> str:
    top_pods = run_kubectl_text(["top", "pods", "-A", "--no-headers"])
    top_nodes = run_kubectl_text(["top", "nodes", "--no-headers"])

    lines = ["=== NODE RESOURCE USAGE ==="]
    if top_nodes.startswith("ERROR"):
        lines.append(f"  {top_nodes}")
    else:
        lines.append(f"  {'NODE':<20} {'CPU':<12} {'CPU%':<10} {'MEMORY':<12} {'MEM%':<10}")
        lines.append("  " + "-" * 64)
        for line in top_nodes.splitlines():
            lines.append(f"  {line}")

    lines.append("\n=== POD RESOURCE USAGE ===")
    if top_pods.startswith("ERROR"):
        lines.append(f"  {top_pods}")
    else:
        lines.append(f"  {'NAMESPACE':<20} {'POD':<50} {'CPU':<12} {'MEMORY':<12}")
        lines.append("  " + "-" * 94)
        for line in top_pods.splitlines():
            lines.append(f"  {line}")

    return "\n".join(lines)


def describe_pod(name: str, namespace: str = "default") -> str:
    output = run_kubectl_text(["describe", "pod", name, "-n", namespace])
    lines = output.splitlines()
    if len(lines) > 100:
        lines = lines[:100] + ["... (truncated)"]
    return "\n".join(lines)


def get_services() -> str:
    data = run_kubectl(["get", "svc", "-A"])
    if "error" in data:
        return f"Error fetching services: {data['error']}"

    items = data.get("items", [])
    lines = [f"{'NAMESPACE':<20} {'NAME':<45} {'TYPE':<15} {'CLUSTER-IP':<16} {'PORT(S)':<30}"]
    lines.append("-" * 126)

    for svc in items:
        ns = svc["metadata"]["namespace"]
        name = svc["metadata"]["name"]
        stype = svc["spec"].get("type", "ClusterIP")
        cluster_ip = svc["spec"].get("clusterIP", "<none>")
        ports = ", ".join(
            f"{p.get('port')}/{p.get('protocol','TCP')}"
            for p in svc["spec"].get("ports", [])
        )
        lines.append(f"{ns:<20} {name:<45} {stype:<15} {cluster_ip:<16} {ports:<30}")

    return "\n".join(lines)


def get_logs(pod_name: str, namespace: str = "default", lines: int = 50, container: str = "") -> str:
    """Get recent logs from a pod."""
    args = ["logs", pod_name, "-n", namespace, f"--tail={lines}"]
    if container:
        args += ["-c", container]
    output = run_kubectl_text(args, timeout=20)
    if not output:
        return "No logs found or pod has not started yet."
    return output


def get_events(namespace: str = "all") -> str:
    """Get recent cluster events sorted by time, warnings highlighted."""
    if namespace == "all":
        data = run_kubectl(["get", "events", "-A", "--sort-by=.lastTimestamp"])
    else:
        data = run_kubectl(["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"])

    if "error" in data:
        return f"Error fetching events: {data['error']}"

    items = data.get("items", [])
    if not items:
        return "No events found."

    lines = [f"{'NAMESPACE':<20} {'TYPE':<10} {'REASON':<25} {'OBJECT':<40} {'MESSAGE':<60}"]
    lines.append("-" * 155)

    # Show last 30 events, warnings first
    warnings = [i for i in items if i.get("type") == "Warning"]
    normal = [i for i in items if i.get("type") != "Warning"]
    sorted_items = warnings[-15:] + normal[-15:]

    for event in sorted_items:
        ns = event["metadata"]["namespace"]
        etype = event.get("type", "Normal")
        reason = event.get("reason", "")
        obj = f"{event.get('involvedObject', {}).get('kind', '')}/{event.get('involvedObject', {}).get('name', '')}"
        message = event.get("message", "")[:58]
        prefix = "!" if etype == "Warning" else " "
        lines.append(f"{prefix}{ns:<19} {etype:<10} {reason:<25} {obj:<40} {message:<60}")

    return "\n".join(lines)


def get_ingress() -> str:
    """List all ingress rules and Traefik IngressRoutes."""
    lines = []

    # Standard ingresses
    data = run_kubectl(["get", "ingress", "-A"])
    if "error" not in data and data.get("items"):
        lines.append("=== STANDARD INGRESSES ===")
        lines.append(f"{'NAMESPACE':<20} {'NAME':<30} {'CLASS':<15} {'HOSTS':<40} {'PORTS':<10}")
        lines.append("-" * 115)
        for ing in data["items"]:
            ns = ing["metadata"]["namespace"]
            name = ing["metadata"]["name"]
            cls = ing["spec"].get("ingressClassName", "<none>")
            rules = ing["spec"].get("rules", [])
            hosts = ", ".join(r.get("host", "*") for r in rules) or "*"
            lines.append(f"{ns:<20} {name:<30} {cls:<15} {hosts:<40}")
    else:
        lines.append("=== STANDARD INGRESSES ===")
        lines.append("  No standard ingresses found.")

    # Traefik IngressRoutes
    ir_data = run_kubectl_text(["get", "ingressroute", "-A", "--no-headers", "2>/dev/null"], timeout=10)
    lines.append("\n=== TRAEFIK INGRESSROUTES ===")
    if ir_data.startswith("ERROR") or not ir_data:
        lines.append("  No IngressRoutes found (or Traefik CRDs not installed).")
    else:
        for line in ir_data.splitlines():
            lines.append(f"  {line}")

    # Traefik services via NodePort
    lines.append("\n=== TRAEFIK ENTRYPOINTS ===")
    traefik_svc = run_kubectl_text(["get", "svc", "traefik", "-n", "kube-system", "--no-headers"])
    if not traefik_svc.startswith("ERROR"):
        lines.append(f"  {traefik_svc}")

    return "\n".join(lines)


def restart_deployment(name: str, namespace: str = "default") -> str:
    """Restart a deployment by triggering a rolling restart."""
    output = run_kubectl_text(["rollout", "restart", f"deployment/{name}", "-n", namespace])
    if output.startswith("ERROR"):
        return f"Failed to restart deployment {name}: {output}"
    # Check rollout status
    status = run_kubectl_text(["rollout", "status", f"deployment/{name}", "-n", namespace, "--timeout=30s"])
    return f"Restart triggered: {output}\nRollout status: {status}"


def argocd_sync(app_name: str) -> str:
    """Trigger an ArgoCD sync for a specific application."""
    # Use kubectl to patch the app annotation to trigger sync
    output = run_kubectl_text([
        "annotate", "application", app_name,
        "-n", "argocd",
        "argocd.argoproj.io/refresh=hard",
        "--overwrite"
    ])
    if output.startswith("ERROR"):
        return f"Failed to trigger sync for {app_name}: {output}"

    # Check current sync status
    data = run_kubectl([f"get", "application", app_name, "-n", "argocd"])
    if "error" in data:
        return f"Sync triggered but could not get status: {output}"

    status = data.get("status", {})
    sync = status.get("sync", {}).get("status", "Unknown")
    health = status.get("health", {}).get("status", "Unknown")

    return f"ArgoCD sync triggered for '{app_name}'\nCurrent sync: {sync}\nHealth: {health}\n{output}"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = {
    "get_pods": {
        "description": "List all pods across the k3s cluster with status, restarts and node assignment",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace to filter by, or 'all' for all namespaces",
                    "default": "all"
                }
            }
        },
        "fn": lambda p: get_pods(p.get("namespace", "all"))
    },
    "get_nodes": {
        "description": "Get node health, roles, Kubernetes version, OS info and resource usage",
        "parameters": {"type": "object", "properties": {}},
        "fn": lambda p: get_nodes()
    },
    "get_argocd_apps": {
        "description": "List ArgoCD applications with their sync status, health status, repo and path",
        "parameters": {"type": "object", "properties": {}},
        "fn": lambda p: get_argocd_apps()
    },
    "get_metrics": {
        "description": "Get real-time CPU and memory usage for all nodes and pods via metrics-server",
        "parameters": {"type": "object", "properties": {}},
        "fn": lambda p: get_metrics()
    },
    "describe_pod": {
        "description": "Get detailed description of a specific pod including events and conditions",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pod name"},
                "namespace": {"type": "string", "description": "Namespace the pod is in", "default": "default"}
            },
            "required": ["name"]
        },
        "fn": lambda p: describe_pod(p["name"], p.get("namespace", "default"))
    },
    "get_services": {
        "description": "List all Kubernetes services across all namespaces",
        "parameters": {"type": "object", "properties": {}},
        "fn": lambda p: get_services()
    },
    "get_logs": {
        "description": "Get recent logs from a specific pod. Use after describe_pod to see actual error output.",
        "parameters": {
            "type": "object",
            "properties": {
                "pod_name": {"type": "string", "description": "Pod name"},
                "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                "lines": {"type": "integer", "description": "Number of log lines to fetch", "default": 50},
                "container": {"type": "string", "description": "Container name (for multi-container pods)", "default": ""}
            },
            "required": ["pod_name"]
        },
        "fn": lambda p: get_logs(p["pod_name"], p.get("namespace", "default"), p.get("lines", 50), p.get("container", ""))
    },
    "get_events": {
        "description": "Get recent cluster events sorted by time. Warnings are shown first. Use to see what happened recently.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace to filter by, or 'all'", "default": "all"}
            }
        },
        "fn": lambda p: get_events(p.get("namespace", "all"))
    },
    "get_ingress": {
        "description": "List all ingress rules, Traefik IngressRoutes and entrypoints",
        "parameters": {"type": "object", "properties": {}},
        "fn": lambda p: get_ingress()
    },
    "restart_deployment": {
        "description": "Restart a deployment by triggering a rolling restart. Use to fix crashlooping pods.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deployment name"},
                "namespace": {"type": "string", "description": "Namespace", "default": "default"}
            },
            "required": ["name"]
        },
        "fn": lambda p: restart_deployment(p["name"], p.get("namespace", "default"))
    },
    "argocd_sync": {
        "description": "Trigger an ArgoCD hard refresh and sync for a specific application",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "ArgoCD application name"}
            },
            "required": ["app_name"]
        },
        "fn": lambda p: argocd_sync(p["app_name"])
    }
}


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class MCPHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        log.info(format % args)

    def send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "tools": list(TOOLS.keys())})
        elif self.path == "/tools":
            tools_def = {
                name: {"description": t["description"], "parameters": t["parameters"]}
                for name, t in TOOLS.items()
            }
            self.send_json(200, tools_def)
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/call":
            self.send_json(404, {"error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        tool_name = req.get("tool")
        params = req.get("parameters", {})

        if tool_name not in TOOLS:
            self.send_json(404, {"error": f"Unknown tool: {tool_name}", "available": list(TOOLS.keys())})
            return

        log.info(f"Calling tool: {tool_name} with params: {params}")
        try:
            result = TOOLS[tool_name]["fn"](params)
            self.send_json(200, {"tool": tool_name, "result": result})
        except Exception as e:
            log.error(f"Tool {tool_name} failed: {e}")
            self.send_json(500, {"error": str(e)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    log.info(f"Starting MCP server on port {port}")
    log.info(f"Available tools: {list(TOOLS.keys())}")
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.server_close()
