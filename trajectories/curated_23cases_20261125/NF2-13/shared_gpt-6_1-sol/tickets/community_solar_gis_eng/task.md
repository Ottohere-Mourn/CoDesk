# Work Order — Community Solar Parcel GIS Screening & Feeder MVA Allocation (`community_solar_gis_eng`)

## Objective
Screen `SOLAR_PV` queue sites on the shared `interconnection_queue` layer in ``/workspace/shared_docs/substation_interconnection.qgs`` (open in **QGIS 3.22**, backed by ``/workspace/shared_docs/interconnection_queue.geojson` and `feeder_corridors.geojson`), evaluate curtailed hosting capacity in ``/workspace/pv_parcels.sqlite``, commit your solar feeder MVA in ``/workspace/shared_docs/grid_interconnection.sqlite`` and ``/workspace/shared_docs/Substation_MVA_Schedule.xlsx`` (open in Calc) per ``/workspace/docs/SOP_Solar_GIS.pdf`` and ``/workspace/exhibits/substation_n1_limit.png``, and write ``/workspace/solar_hosting_audit.json``.
