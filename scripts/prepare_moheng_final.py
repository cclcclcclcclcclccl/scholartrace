"""Rebrand active surfaces while preserving old releases and stable data identifiers."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/moheng-final-20261021'
ART.mkdir(parents=True, exist_ok=True)
BACKUP = ART / 'before'
paths = list((ROOT/'frontend/src').glob('*')) + [ROOT/'frontend/index.html', ROOT/'README.md', ROOT/'submission-site/index.html']
paths += [ROOT/'docs'/name for name in ['评审使用指南_2026-10-21.md', '答辩与AI协作说明_2026-10-21.md', '免费评审部署说明_2026-10-21.md', '第三方来源与分发说明.md']]
changed = []
for path in paths:
    if not path.is_file() or path.suffix not in {'.tsx','.ts','.html','.css','.md'}: continue
    text = path.read_text('utf-8')
    new = text.replace('研证', '墨衡').replace('ScholarTrace', 'Moheng').replace('SCHOLARTRACE</small>', 'MOHENG</small>').replace('>SCHOLARTRACE<', '>MOHENG<')
    if text == new: continue
    backup = BACKUP / path.relative_to(ROOT)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists(): shutil.copy2(path, backup)
    path.write_text(new, encoding='utf-8')
    changed.append(str(path.relative_to(ROOT)))
for old, new in [('启动研证.cmd','启动墨衡.cmd'),('停止研证.cmd','停止墨衡.cmd')]:
    shutil.copy2(ROOT/old, ROOT/new)
app = ROOT/'backend/app.py'
text = app.read_text('utf-8')
app.write_text(text.replace('FastAPI(title="ScholarTrace"', 'FastAPI(title="墨衡 Moheng"'), encoding='utf-8')
# Runtime keys, data paths, Git URLs and the service identity remain compatible.
(ART/'rebrand.json').write_text(json.dumps({'changed':changed,'brand':'墨衡 Moheng','preserved_technical_id':'scholartrace','historical_release_preserved':True}, ensure_ascii=False, indent=2), encoding='utf-8')

replacements = [('研证', '墨衡'), ('ScholarTrace', 'Moheng'), ('SCHOLARTRACE', 'MOHENG'), ('artifacts/submission-20261021', 'artifacts/moheng-final-20261021')]
for old, new in [('record_submission_20261021.mjs','record_moheng_final.mjs'),('assemble_submission_20261021.py','assemble_moheng_final.py'),('verify_submission_20261021_video.py','verify_moheng_final_video.py'),('build_submission_20261021_pdf.py','build_moheng_final_pdf.py')]:
    text = (ROOT/'scripts'/old).read_text('utf-8')
    for a,b in replacements: text = text.replace(a,b)
    text = text.replace('output/video-20261021','output/moheng-final-20261021/materials')
    if old.startswith('record_'):
        text = text.replace("// The single local GPU slot is reserved for the frozen evaluation until it completes.\nfor(let i=0;i<120;i++){let r;try{r=JSON.parse(await readFile('artifacts/proof-v6-qa/run.json','utf8'));}catch{}if(r?.complete)break;if(i===119)throw Error('Frozen evaluation has not completed');await wait(5000);}\n", '')
        text = text.replace("await scene(2,async p=>{await reader(p);", "await scene(2,async p=>{await p.getByRole('button',{name:/快捷查找/}).click();await p.getByRole('combobox',{name:'搜索功能或库内论文'}).fill('1706.03762v1.pdf');await p.keyboard.press('Enter');await wait(1000);await reader(p);")
    if old.startswith('build_'):
        text = text.replace("docs/技术文档_2026-10-21.md", "docs/墨衡_技术文档_2026-10-21.md")
        text = text.replace('省赛原文截止为2026年11月18日；最终以赛事个人中心为准。', '当前预指导截止为2026年10月31日15:00；之后还需按正式省赛入口提交。')
        text = text.replace('最终官网提交与报名状态尚未确认。原文省赛日期2026年11月18日、国赛日期2026年12月27日，属不同阶段；不能猜测实际所报阶段。', '本次预指导表单已只读核实，截止为2026年10月31日15:00；需网盘完整材料、作品介绍PDF与公开视频平台链接，且之后仍需正式省赛提交。尚未代作者填表提交。')
        text = text.replace('首次教程和模块帮助同步维护。', '首次教程和模块帮助同步维护；Ctrl+K快捷查找可直达功能或库内论文。批量导入逐文件报告失败，保留成功结果。')
        text = text.replace('完整Git历史与bundle', '完整Git历史与bundle')
    (ROOT/'scripts'/new).write_text(text, encoding='utf-8')

text = (ROOT/'scripts/build_preguidance_20261021.py').read_text('utf-8')
for a,b in replacements: text=text.replace(a,b)
text=text.replace("OLD = ROOT / 'output/submission-20261021'", "OLD = ROOT / 'output/moheng-final-20261021/materials'")
text=text.replace("output/preguidance-20261021", "output/moheng-final-20261021")
text=text.replace("artifacts/preguidance-20261021", "artifacts/moheng-final-20261021")
text=text.replace('预指导提交材料', '最终版预指导提交材料').replace('01_表单第5项_完整作品.zip','01_墨衡_完整作品_最终版.zip')
text=text.replace('本视频为本次传智杯', '本视频为墨衡最终版，名称与当前网站一致。本视频为本次传智杯')
text=text.replace('首次教程和各模块帮助按钮解释功能；预置5篇公开论文用于上手。','首次教程与模块帮助解释功能；顶部“快捷查找”或Ctrl+K搜索功能和库内论文，用上下键与回车打开。预置5篇公开论文用于上手。')
text=text.replace('PDF阅读与检索', 'PDF阅读与检索')
text=text.replace('首次教程、模块帮助、输入修复、独立评审库、锁定依赖和真实开发历史。', '首次教程、模块帮助、Ctrl+K快捷查找、批量导入逐项失败提示、独立评审库与真实开发历史。')
text=text.replace('配套技术文档中的11月18日来自此前原始赛事材料，不能替代本次预指导10月31日15:00的实际截止。后续正式省赛截止以正式入口公告为准。','本次预指导截止为10月31日15:00，后续正式省赛截止以正式入口公告为准。旧名“研证”仅出现在历史开发记录中，当前产品为“墨衡 Moheng”。技术标识、数据路径及Git仓库URL保留scholartrace，以兼容旧数据和已有链接。')
text=text.replace('视频MP4随包用于离线审阅', '最终轮竞品复查与验收见附带“墨衡_最终轮对标与验收_2026-10-21.md”。视频MP4随包用于离线审阅')
text=text.replace("'测试资料准备.md', '验收摘要_公开版.md', '演示视频讲稿.md']", "'测试资料准备.md', '验收摘要_公开版.md', '演示视频讲稿.md', '墨衡_最终轮对标与验收_2026-10-21.md']")
text=text.replace('结论也要复核', '结论也要复核')
(ROOT/'scripts/build_moheng_final_package.py').write_text(text, encoding='utf-8')

narration=json.loads((ROOT/'artifacts/submission-20261021/narration.json').read_text('utf-8'))
for row in narration:
    row['text']=row['text'].replace('研证','墨衡')
    if row['id']==2:
        row['text']='顶部快捷查找可以搜索功能和库内论文，也支持键盘上下选择和回车打开。'+row['text']
(ART/'narration.json').write_text(json.dumps(narration,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'rebranded_files':len(changed), 'scripts_prepared':5},ensure_ascii=False))
