"""Real local-model checks; controlled perturbations are not independent accuracy data."""
import asyncio,json,hashlib,time
from pathlib import Path
import httpx
from backend import audit,model,review,store
ROOT=Path('artifacts/version-review-quality');ROOT.mkdir(exist_ok=True)

async def main():
    with store.connection() as c:
        snapshot={t:{str(r['id']):hashlib.sha256(json.dumps(dict(r),sort_keys=True,ensure_ascii=False).encode()).hexdigest() for r in c.execute('SELECT * FROM '+t)} for t in ['documents','blocks','evidence_notes','artifacts']}
    (ROOT/'before.json').write_text(json.dumps(snapshot),encoding='utf8')
    cases=[
        ('synthetic_batch','The batch size is 64.','The batch size is 128.','训练批大小是否改变？','claim_changed'),
        ('synthetic_negation','The model does converge.','The model does not converge.','模型是否收敛？','claim_changed'),
        ('synthetic_equivalent','The rate is 0.001.','The rate is 1e-3.','学习率是否改变？','same_claim'),
        ('synthetic_distractor','We use 8 GPUs. The score is 25.','We use 8 GPUs. The score is 30.','训练 GPU 数量是否改变？','same_claim'),
    ]
    results=[]
    async with httpx.AsyncClient(timeout=80,trust_env=False) as client:
        for name,old,new,observation,expected in cases:
            item={'status':'review_required','note':{'note':observation,'quote':old},'candidate':{'text':new}}
            started=time.monotonic();value=await review.review_change(item,client,model.URL,model.NAME)
            results.append({'id':name,'kind':'controlled perturbation, not real paper revision','expected':expected,'item':item,'result':value,'seconds':round(time.monotonic()-started,2)})
            (ROOT/'local-model-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
            print(name,value.get('decision',value.get('status')),flush=True)
        target=next(d for d in store.list_documents() if d.get('arxiv_id')=='1706.03762' and d.get('version')==7)
        aligned=audit.audit_against(target['id'])
        for item in aligned['results']:
            value=await review.review_change(item,client,model.URL,model.NAME)
            results.append({'id':'real-note-'+str(item['note']['id']),'kind':'real Attention v1/v7 saved note','item':item,'result':value})
        (ROOT/'local-model-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    # Force a known wrong model answer to demonstrate the guard's exact boundary.
    value={'decision':'same_claim','reason':'相同','old_indices':[0],'new_indices':[0]}
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(value)}}]}))
    item={'status':'review_required','note':{'note':'GPU count','quote':'We use 8 GPUs.'},'candidate':{'text':'We use 16 GPUs.'}}
    async with httpx.AsyncClient(transport=transport) as client:checked=await review.review_change(item,client,'http://test','test')
    (ROOT/'controlled-wrong-model.json').write_text(json.dumps({'input':item,'raw_response':value,'checked':checked},ensure_ascii=False,indent=2),encoding='utf8')
asyncio.run(main())
