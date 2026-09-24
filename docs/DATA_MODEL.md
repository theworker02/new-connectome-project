# Atlas data model

## Global neuron ID

`species/specimen/dataset/source_id`

Example: `drosophila_melanogaster/hemibrain_v1_2_1/hemibrain/387364605`

## Packs (`data/connectomes/<id>/`)

| File | Role |
|---|---|
| `nodes.parquet` | Neuron table |
| `edges.parquet` | Sparse synaptic edges |
| `synapses.parquet` | Optional synapse loci |
| `neuron_index.parquet` | Searchable atlas index |
| `skeletons/*.skbin` | Compact binary skeletons |
| `skeletons/*.lod.skbin` | Display LOD |
| `connectome_manifest.json` | Coverage, provenance, atlas flags |

## Graph layers

- `OBSERVED_MORPHOLOGY`
- `OBSERVED_SYNAPTIC`
- `INFERRED_CIRCUIT` (never mixed into observed edges)
