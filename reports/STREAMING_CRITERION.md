# Streaming storage criterion

Success criterion: open/explore a source whose **remote size ≥ 100× local free-disk budget**,
while cache stays ≤ 10 GB and the app never attempts a full EM download.

| Connectome | Local bytes | Remote bytes | Ratio | Pass (≥100×) |
|---|---:|---:|---:|:---:|
| `hemibrain_pen_a_v0.1` | 87,578 | 28,587,302,322,176 | 326421045× | YES |
| `hemibrain_epg_v0.1` | 12,202,804 | 28,587,302,322,176 | 2342683× | YES |
| `optic_lobe_t4_v0.1` | 13,072,443 | 5,497,558,138,880 | 420546× | YES |
| `manc_sample_v0.1` | 1,514,168,707 | 8,796,093,022,208 | 5809× | YES |
| `cremi_sample_a_v0.2` | 170,884 | 183,500,800 | 1074× | YES |
| `bombus_terrestris_cx_projectome_v0.1` | 19,865,451 | 0 | — |
| `megalopta_ibdb_morphology_v0.1` | 30,390 | 0 | — |
| `rhyparobia_ibdb_morphology_v0.1` | 25,579 | 0 | — |
| `schistocerca_ibdb_morphology_v0.1` | 45,783 | 0 | — |

## Demonstration pack

- Connectome: `hemibrain_pen_a_v0.1`
- Local Tier-0/1: **0.08 MB**
- Remote EM ecosystem referenced: **26.0 TB**
- Ratio: **326421045×** (criterion ≥ 100×)
- Cache recommendation: 5 GB (hard ceiling 10 GB)
- Behavior: neuron index + graph local; skeletons streamed/cached; EM cutouts on demand only.

PASS
