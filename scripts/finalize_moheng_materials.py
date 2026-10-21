"""Refresh current material text with verified final facts; do not publish secrets."""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/moheng-final-20261021'
OUT=ROOT/'output/moheng-final-20261021/materials'
OUT.mkdir(parents=True,exist_ok=True)
public=json.loads((ART/'public-browser.json').read_text('utf-8'))
assert public['complete'] and not public['errors']
assert json.loads((ART/'browser-final.json').read_text('utf-8'))['complete']
assert '420 passed' in (ART/'backend-tests.log').read_text('utf-8',errors='replace')
names=['评审使用指南_2026-10-21.md','答辩与AI协作说明_2026-10-21.md','免费评审部署说明_2026-10-21.md','测试资料准备.md','墨衡_最终轮对标与验收_2026-10-21.md']
for name in names:
    path=ROOT/'docs'/name
    text=path.read_text('utf-8')
    text=text.replace('研证','墨衡').replace('ScholarTrace','Moheng')
    text=text.replace('公网带凭据验证待授权','公网登录与真实问答已通过一次验证')
    if name=='免费评审部署说明_2026-10-21.md':
        text+='\n\n最终轮补充：作者已明确授权评审专用账号通过Cloudflare；2026-10-21已完成一次公网HTTPS登录、匿名访问拒绝、五篇隔离文库、Secure/HttpOnly会话及真实问答检查。该检查来自开发机，不是跨独立网络或连续24/72小时验证。\n'
    path.write_text(text,encoding='utf-8')
    shutil.copy2(path,OUT/name)

old=ROOT/'output/submission-20261021/评审访问说明_仅供提交.txt'
private=old.read_text('utf-8-sig').replace('研证','墨衡').replace('ScholarTrace','Moheng')
private+='\n最终版访问验证：已按作者明确授权，通过上述公网HTTPS完成专用账号登录及真实问答；仍需保持电脑开机联网。\n'
(OUT/'评审访问说明_仅供提交.txt').write_text(private,encoding='utf-8-sig')
rows=json.loads((ART/'narration.json').read_text('utf-8'))
(OUT/'演示视频讲稿.md').write_text('# 墨衡 Moheng 最终版演示讲稿\n\n真实浏览器操作、普通话合成旁白，等待与停留经剪辑。\n\n'+'\n\n'.join(f"## {r['id']}. {r['title']}\n\n{r['text']}" for r in rows),encoding='utf-8')

summary='''# 墨衡 Moheng 最终版验收摘要（公开）

日期：2026-10-21。作者：蔡晨霖，西安交通大学人工智能2501。

- 最终后端工程回归420项通过，61.51秒；官方资料存在，未把跳过计为通过。
- 前端TypeScript与生产构建通过；14项真实浏览器检查通过，无脚本异常，覆盖快捷查找、输入法、页码、真实部分失败批量导入与手机布局。
- 八段真实浏览器操作重新录制，品牌为墨衡。1080p、H264/AAC、约6分45秒，本地普通话合成旁白，生成等待经剪辑。
- 作者明确授权后，公网HTTPS专用账号登录、匿名数据访问拒绝、五篇隔离文库、Secure/HttpOnly会话与真实模型问答全部通过一次验证，无页面脚本异常。不包含私人账号、数据库或笔记。
- 本轮复查55个平台及1个阅读功能页，41个HTTP 200；15个失败。另观察8个公开浏览器界面，不冒充登录后或付费模型实测，不声称超过所有产品。
- 对原名的更改覆盖当前界面、导出、文档、演示和最终包；历史记录保留当时名称，技术标识及Git URL保持兼容。

420项工程测试不等于科研准确率。此前4题11次真实调用是开发案例，不是独立盲测；复杂问答、扫描公式、专业翻译仍会出错。未做真人用户研究，未训练模型权重。

公网检查从开发机访问免费Cloudflare隧道，不证明独立网络或24/72小时持续可用性。本机需开机联网。网盘链接、B站审核后的播放链接、UID/手机号与WPS最终提交仍由作者本人完成；预指导不等于正式省赛提交。未购买服务器、域名、付费API、会员或推广。

原始失败、截图和详细检查记录本地留存。公开摘要不含账号密码、原始论文全文及开发原始证据大包。
'''
(OUT/'验收摘要_公开版.md').write_text(summary,encoding='utf-8')

for script in ['build_moheng_final_pdf.py','build_moheng_final_package.py']:
    path=ROOT/'scripts'/script
    text=path.read_text('utf-8')
    replacements={
      '约6分37秒':'约6分45秒', '6分37秒':'6分45秒',
      '公网完整登录和长期连续可用性尚未验证':'公网专用账号登录与真实问答已通过一次验证；长期连续可用性尚未验证',
      '公网完整登录体验、跨独立网络及24/72小时可用性尚未验证':'公网HTTPS专用账号登录与真实问答已通过一次验证；跨独立网络及24/72小时可用性尚未验证',
      '公网登录全流程与持续可用性尚未验证':'公网登录与真实问答已通过一次验证；持续可用性尚未验证',
      '公网完整登录和长期可用性验证':'独立网络与长期可用性验证',
      '公网带凭据自动验证先前被自动审批拒绝，尚未执行；若希望我继续这项验证，需要明确允许评审专用账号与会话经过Cloudflare。你自行浏览器测试时亦通过该免费隧道。':'作者本轮已明确授权评审专用账号经过Cloudflare，现已通过一次公网登录和真实问答检查。提交前仍建议本人用手机移动网络复查，免费隧道并非长期在线保证。',
      'reused_files_match_previous_release':'packaged_files_match_final_sources',
      '视频为程序化真实浏览器录像':'视频为程序化真实浏览器录像',
    }
    for a,b in replacements.items(): text=text.replace(a,b)
    path.write_text(text,encoding='utf-8')

site=ROOT/'submission-site/index.html'
text=site.read_text('utf-8').replace('releases/tag/submission-20261021','releases/tag/moheng-final-20261021')
text=text.replace('公网健康接口已连通；公网登录验证待授权，持续在线尚未证明。','公网专用账号登录与真实问答已通过一次验证；持续在线尚未证明。')
text=text.replace('完整逐步使用说明 →','完整逐步使用说明（含快捷查找） →')
site.write_text(text,encoding='utf-8')
for name in ['scene-2.png','scene-4.png','scene-8.png']: shutil.copy2(ART/name,ROOT/'submission-site'/name)
runtime={'url':public['url'],'checked_at':'2026-10-21','status':'公网专用账号登录与真实问答已通过一次验证；需保持电脑开机联网，未证明跨独立网络或长期可用性。'}
(ROOT/'submission-site/runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
print('Final facts and active materials synchronized; no credential values printed.')
