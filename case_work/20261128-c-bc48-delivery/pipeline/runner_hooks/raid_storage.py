"""Opt-in RAID /storage binding for newly created BC Guests only."""
import os
from pathlib import Path

def install_raid_storage_hook():
    raw = os.environ.get("SWCUB_OSWORLD_STORAGE_HOST_DIR")
    if not raw:
        return
    storage = Path(raw).resolve()
    if not storage.is_relative_to(Path("/mnt/raid1")):
        raise RuntimeError("BC /storage must be bound to RAID")
    from docker.models.containers import ContainerCollection
    original = ContainerCollection.run
    if getattr(original, "_bc_raid_storage_patch", False):
        return
    def run_with_storage(self, image, command=None, **kwargs):
        storage.mkdir(parents=True, exist_ok=True)
        volumes = dict(kwargs.get("volumes") or {})
        volumes = {src: spec for src, spec in volumes.items()
                   if not isinstance(spec, dict) or spec.get("bind") != "/storage"}
        volumes[str(storage)] = {"bind": "/storage", "mode": "rw"}
        kwargs["volumes"] = volumes
        return original(self, image, command, **kwargs)
    run_with_storage._bc_raid_storage_patch = True
    ContainerCollection.run = run_with_storage
