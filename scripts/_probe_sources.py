"""One-shot probe of live connectome sources (dev helper)."""
from __future__ import annotations

import os

import requests
from neuprint import Client, fetch_custom

token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
c = Client("neuprint.janelia.org", dataset="hemibrain:v1.2.1", token=token)
queries = {
    "CX": r"n.type =~ '(?i)^(EPG|PEN|PEG|Delta7|PFN|PFL|EL|ER|ExR|LNO).*'",
    "MB": r"n.type =~ '(?i)^(KC|MBON|DAN|APL).*'",
    "OL": r"n.type =~ '(?i)^(T4|T5|L[1-5]|Mi[0-9]|Tm[0-9]|Dm[0-9]|C[2-3]).*'",
}
for name, where in queries.items():
    df = fetch_custom(f"MATCH (n:Neuron) WHERE {where} RETURN count(n) AS n", client=c)
    print(name, int(df.n.iloc[0]))

r = requests.get(
    "https://neuprint.janelia.org/api/dbmeta/datasets",
    headers={"Authorization": f"Bearer {token}"},
    timeout=60,
)
print("datasets status", r.status_code)
if r.ok:
    data = r.json()
    keys = list(data.keys()) if isinstance(data, dict) else data
    print("neuprint datasets:", keys[:30])

r2 = requests.get("https://insectbraindb.org/api/v2/species/", timeout=60)
print("ibdb", r2.status_code)
if r2.ok:
    for s in r2.json()[:20]:
        print(" ", s.get("id"), s.get("scientific_name") or s.get("name"), s)
