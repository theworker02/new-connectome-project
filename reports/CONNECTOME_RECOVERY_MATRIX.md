# Connectome Recovery Matrix

**Audit date:** 2026-09-22  
**Phase:** 3 — Multi-species assembly, recovery & reconstruction  
**Rule:** `FOUND` only when the artifact is accessible or availability was directly verified.  
**Deep-search log:** `reports/PHASE3_SEARCH_LOG.md`

Legend: **Y** = public/local; **R** = remote API (token/request); **—** = `PUBLIC_ARTIFACT_NOT_FOUND`; **P** = partial; **Req** = request-only (not anonymous public).

## Drosophila reference (reuse, do not merge specimens)

| Species | Dataset | Region | Raw EM | Aligned EM | Skeletons | Segmentation | Synapses | Annotations | Connectivity | Proofreading | Local storage | Remaining work |
|---------|---------|--------|--------|------------|-----------|--------------|----------|-------------|--------------|--------------|---------------|----------------|
| D. melanogaster | hemibrain neuPrint v1.2.1 | central brain | R | R | R | R | Y | Y | Y | Y | packs: `hemibrain_epg_v0.1`, `hemibrain_pen_a_v0.1` | optional larger typed packs |
| D. melanogaster | MANC neuPrint v1.2.3 | male VNC | R | R | R | R | Y | Y | Y | Y | `manc_sample_v0.1` (~1.4 GB) | consider typed subpacks to shrink |
| D. melanogaster | optic-lobe neuPrint v1.1 | optic lobe | R | R | R | R | Y | Y | Y | Y | `optic_lobe_t4_v0.1` | more cell-type packs |
| D. melanogaster | male-cns neuPrint v1.0 | whole CNS | R | R | R | R | R | R | R | Y | not imported | import typed subgraph |
| D. melanogaster | FlyWire / FAFB | whole brain | R | R | R | R | Y (Zenodo feather) | Y | Y | Y | not imported | optional offline pack (~852 MB connections) |
| D. melanogaster | BANC / FANC | CNS / VNC | R | R | R | R | R | R | R | Y | not imported | BossDB/VFB adapters |
| D. melanogaster | CREMI sample A | EM challenge ROI | Y | Y | — | Y (GT) | Y | Y | Y | N/A | `cremi_sample_a_v0.2` | validation ROI only |

## Heinze / Gillet 2026 six-species central complex

Paper: eLife reviewed preprint **110789** / bioRxiv **10.64898/2026.02.25.708065**.

**Data availability (verbatim summary):** code on GitHub (Heinze-lab); skeletons & figure-4 segmentation *upon publication* → Insect Brain Database; CAVE (segmentation + synapses) *upon request*. CATMAID hosted on private Tedore Interactive servers.

| Species | Dataset | Region | Raw EM | Aligned EM | Skeletons | Segmentation | Synapses | Annotations | Connectivity | Proofreading | Local storage | Remaining work |
|---------|---------|--------|--------|------------|-----------|--------------|----------|-------------|--------------|--------------|---------------|----------------|
| Megalopta genalis (sweat bee) | Heinze CX 2026 | CX multi-res | — | — (SOFIMA code Y) | — (2026); **Y** prior IBdb morph (33) | Req CAVE | Req CAVE | P | — synaptic; morph pack Y | Req CAVE | `megalopta_ibdb_morphology_v0.1` | await IBdb upload / CAVE grant |
| Eciton hamatum (army ant) | Heinze CX 2026 | CX multi-res | — | — | — | Req | Req | — | — | Req | none | deposit / collaboration |
| Schistocerca gregaria (locust) | Heinze CX 2026 | CX multi-res | — | — | — (2026); **Y** prior IBdb morph (60) | Req | Req | P | morph only | Req | `schistocerca_ibdb_morphology_v0.1` | await 2026 skeletons |
| Sphodromantis lineola (mantis) | Heinze CX 2026 | CX multi-res | — | — | — | Req | Req | — | — | Req | none | deposit / collaboration |
| Rhyparobia maderae (cockroach) | Heinze CX 2026 | CX multi-res | — | — | — (2026); **Y** prior IBdb morph (22) | Req | Req | P | morph only | Req | `rhyparobia_ibdb_morphology_v0.1` | await 2026 skeletons |
| Forficula auricularia (earwig) | Heinze CX 2026 | CX multi-res | — | — | — | Req | Req | — | — | Req | none | highest priority when released (~1 TB class) |

## Related non-fly recoverable (not the 2026 six)

| Species | Dataset | Region | Raw EM | Aligned EM | Skeletons | Segmentation | Synapses | Annotations | Connectivity | Proofreading | Local storage | Remaining work |
|---------|---------|--------|--------|------------|-----------|--------------|----------|-------------|--------------|--------------|---------------|----------------|
| Bombus terrestris | Sayre et al. 2021 IBdb EIN-0000061 | CX projectome | — | — | Y | — | — | P | morph projectome only | manual tracing | `bombus_terrestris_cx_projectome_v0.1` (678 n) | synaptic graph if ever released |

## Assembled local connectome packs (queryable now)

| Pack ID | Species | Layer | Neurons | Edges / synapses | Notes |
|---------|---------|-------|---------|------------------|-------|
| `hemibrain_epg_v0.1` | Drosophila | OBSERVED_SYNAPTIC | 50 | adjacency | CX head-direction validation |
| `hemibrain_pen_a_v0.1` | Drosophila | OBSERVED_SYNAPTIC | 20 | adjacency | typed subgraph |
| `manc_sample_v0.1` | Drosophila | OBSERVED_SYNAPTIC | 23609 | ~6.2M edges | large; keep as offline pack |
| `optic_lobe_t4_v0.1` | Drosophila | OBSERVED_SYNAPTIC | 3438 | adjacency | T4.* filter |
| `cremi_sample_a_v0.2` | Drosophila | OBSERVED_SYNAPTIC | 105 | 216 syn | GT import |
| `bombus_terrestris_cx_projectome_v0.1` | Bombus | OBSERVED_MORPHOLOGY | 678 | 0 | projectome |
| `megalopta_ibdb_morphology_v0.1` | Megalopta | OBSERVED_MORPHOLOGY | 33 | 0 | not 2026 EM |
| `rhyparobia_ibdb_morphology_v0.1` | Rhyparobia | OBSERVED_MORPHOLOGY | 22 | 0 | not 2026 EM |
| `schistocerca_ibdb_morphology_v0.1` | Schistocerca | OBSERVED_MORPHOLOGY | 60 | 0 | not 2026 EM |

## Gap ranking (information / GPU-hour) — no EM compute until public ROI exists

1. **Blocked:** Heinze 2026 CAVE materializations / CATMAID exports (collaboration request already sent).
2. **Blocked:** IBdb upload of 2026 skeletons (promised upon publication).
3. **Ready without EM:** Import male-cns / FlyWire feather / BANC typed packs as additional Drosophila references.
4. **Do not:** Re-segment or re-detect synapses for the six species while public EM is absent.

## Three-layer policy for multi-resolution CX (when data arrive)

| Layer | Content | Status today (six spp.) |
|-------|---------|-------------------------|
| OBSERVED_MORPHOLOGY | cellular-res projectome / skeletons | prior IBdb only for 3 spp.; 2026 = NOT_FOUND |
| OBSERVED_SYNAPTIC | high-res compartment synapses | REQUEST_ONLY |
| INFERRED_CIRCUIT | extrapolated from CX regularity | not constructed (would require observed synaptic seed) |
