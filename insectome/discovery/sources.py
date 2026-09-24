"""Seeded discovery notes — verify before promoting to registry."""

from __future__ import annotations

KNOWN_SOURCES = [
    {
        "name": "BossDB",
        "url": "https://bossdb.org/projects",
        "method": "Browse tagged TEM/ssTEM projects; verify insect species on project page.",
    },
    {
        "name": "CREMI",
        "url": "https://cremi.org/data/",
        "method": "Challenge volumes with neuron + synapse GT (Drosophila).",
    },
    {
        "name": "Janelia FlyEM source data",
        "url": "https://www.janelia.org/open-science/flyem-connectome-project-em-neural-circuits-source-data",
        "method": "Small GT cubes; check whether figshare is link-only.",
    },
    {
        "name": "Virtual Fly Brain EM docs",
        "url": "https://www.virtualflybrain.org/docs/data/em/",
        "method": "Catalog of Drosophila EM reconstructions (often existing connectomes).",
    },
    {
        "name": "EMPIAR",
        "url": "https://www.ebi.ac.uk/empiar/",
        "method": "Search volume-EM insect entries; require verified accession before registry.",
    },
    {
        "name": "Insect Brain Database",
        "url": "https://insectbraindb.org/",
        "method": "Often skeletons/atlases; confirm raw EM separately.",
    },
    {
        "name": "Heinze comparative CX preprint",
        "url": "https://doi.org/10.64898/2026.02.25.708065",
        "method": "Track data deposition; code is public, raw EM not verified public.",
    },
]


def list_sources() -> list[dict]:
    return list(KNOWN_SOURCES)
