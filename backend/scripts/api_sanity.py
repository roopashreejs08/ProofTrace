import sys

sys.path.insert(0, ".")

from app.clients.crossref import CrossrefClient
from app.clients.http import ApiClient
from app.clients.openalex import OpenAlexClient
from app.memory import Memory


api = ApiClient(Memory("sanity.db"))

doi = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "10.1038/nature14539"
)

cr = CrossrefClient(api)
oa = OpenAlexClient(api)

print("CROSSREF :", cr.by_doi(doi))
print("OPENALEX :", oa.by_doi(doi))
print("UPDATES  :", cr.updates_for(doi))