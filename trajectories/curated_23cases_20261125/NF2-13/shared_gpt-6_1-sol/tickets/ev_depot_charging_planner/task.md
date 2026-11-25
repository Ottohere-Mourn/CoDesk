# Work Order — Transit EV DCFC Depot Harmonic MVA Sizing & Feeder Allocation (`ev_depot_charging_planner`)

## Objective
Screen `EV_DCFC` depot entries on the shared `interconnection_queue` layer in ``/workspace/shared_docs/substation_interconnection.qgs`` (open in **QGIS 3.22**, backed by ``/workspace/shared_docs/interconnection_queue.geojson` and `feeder_corridors.geojson`), size fleet DCFC apparent power across ``/workspace/ev_depots.sqlite``, commit your EV depot MVA allocation in ``/workspace/shared_docs/grid_interconnection.sqlite`` and ``/workspace/shared_docs/Substation_MVA_Schedule.xlsx`` (open in Calc) per ``/workspace/docs/SOP_EV_Interconnect.pdf`` and ``/workspace/exhibits/substation_n1_limit.png``, and write ``/workspace/ev_interconnect_audit.json``.
