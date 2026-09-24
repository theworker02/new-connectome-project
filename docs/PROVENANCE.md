# Provenance

Every atlas object must remain traceable.

Observed synaptic edge:

`edge → synapse table / adjacency record → dataset version → publication`

Morphology:

`skeleton → source database (neuPrint / IBdb / CATMAID) → dataset → publication`

Geometry kinds that are not EM arbors (e.g. CREMI `SYNAPSE_SITE_STAR`) must set `geometry_kind` in skeleton metadata and must not be labeled as observed morphology arbors.
