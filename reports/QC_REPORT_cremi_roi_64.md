# QC report — CREMI Sample A ROI

- Coverage claim: `ROI`
- Dataset: `cremi_sample_a`
- ROI origin (z,y,x): `(0, 256, 960)`
- ROI shape: `(64, 64, 64)`
- SOURCE_DOCUMENTED synapses in ROI: `12`
- Graph nodes: `5`
- Graph edges: `4`

## Segmentation metrics vs CREMI neuron_ids (baseline watershed)

- **variation_of_information**: `4.662088780578642`
- **vi_split**: `1.2134000873181352`
- **vi_merge**: `3.4486886932605074`
- **adapted_rand_error**: `0.7893244645235714`
- **gt_neuron_count**: `78`
- **pred_label_count**: `125`

## Findings

- `medium` **SYNAPSE_OUTSIDE_SEGMENTATION**: 8 synapses could not be assigned to neuron labels in ROI
- `info` **LABEL_COUNT**: Segmentation contains 125 positive label ids

## Integrity notes

- Baseline segmentation is `MODEL_PREDICTED` and is **not** claimed as proofread biology.
- Connectome edges use CREMI `SOURCE_DOCUMENTED` partner annotations only.
- Proximity was never used to invent synapses.
