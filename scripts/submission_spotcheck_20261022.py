"""Single frozen submission spot-check; developer-authored, not independent accuracy."""
import asyncio
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import transfer_study as study
from backend import store
study.PROTOCOL=study.ROOT/'artifacts/handoff-20261022/spotcheck-protocol.json'
study.ARTIFACTS=study.ROOT/'artifacts/handoff-20261022'
def freeze():
 if study.PROTOCOL.exists(): raise RuntimeError('Do not overwrite frozen protocol')
 file='1706.03762v1.pdf'
 doc=next(d for d in store.list_documents() if d['name']==file)
 blocks={b['id']:b for b in store.get_blocks(doc['id'])}
 specs=[
 ('scaling','为什么Transformer要把注意力点积乘以1/√dk？请说明dk较大时的现象、作者的解释，并区分实验观察和推测。',['cf181c56b46556d04d06e479'],['dk较大时未缩放点积注意力不如加性注意力','作者推测点积幅值增大影响softmax后的有效梯度，不能说成严格证明','以1/√dk缩放'],False),
 ('ffn','Transformer的逐位置前馈网络包含什么操作？参数在不同位置之间是否共享，在不同层之间是否共享？请分别回答。',['837a63eae1993f4384849a1c','edd3c7fc5944701cc35bc910'],['两次线性变换中间为ReLU','不同位置共享同层变换','不同层采用不同参数'],False),
 ('embeddings','论文3.4节中，哪些部分共享同一个权重矩阵？嵌入层还对权重进行了什么缩放？',['4512687a6871e326e423c1b8'],['输入和输出两套嵌入及pre-softmax线性变换共享同一个权重矩阵','嵌入层乘以√dmodel'],False),
 ('missing_h100','这篇2017年的论文报告了单张H100训练Transformer big时的实测峰值显存吗？若没有，不能估算GB数，也不能用P100硬件数量替代显存。',[],['不提供H100实测峰值显存数字，明确依据不足或未找到'],True)]
 cases=[dict(id=i,split='confirmation',files=[file],question=q,sources=[blocks[b] for b in ids],gold_facts=f,unanswerable=u) for i,q,ids,f,u in specs]
 protocol=dict(created_at=datetime.now(timezone.utc).isoformat(),notice='提交前一次性开发者抽查；问题和判分依据先冻结。论文已参与开发，不是独立盲测，所有失败保留，不用于总体准确率。',rubric={'reviewer':'同一开发助手核对原文，非独立人工','complete':'全部要点正确','partial':'遗漏要点','wrong':'实质错误','abstained':'可答题未答','correct_abstention':'缺信息题未编造','error':'异常计入总数'},settings={'case_timeout_seconds':240,'method_order':['product']},papers={file:{'id':doc['id'],'title':doc['title'],'pdf_sha256':study.digest(store.get_document(doc['id'])['path'])}},cases=cases)
 study.write(study.PROTOCOL,protocol)
 study.write(study.PROTOCOL.parent/'freeze.json',{'protocol_sha256':study.digest(study.PROTOCOL),'code_sha256':study.code_hashes()})
 print('Frozen four cases',study.digest(study.PROTOCOL),flush=True)
if __name__=='__main__':
 freeze()
 asyncio.run(study.run('confirmation','spotcheck-once',True))
