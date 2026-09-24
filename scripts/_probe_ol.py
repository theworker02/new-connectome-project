import os
from neuprint import Client, fetch_custom

token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
q = "MATCH (n:Neuron) WHERE n.type =~ '^(T4|T5).*' RETURN count(n) AS n"
for ds in ["optic-lobe:v1.1", "optic-lobe:v1.0.1", "hemibrain:v1.2.1"]:
    try:
        c = Client("neuprint.janelia.org", dataset=ds, token=token)
        df = fetch_custom(q, client=c)
        print(ds, int(df.n.iloc[0]))
    except Exception as e:
        print(ds, "ERR", e)
