# Storage report

Objective: a multi-TB remote dataset should require only MB–low-GB locally.

| dataset_id | reuse % | level | remote raw (est.) | local required (est.) | offline pack (est.) |
|---|---:|---:|---:|---:|---:|
| flywire_codex | 100 | 0 | 26624.00 GB | 50.00 MB | 300.00 MB |
| hemibrain_neuprint | 100 | 0 | 26624.00 GB | 50.00 MB | 300.00 MB |
| cremi_sample_a | 92 | 0 | 175.00 MB | 2.00 MB | 500.00 KB |
| cremi_sample_b | 92 | 0 | 175.00 MB | 2.00 MB | 500.00 KB |
| cremi_sample_c | 92 | 0 | 175.00 MB | 2.00 MB | 500.00 KB |
| banc_drosophila_2025 | 90 | 0 | 51200.00 GB | 100.00 MB | 500.00 MB |
| flyem_medulla_training2_gt | 60 | 3 | UNKNOWN | UNKNOWN | UNKNOWN |
| bombus_cx_projectome_sayre2021 | 50 | 4 | UNKNOWN | 50.00 MB | 50.00 MB |
| aedes_antennal_lobe_bao2025 | 0 | 6 | 5120.00 GB | 5.00 MB | UNKNOWN |
| heinze_cx_army_ant_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |
| heinze_cx_cockroach_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |
| heinze_cx_earwig_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |
| heinze_cx_locust_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |
| heinze_cx_mantis_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |
| heinze_cx_sweat_bee_2026 | 0 | 99 | UNKNOWN | UNKNOWN | UNKNOWN |

## Notes

- Estimates marked UNKNOWN when publishers do not state sizes.
- `local required` assumes reuse-first import (graph/metadata), not full EM.
- Cache hard limit default: 10 GB (`~/.insectome/cache`).
