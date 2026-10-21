"""Second dated public-source audit; preserves prior snapshot."""
import concurrent.futures
import json
from pathlib import Path
import audit_competitor_sources as audit

audit.ROOT = Path('artifacts/competitor-audit-2026-10-14')
audit.ROOT.mkdir(parents=True, exist_ok=True)
EXTRA = [
 ('pubmed','PubMed','https://pubmed.ncbi.nlm.nih.gov/'),
 ('europepmc','Europe PMC','https://europepmc.org/'),
 ('openalex','OpenAlex','https://openalex.org/'),
 ('dimensions','Dimensions','https://www.dimensions.ai/'),
 ('lens','The Lens','https://www.lens.org/'),
 ('sciencedirect','ScienceDirect','https://www.sciencedirect.com/'),
 ('springer','Springer Nature Link','https://link.springer.com/'),
 ('ieee','IEEE Xplore','https://ieeexplore.ieee.org/'),
 ('acm','ACM Digital Library','https://dl.acm.org/'),
 ('arxiv','arXiv','https://arxiv.org/'),
 ('perplexity','Perplexity','https://www.perplexity.ai/'),
 ('semantic-reader','Semantic Reader','https://www.semanticscholar.org/product/semantic-reader'),
 ('scinapse','Scinapse','https://www.scinapse.io/'),
 ('keenious','Keenious','https://keenious.com/'),
 ('scholarai','ScholarAI','https://scholarai.io/'),
 ('sourcely','Sourcely','https://www.sourcely.net/'),
]
if __name__ == '__main__':
 for filename, sites in [('sources.json',audit.SITES + EXTRA), ('traffic.json', [('traffic-'+d.replace('.','-'),d,'https://www.semrush.com/website/'+d+'/overview/') for d in ['semanticscholar.org','researchgate.net','academia.edu','scispace.com','consensus.app','elicit.com','overleaf.com','arxiv.org','pubmed.ncbi.nlm.nih.gov','sciencedirect.com','scite.ai','researchrabbit.ai','perplexity.ai','notebooklm.google.com']])]:
  results=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   for item in pool.map(audit.fetch, sites):
    results.append(item)
    (audit.ROOT/filename).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(item['id'],item.get('status'),item.get('chars'),item.get('error','')[:80],flush=True)
