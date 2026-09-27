#!/usr/bin/env python3
"""Add a pinned-runtime override and RAID1-backed QEMU overlays to local OSWorld V2.1."""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED = "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9"
RUNTIME_MARKER = "# SWCUB_LOCAL_RUNTIME_OVERRIDE"
OVERLAY_MARKER = "# SWCUB_RAID1_OVERLAY_MOUNT"
OWNERSHIP_MARKER = "# SWCUB_OWNED_RESOURCE_SAFETY"


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    original = source
    if RUNTIME_MARKER not in source:
        old = f'''                self.container = self.client.containers.run(
                    "{PINNED}",'''
        new = f'''                {RUNTIME_MARKER}
                runtime_image = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "{PINNED}")
                self.container = self.client.containers.run(
                    runtime_image,'''
        if source.count(old) != 1:
            raise RuntimeError(f"Expected exactly one pinned provider image call in {path}")
        source = source.replace(old, new)

    if OVERLAY_MARKER not in source:
        runtime_line = f'''                runtime_image = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "{PINNED}")'''
        overlay_setup = '''
                # SWCUB_RAID1_OVERLAY_MOUNT
                overlay_host_dir = os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR")
                volume_mounts = {
                    os.path.abspath(path_to_vm): {"bind": "/System.qcow2", "mode": "ro"}
                }
                if overlay_host_dir:
                    Path(overlay_host_dir).mkdir(parents=True, exist_ok=True)
                    self.environment["SWCUB_VM_OVERLAY"] = f"/vm-overlay/osworld-{uuid.uuid4().hex}.qcow2"
                    volume_mounts[overlay_host_dir] = {"bind": "/vm-overlay", "mode": "rw"}'''
        if source.count(runtime_line) != 1:
            raise RuntimeError(f"Expected exactly one runtime image assignment in {path}")
        source = source.replace(runtime_line, runtime_line + overlay_setup)
        old_volumes = '''                    volumes={
                        os.path.abspath(path_to_vm): {
                            "bind": "/System.qcow2",
                            "mode": "ro"
                        }
                    },'''
        if source.count(old_volumes) != 1:
            raise RuntimeError(f"Expected exactly one provider volume mapping in {path}")
        source = source.replace(old_volumes, "                    volumes=volume_mounts,")

    if "import uuid\n" not in source:
        source = source.replace("import time\n", "import time\nimport uuid\n")

    if OWNERSHIP_MARKER not in source:
        imports = '''from pathlib import Path
\n# SWCUB_OWNED_RESOURCE_SAFETY
from swcub.resource_safety import (ResourceLedger, ensure_resource_identity,
                                   remove_verified_container, verify_container_identity)
'''
        if source.count("from pathlib import Path\n") != 1:
            raise RuntimeError(f"Expected one pathlib import in {path}")
        source = source.replace("from pathlib import Path\n", imports, 1)

        init_old = """        self.container = None
        self.environment = {"DISK_SIZE": "32G", "RAM_SIZE": "4G", "CPU_CORES": "4"}  # Modify if needed
"""
        init_new = """        self.container = None
        self._swcub_identity = ensure_resource_identity()
        self._swcub_container_id = None
        self.environment = {"DISK_SIZE": "32G", "RAM_SIZE": "4G", "CPU_CORES": "4"}  # Modify if needed
"""
        if source.count(init_old) != 1:
            raise RuntimeError(f"Expected one DockerProvider container initialization in {path}")
        source = source.replace(init_old, init_new, 1)

        call_end = """                    detach=True
                )
"""
        call_end_new = """                    detach=True,
                    labels=self._swcub_identity.labels,
                )
                self._swcub_container_id = self.container.id
                self.container.reload()
                verify_container_identity(self._swcub_container_id,
                                          self.container.attrs, self._swcub_identity)
                ResourceLedger(self._swcub_identity.ledger_path).created_container(
                    self._swcub_container_id, self._swcub_identity,
                    name=self.container.name, image=runtime_image)
"""
        if source.count(call_end) != 1:
            raise RuntimeError(f"Expected one Docker container run terminator in {path}")
        source = source.replace(call_end, call_end_new, 1)

        exception_cleanup_old = """        except Exception as e:
            # Clean up if anything goes wrong
            if self.container:
                try:
                    self.container.stop()
                    self.container.remove()
                except:
                    pass
            raise e
"""
        exception_cleanup_new = """        except Exception:
            if self.container:
                self._swcub_cleanup_container("start_emulator_error")
            raise
"""
        if source.count(exception_cleanup_old) != 1:
            raise RuntimeError(f"Expected one DockerProvider start failure cleanup block in {path}")
        source = source.replace(exception_cleanup_old, exception_cleanup_new, 1)

        method_marker = "    def get_ip_address(self, path_to_vm: str) -> str:\n"
        safe_method = """    def _swcub_cleanup_container(self, reason: str) -> None:
        if self.container is None:
            return
        if self._swcub_container_id is None:
            raise RuntimeError("refusing cleanup: no recorded full container ID")
        remove_verified_container(self.container, self._swcub_identity, reason=reason)
        self.container = None
        self._swcub_container_id = None
        self.server_port = None
        self.vnc_port = None
        self.chromium_port = None
        self.vlc_port = None

"""
        if source.count(method_marker) != 1:
            raise RuntimeError(f"Expected one get_ip_address method in {path}")
        source = source.replace(method_marker, safe_method + method_marker, 1)

        stop_old = """    def stop_emulator(self, path_to_vm: str, region=None, *args, **kwargs):
        # Note: region parameter is ignored for Docker provider
        # but kept for interface consistency with other providers
        if self.container:
            logger.info("Stopping VM...")
            try:
                self.container.stop()
                self.container.remove()
                time.sleep(WAIT_TIME)
            except Exception as e:
                logger.error(f"Error stopping container: {e}")
            finally:
                self.container = None
                self.server_port = None
                self.vnc_port = None
                self.chromium_port = None
                self.vlc_port = None
"""
        stop_new = """    def stop_emulator(self, path_to_vm: str, region=None, *args, **kwargs):
        # Note: region parameter is ignored for Docker provider.
        # Remove only the full-ID container created and ledgered by this run.
        if self.container:
            logger.info("Stopping verified project Guest container...")
            self._swcub_cleanup_container("provider.stop_emulator")
            time.sleep(WAIT_TIME)
"""
        if source.count(stop_old) != 1:
            raise RuntimeError(f"Expected one DockerProvider stop method in {path}")
        source = source.replace(stop_old, stop_new, 1)

    if source != original:
        path.write_text(source, encoding="utf-8")
    return source != original


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("osworld_v2_dir", type=Path)
    args = parser.parse_args()
    path = args.osworld_v2_dir / "desktop_env/providers/docker/provider.py"
    changed = patch(path)
    print(f"patched={changed} provider={path}")
    print(f"default_runtime_image={PINNED}")


if __name__ == "__main__":
    main()
