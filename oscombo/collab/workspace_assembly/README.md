# Workspace Assembly

Offline-ready CoDesk Case 7: file-manager organization + Writer report-reference repair.

```bash
python -m oscombo.collab.workspace_assembly plan collaborative_isolated
python -m oscombo.collab.workspace_assembly prepare runs/workspace-assembly/demo --run-id demo
python -m oscombo.collab.workspace_assembly configure runs/workspace-assembly/demo collaborative_shared
python -m oscombo.collab.workspace_assembly evaluate runs/workspace-assembly/demo
python -m oscombo.collab.workspace_assembly reset runs/workspace-assembly/demo --run-id demo
python -m pytest -q tests/test_workspace_assembly.py
```

The runner requires a new/empty run directory. Reset snapshots the current workspace before restoring the initial tree. Guest mount topology and GUI behavior remain pending.
