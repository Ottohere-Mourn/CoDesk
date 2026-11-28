"""Opt-in Python startup hook for BC's isolated formal OSWorld runner process."""

import os

if os.environ.get("SWCUB_OSWORLD_STORAGE_HOST_DIR"):
    from pipeline.runner_hooks.raid_storage import install_raid_storage_hook
    install_raid_storage_hook()

if os.environ.get("CODEDESK_BC_RW_CLI") == "1":
    from pipeline.codex_config_hook import install_codex_harness_hook

    install_codex_harness_hook()

if os.environ.get("CODEDESK_BC_CAPTURE_PLAN"):
    from pipeline.runner_hooks.formal_capture import install_formal_capture_hook

    install_formal_capture_hook()
