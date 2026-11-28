# BC-04 tool adaptation: GIMP in place of Inkscape

The approved Guest dependency probe found Google Chrome and GIMP, but not Inkscape. BC-04 therefore keeps `launch_board.svg` as the editable source of truth, uses the standard-library XML tooling/Guest CLI or another available editor to update SVG elements, and uses Chrome's local preview/crop routes plus GIMP to inspect the exported raster crops. It does not pretend that GIMP is a vector editor or require Inkscape.

The host Oracle checks SVG structure and exact content, PNG signatures/dimensions, and a host-collected preview receipt whose SVG digest must match the final source. This is a deterministic structural/export check, not pixel-semantic image understanding. The current tests do not prove a real Guest rendering or GIMP GUI launch. Those must be verified through the Shared production adapter before BC-04 is queue-admitted.

Relevant implementation:

- `cases/BC-04/guest/setup.py`: English seed SVG, output tree and optional local preview startup.
- `cases/BC-04/guest/board_service.py`: loopback live preview plus `/hero.svg` and `/pricing.svg` crop responses.
- `cases/BC-04/prompts/`: role-scoped English tasks with GIMP visual QA and open GUI/Guest CLI access.
- `cases/BC-04/oracle/oracle.py`: host-only deterministic checks; never copy this directory to the Guest.
