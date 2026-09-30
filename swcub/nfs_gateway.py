"""Run-scoped, ownership-ledgered NFSv4 gateway for shared workspace validation."""
from __future__ import annotations

import socket
import time
from typing import Any

import docker

from .resource_safety import (ResourceIdentity, ResourceLedger,
                              remove_verified_container,
                              verify_container_identity)


class NfsGateway:
    def __init__(self, container: Any, identity: ResourceIdentity,
                 server_ip: str, port: int):
        self.container = container
        self.identity = identity
        self.server_ip = server_ip
        self.port = port
        self.closed = False

    @classmethod
    def start(cls, *, export_root: str, identity: ResourceIdentity,
              host_uid: int, host_gid: int, port: int = 12049,
              image: str = "swcub/codesk-nfs-gateway:jammy-v2",
              timeout: float = 20.0) -> "NfsGateway":
        client = docker.from_env()
        bridge = client.networks.get("bridge").attrs
        configs = (bridge.get("IPAM") or {}).get("Config") or []
        if not configs or not configs[0].get("Gateway"):
            raise RuntimeError("Docker bridge has no recorded gateway address")
        server_ip = configs[0]["Gateway"]
        if not 1024 <= port <= 65535:
            raise ValueError("NFS gateway port must be non-privileged")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            try:
                probe.bind((server_ip, port))
            except OSError as exc:
                raise RuntimeError(f"NFS gateway bridge port is unavailable: {server_ip}:{port}") from exc
        root = export_root
        for name in ("task", "reset"):
            import os
            if not os.path.isdir(os.path.join(root, name)):
                raise FileNotFoundError(f"NFS export directory is missing: {name}")
        ledger = ResourceLedger(identity.ledger_path)
        container = client.containers.run(
            image, detach=True,
            name=f"codesk-nfs-{identity.run_id[:18]}",
            labels=identity.labels,
            environment={"CODESK_NFS_ANON_UID": str(host_uid),
                         "CODESK_NFS_ANON_GID": str(host_gid)},
            volumes={
                f"{root}/task": {"bind": "/exports/task", "mode": "rw"},
                f"{root}/reset": {"bind": "/exports/reset", "mode": "rw"},
            },
            ports={f"{port}/tcp": (server_ip, port)},
        )
        container.reload()
        verify_container_identity(container.id, container.attrs, identity)
        ledger.created_container(container.id, identity, name=container.name, image=image)
        ledger.record("metadata", "container", container.id, identity,
                      purpose="run-scoped NFSv4 workspace gateway",
                      host_bind_ip=server_ip, host_port=port, export_root=root)
        gateway = cls(container, identity, server_ip, port)
        try:
            deadline = time.monotonic() + timeout
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                container.reload()
                state = container.attrs.get("State") or {}
                if not state.get("Running"):
                    logs = container.logs(tail=80).decode(errors="replace")
                    raise RuntimeError(f"NFS gateway exited during startup: {logs}")
                try:
                    with socket.create_connection((server_ip, port), timeout=0.5):
                        return gateway
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.2)
            logs = container.logs(tail=80).decode(errors="replace")
            raise TimeoutError(f"NFS gateway did not listen at {server_ip}:{port}; "
                               f"last_error={last_error}; logs={logs}")
        except BaseException:
            gateway.close(reason="nfs_gateway_startup_failure")
            raise

    def close(self, *, reason: str = "nfs_gateway_close") -> None:
        if self.closed:
            return
        remove_verified_container(self.container, self.identity, reason=reason)
        self.closed = True
