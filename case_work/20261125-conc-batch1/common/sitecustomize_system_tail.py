"""Append the existing Debian package directory after the active venv."""
import sys

system_packages = "/usr/lib/python3/dist-packages"
if system_packages not in sys.path:
    sys.path.append(system_packages)

# Resolve the binary Pillow extension while the virtual environment still has
# precedence.  Some OSWorld modules subsequently insert the checkout root at
# the front of sys.path; caching this binding prevents Debian's incompatible
# Pillow build from shadowing the venv's compiled image module.
import requests  # noqa: E402
from PIL import Image, ImageStat  # noqa: E402,F401
