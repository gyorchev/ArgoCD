#!/usr/bin/env python3
"""Run on the Pi - adds create/delete on pods and patch/update on
deployments + applications directly to the source rbac.yaml file,
anchored on the confirmed real file content."""

path = "/home/smarty/ArgoCD/mcp-manifests/rbac.yaml"

with open(path, "r") as f:
    content = f.read()

if 'verbs: ["create", "delete"]' in content:
    print("Already present - nothing to do")
else:
    anchor = '''  # Apps - deployments, replicasets etc
  - apiGroups: ["apps"]
    resources:
      - deployments
      - replicasets
      - statefulsets
      - daemonsets
    verbs: ["get", "list", "watch"]'''

    insertion = '''
  # Pod lifecycle - needed for the hardcoded demo crashpod start/delete tools
  - apiGroups: [""]
    resources:
      - pods
    verbs: ["create", "delete"]
  # Deployment rollout restarts - needed for restart_deployment tool
  - apiGroups: ["apps"]
    resources:
      - deployments
    verbs: ["patch", "update"]
  # ArgoCD application sync - needed for argocd_sync tool
  - apiGroups: ["argoproj.io"]
    resources:
      - applications
    verbs: ["patch", "update"]'''

    if anchor not in content:
        print("ERROR: anchor not found exactly - aborting")
    else:
        content = content.replace(anchor, anchor + insertion, 1)
        with open(path, "w") as f:
            f.write(content)
        print("SUCCESS: RBAC additions written to source file")
