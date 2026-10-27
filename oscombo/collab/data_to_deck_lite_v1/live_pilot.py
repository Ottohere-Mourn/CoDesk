"""Data-to-Deck Lite v1 CLI, reusing the verified original Guest runner."""
from __future__ import annotations
import sys
from oscombo.collab.data_to_deck.live_pilot import main


if __name__ == "__main__":
    main(["--case-lite-v1", *sys.argv[1:]])
