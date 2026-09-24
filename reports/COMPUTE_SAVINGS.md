# Compute savings (estimates)

Values are order-of-magnitude estimates for planning — not audited billing figures.

| dataset_id | if reconstructed from EM (est.) | reuse-based path | avoided work |
|---|---|---|---|
| flywire_codex | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| hemibrain_neuprint | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| cremi_sample_a | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| cremi_sample_b | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| cremi_sample_c | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| banc_drosophila_2025 | weeks–months GPU/CPU + multi-TB I/O (ESTIMATE) | seconds–minutes API/HDF annotation import | segmentation + synapse detection + proofreading |
| flyem_medulla_training2_gt | days–weeks (ESTIMATE) | hours on missing stages only | re-segmentation of existing labels |
| bombus_cx_projectome_sayre2021 | UNKNOWN | UNKNOWN | UNKNOWN |
| aedes_antennal_lobe_bao2025 | ROI-first days (ESTIMATE); full volume last resort | none yet — gap fill only | 0% until partial products appear |
| heinze_cx_army_ant_2026 | N/A | wait for deposit | N/A — inaccessible |
| heinze_cx_cockroach_2026 | N/A | wait for deposit | N/A — inaccessible |
| heinze_cx_earwig_2026 | N/A | wait for deposit | N/A — inaccessible |
| heinze_cx_locust_2026 | N/A | wait for deposit | N/A — inaccessible |
| heinze_cx_mantis_2026 | N/A | wait for deposit | N/A — inaccessible |
| heinze_cx_sweat_bee_2026 | N/A | wait for deposit | N/A — inaccessible |

## Principle

Ideal operation: **zero new EM segmentation**.
Second-best: tiny unresolved ROI.
Full-volume reconstruction: absolute last resort.
