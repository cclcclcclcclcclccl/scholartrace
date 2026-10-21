"""Build an offline research dashboard from the reviewed comparison report."""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPORT = DOCS / "竞品调研与功能界面对比_2026-10-13.md"
OUTPUT = DOCS / "竞品对照看板_2026-10-13.html"
text = REPORT.read_text(encoding="utf-8")


def rows(section):
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| ---")
    ]


catalog_section = text.split("## 三、", 1)[1].split("## 四、", 1)[0]
catalog = []
for category_section in catalog_section.split("### ")[1:]:
    category = category_section.splitlines()[0].split("：")[0]
    for cells in rows(category_section)[1:]:
        link = re.fullmatch(r"\[(.*?)\]\((https://.*?)\)", cells[0])
        assert link, cells[0]
        catalog.append(
            {"name": link[1], "url": link[2], "category": category,
             "evidence": cells[1], "features": cells[2], "lesson": cells[3]}
        )
assert len(catalog) == 40

traffic_section = text.split("## 二、", 1)[1].split("官方用户规模声明", 1)[0]
traffic = rows(traffic_section)[1:]
assert len(traffic) == 12
gaps = rows(text.split("## 四、", 1)[1].split("### 质量", 1)[0])[1:]
ui = rows(text.split("## 五、", 1)[1].split("截图索引", 1)[0])[1:]
scales = rows(text.split("官方用户规模声明", 1)[1].split("## 三、", 1)[0])[1:]


def safe_markdown(value):
    escaped = html.escape(value)
    return re.sub(
        r"\[(.*?)\]\((https://[^\s)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1 ↗</a>',
        escaped,
    )


def table(headings, records):
    header = "".join(f"<th scope='col'>{html.escape(h)}</th>" for h in headings)
    body = "".join("<tr>" + "".join(f"<td>{safe_markdown(c)}</td>" for c in record) + "</tr>" for record in records)
    return f"<div class='table-scroll' tabindex='0'><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


template = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>研证 · 40 个科研工具对照看板</title>
<style>
:root{color-scheme:light;--ink:#203e35;--muted:#53675e;--line:#d5e0d9;--green:#215d49;--pale:#edf4ee;--paper:#fff;--amber:#75521b}
*{box-sizing:border-box}body{margin:0;background:#f5f7f3;color:var(--ink);font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}a{color:#175c46;text-underline-offset:3px}button,input,select{font:inherit}button,select{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #ae7826;outline-offset:3px}.wrap{max-width:1360px;margin:auto;padding:36px 32px}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--muted);font-weight:700}h1{font-size:clamp(27px,4vw,43px);line-height:1.2;letter-spacing:-1px;margin:14px 0}h2{font-size:24px;margin:0 0 12px}h3{font-size:18px;margin:0 0 8px}p{margin:8px 0 16px}.lede{max-width:930px;color:var(--muted);font-size:17px}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}.stat{padding:16px 22px;background:var(--paper);border:1px solid var(--line);border-radius:12px;min-width:170px}.stat b{font-size:28px;margin-right:10px}.stat span{color:var(--muted);font-size:13px}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.tabs button{border:1px solid var(--line);border-radius:8px;background:white;padding:10px 18px;color:var(--ink)}.tabs button[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}.panel{background:var(--paper);padding:26px;border:1px solid var(--line);border-radius:16px}.panel[hidden]{display:none}.note{border-left:3px solid #acbeae;background:var(--pale);padding:13px 17px;font-size:14px;margin:18px 0}.toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:22px 0}label{display:flex;flex-direction:column;gap:5px;font-size:13px;font-weight:600;color:var(--muted)}input,select{border:1px solid #aabeb0;border-radius:7px;padding:10px 12px;background:white;color:var(--ink);max-width:100%}input{min-width:290px}.count{font-size:13px;color:var(--muted);margin:12px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.card{padding:20px;border:1px solid var(--line);border-radius:12px;background:#fdfefd;display:flex;flex-direction:column}.card h3 a{text-decoration:none}.badge{align-self:start;font-size:12px;padding:3px 8px;border-radius:5px;background:var(--pale);color:var(--green);margin-bottom:10px}.card p{font-size:14px;margin:6px 0 10px}.card .status{border-top:1px solid var(--line);padding-top:10px;font-size:12px;color:var(--muted);margin-top:auto}.card .status.limited{color:var(--amber)}.tiny{font-size:12px;color:var(--muted)}.table-scroll{overflow:auto;margin:14px 0 28px}table{border-collapse:collapse;width:100%;font-size:14px;min-width:800px}th{text-align:left;background:var(--pale);font-size:13px;color:var(--green)}td,th{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top}td:first-child{font-weight:650;min-width:140px}#scale table{min-width:660px}.compare{display:grid;grid-template-columns:1fr 1fr;gap:18px}.compare figure{margin:0;min-width:0}.compare label{margin-bottom:12px}.compare img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:9px}.compare figcaption{font-size:13px;color:var(--muted);margin:10px 0}.priority{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.priority article{border:1px solid var(--line);padding:20px;border-radius:12px}.priority ol{padding-left:23px}.priority li{margin:8px 0}.foot{margin-top:24px;color:var(--muted);font-size:13px}.empty{padding:28px;background:var(--pale);border-radius:12px}#reset{background:white;border:1px solid #aabeb0;border-radius:7px;padding:10px 14px}
@media(max-width:1000px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.wrap{padding:22px 14px}.panel{padding:18px 14px}.cards,.compare,.priority{grid-template-columns:1fr}.stat{min-width:0;flex:1;padding:10px}.stat b{display:block}.tabs button{padding:9px 12px}.toolbar label{width:100%}input{min-width:0;width:100%}h2{font-size:21px}}
</style></head><body><main class="wrap">
<div class="eyebrow">SCHOLARTRACE / COMPETITIVE RESEARCH / 2026.10.13</div>
<h1>科研工具很多，<br>我们要把什么做得更好？</h1>
<p class="lede">研证的下一步：让文献、证据和研究成果真正连起来。以公开来源、实际界面和现有代码为依据，区分缺失功能、成熟度差距与值得保留的特色。</p>
<div class="stats"><div class="stat"><b>40</b><span>相关产品</span></div><div class="stat"><b>12</b><span>公开访问量估计</span></div><div class="stat"><b>13</b><span>外部有效页面实拍</span></div><div class="stat"><b>14</b><span>功能比较维度</span></div></div>
<nav class="tabs" aria-label="报告内容"><button aria-pressed="true" aria-controls="catalog" data-tab="catalog">产品目录</button><button aria-pressed="false" aria-controls="scale" data-tab="scale">流量与规模</button><button aria-pressed="false" aria-controls="gaps" data-tab="gaps">功能差距</button><button aria-pressed="false" aria-controls="design" data-tab="design">界面对照</button><button aria-pressed="false" aria-controls="next" data-tab="next">改进顺序</button></nav>
<section class="panel" id="catalog"><h2>40 个产品，按任务找参考</h2><p>先看相关性，再看成熟度。下列“能力”来自公开说明或已有定位；受限项目明确标注，不代表全部已经实测。</p>
<div class="toolbar"><label>搜索名称、功能、可借鉴点<input id="search" type="search" placeholder="例如：引用、图谱、写作、Zotero"></label><label>产品类别<select id="category"><option value="">全部类别</option></select></label><label>证据筛选<select id="evidence"><option value="">全部证据状态</option><option value="limited">包含受限／待核验</option><option value="readable">已读到有效公开说明或界面</option></select></label><button id="reset" type="button">重置</button></div>
<p id="count" class="count" aria-live="polite"></p><div class="cards" id="cards"></div>
</section>
<section class="panel" id="scale" hidden><h2>哪些确实有较大规模</h2><div class="note">Semrush 是访问次数估计，绝不是月活用户数。不同网站可见月份不同，因此没有制作一个混月份的统一排名。2026 年 9 月与 8 月分别列出；没有数据不等于没有流量。</div>__TRAFFIC__<h3>官方用户声明：单独列示</h3><p>下表不是第三方审计。用户、机构、论文数量与访问次数不能混算；文案冲突如实保留。</p>__SCALES__</section>
<section class="panel" id="gaps" hidden><h2>功能覆盖已经广，深度和衔接仍需补齐</h2><div class="note">P0 = 可信度与主流程；P1 = 专业能力；P2 = 扩展。已有功能不重复当成缺失项，建议也不代表已经实现。</div>__GAPS__<p>特别注意：出处存在不等于结论正确。现有机械问答检查和 169 项后端测试，均不能替代独立语义准确性评测。</p></section>
<section class="panel" id="design" hidden><h2>界面实拍对照</h2><p>同样的桌面视口，观察主任务、内容空间和信息层级。点击截图查看原图。</p><div class="note">右侧部分是官网中的产品展示，不是登录工作台；不能用营销页直接评判复杂任务效率。所有截图都标明场景。</div><div class="compare"><figure><label>研证当前页面<select id="ours"></select></label><a id="ours-link" target="_blank"><img id="ours-img" alt=""></a><figcaption id="ours-caption"></figcaption></figure><figure><label>竞品公开页面<select id="other"></select></label><a id="other-link" target="_blank"><img id="other-img" alt=""></a><figcaption id="other-caption"></figcaption></figure></div><h3>我们自己的界面问题，有哪些可核对证据</h3>__UI__</section>
<section class="panel" id="next" hidden><h2>先让一条完整科研任务链可靠运行</h2><div class="note">值得主攻的差异：来源版本改变 → 找到受影响笔记／结论／报告／实验方案 → 逐项复核 → 保留决定。它是待验证的特色方向，不宣称行业独有。</div><div class="priority">
<article><span class="badge">第一阶段 · 主流程</span><h3>文献和阅读回到界面中心</h3><ol><li>导航分层、任务抽屉、文献库表格和批量操作。</li><li>压缩阅读横幅，调整分栏、字号、对比度。</li><li>项目贯通资料、对话、证据、成果；支持恢复位置。</li></ol></article>
<article><span class="badge">第二阶段 · 可信研究</span><h3>把“有出处”推进到“说得对”</h3><ol><li>独立问答、翻译、复杂解析题集；保留失败。</li><li>连续对话的范围管理、问题澄清与支持性检查。</li><li>逐格有证据的比较矩阵、元数据和引文互通。</li></ol></article>
<article><span class="badge">第三阶段 · 核心特色</span><h3>让版本复核变成可见的收益</h3><ol><li>用真实论文前后版本做可重置演示。</li><li>统一显示待复核结论与新旧证据。</li><li>量化漏报、误报、人工修订时间；包含无关变更负例。</li></ol></article>
<article><span class="badge">第四阶段 · 成果交付</span><h3>输出能够持续编辑、带走和复现</h3><ol><li>文稿局部修改、引文样式与可靠导出。</li><li>图形可选中元素、局部修改与撤销。</li><li>新设备启动检查、公开评审入口与稳定示例。</li></ol></article>
</div><p class="foot">这些是建议顺序，没有修改产品业务代码。零预算优先利用可用公开接口、开源组件与通用文件格式；不以复制所有产品的功能数量为目标。</p></section>
<footer class="foot">调研日期 2026-10-13 · <a href="竞品调研与功能界面对比_2026-10-13.md">完整报告与来源</a> · <a href="../artifacts/competitor-audit-2026-10-13/screens/observations.json">浏览器记录</a><br>未测试外部付费或登录功能；不据官网宣传比较模型准确率。本看板离线可用，截图依赖相邻 artifacts 目录。</footer>
</main><script>
const catalog=__CATALOG__;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const limited=s=>/受限|失败|待核验|未获得/.test(s);
const category=document.getElementById('category');
for(const name of [...new Set(catalog.map(x=>x.category))]) category.add(new Option(name,name));
function render(){const q=document.getElementById('search').value.trim().toLowerCase(),cat=category.value,e=document.getElementById('evidence').value;const found=catalog.filter(x=>(!cat||x.category===cat)&&(!q||Object.values(x).join(' ').toLowerCase().includes(q))&&(!e||(e==='limited'?limited(x.evidence):!limited(x.evidence))));document.getElementById('count').textContent=`显示 ${found.length} / 40 个产品`;document.getElementById('cards').innerHTML=found.length?found.map(x=>`<article class="card"><span class="badge">${esc(x.category)}</span><h3><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.name)} ↗</a></h3><p>${esc(x.features)}</p><p><strong>借鉴方向</strong> · ${esc(x.lesson)}</p><p class="status ${limited(x.evidence)?'limited':''}">${esc(x.evidence)}</p></article>`).join(''):'<p class="empty">没有匹配项，请换个关键词或重置筛选。</p>';}
for(const id of ['search','category','evidence'])document.getElementById(id).addEventListener('input',render);
document.getElementById('reset').addEventListener('click',()=>{for(const id of ['search','category','evidence'])document.getElementById(id).value='';render();});
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==button.dataset.tab);}));
const shots={ours:[['ours-library','文献管理','实际运行界面：首先是单篇编辑与维护操作。'],['ours-reader','阅读与问答','实际运行界面：多层横幅与工具栏压缩论文区域。'],['ours-discover','论文发现','实际运行界面：查询与筛选的优先级需要优化。'],['ours-studio','科研工作室','实际运行界面：多个研究任务堆叠。'],['ours-audit','版本复核','实际运行界面：已有三步引导，仍需要直观示例。'],['ours-tasks','任务与成果','实际运行界面：成果标题和摘要辨识度不足。']],other:[['paperpile','Paperpile · 官网展示','官网及产品示意，未进入登录后的文献库。'],['consensus','Consensus · 公开入口','可访问的公开搜索入口；未提交付费研究任务。'],['jenni','Jenni · 官网展示','官网编辑器展示，未实测完整写作流程。'],['connectedpapers','Connected Papers · 公开入口','种子论文输入和产品说明；相似图不等同于引用图。'],['ima','腾讯 ima · 公开入口','公开界面中的知识库、任务示例与历史组织。'],['elicit','Elicit · 官网展示','官网对研究工作流的说明，未完成登录后任务。'],['aminer','AMiner · 公开入口','有分组导航，也有较多入口与引导。'],['biorender','BioRender · 官网展示','官方科研绘图展示，未进入付费编辑器。'],['litmaps','Litmaps · 官网展示','公开产品页；发现、可视化、分享与监控。']]};
for(const side of ['ours','other']){const select=document.getElementById(side);shots[side].forEach((x,i)=>select.add(new Option(x[1],String(i))));const update=()=>{const [id,label,caption]=shots[side][Number(select.value)];const src='../artifacts/competitor-audit-2026-10-13/screens/'+id+'.png';document.getElementById(side+'-img').src=src;document.getElementById(side+'-img').alt=label;document.getElementById(side+'-link').href=src;document.getElementById(side+'-caption').textContent=caption;};select.addEventListener('change',update);update();}
render();
</script></body></html>"""

replacements = {
    "__CATALOG__": json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c"),
    "__TRAFFIC__": table(["网站", "月份", "估计月访问次数", "范围与来源"], traffic),
    "__SCALES__": table(["网站", "官方规模声明", "限制"], scales),
    "__GAPS__": table(["维度", "已有能力", "差距", "参考", "优先级"], gaps),
    "__UI__": table(["问题", "实测／实拍", "影响", "建议"], ui),
}
for key, value in replacements.items():
    template = template.replace(key, value)
assert not re.search(r"__[A-Z]+__", template)
OUTPUT.write_text(template, encoding="utf-8")
print(json.dumps({"catalog": len(catalog), "traffic": len(traffic), "gaps": len(gaps), "ui": len(ui), "output": str(OUTPUT)}, ensure_ascii=False))
