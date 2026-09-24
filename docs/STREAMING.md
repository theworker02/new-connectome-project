# Zero-storage streaming architecture

Principle: **source size must not determine local disk use.**

```
LOCAL (≤5 GB metadata + ≤10 GB cache)
  Tier 0  neuron index, edges, annotations, pointers
  Tier 1  skeletons (on demand)
  Tier 2  meshes LOD (on demand, never whole brain)
  Tier 3  EM chunks (disposable)

REMOTE (TB–PB)
  Neuroglancer / neuPrint / DANDI / BossDB / CAVE / …
```

## Cache

`~/.insectome/cache` — content-addressable, weighted LRU.

```bash
insectome cache status
insectome cache set-limit --soft-gb 5 --hard-gb 10 --ram-mb 512
insectome cache clear --kinds em_chunk,mesh_hi
```

Eviction order preference: EM → hi mesh → lo mesh → rare skeletons. Metadata preserved longest.

`reserve(bytes)` must succeed before disk write; otherwise stream RAM-only / skip persist.

## RemoteVolume

```python
from insectome.remote.neuprint_remote import NeuPrintRemote
from insectome.remote.cremi_remote import CremiRemote
```

Methods: `get_metadata`, `get_skeleton`, `get_mesh`, `get_chunk`, `get_em_cutout`.

## Streaming manifests

```bash
insectome streaming-report
```

Writes `streaming_manifest.json` per pack + `reports/STREAMING_CRITERION.md`.

## Success criterion

Explore a connectome whose remote EM ecosystem is ≥100× local pack size, with cache ≤10 GB, without downloading the remote volume. Hemibrain EPG pack demonstrates this (TB-class remote vs MB-class local).
