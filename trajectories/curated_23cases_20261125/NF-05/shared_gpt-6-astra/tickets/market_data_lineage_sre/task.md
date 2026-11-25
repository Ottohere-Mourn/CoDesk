# Work Order — Market-Data DAG Backfill Lineage & Partition Skew Triage (`market_data_lineage_sre`)

## Context & Objective
Audit the 5-stage market-data pipeline on `http://127.0.0.1:19505/etl-lineage` in Chromium alongside ``/workspace/docs/Lineage_Replay_Runbook.pdf``, ``/workspace/docs/flink_repartition_topology_scan.png``, and ``/workspace/telemetry/kafka_partition_events.jsonl``.

## Deliverables
- Write ``/workspace/lineage_sre_audit.json`` conforming to Section 4 of ``Lineage_Replay_Runbook.pdf``, covering deduplicated partition watermark/dead-letter counts, critical-path replay latency before and after key-salting the bottleneck operator, transitive downstream blast radius of corporate-action enrichment, and the replay manifest token.
