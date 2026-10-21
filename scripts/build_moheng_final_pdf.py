"""Build the reviewable competition technical PDF from current evidence and screenshots."""
from pathlib import Path
import json, html
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf';OUT.mkdir(parents=True,exist_ok=True)
FONT='Yahei';pdfmetrics.registerFont(TTFont(FONT,'C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('YaheiBold','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
INK=colors.HexColor('#193F37');MUTED=colors.HexColor('#566862');GOLD=colors.HexColor('#B79557')
styles={
 'title':ParagraphStyle('title',fontName='YaheiBold',fontSize=26,leading=38,textColor=INK,spaceAfter=20),
 'h':ParagraphStyle('h',fontName='YaheiBold',fontSize=20,leading=30,textColor=INK,spaceAfter=16),
 'p':ParagraphStyle('p',fontName=FONT,fontSize=11.5,leading=20.5,spaceAfter=11,wordWrap='CJK',textColor=colors.HexColor('#26342F')),
 'small':ParagraphStyle('small',fontName=FONT,fontSize=8.5,leading=14,spaceAfter=8,wordWrap='CJK',textColor=MUTED),
 'cell':ParagraphStyle('cell',fontName=FONT,fontSize=10,leading=17,wordWrap='CJK'),
 'k':ParagraphStyle('k',fontName=FONT,fontSize=10,leading=16,textColor=GOLD,spaceAfter=12),
}
story=[];md=['# 墨衡 Moheng 技术文档\n\n蔡晨霖 · 西安交通大学人工智能2501 · 2026-10-21\n']
def p(text,kind='p'):
 story.append(Paragraph(html.escape(text).replace('\n','<br/>'),styles[kind]));md.append(text+'\n')
def title(num,name):
 if story:story.append(PageBreak())
 p(f'MOHENG / {num:02d}', 'k');p(name,'h');md.append('## '+name+'\n')
def table(rows,widths):
 cells=[[Paragraph(html.escape(str(v)),styles['cell']) for v in row] for row in rows]
 t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E2EEE7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCD9CF')),('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDE5DF')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.extend([t,Spacer(1,13)]);md.extend([' | '.join(map(str,row)) for row in rows]);md.append('\n')
def shot(name,caption,maxh=255):
 f=ROOT/'artifacts/moheng-final-20261021'/name
 if f.exists():
  im=Image(str(f));scale=min(485/im.imageWidth,maxh/im.imageHeight);im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale;story.extend([im,Spacer(1,6)]);p(caption,'small');md.append(f'![{caption}](../../artifacts/moheng-final-20261021/{name})\n')

p('MOHENG / 墨衡','k');story.append(Spacer(1,35));p('让研究结论\n跟随证据一起更新','title')
p('基于大模型与 Agent 的全流程科研助手','h')
p('参赛者：蔡晨霖\n学校：西安交通大学\n专业班级：人工智能2501\n提交材料版本：2026-10-21')
p('核心特色：原文证据绑定、版本变化影响复核、条件敏感的比较与补查。完整覆盖六类科研工作台功能，以可核验的来源和真实失败记录支撑技术说明。')
shot('scene-2.png','当前版本真实浏览器：论文原版阅读与问答工作台。',215)
p('按用户提供的赛项原文整理。当前预指导截止为2026年10月31日15:00；之后还需按正式省赛入口提交。报名状态尚未核验，不虚构官方验收或获奖保证。','small')

title(2,'需求分析与科研工作流')
p('论文阅读的困难不仅是检索信息，也包括分辨实验条件、保存证据、比较不同论文，以及版本更新后确认旧结论是否仍适用。墨衡将文献、原文块、笔记、项目和成果连接成可追踪的数据链。')
table([['阶段','操作与产物'],['导入','标准PDF、扫描件、版本候选与逐页覆盖检查'],['阅读','原版页码和坐标，目录、正文搜索、双语联动'],['提问','文献范围过滤、分项回答、原文引用与缺证据状态'],['比较','证据对照表、条件/单位线索、待补查任务'],['更新','两侧证据、笔记与成果影响复核、人工确认'],['产出','有来源框架、方案、图稿、CSV图和可恢复导出']],[85,400])
p('关键约束：零付费模型API；保留用户资料；真实历史不重写；生成结论必须可回到原文。功能实现、工程测试、真实模型表现和独立用户效果分别记录，不互相替代。')
p('依据：docs/赛事要求原文_用户提供_2026-10-11.txt 与 docs/需求验收矩阵.md。原始需求标准保持不变；实现覆盖不等于全部质量标准已经通过。','small')

title(3,'系统架构与 Agent 编排')
table([['层次','实现与责任'],['交互层','React / TypeScript，PDF.js 原版渲染，Mermaid 图稿；问题、证据与来源并排'],['应用层','FastAPI，账号/项目范围，结构化工具参数，持久任务、重试、取消与恢复'],['智能层','BM25 + multilingual MiniLM + 排名融合；llama.cpp / Qwen3-4B；候选生成与验证'],['数据层','SQLite：文献、版本、页码块、证据笔记、成果及任务；文件与模型独立存储']],[85,400])
p('Agent 使用结构化计划与允许的工具进行任务拆分和编排，模型不能任意运行系统命令。长任务保存状态；后台问答按论文保存检查点。保存冲突通过版本检查提示，防止陈旧页面覆盖新结果。')
p('来源主键包含文献版本、页码、文本块和坐标。检索限定当前论文、多篇或全库；项目内空范围拒绝请求。原文与成果依赖保留，为版本变化复核提供基础。')
p('实现为单机资源约束下的受控科研工作流，不宣称具备无限自主科研能力、成熟多智能体集群或生产级高并发。')

title(4,'模型选择、集成与优化')
p('生成模型为 Qwen3-4B Q4_K_M，本地 llama.cpp 兼容接口，8192上下文。选择依据是零API预算、本机计算资源和资料隐私；并未宣称与更强云端模型等价。模型安装脚本校验固定文件指纹。')
p('检索使用 BM25、多语言 MiniLM 与排名融合，辅助中文问题定位英文论文。生成按结构化字段输出论断与引文，服务端核对真实来源，再执行数值、条件、语义支持与重复内容过滤。')
table([['优化位置','采用机制及边界'],['检索/问题组织','保留子问题原句与文献归属，避免对象和范围串联'],['来源校验','引文存在、页码块归属、完整原文一致性；不能只验证引用编号'],['数字与条件','有限数量角色、单位、否定及实验条件防护；规则不能覆盖所有语义'],['模型支持初筛','结合子问题与完整引文复核；同模型误判仍可能存在'],['缺失处理','保留部分答案、未解决项和候选原文；不凭空补全']],[115,370])
p('未做基础模型微调或权重训练。迭代主要是检索、提示、约束与工作流优化；失败实验和撤回方案保留在证据包中。')

title(5,'核心特色：证据变化影响复核')
p('传统文本差异回答“哪里改了”，墨衡进一步帮助核查“哪些既有笔记与研究成果需要重新检查”。用户先保存结论及原文，新版本进入后定位对应段落，比较数值、条件、数据集与报告范围，输出保持、变化或不确定的模型初判。')
table([['环节','可审查输出'],['证据对齐','旧引文、新版本候选原文与各自页码'],['语义条件检查','相同数字是否指同一对象，否定与适用条件是否变化'],['影响追踪','引用这段证据的笔记、回答或后续成果待复核'],['用户确认','保留历史与原始出处，人工确认，不自动裁决论文真伪']],[110,375])
shot('scene-4.png','当前版本实录：版本复核与两侧来源。',230)
p('历史开发回归曾达到48/48受控案例、12/12已见真实版本案例；均为开发方构造或已暴露标签，不代表总体100%准确，也不是独立评审。','small')

title(6,'创新补强：从漏答到原文补查')
p('回答核对清单从用户明确要求提取核对项，定位相关表述并准备补问。比较前检查显示缺格和原文中的单位/阶段线索；不把关键词命中当作答全，也不把单位相同当作科学可比。')
p('新增“只依据此段追问”：用户从证据卡片选择完整原文，服务端重新核验归属和文本一致性。只向模型提供该段，仍执行完整校验；生成失败仅保留该原文，不自动退回全文检索。保存与导出保留页码、块标识、文本哈希和范围说明。')
shot('scene-8.png','当前版本实录：展开并核对限定追问的完整原文。',255)
p('切换论文或检索范围会清除旧选段。此段缺信息不能推断整篇论文未报告。当前只支持12—4000字符的单个完整原文块，过长则明确提示。')


title(7,'文献解析、阅读与双语')
p('原生PDF使用文字层和页面坐标；扫描件使用OCR。混合PDF补充文字覆盖诊断；按页补识别保留原生块并过滤同位置重复，避免简单重导入损坏历史引文。公式与复杂表格保留原图核对入口。')
p('既有资料覆盖标准Transformer、扫描版和541页长书；此前长书第500页抽查证明后部可定位，但不能据此认为541页每个公式都准确。公开评审库仅预置5篇上手文献，完整测试规模见独立证据包。')
p('阅读支持页码删空重输、目录、缩放、正文搜索与书签；Enter发送与换行可选。首次教程和模块帮助同步维护；Ctrl+K快捷查找可直达功能或库内论文。批量导入逐文件报告失败，保留成功结果。双语按原文段落对齐、联动滚动，公式/代码/URL/数值保护后导出Markdown或HTML。')
shot('bilingual.png','真实浏览器：双语段落与原文对照。',260)
p('术语翻译、否定范围、扫描符号仍需人工核验；不承诺任意PDF原位双语排版或完整结构精度。')

title(8,'论文发现、引用图谱与研究辅助')
p('发现入口包括准确题名、主题、DOI/arXiv编号；使用arXiv、Crossref等免费公开接口。当前论文可作关联推荐起点，反馈调整推荐，检索历史与定期追踪保留。开放全文可入库，访问失败、限流或无权限会明确报告。')
p('图谱从本地参考文献与可获得的外部记录建立局部引用边，PageRank/中心性作为核心节点线索。综述和Future Work候选保留来源与时间范围；对“后续研究已解决”的判断依赖已查到文献，不能证明全球范围的新颖性。')
p('研究项目组织文献、证据笔记与成果；对照表保存单位、指标、实验条件和待补查项；补查任务能附原文后回填，也允许说明原因未解决关闭。')
shot('scene-6.png','当前版本真实研究项目：文献、研究目标与成果组织。',250)
p('推荐理由和引用数量都不是文献质量的确定性证明。外部接口在不同时间可能变化，需区分历史验收与当前连通。')

title(9,'写作辅助、实验与绘图')
p('写作从已有证据生成框架，References来自真实记录；草稿可编辑并保留历史。实验设计卡包含对照、指标、种子与预算等检查项，生成方案仍是待验证假设，不冒充已完成实验。')
p('自然语言图意先生成节点/边结构，再编译Mermaid。校验重复ID、非法端点、判断分支和回环，失败携具体错误重试；合法图结构仍需核对科研语义。CSV绘图保留原始数据、坐标单位、统计说明与可重跑脚本，图注不得把相关性写成因果。')
shot('scene-7.png','真实模型图稿：合格/不合格分支与人工修正回环。',270)
p('上述图稿来自实际后端请求，没有替换API返回。图像视频画面只能证明本次演示动作，不代表任意复杂图意都正确。')

title(10,'测试设计与真实结果')
table([['验证层级','已记录事实','结论边界'],['工程回归','420项后端测试；前端类型和构建通过','不等于420道科研题正确'],['选段开发检查','4题、11次真实模型调用，无调用错误','开发者预选段落，已暴露论文'],['真实浏览器','选段读取/问答/导出/解除/切换4组通过','自动走查，不是真人效果'],['数据保全','正式文库29张非FTS表内容一致','针对所记录验证时段'],['演示录制','当前版本8段真实浏览器操作完成','合成旁白；等待和停留经剪辑']],[90,205,190])
table([['真实案例','结果'],['原复杂Pre-LN问题','仍部分回答，结构/适用条件漏答，不认定已解决'],['聚焦Post-LN梯度与warm-up','解释有原文依据；存在重复措辞'],['LN与batch size 1','主要事实有据；中英混杂影响表达'],['同段问精确GPU峰值显存','未生成无据论断，仅本段不足，不推断全文缺失']],[160,325])
p('本地提交证据包保留协议、全部调用和输出、代码哈希、首次失败及撤回实验；公开Release提供验收摘要。没有独立用户研究，不声称效率提升百分比或盲测准确率。','small')

title(11,'零费用部署与运行')
p('本机运行模型及完整后端；GitHub托管源码和固定评审入口，免费HTTPS隧道连接独立评审实例。无购买云服务器、域名、模型API或付费订阅；本机电力、网络与硬件仍需已有条件。')
p('固定入口：https://cclcclcclcclcclccl.github.io/scholartrace/\n源码：https://github.com/cclcclcclcclcclccl/scholartrace')
p('评审库另建账号，只预置5篇公开论文，不复制作者笔记与私人账号。公开模式关闭注册，研究接口需要登录，cookie使用Secure/HttpOnly。账号凭据单独交付，不进入公开仓库或技术PDF。')
p('已验证免费公网健康接口可达；独立评审账号已在本机完成登录、资料隔离和真实问答检查。公网HTTPS专用账号登录与真实问答已通过一次验证；跨独立网络及24/72小时可用性尚未验证。不得把静态入口或一次HTTP成功写成评审期持续可用。')
p('运行条件：电脑开机、联网、模型与隧道进程保持；休眠关机或免费隧道中断会影响完整应用，隧道重启可能更换地址。稳定入口需同步最新后端地址。固定入口、仓库及材料发布结果以最终验收清单为准。')

title(12,'安装、恢复与材料清单')
p('Windows安装：Python 3.12与Node 22.12+；python -m venv .venv；安装requirements-lock.txt；npm --prefix frontend ci及npm --prefix frontend run build；下载校验llama.cpp、Qwen3-4B与MiniLM；node scripts/start.mjs。首次模型下载需要数GB磁盘，不使用付费API。')
p('本轮修复运行时安装器对历史artifacts缓存的依赖，改为固定官方版本、SHA256校验与自动解压。网络证书使用系统可信根，不关闭TLS验证。公式识别按独立安装脚本准备。Docker配置保留但未在本机实跑。')
table([['提交材料','对应要求'],['GitHub源码与真实历史','README、架构、安装、作者、环境模板、依赖锁及历史'],['技术文档PDF','不超过30页，覆盖概述/需求/架构/AI/实现/测试部署/展望'],['MP4演示视频','当前实录，普通话合成讲解，1080p，5—8分钟'],['在线体验及专用账号','固定入口和独立空间；持续在线仍依赖本机条件'],['附件','字幕、讲稿、使用教程、验证证据、哈希与Git bundle']],[140,345])
p('本次预指导表单已只读核实，截止为2026年10月31日15:00；需网盘完整材料、作品介绍PDF与公开视频平台链接，且之后仍需正式省赛提交。尚未代作者填表提交。')

title(13,'创新定位、局限与展望')
p('技术创新定位：将原文证据、版本变化和笔记/成果依赖组合，围绕已有结论做条件敏感的复核；将限定原文和共享验证结合，避免补问时悄悄漂移检索范围。应用创新定位：把阅读中的漏答、比较缺项与证据变化转为可操作的补查和复核流程。')
p('没有声称提出新基础模型或经同行评审的算法突破。版本初判与支持性复核仍依赖小模型，可能共享错误；长复合问答、专业翻译、表格公式仍有质量差距；外部资料覆盖不全，无法保证新颖性判断。')
p('后续以未参与调参的新题和独立标注为主，分别测量检索命中、回答覆盖、错误接受与错误拒答；同一协议比较模型成本和收益。真人研究可用后，验证版本复核是否降低遗漏，不能预先虚构效果。')
p('赛事原始标准不会因当前限制被降低。已有功能、工程验证和可公开交付分别列明；无任何获奖保证。')

title(14,'来源与 AI 协作披露')
p('赛项依据为用户提供的完整文字与科研小助手资料包；技术参考包括Qwen3、llama.cpp、PyMuPDF、PDF.js、MiniLM、FastAPI、React与Mermaid上游说明，具体版本由依赖锁与安装器固定。原论文版本、页码和哈希见证据协议。')
p('AI编程助手参与需求整理、代码、调试、评测、材料与部署；作者提出目标和修改意见，须理解、核验并对提交负责。演示为程序化真实浏览器录像和Microsoft Huihui本地普通话合成，生成等待经剪辑；没有伪造API响应或真人实验。')
table([['可复查材料','用途'],['docs/需求验收矩阵.md','原始需求与验收标准'],['docs/限定原文追问与验收_2026-10-21.md','当前增量与失败边界'],['artifacts/source-followup-20261021/','四题协议、原始输出、11次调用及浏览器记录'],['artifacts/moheng-final-20261021/','本轮录屏、媒体/PDF/部署及包验证'],['docs/开发历史与历轮验收.md','历史实验、撤回方案与交付索引'],['完整Git历史与bundle','真实已有提交与本轮整理提交，不伪造日期']],[265,220])
p('模型权重、个人数据库、评审密码和原版论文不进入公开源码仓库。第三方组件和模型分别遵循上游许可，详见第三方来源与分发说明。')

def footer(c,doc):
 c.setStrokeColor(colors.HexColor('#DCE6DE'));c.line(48,48,547,48);c.setFont(FONT,8);c.setFillColor(MUTED);c.drawString(48,32,'墨衡 Moheng / 蔡晨霖 / 2026-10-21');c.drawRightString(547,32,str(doc.page))
file=OUT/'墨衡_Moheng_技术文档_2026-10-21.pdf'
SimpleDocTemplate(str(file),pagesize=(595.28,841.89),leftMargin=55,rightMargin=55,topMargin=48,bottomMargin=65,title='墨衡 Moheng 技术文档',author='蔡晨霖').build(story,onFirstPage=footer,onLaterPages=footer)
(ROOT/'docs/墨衡_技术文档_2026-10-21.md').write_text('\n'.join(md),encoding='utf-8');print(file)
