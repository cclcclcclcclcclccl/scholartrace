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
story=[];md=['# 研证 ScholarTrace 技术文档\n\n蔡晨霖 · 西安交通大学人工智能2501 · 2026-10-18\n']
def p(text,kind='p'):
 story.append(Paragraph(html.escape(text).replace('\n','<br/>'),styles[kind]));md.append(text+'\n')
def title(num,name):
 if story:story.append(PageBreak())
 p(f'SCHOLARTRACE / {num:02d}', 'k');p(name,'h');md.append('## '+name+'\n')
def table(rows,widths):
 cells=[[Paragraph(html.escape(str(v)),styles['cell']) for v in row] for row in rows]
 t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E2EEE7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CCD9CF')),('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDE5DF')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.extend([t,Spacer(1,13)]);md.extend([' | '.join(map(str,row)) for row in rows]);md.append('\n')
def shot(name,caption,maxh=255):
 f=ROOT/'artifacts/submission-20261018'/name
 if f.exists():
  im=Image(str(f));scale=min(485/im.imageWidth,maxh/im.imageHeight);im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale;story.extend([im,Spacer(1,6)]);p(caption,'small');md.append(f'![{caption}](../../artifacts/submission-20261018/{name})\n')
# 01
p('SCHOLARTRACE · 研证','k');story.append(Spacer(1,55));p('让研究结论\n跟随证据一起更新','title');p('基于大模型与 Agent 的全流程科研助手','h');p('技术说明与可复核验证记录\n参赛者：蔡晨霖\n学校与班级：西安交通大学 · 人工智能2501\n版本日期：2026-10-18')
story.append(Spacer(1,18));p('核心主线：论文 → 原文证据 → 研究笔记 → 版本变化复核 → 研究成果。以来源可返回、变化可追踪、失败可检查为设计原则。')
p('当前交付为本机可运行作品及参赛材料审阅版。公开演示、报名状态、官方截止时间与独立用户研究尚未完成核验；本文不构成完整赛事验收或获奖保证。','small')
shot('reader.png','真实浏览器：原版论文、证据问答和研究空间。',190)
#02
title(2,'问题定义与使用路径')
p('目标用户是需要反复阅读、比较与跟踪论文的学生和初入科研的研究者。痛点包括：论文过多但关联不清；答案没有出处；数字与实验条件混淆；读过的结论在版本更新后失效；笔记、引用和写作成果分散。')
p('本作品覆盖六类科研任务，同时把“证据变化影响复核”作为主要辨识点。技术创新的可检验目标是：对一条已有笔记，找到旧版本的支持段落、新版本的对应证据，并说明可比条件与不确定性；应用创新是将复核结果连接到用户已有的研究材料。')
table([['步骤','用户操作','可审阅产物'],['1 建立资料范围','导入论文，加入研究项目','文献、版本与项目关联'],['2 阅读与提问','选择单篇或多篇，提出具体问题','分项回答、未解决项、原文页码'],['3 留存证据','定位原文，将结论存为笔记','结论与完整引用、坐标'],['4 版本更新','选择对照版本，执行复核','两侧证据、警示、复核报告'],['5 形成研究成果','整理矩阵、方案、图稿与数据图','可编辑成果、引用与导出包']],[70,190,225])
p('验收原则：功能存在、自动测试通过、真实模型输出正确、独立研究者认可，是不同层级的证据。本文分别标明，不用单元测试数量代替模型正确率。')
#03
title(3,'赛项需求与实现范围')
table([['赛项模块','当前实现','验收边界'],['文献管理与解析','批量导入、哈希去重、版本候选、文本坐标、OCR、结构与公式工具','复杂公式、扫描表格需原图复核'],['抗幻觉问答','混合检索、分题取证、多篇范围、引用和数值核验、支持性复核','漏答、错误拒答和语义错误仍可能发生'],['阅读与翻译','PDF原版、页码、目录、划词、双语段落同步、MD/HTML导出','不承诺任意论文的原位双语PDF'],['检索与推荐','题名/标识符/主题、关联推荐、开放全文入库、周期追踪','受网络、元数据覆盖和开放权限限制'],['引用与研究辅助','局部引用图、中心性、综述、未来工作候选、实验设计卡','图谱覆盖不完整；候选想法不是新颖性证明'],['写作与绘图','带来源框架、方案修订、Mermaid、CSV数据图、重跑包','图结构合法不代表语义完全正确']],[92,206,187])
p('需求台账保存在 docs/需求验收矩阵.md，共54个原始需求编号。本文聚合展示模块，不将局部真实验证扩大为54项全部独立验收。公开部署、实战人测和提交入口核验列在收尾清单。')
#04
title(4,'系统架构与数据流')
d=Drawing(485,245)
boxes=[(12,172,220,55,'React / TypeScript','PDF.js · 项目 · 工作台'),(254,172,220,55,'FastAPI / Agent','受控工具 · 持久任务'),(12,73,145,55,'检索与解析','BM25 + MiniLM'),(170,73,145,55,'本地生成模型','Qwen3-4B / llama.cpp'),(328,73,145,55,'持久数据','SQLite · PDF · 成果')]
for x,y,w,h,a,b in boxes:
 d.add(Rect(x,y,w,h,fillColor=colors.HexColor('#EEF4EF'),strokeColor=INK,strokeWidth=.7));d.add(String(x+10,y+33,a,fontName=FONT,fontSize=11,fillColor=INK));d.add(String(x+10,y+13,b,fontName=FONT,fontSize=9,fillColor=MUTED))
for x1,y1,x2,y2 in [(232,199,254,199),(365,172,85,128),(365,172,242,128),(365,172,400,128)]:d.add(Line(x1,y1,x2,y2,strokeColor=GOLD,strokeWidth=1.4))
d.add(String(12,31,'所有候选生成结果通过来源与参数检查后再进入保存流程',fontName=FONT,fontSize=11,fillColor=INK));story.append(d)
p('前端以原版阅读器为中心，任务与成果在项目中聚合。后端将解析、检索、翻译、问答、版本复核及绘图分为模块；Agent 的工具名和参数经过结构化校验，不能任意执行模型生成的系统命令。')
p('文献记录保留文件指纹；证据块保存文献ID、页码、顺序、坐标及提取方法。研究笔记和成果引用已有证据，不通过删除或重新导入改变历史。项目关联与原始资料分离，取消关联不删除文献。')
p('长任务持久化进度、状态和错误，提供取消、重试与恢复。保存使用版本冲突检测；陈旧页面提交返回409，避免静默覆盖。单机推理以有限并发降低显存压力，不能据此宣称已经支持高并发生产负载。')
#05
title(5,'模型选型与抗幻觉问答')
p('生成模型使用 Qwen3-4B-Q4_K_M，通过 llama.cpp 的本地兼容接口调用。选择依据是零API费用、隐私数据留在本机和本机显存条件。运行配置为8192上下文、单推理槽、8线程；模型大小限制复杂推理和翻译润色能力，不能当作强力云模型的等价替代。')
p('检索采用 BM25 与多语言 MiniLM 融合，中文问题可生成英文检索词。每篇论文独立取证；复合问题保留子问题原句和归属。为“请分别给出数量”等泛指追问保留前文，避免将它拆成无对象的问题。')
table([['环节','约束与失败行为'],['生成前','明确文献范围与子问题，检索真实证据，不让模型凭参数记忆填充来源'],['生成后','检查引用ID、原文片段、数值、单位、对象、否定及实验条件'],['支持性复核','结合当前子问题复核，避免误删用户明确要求比较的基线数据'],['保留与展示','逐项保留通过初筛的回答；未解决项提供候选出处或明确缺证据'],['修复策略','引用错配只在唯一兼容候选时提出改引，再经普通核验；同文献同子问题的完全重复论断去重']],[95,390])
p('当前仍需改进的例子还包括Whisper遗漏下采样/VAD用途，以及QLoRA附加12小时描述未保留模型配置。这些机制是防护层，不是真理判定器。模型自检可能与生成共享偏差；数字在原文出现，也不代表属于同一实验。用户仍应核对完整引用和上下文。')
#06
title(6,'问答质量：保留失败与回归')
rows=[['轮次','范围','可支持的结论'],['v1首轮','12个真实问答案例','7个可答题：4完整、2部分、1拒答；保留首轮结果'],['v4修复回归','15个已见问题','12个可答题9个完整；3个虚构实验题拒答；25条论断22条完整引用支持']]
for key in ['v5','v6','v7']:
 f=ROOT/f'artifacts/proof-{key}-qa/agent-source-audit.json'
 if f.exists():
  a=json.loads(f.read_text('utf-8'));from collections import Counter
  c=Counter(x['verdict'] for x in a['cases']);n=sum(sum(x['claim_supported_by_full_quote']) for x in a['cases']);total=sum(len(x['claim_supported_by_full_quote']) for x in a['cases']);rows.append([key+'开发回归','15个已见问题',f"完整有据{c['complete_supported']}，正确拒答{c['correct_abstention']}；{n}/{total}条论断完整引用支持"])
table(rows,[85,110,290])
p('代表性修复：CLIP比较题曾正确检索到ImageNet的128万张训练样本，却被支持性复核误判为无关。现在复核显式考虑当前子问题与比较基线，但该漏答在最终回归中仍未解决。BLOOM和Switch案例暴露了“数值正确但引用对象错误”，增加计数对象核验；同时拦截把“查询集合中的任一项”写成“全部查询”的泛化。')
p('最终交付采用v6冻结代码。v7启用推理审核后，严格完整有据仍为9/12；单题耗时中位数从13.1秒升至16.7秒，因此撤回该默认设置。v7原始结果与源代码快照仍保留，不能把这次尝试写成准确率提升。')
p('每轮先固定问题、预期与代码哈希，再执行真实模型调用，保存原始回答、完整引用、模型调用和耗时。报告包含失败筛选，不能只展示成功案例。新增修复在已见题上验证，因此属于开发回归，不是独立泛化准确率。')
p('原始证据：evaluation/proof_v1、proof_v4_qa、proof_v5_qa、proof_v6_qa；对应 artifacts/proof-* 目录。完整交互报告位于 evaluation/reliability/report.html。独立人工标注人数目前为0。','small')
#07
title(7,'特色：证据变化影响复核')
p('普通段落差异只能指出文字变动。研证以已有研究结论为入口，检索新版本中的对应证据，再检查结论是否仍受支持。用户看到的是“哪条笔记需要重新核验、为什么、应查看哪段原文”。')
table([['步骤','输出','控制误判'],['对齐','旧证据与新版本候选段落','未对齐不能直接认定结论被推翻'],['语义初判','保持、变化或不确定的候选判断','要求两侧可核对的原文'],['一致性保护','数值/单位/否定/数据集/条件警示','条件不同时不当作可直接比较'],['影响检查','笔记与相关研究成果的复核入口','保留原始版本与人工最终判断']],[68,170,247])
p('对照实验采用文本对齐基线。在两组已见受控案例合计48项中，最终开发回归判定48项符合预设标签，基线21项；同轮12项真实版本案例符合预设判断。标签为开发方制定，案例数量有限，不能据此宣传真实科研场景100%准确。')
shot('scene-4.png','真实版本复核界面：两侧证据与结果。',230)
#08
title(8,'PDF解析与复杂文献')
p('系统保存原版PDF，解析层提供文本、页码、坐标和结构候选。标准文档使用原生文字层，扫描文档通过OCR补充文字；公式工具保留原图并允许编辑LaTeX，避免将识别候选包装成确定结果。')
table([['本轮抽查','页码','已验证事实'],['Transformer原版','3 / 8','分别提取11 / 24个证据块；保存页面渲染'],['Transformer扫描版','3','提取13个OCR证据块；保留原图'],['Understanding Deep Learning','500 / 总541','提取50个证据块，可定位长书后部']],[195,95,195])
p('以上是页面覆盖与提取存在性验证，不是表格、公式、标题树的精确率。双栏顺序、跨页表头、扫描符号、页眉干扰仍需更大规模逐项标注。原图始终作为复核依据，OCR文本仅作为检索和阅读辅助。')
p('新增复测保存了4个页面的源文件哈希、提取文本、方法、结构与PNG，位于 artifacts/module-quality-20261015-repair。自动规则无法证明每个符号都正确。')
p('版本策略同时考虑内容哈希、论文标识符、标题及文本相似度；同一论文不同版本保留各自来源。建议最新版本不代表强制删除旧稿，复核历史必须保留。')
#09
title(9,'阅读、翻译与交互完成度')
p('页码输入允许先删空，再输入7，回车或跳转按钮确认；问答默认Enter发送、Shift+Enter换行，可切换为Enter换行。首次访问显示教程，各模块可随时打开帮助，降低版本复核等新功能的学习成本。')
p('翻译按段落缓存并保留原文关联。代码、公式、URL、数值和引用经过占位保护；本轮修复用户自带占位符与嵌套代码冲突，采用一次性恢复。中文翻译若只有英文会重试；句子含公式时不再直接当作纯公式原样返回。')
p('8个已见翻译诊断样例均完成实际调用并通过保留检查。否定、可能性、数值、未评估条件和特殊标记得到保留；“500个查询之一”的中文表达仍生硬，不能称为8/8专业翻译准确。完整源文与译文公开在本地证据包中。')
shot('bilingual.png','双语与引文：段落对齐及原文核对。',265)
#10
title(10,'发现、推荐与引用洞察')
p('论文发现支持从准确题名、DOI/arXiv标识符或研究主题进入。arXiv与Crossref提供外部元数据，开放全文可下载后入库；当前论文可以作为关联推荐起点，研究偏好和反馈用于调整推荐。周期追踪保留任务状态与搜索历史。')
p('来源限制必须显式展示：开放元数据不是完整全文库；推荐相近不等于质量可靠；引用计数、仓库许可与更新情况只作为可复核线索。网络超时、限流、闭源全文等情况应报告失败并允许重试，不能返回伪造论文。')
p('引用图谱基于已解析参考文献与可获得的外部记录，提供版本折叠、PageRank/中心性及局部关系。图谱边只代表当前资料中的关联，不是全领域完整引用网络。研究综述与未来工作候选应携带真实来源，并标注缺少后续文献核查的范围。')
shot('scene-5.png','论文发现入口；画面本身不代表本轮已执行外部检索评测。',270)
p('本轮重点回归问答、翻译、解析和绘图；外部检索之前的验证记录见 docs/搜索推荐真实验收_2026-10-14.md。其日期、网络和来源覆盖不能自动视为今天持续可用。','small')
#11
title(11,'研究组织、写作与意图绘图')
p('研究项目管理问题、论文、笔记、任务和成果。项目内的空文献范围被拒绝，防止用户以为仅查本项目，实际上查了整个文献库。项目导出保存来源和关联信息，成果可继续编辑与归档。')
p('写作辅助生成框架、证据矩阵和待验证方案，References/BibTeX必须来自实际记录。实验设计卡记录对照、指标、种子和失败标准；CSV统计保留原始点、样本标准差及均值区间，不把模拟或缺失数据称为真实实验。')
p('绘图先生成结构化节点和边，再编译Mermaid。判断节点至少包含两条有区别的分支标签；重复ID、无效端点与重复边被拒绝。重试携带先前输出和具体错误，方向、并行和回环遵循用户意图。三个已见复杂度不同的真实模型图稿均通过结构检查与开发方意图核对。')
shot('scene-7.png','真实生成并渲染的图稿；语义正确性仍需用户核对。',265)
#12
title(12,'工程验证与证据保全')
table([['检查','本轮结果','解释'],['后端自动测试','272 passed','覆盖逻辑、防护与工作流；不等于272个真实模型题'],['翻译/绘图真实诊断','8段翻译、3个图稿','保留原始失败和修复回归；非盲测'],['解析页面抽查','4页，含扫描件与长书','验证提取、来源和渲染；非结构精度统计'],['数据保全','评测使用SQLite快照','对比主库表计数、哈希与integrity_check'],['浏览器录屏','真实交互，隔离演示库','不拦截替换API响应；合成旁白明确标注'],['独立用户研究','0名参与者','已有任务页与评分脚本，尚未真实招募']],[112,140,233])
p('所有真实模型轮次保留代码哈希、协议哈希、输入资料哈希、原始结果与计时。版本复核使用基线对照；问答逐条检查完整引用支持，不能只检查页码存在。自动UI回放与真实模型输出分开标记。')
p('安全与稳健性机制包括：账号资料范围隔离、输入结构校验、生成内容转义、任务取消与去重、冲突提示、失败保留和数据库备份。它们不能替代公开部署后的安全测试和长期稳定性监控。')
#13
title(13,'部署、运行与复现')
p('本机运行：在项目根目录执行 node scripts/start.mjs，或双击“启动研证.cmd”。网页监听127.0.0.1:8765，本地模型监听127.0.0.1:8081；不需要付费API。停止脚本核对进程身份后只结束本项目拥有的进程。')
p('新环境依赖：Python 3.12、Node.js 22+；安装 requirements-lock.txt，frontend 内运行 npm ci 与 npm run build。模型权重、向量模型与 llama.cpp 需按README下载并核对许可证。代码包不包含个人数据库、原版论文、模型权重或环境密钥。')
p('复现测试：.venv/Scripts/python.exe -m pytest -q；前端在frontend运行npm run build。评测以协议和哈希为准；如果更改产品代码，应创建新轮次目录，不覆盖历史冻结结果。原始数据备份使用SQLite备份机制，避免直接复制活跃WAL文件。')
p('当前服务是单机演示。提交要求的公网地址尚未部署；上线前需选择持续在线主机、HTTPS和访问策略，关闭调试入口，配置评审空间与必要限流，完成清洁环境恢复和连续可用性检查。仅把本机端口映射出去不等于完成部署验收。')
p('演示视频与技术PDF分别满足文件格式、页数/时长等形式要求后，也仍需本人复核内容；参赛报名、收费与最终提交必须基于真实赛事账号状态。')
#14
title(14,'收尾清单与进一步改进')
table([['事项','当前状态','完成条件'],['技术PDF、演示材料','本轮制作并校验','本人阅读，核对赛事最终版本要求'],['本机应用与回归','可运行；有测试及真实输出','保留结果，不推广为全场景保证'],['公开代码仓库','尚未核验公开可访问','上传经审查的源码与真实Git历史'],['公网演示与评审账号','未完成','持续在线部署、登录体验与数据隔离验证'],['官方日期/报名状态','待本人或官方账号核实','原材料存在不同阶段日期，不能猜测'],['独立质量评估','未完成','新题盲测、人工标注、真实用户任务'],['本人答辩与最终提交','未完成','理解系统、录制/确认讲解、官网提交']],[132,145,208])
p('后续优先级：第一，进行未参与调参的新题集及双人标注；第二，扩大复杂表格/公式的真实错误分析；第三，在相同协议上对比更强模型的正确率、延迟与成本；第四，证明版本复核确实减少遗漏或节约时间。模型升级必须由对照结果支持，不因模型名称更强就宣称质量提升。')
p('已知边界：本地4B模型存在复杂问题漏答、表达重复、翻译生硬和自检误判；扫描与公式识别不完美；外部检索不保证全覆盖；设计方案不等于实验完成；已见题回归不能证明泛化。')
#15
title(15,'来源、开发过程与AI协作说明')
p('赛事依据来自用户提供的赛项文字和资料包。技术文档按其中“项目概述、需求分析、架构、AI方案、核心功能、测试部署、总结展望、创新点”组织。材料内含不同阶段截止日期，正式提交须回到赛事账号核实。')
p('开发使用人工智能编程助手参与需求梳理、代码实现、测试、错误分析和文档制作；用户提出产品目标、交互需求与修改方向。本文不虚构独立人测、真人访谈、实验训练或未发生的提交记录。合成旁白和程序化真实浏览器录制在视频及说明中披露。')
table([['来源/产物','用途'],['docs/赛事要求原文_用户提供_2026-10-11.txt','原始比赛约束；保留来源，待官方核验'],['docs/需求验收矩阵.md','54项原始需求与实现范围'],['evaluation/reliability/report.html','完整多轮记录、引用与失败筛选'],['evaluation/proof_v*/protocol.json、freeze.json','预设问题、标签及代码/协议哈希'],['artifacts/proof-*/run.json、model-calls.json','真实推理与计时；不覆盖旧轮次'],['artifacts/module-quality-20261015-repair/run.json','8段翻译、3图稿、4页解析原始记录'],['README.md、docs/部署与复现.md','环境与运行步骤、模型及第三方来源']],[272,213])
p('论文案例使用Transformer、Whisper、CLIP、QLoRA、DPO、BLOOM、Switch、ZeRO、InstructGPT等原论文。具体版本、原文页码和文件指纹以协议中的sources及运行记录为准，避免文档中转录不完整引用。')
def footer(c,doc):
 c.setStrokeColor(colors.HexColor('#DCE6DE'));c.line(48,48,547,48);c.setFont(FONT,8);c.setFillColor(MUTED);c.drawString(48,32,'研证 ScholarTrace · 蔡晨霖 · 2026-10-18 · 技术文档');c.drawRightString(547,32,str(doc.page))
file=OUT/'研证_ScholarTrace_技术文档_2026-10-18.pdf'
SimpleDocTemplate(str(file),pagesize=(595.28,841.89),leftMargin=55,rightMargin=55,topMargin=48,bottomMargin=65,title='研证 ScholarTrace 技术文档',author='蔡晨霖').build(story,onFirstPage=footer,onLaterPages=footer)
(ROOT/'docs/技术文档_2026-10-18.md').write_text('\n'.join(md),'utf-8');print(file)
