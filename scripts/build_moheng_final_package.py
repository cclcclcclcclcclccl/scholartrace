"""Prepare the seven-field WPS pre-guidance handoff without submitting anything."""
from pathlib import Path
import hashlib
import html
import json
import shutil
import zipfile

from PIL import Image as PILImage, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'output/moheng-final-20261021/materials'
OUT = ROOT / 'output/moheng-final-20261021'
ART = ROOT / 'artifacts/moheng-final-20261021'
KIT = OUT / '03_B站投稿素材'
PACK = OUT / '完整作品_供评审'
for folder in (OUT, ART, KIT, PACK, ROOT / 'output/pdf'):
    folder.mkdir(parents=True, exist_ok=True)
SITE = 'https://cclcclcclcclcclccl.github.io/scholartrace/'
REPO = 'https://github.com/cclcclcclcclcclccl/scholartrace'
FORM = 'https://f.kdocs.cn/ksform/w/write/n2ch15Dh#routePromt'
PDF_NAME = '02_作品介绍文档_蔡晨霖_墨衡.pdf'
FONT_PATH = 'C:/Windows/Fonts/msyh.ttc'
BOLD_PATH = 'C:/Windows/Fonts/msyhbd.ttc'
pdfmetrics.registerFont(TTFont('Yahei', FONT_PATH, subfontIndex=0))
pdfmetrics.registerFont(TTFont('YaheiBold', BOLD_PATH, subfontIndex=0))
GREEN = colors.HexColor('#183F38')
styles = {
    'title': ParagraphStyle('title', fontName='YaheiBold', fontSize=26, leading=38, textColor=GREEN, spaceAfter=16),
    'h': ParagraphStyle('h', fontName='YaheiBold', fontSize=19, leading=29, textColor=GREEN, spaceAfter=16),
    'p': ParagraphStyle('p', fontName='Yahei', fontSize=10.6, leading=18.5, wordWrap='CJK', spaceAfter=11),
    'small': ParagraphStyle('small', fontName='Yahei', fontSize=8.6, leading=14, wordWrap='CJK', textColor=colors.HexColor('#536961'), spaceAfter=8),
    'cell': ParagraphStyle('cell', fontName='Yahei', fontSize=9.5, leading=16, wordWrap='CJK'),
    'k': ParagraphStyle('k', fontName='YaheiBold', fontSize=9, leading=15, textColor=colors.HexColor('#967641'), spaceAfter=15),
}
story, source = [], []


def p(text, kind='p'):
    story.append(Paragraph(html.escape(text).replace('\n', '<br/>'), styles[kind]))
    source.append(text + '\n')


def page(label, title):
    if story:
        story.append(PageBreak())
    p('MOHENG / 省赛作品预指导 / ' + label, 'k')
    p(title, 'h')


def table(rows, widths):
    cells = [[Paragraph(html.escape(str(v)), styles['cell']) for v in row] for row in rows]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3EDE7')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#CCD9CF')),
        ('INNERGRID', (0, 0), (-1, -1), .3, colors.HexColor('#DDE5DF')),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.extend([t, Spacer(1, 12)])
    source.extend([' | '.join(row) for row in rows])


def shot(name, caption, height=225):
    f = ROOT / 'artifacts/moheng-final-20261021' / name
    im = Image(str(f))
    scale = min(485 / im.imageWidth, height / im.imageHeight)
    im.drawWidth, im.drawHeight = im.imageWidth * scale, im.imageHeight * scale
    story.extend([im, Spacer(1, 6)])
    p(caption, 'small')
    source.append(f'图片：{f.relative_to(ROOT).as_posix()}\n')


page('01 / 项目详情', '墨衡 Moheng')
p('让研究结论\n跟随证据一起更新', 'title')
p('面向证据更新的全流程科研助手\n蔡晨霖 · 西安交通大学 · 人工智能2501\n作品介绍文档 / 2026年10月21日')
p('一、项目详情及使用方式', 'h')
p('面向需要阅读、比较和持续追踪论文的学生与科研人员。系统将PDF原文、问答引文、证据笔记、文献版本和研究成果关联起来，帮助用户发现漏答、检查比较条件，并在文献更新后重新核对已有结论。')
p('项目以六类能力组成工作流：文献管理与解析、论文问答与比较、阅读与翻译、论文发现与追踪、引用分析与研究辅助、写作与可视化。核心不是替用户保证科研结论正确，而是保留可返回原文的检查路径。')
table([['查看方式', '地址或文件'], ['固定入口', SITE], ['公开源码', REPO], ['离线材料', '完整作品包内含技术文档、源码ZIP、Git历史、演示视频、字幕和使用指南。']], [88, 397])
p('本文件按当前预指导表单的七项要求组织。预指导截止：2026年10月31日15:00；预指导不代替之后的正式省赛提交。资料未声称获得奖项或通过官方验收。', 'small')

page('01 / 使用方式', '从一段原文开始体验')
p('在线使用：打开固定入口，进入科研工作台，按随作品包提供的“评审访问说明_仅供提交.txt”登录专用空间。首次教程与模块帮助解释功能；顶部“快捷查找”或Ctrl+K搜索功能和库内论文，用上下键与回车打开。预置5篇公开论文用于上手。')
table([['步骤', '怎么做 / 检查什么'],
       ['1 阅读与定位', '文献阅读台选择 Attention Is All You Need v1；页码框删空，输入7并回车，检查原版页定位。'],
       ['2 提问与查证', '问“Transformer训练使用了什么GPU？base模型训练需要多长时间？”；展开引用并返回原文。Enter发送方式可切换。'],
       ['3 限定原文追问', '在证据卡选择“只依据此段追问”，核对完整段落后补问；解除限定恢复全文检索，切换论文清除旧选段。'],
       ['4 版本变化复核', '保存有出处的笔记，进入版本复核并选择v7，查看两侧原文和模型初判；人工确认是否影响旧结论。'],
       ['5 扩展研究', '双语对照、题名/DOI检索、关联推荐；项目中整理条件与指标，补查任务记录缺项。'],
       ['6 产出与导出', '写作框架、实验方案和图稿都作为待核对草稿；图稿可编辑，CSV图保留数据与单位。']], [96, 389])
p('本地运行：按源码README准备Python 3.12、Node 22.12+和锁定依赖，下载免费本地模型，运行 node scripts/start.mjs。模型权重、原论文和私人数据库不打入源码包，首次安装需要联网下载和数GB磁盘空间。')
p('免费在线模式依赖作者电脑开机联网、模型和隧道运行。固定入口是导航页，不能代替后端；公网专用账号登录与真实问答已通过一次验证；长期连续可用性尚未验证。断网时可先审看视频和技术文档，或按README复现。', 'small')

page('02 / 项目亮点', '把“可追溯”做成可操作的流程')
p('二、项目亮点', 'h')
table([['问题', '项目中的具体处理'],
       ['论文更新，旧笔记可能失效', '将证据绑定到文献版本、页码和文本块；新版本到来后并列两侧原文，辅助检查已有笔记和成果是否需要复核。'],
       ['引用看似真实，却未必支持结论', '同时核对来源归属、完整原文和部分数值/条件线索；显示缺证据与不确定状态，仍保留人工检查入口。'],
       ['追问后检索范围悄悄变化', '“只依据此段追问”限定单个完整原文块；服务端重验选段，失败时保留原文，不自动扩大检索。'],
       ['多篇论文比较缺条件、缺指标', '证据对照表记录条件与单位线索，缺格转成补查任务；同单位不自动视为科学可比。']], [143, 342])
shot('scene-4.png', '真实界面：版本复核呈现两侧来源。模型初判由用户核对，不自动裁决论文真伪。', 215)
p('创新定位是证据、版本与成果依赖之间的工作流组合；没有声称发明新基础模型或已获同行评审认可的算法突破。', 'small')

page('03 / AI测试落地', '把模型失败纳入质量检查')
p('三、AI测试技术落地使用情况概述', 'h')
p('AI应用：本地Qwen3-4B参与有出处问答、段落翻译、版本语义初判、研究草稿和图意生成；检索与服务端验证约束输入输出。AI辅助测试：编程助手协助设计测试、分析失败和修订代码，最终结果以实际执行记录为依据。')
table([['测试层', '落地方式与记录'],
       ['确定性工程回归', '隔离数据环境检查页码、论文范围、引文归属、权限和保存冲突等。最终源码带官方6份PDF时420项通过；不带资料时394项通过、26项明确跳过。'],
       ['真实模型调用', '限定原文追问开发检查含4题、11次真实调用。观察可回答事实、复杂条件漏答和缺信息拒答；未用模拟返回替代真实输出。'],
       ['浏览器与演示', '实际页面验证选段、问答、导出、解除与切换；演示含8段真实浏览器操作。视频已完整解码检查并抽查9帧。'],
       ['发布与恢复', '源码依赖、Git bundle恢复、PDF渲染、文件指纹与媒体检查分别记录；发布的源码和模型运行数据分离。']], [105, 380])
p('已发现的失败：复杂Pre-LN复合问题仍会漏掉结构或适用条件；答案可能重复或中英混杂；模型支持性初筛可能误判。系统保留未解决项、原文和失败记录，不把“有引用”视为充分正确性证明。')
p('上述420项是工程测试数量，不是420道科研题的正确率。4题为开发者预选的已见案例，不构成独立盲测；没有真人用户实验或可靠的效率提升百分比。没有进行基础模型微调、权重训练或自主自我训练。')
p('复查：完整作品包内的“验收摘要_公开版.md”“测试资料准备.md”和技术文档。原始开发证据保留在作者本机，可按评审要求另行提供；不在网盘包中散发全部原论文摘录与运行日志。', 'small')

page('04 / 关键技术', '本地模型与受控科研工作流')
p('四、项目涉及的关键技术', 'h')
table([['层次', '实现与作用'],
       ['界面与阅读', 'React / TypeScript / Vite；PDF.js渲染原版页面，目录、页码与证据定位；首访教程和模块帮助。'],
       ['解析与存储', 'PyMuPDF文字层与坐标、RapidOCR扫描识别、逐页覆盖诊断；SQLite保存文献版本、文本块、笔记与成果。'],
       ['检索与模型', 'BM25、多语言MiniLM及排名融合；llama.cpp运行Qwen3-4B量化模型，使用本地兼容接口。'],
       ['Agent编排', '结构化计划和允许的工具、任务持久化、取消/重试/恢复；不允许模型任意执行系统命令。'],
       ['可信输出', '服务端重新核验论文范围、来源和选段；部分数字、条件及语义支持检查；不足时返回缺失项与原文。'],
       ['图稿与研究成果', '结构化节点/边编译Mermaid，检查非法端点、分支与回环；CSV绘图保留数据、单位和可重跑脚本。'],
       ['发布与部署', 'GitHub源码/固定入口，独立评审库和免费HTTPS隧道；本机推理，不调用付费模型API。']], [105, 380])
p('资源边界：Qwen3-4B适配零API预算，不等同于强力云端模型。复杂表格、公式、专业翻译、跨文献因果比较仍需核对。外部文献接口会受限流和全文权限影响，不能据有限检索证明全球新颖性。')
p('来源与许可：项目包另附第三方来源说明；模型、组件及论文分别按其上游许可使用，不将第三方基础能力宣称为本项目原创。', 'small')

page('05 / 项目图片', '真实工作台与可核验输出')
p('五、项目相关图片', 'h')
shot('scene-2.png', '图1　文献阅读台：原版PDF、页码定位与右侧问答区域。画面来自实际浏览器录制。', 244)
shot('scene-8.png', '图2　限定原文追问：展开完整原文，明确当前问题只依据该段。图中结果不代表其他问题也同样准确。', 244)
p('更多画面见配套约6分45秒演示视频：入门、阅读、有出处问答、版本复核、双语/发现、研究项目、图稿及限定追问。视频使用本机普通话合成旁白，等待和停留经剪辑；没有替换真实API响应，不用于衡量推理延迟。', 'small')

page('06—07 / 来源声明', '既往情况与项目优化说明')
p('六、项目之前是否发表过或获奖', 'h')
p('根据作者蔡晨霖于2026年10月21日的确认，除本次GitHub公开发布外，本项目此前没有参加其他比赛、发表或获奖。当前也不主张任何尚未获得的赛事成绩。')
p('本次公开情况：2026年10月21日在GitHub发布项目源码、固定导航入口和演示材料，用于本次参赛展示及复现。公开代码与材料不等同于学术论文发表，也不代表赛事获奖。')
p(REPO, 'small')
p('七、是否基于其他项目优化及优化部分', 'h')
p('现有项目来源和开发记录显示，本作品围绕本次科研助手任务逐步开发，未发现基于某个第三方完整科研助手项目直接修改交付的记录。项目集成了Qwen3、llama.cpp、MiniLM、PyMuPDF、PDF.js、RapidOCR、FastAPI、React和Mermaid等第三方基础组件；这些组件与基础模型不是本作品原创。')
table([['基础能力', '本项目增加或优化的部分'],
       ['PDF阅读与检索', '文献版本、页码、文本块和证据绑定；逐页诊断与选页补识别；原文定位和可恢复导出。'],
       ['模型生成', '限定原文追问、范围核验、数字/条件防护、部分回答与未解决项；失败不隐式扩大来源。'],
       ['科研组织', '证据变化影响复核、研究成果依赖、条件敏感对照与补查任务；用户确认后闭环。'],
       ['交付与易用性', '首次教程、模块帮助、Ctrl+K快捷查找、批量导入逐项失败提示、独立评审库与真实开发历史。']], [105, 380])
p('AI协作披露：AI编程助手参与需求整理、代码、调试、评测、材料制作和部署；作者提出目标及修改意见，并负责理解、核验和最终提交。普通话旁白为合成语音。项目不宣称全部代码为作者手工独立编写。', 'small')


def footer(c, doc):
    c.setStrokeColor(colors.HexColor('#DCE6DE'))
    c.line(55, 48, 540, 48)
    c.setFont('Yahei', 8)
    c.setFillColor(colors.HexColor('#536961'))
    c.drawString(55, 32, '墨衡 Moheng / 蔡晨霖 / 预指导材料 2026-10-21')
    c.drawRightString(540, 32, str(doc.page))


pdf = ROOT / 'output/pdf' / PDF_NAME
SimpleDocTemplate(str(pdf), pagesize=(595.28, 841.89), leftMargin=55, rightMargin=55,
                  topMargin=46, bottomMargin=64, title='墨衡 Moheng 作品介绍文档', author='蔡晨霖').build(story, onFirstPage=footer, onLaterPages=footer)
shutil.copy2(pdf, OUT / PDF_NAME)
(ART / '作品介绍文档_内容源.md').write_text('\n'.join(source), encoding='utf-8')
reader = PdfReader(pdf)
assert len(reader.pages) == 7, f'Unexpected pagination: {len(reader.pages)}'
assert pdf.stat().st_size < 100_000_000
text = '\n'.join(pg.extract_text() for pg in reader.pages)
for heading in ('一、项目详情及使用方式', '二、项目亮点', '三、AI测试技术落地使用情况概述', '四、项目涉及的关键技术', '五、项目相关图片', '六、项目之前是否发表过或获奖', '七、是否基于其他项目优化及优化部分'):
    assert heading in text, heading

# Reuse byte-identical, previously validated video and source artifacts.
copy_names = ['墨衡_Moheng_技术文档_2026-10-21.pdf',
              '墨衡_Moheng_演示_1080p_2026-10-21.mp4', '墨衡_演示字幕_2026-10-21.srt',
              'Moheng-source-20261021.zip', 'Moheng-history-20261021.bundle',
              '评审使用指南_2026-10-21.md', '评审访问说明_仅供提交.txt',
              '答辩与AI协作说明_2026-10-21.md', '免费评审部署说明_2026-10-21.md',
              '测试资料准备.md', '验收摘要_公开版.md', '演示视频讲稿.md', '墨衡_最终轮对标与验收_2026-10-21.md']
for name in copy_names:
    shutil.copy2(OLD / name, PACK / name)
shutil.copy2(pdf, PACK / PDF_NAME)
shutil.copy2(ROOT / 'docs/第三方来源与分发说明.md', PACK / '第三方来源与分发说明.md')
for name in ('墨衡_Moheng_演示_1080p_2026-10-21.mp4', '墨衡_演示字幕_2026-10-21.srt'):
    shutil.copy2(OLD / name, KIT / name)

vm = json.loads((OLD / 'video-manifest.json').read_text(encoding='utf-8'))
chapters = '\n'.join(f"{int(s['start'])//60:02d}:{int(s['start'])%60:02d} {s['title']}" for s in vm['scenes'])
video_copy = f'''标题：
墨衡Moheng｜有出处的论文问答与版本复核｜传智杯AI大模型创新应用挑战赛作品演示

简介（直接复制以下段落）：
作者：蔡晨霖，西安交通大学人工智能2501。
墨衡Moheng是一款面向证据更新的科研助手：把PDF原文、问答引用、笔记和文献版本关联起来，辅助发现漏答、检查比较条件、复核文献更新对旧结论的影响。

本视频为墨衡最终版，名称与当前网站一致。本视频为本次传智杯AI大模型创新应用挑战赛作品展示，包含真实浏览器操作。使用本机普通话合成旁白，生成等待与画面停留经剪辑，没有替换实际API响应；不用于衡量推理延迟。AI助手参与开发与材料制作。模型仍可能漏答和误判，结果需回到原文核对。

功能导航：
{chapters}

源码：{REPO}
固定体验入口：{SITE}
完整应用依赖本机开机联网；无需购买付费API。视频不宣称获奖、官方认证或零幻觉。

建议标签：传智杯、人工智能、科研工具、大模型、论文阅读、项目展示
分区：按投稿页面当前分类选择人工智能／计算机技术等最贴近的科技分区。
类型：按实际原创项目演示选择；如页面有AI生成或合成内容声明，请如实勾选／说明合成旁白和AI辅助制作。
发布范围：公开，不设置付费观看或仅自己可见。
封面：B站封面_1920x1080.jpg。字幕：同文件夹SRT（若平台不支持导入，可使用自动字幕并校对）。
不要把“评审访问说明_仅供提交.txt”、密码或网盘评审包链接放进公开视频简介。
审核完成后复制 https://www.bilibili.com/video/BV... 的播放页链接，填表单第7项。
这份文件不是已经发布的视频链接。尚未登录B站或投稿。
'''
(KIT / '投稿文案_直接复制.txt').write_text(video_copy, encoding='utf-8-sig')
cover = PILImage.new('RGB', (1920, 1080), '#102F2B')
d = ImageDraw.Draw(cover)
f = lambda size, bold=False: ImageFont.truetype(BOLD_PATH if bold else FONT_PATH, size)
d.text((100, 92), 'MOHENG / 墨衡', font=f(62, True), fill='#EFE9D8')
d.text((100, 228), '论文会更新', font=f(104, True), fill='white')
d.text((100, 366), '结论也要复核', font=f(104, True), fill='white')
d.text((105, 560), '有出处问答 · 版本复核 · 限定原文追问', font=f(37), fill='#BBD6C8')
d.text((105, 870), '传智杯 AI 大模型创新应用挑战赛', font=f(36), fill='#DFBC75')
d.text((105, 940), '西安交通大学  蔡晨霖  /  作品实录', font=f(34), fill='#CDDED5')
screen = PILImage.open(ROOT / 'artifacts/moheng-final-20261021/scene-4.png').convert('RGB')
screen.thumbnail((840, 650))
x, y = 1000, 260
d.rounded_rectangle((x-12, y-12, x+screen.width+12, y+screen.height+12), radius=14, fill='#D5E2D8')
cover.paste(screen, (x, y))
d.text((1010, y+screen.height+35), '真实界面：两侧证据，逐项核对', font=f(31), fill='#CDDED5')
cover.save(KIT / 'B站封面_1920x1080.jpg', quality=94)

package_readme = f'''# 墨衡 Moheng · 省赛作品预指导完整作品

作者：蔡晨霖，西安交通大学人工智能2501。材料版本：2026-10-21。
当前预指导表单：{FORM}
当前预指导截止：2026-10-31 15:00（北京时间）。预指导后仍需正式省赛提交。

## 推荐审阅顺序
1. 02_作品介绍文档_蔡晨霖_墨衡.pdf：按表单7项介绍要求组织，7页。
2. 演示MP4：约6分45秒、1920×1080，真实浏览器操作与普通话合成旁白。
3. 技术文档PDF：14页，架构、模型、测试、局限、安装和来源。
4. 评审使用指南 + 评审访问说明_仅供提交.txt：固定入口与专用账号。
5. Moheng-source-20261021.zip：源码、README、锁定依赖、环境模板和说明。
6. Moheng-history-20261021.bundle：真实Git历史；可用git clone恢复。
7. 验收摘要、测试资料准备、第三方来源和AI协作说明：核对复现条件与边界。

固定入口：{SITE}
源码：{REPO}
运行模型和全文资料通过源码安装/下载入口准备；不包含模型权重、个人数据库、密钥、原版论文或全量开发日志。没有模型API付费步骤。

## 材料版本说明
本次预指导截止为10月31日15:00，后续正式省赛截止以正式入口公告为准。旧名“研证”仅出现在历史开发记录中，当前产品为“墨衡 Moheng”。技术标识、数据路径及Git仓库URL保留scholartrace，以兼容旧数据和已有链接。
本包替代旧“官网填写建议”作为本次预指导的整理入口；此前归档原样保留。
最终轮竞品复查与验收见附带“墨衡_最终轮对标与验收_2026-10-21.md”。视频MP4随包用于离线审阅，但表单第7项必须填B站/抖音等平台播放页，不能填网盘或GitHub下载地址。

## 访问与保密范围
本包含独立评审空间专用账号，只通过赛事表单的网盘分享交给评审；建议使用长期有效且有提取码的分享，不发布到B站简介或公开源码Release。
账号与私人工作区分离；公网登录与真实问答已通过一次验证；持续可用性尚未验证。本机必须开机联网。入口失效时可先审看视频或本地复现。
原始开发证据留存作者本机；如评审要求，再提供相关范围的材料。

## 校验
SHA256SUMS.txt记录本包各文件指纹；manifest.json列出体积及哈希。
工程测试420项通过不等于科研答案正确率；真实模型案例与未解决项见技术文档和验收摘要。
'''
(PACK / '00_请先阅读.md').write_text(package_readme, encoding='utf-8-sig')

instructions = f'''墨衡 Moheng｜预指导提交操作表（2026-10-21）

结论：本地材料已按实际7字段整合；网盘分享、B站投稿和WPS最终提交仍需本人登录完成。没有支付费用。
实际表单：{FORM}
截止：2026年10月31日15:00，北京时间。按报名队伍提交一次；本次是预指导，之后仍需正式省赛提交。
在线只读核验发现表单需要登录，附件接受PDF，最多1个且100MB以内。未登录或替你提交。

第一步：百度网盘免费上传（表单第5项）
1. 用你自己的账号打开 https://pan.baidu.com/ ，没有账号则按官方界面自行注册/登录。
2. 上传本文件夹“01_墨衡_完整作品_最终版.zip”。上传压缩包本身，不是项目整个工作目录。
3. 上传完成后选中文件→分享→设置长期有效/永久（以当前免费选项为准）并设置提取码。
4. 若账户当前不提供免费长期分享，不开会员；选择最长免费时效并在评审期前维护链接，或使用夸克/阿里云盘免费长期分享。
5. 复制分享链接与提取码，用另一个无痕窗口打开，核对文件名、可下载状态和有效期。需要登录下载时确认正常免费账号可下载。
6. 只把链接交给赛事评审；包内有专用评审账号，不把网盘链接贴到公开视频简介。保留分享有效期到正式评审结束。
我无法凭空建立你本人的网盘账号或完成短信/扫码身份验证；当前没有真实网盘分享链接。

第二步：B站免费投稿（表单第7项）
1. 打开 https://member.bilibili.com/ ，登录你的B站账号，进入视频投稿。
2. 上传“03_B站投稿素材”里的MP4。此文件与已验证演示完全相同，约6分45秒。
3. 选用同目录封面JPG，复制“投稿文案_直接复制.txt”的标题、简介和标签。按当前投稿页如实声明AI辅助/合成旁白。
4. 设为公开且可免费观看，按实际页面要求完成校验；不要购买推广、会员或付费服务。
5. 审核通过后，从公开视频播放页复制 https://www.bilibili.com/video/BV... 链接。
6. 用退出登录/无痕窗口打开，实际播放开头、中间、结尾，检查画面和声音。不要填创作中心管理地址、草稿地址、网盘地址或GitHub MP4下载链接。
如B站审核来不及，可在本人抖音账号发布相同视频并使用公开https播放链接，仍需退出登录验证。

第三步：填WPS表单
1. 传智杯UID：从赛事个人中心复制实际UID；不是GitHub/B站用户名、学号或手机号。
2. 姓名：蔡晨霖
3. 您的学校：西安交通大学
4. 联系手机号：填写你能接收赛事通知的真实手机号，直接在表单输入即可。
5. 完整作品文件链接：粘贴第一步真实网盘链接 + 提取码。
6. 作品介绍文档：只上传“02_作品介绍文档_蔡晨霖_墨衡.pdf”。不要上传ZIP或同时选两份PDF。
7. 演示视频地址：只粘贴第二步公开https播放页链接。

第四步：提交前最后检查
[ ] 确认报名队伍和本次提交人，没有重复提交。
[ ] 网盘链接能打开、文件完整、提取码正确，分享期限足够。
[ ] B站视频已审核通过、可公开播放、有画面和声音。
[ ] 第6项正确PDF上传成功，预览可读。
[ ] UID、姓名、学校和手机号与报名一致。
[ ] 阅读表单当前完整说明后点击一次“提交”，保存成功回执和提交时间。
[ ] 关注后续正式省赛提交入口；预指导回执不能当作正式参赛提交完成。

第五步：保持评审体验可用
项目根目录“启动免费评审.cmd”用于准备/恢复本机模型、评审实例和免费隧道。评审期间电脑需开机联网，勿休眠；固定入口：{SITE}
先自行访问并按包内评审说明登录，用手机移动网络打开页面实际问一道题。不要把静态入口可打开当作完整后端可用。
作者本轮已明确授权评审专用账号经过Cloudflare，现已通过一次公网登录和真实问答检查。提交前仍建议本人用手机移动网络复查，免费隧道并非长期在线保证。

本次不会冒充你完成账号注册/扫码/短信、视频实名校验、发布平台审核或最终赛事提交，也没有虚构任何已获得的链接、提交回执和获奖结果。
'''
(OUT / '04_逐项填写与上传说明.txt').write_text(instructions, encoding='utf-8-sig')
(OUT / '05_提交前填写.txt').write_text(f'''此页仅为本地记录，不是已提交回执。不要原样复制含空白的字段。
传智杯UID：
姓名：蔡晨霖
学校：西安交通大学
联系手机号：（直接在WPS表单填写，无需保存到此文件）
网盘真实分享链接：
网盘提取码：
分享失效时间：
B站公开播放页：https://www.bilibili.com/video/（上传后填写真实BV链接）
作品介绍PDF：{PDF_NAME}
WPS预指导表单：{FORM}
截止：2026-10-31 15:00
提交时间：
成功回执保存位置：
后续正式省赛提交入口：（等待官方正式入口，不能以预指导代替）
''', encoding='utf-8-sig')

def digest(file):
    return hashlib.file_digest(file.open('rb'), 'sha256').hexdigest()

entries = [{'file': f.name, 'bytes': f.stat().st_size, 'sha256': digest(f)}
           for f in sorted(PACK.iterdir()) if f.is_file() and f.name not in ('manifest.json', 'SHA256SUMS.txt')]
(PACK / 'manifest.json').write_text(json.dumps({'version':'2026-10-21', 'files':entries}, ensure_ascii=False, indent=2), encoding='utf-8')
(PACK / 'SHA256SUMS.txt').write_text('\n'.join(f"{e['sha256']}  {e['file']}" for e in entries) + '\n', encoding='utf-8')
archive = OUT / '01_墨衡_完整作品_最终版.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for file in sorted(PACK.iterdir()):
        if file.is_file():
            z.write(file, f'墨衡_蔡晨霖_预指导完整作品/{file.name}')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('evidence-20261021.zip' in n for n in z.namelist())
    for item in entries:
        assert hashlib.sha256(z.read(f"墨衡_蔡晨霖_预指导完整作品/{item['file']}")).hexdigest() == item['sha256']
for name in copy_names:
    assert digest(OLD / name) == digest(PACK / name)
archive_sha = digest(archive)
(OUT / '01_完整作品_SHA256.txt').write_text(f'{archive_sha}  {archive.name}\n', encoding='utf-8')
report = {'form_live_verified':True,'fields':7,'attachment_accepts_pdf':True,'pdf_pages':len(reader.pages),
          'pdf_bytes':pdf.stat().st_size,'seven_content_sections_verified':True,
          'author_confirmed_no_other_publications_awards_or_contests':True,
          'archive_bytes':archive.stat().st_size,'archive_sha256':archive_sha,'archive_crc_and_file_hashes_verified':True,
          'packaged_files_match_final_sources':True,'video_seconds':vm['duration_seconds'],
          'video_resolution':vm['resolution'],'raw_evidence_not_included':True,
          'contains_reviewer_account_for_judges_only':True,'paid_actions':False,
          'online_submission_completed':False,'netdisk_link':None,'video_platform_link':None,
          'pending':['本人账号网盘上传分享','B站投稿和审核','UID和手机号本人填写','本人登录WPS最终提交','独立网络与长期可用性验证']}
(OUT / '06_材料核对结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(ART / 'material-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
landing = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>墨衡｜最终版预指导提交材料</title>
<style>body{{margin:0;background:#edf2ed;color:#193f37;font:17px/1.8 'Microsoft YaHei',sans-serif}}main{{max-width:940px;margin:55px auto;padding:38px;background:white;border-radius:18px}}h1{{font-size:34px;line-height:1.4}}a{{color:#14624d;overflow-wrap:anywhere}}.tag{{color:#80612d}}.card{{padding:20px;margin:18px 0;background:#f3f7f3;border-radius:12px}}li{{margin:9px 0}}strong{{color:#9a4727}}@media(max-width:700px){{main{{margin:12px;padding:22px}}h1{{font-size:26px}}}}</style>
<main><div class="tag">蔡晨霖 · 西安交通大学 · 2026-10-21</div><h1>墨衡 Moheng<br>省赛作品最终版预指导提交材料</h1>
<p><strong>本地材料已经整合；尚未在线提交。</strong><br>截止：2026年10月31日15:00。预指导之后仍需正式省赛提交。</p>
<div class="card"><h2>先按这三件材料操作</h2><ol>
<li><a href="01_墨衡_完整作品_最终版.zip">完整作品ZIP</a>：{archive.stat().st_size/1024/1024:.2f} MiB，上传百度网盘免费空间，生成有效分享链接与提取码，填第5项。<strong>内含评审专用账号，只交给评审。</strong></li>
<li><a href="{PDF_NAME}">作品介绍PDF</a>：7页，覆盖七项说明，直接上传表单第6项。</li>
<li><a href="03_B站投稿素材/墨衡_Moheng_演示_1080p_2026-10-21.mp4">演示视频MP4</a>：1080p、约6分45秒，上传B站并通过审核，将公开播放页填第7项。</li></ol></div>
<p><a href="04_逐项填写与上传说明.txt">逐步上传与填表说明</a> · <a href="03_B站投稿素材/投稿文案_直接复制.txt">B站标题/简介/章节</a> · <a href="03_B站投稿素材/B站封面_1920x1080.jpg">B站封面</a> · <a href="05_提交前填写.txt">提交记录表</a> · <a href="06_材料核对结果.json">材料校验结果</a></p>
<p><a href="{FORM}">打开实际WPS预指导表单</a> · <a href="{SITE}">作品固定入口</a> · <a href="{REPO}">公开源码</a></p>
<p>请用本人的账号完成网盘上传、B站投稿、WPS登录；UID和手机号直接在官方表单填写。无需购买会员或付费推广。电脑开机联网是完整应用在线运行的条件。</p>
<p>原材料与开发证据仍保留。新包不包含原始证据大包、私人数据库和模型权重；运行所需模型按源码说明免费下载。</p></main></html>'''
(OUT / '00_从这里开始.html').write_text(landing, encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
