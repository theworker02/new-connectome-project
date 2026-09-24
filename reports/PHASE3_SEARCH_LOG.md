# Phase 3 deep search log — 2026-09-22

Target: locate public derivatives for Heinze/Gillet 2026 six-species CX + assemble all recoverable graphs.

## Search paths completed

| # | Path | Result |
|---|------|--------|
| 1 | Primary publication (eLife 110789) | Pipeline described; no public volume URLs |
| 2 | Data availability section | Code public; skeletons → IBdb upon publication; CAVE upon request |
| 3 | Code availability / Heinze-lab GitHub | EMalign, EMtrain, EMsegment, LSDtoPCG, synful_312 — **code only**; zarr names like `megalopta_FB_1` are local conventions |
| 4 | ktedore/catmaid-neuroglancer(+api) | Viewer glue; no public CX volumes |
| 5 | bioRxiv 10.64898/2026.02.25.708065 | Same data policy; no accession IDs |
| 6 | Supplementary / figure supplements | Morphology & connectivity *figures*; no downloadable tables for full graphs |
| 7 | Insect Brain Database | Exp 61 Bombus projectome **FOUND**; 2026 six-species EM experiments **not public**; species morphologies for Megalopta/Rhyparobia/Schistocerca **FOUND** |
| 8 | EMPIAR | No matching six-species CX deposit found |
| 9 | BossDB | No matching deposit |
| 10 | Zenodo | SOFIMA tooling DOI only; no Heinze CX volumes |
| 11 | Figshare / Dryad / OSF | No verified CX EM/skeleton deposits for the six |
| 12 | CATMAID public instance | Private Tedore-hosted servers per Methods |
| 13 | CAVE public | Shared Tedore deployment; access by request |
| 14 | Neuroglancer public states | None found for these volumes |
| 15 | Google/AWS public buckets | No verified anonymous buckets |
| 16 | neuPrint / Codex / VFB | Drosophila only (used for reference packs) |
| 17 | Author / institutional repos | Lund Heinze-lab GitHub only (code) |
| 18 | Predecessor datasets | Sayre 2021 Bombus CX projectome on IBdb — assembled |
| 19 | DOI / accession follow-ups | No EMPIAR/BIA accession in Data availability |
| 20 | Email request | Sent to valentin.gillet@biol.lu.se, stanley.heinze@biol.lu.se (2026-09-22); draft deleted after send |

## Classification

For Heinze 2026 **raw EM, aligned EM, CATMAID skeletons, CAVE segmentation, synapse tables, connectivity matrices**:

**PUBLIC_ARTIFACT_NOT_FOUND** (as of 2026-09-22)

Recoverable substitutes:

- Drosophila neuPrint subgraphs + CREMI GT (synaptic graphs)
- Bombus IBdb projectome (morphology)
- Prior IBdb morphologies for three of the six species (morphology only — **not** the 2026 EM reconstructions)
