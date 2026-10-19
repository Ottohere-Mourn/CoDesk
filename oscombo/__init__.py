"""oscombo: composite OSWorld tasks -- several official OSWorld tasks on one shared desktop.

Layers (each one replaceable):
  osworld.py   locate the OSWorld checkout, load tasks, read scores
  guest.py     the shared Guest (DesktopEnv + the in-VM HTTP server)
  combo.py     boot, multi-task setup, decoupled multi-task evaluation
  harness/     how an agent drives the Guest (step loop around a policy, or an external process)
  policies/    which model decides the next action inside the step loop
  runner.py    run modes (solo / sequential / parallel / isolated / shadow) and the result record
"""
__version__ = "0.1.0"
