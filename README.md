# 研证 · ScholarTrace

面向研究证据更新审计的科研助手。参赛者：蔡晨霖，西安交通大学人工智能 2501 班。

本项目围绕“保存结论与出处 → 对比论文版本 → 找出需要重新核验的内容”建立特色，以本地模型完成科研阅读、翻译、检索、图谱与写作。2026-10-12 已形成六模块可运行工作台；复杂公式/扫描表格精度、固定问题集、独立公网与提交材料仍需验收。具体证据及边界见 [本轮验收记录](docs/六模块实现与验收_2026-10-12.md)。

## 可用功能

- React/TypeScript 前端和 FastAPI 后端，原生 PDF.js 阅读、换页与证据块坐标高亮。
- 阅读器支持内嵌目录搜索与跳转、75%–200% 相对适合宽度缩放、原生文字选择、按文献保存阅读页码；点击证据自动滚动至出处。
- 页码可删空编辑，Enter／跳转按钮／失焦后确认；提问默认 Enter 发送、Shift+Enter 换行，可切换 Enter 换行并保存偏好。
- 首次访问弹出四步教程，顶部可重新打开；文献库、阅读器、问答、笔记及版本复核提供独立帮助入口与真实操作示例。
- 本机 SQLite 文献库，BM25 与多语言 MiniLM 语义检索融合，中文问题用本地模型转为英文检索词，持久保存页码、坐标及版本。现有语料 40 份 PDF（赛事原始 39 份与独立补充 GPT-2 原论文），47,872 段已建立向量索引。
- 上传 PDF、内容哈希去重；正文标识符/标题与文本相似度辅助识别版本，不依赖文件名。
- 保存研究笔记及原始引文，用文本对齐基线找到变化，再由本地模型围绕笔记进行语义初判；两侧原文引用均检查存在性。
- 本地 OpenAI-compatible 推理接口；模型不可用时明确显示证据检索模式，不伪造生成回答。
- 资料检查、扫描件 OCR、真实 PDF 集成测试和浏览器验收脚本。
- 文献归档/恢复、标题编辑、章节/图表/参考文献结构、541 页长书后台解析；双版本全文差异及两侧原文跳转。
- 本地公式 OCR：原生 PDF 自动候选、扫描件手动框选、可编辑 LaTeX 与原图并排核对、公式保存和导出；符号错误仍需人工检查。
- 单篇与多篇问答：每篇独立取证、引用存在检查、模型支持性初筛、缺证据提示；自动保存回答供版本更新时复核。
- PDF 正文引用与文末参考文献往返；选段/整篇中英翻译、逐段双向滚动、Markdown 与双语 HTML 导出，数字和代码保留检查。
- arXiv/Crossref 实际检索、开放全文下载入库、周期追踪、偏好反馈、主题推荐及 GitHub 公开仓库状态/许可核验。
- 原文引用关系图、版本折叠、PageRank/中心性、引用用途线索、主题综述与未来工作进展初判。
- 待验证研究方案、真实来源 References/BibTeX、按目标生成 Mermaid 图稿、CSV 折线/柱状/表格/三维雷达与数据图注，图表导出 PNG/SVG/PDF 和重跑包。
- Agent 规划与结构化工具参数校验、真实执行/流式事件记录；持久化任务、取消/重试、崩溃后恢复；账号空间与文献权限隔离。
- 实验设计卡支持明确对照、变量、指标、种子和失败条件，修改生成新版本；重复实验 CSV 统计保留设计快照、原始点、均值、样本标准差及 95% t 均值区间，可下载原始数据与实际重跑包。
- 研究方案可生成保留原稿和引文的独立修订稿；对维度、任务指标、独立种子、训练预算和计时条件给出可检查提示。真实本地模型修订仍有遗漏，详见 [最新实验与问答验收](docs/实验设计统计与问答改进_2026-10-12.md)。
- 注意力试跑设计支持结构化参数校验、保存版本的 CPU 小张量前向预检、下载重跑及历史快照；没有执行完整训练。新题集暴露的否定比较错误已增加保护，多行规格表保留表头来源；真实结果及边界见 [新问题评测与执行预检](docs/新问题评测与执行预检_2026-10-12.md)。

本地生成模型为 Qwen3-4B，向量模型为多语言 MiniLM，均无付费 API 回退。版本审计和论断支持判断是辅助初筛，不能证明科研结论的真伪。公式使用 RapidLaTeXOCR 离线识别候选，实测存在括号错误，须对照原图校正；扫描表格结构也需要核对。外部检索会受到数据源限流影响，系统保留失败任务并允许重试。

## 本机使用

已配置环境时，双击根目录 `启动研证.cmd`，或在项目根目录运行：

```powershell
node scripts/start.mjs --open
```

访问 `http://127.0.0.1:8765`。若浏览器显示“拒绝连接”，先双击 `启动研证.cmd`，等待浏览器打开；这通常表示本机网页服务未运行。电脑重启后也需要重新双击启动。

Windows 启动器会创建独立于临时开发命令的后台守护进程，检查并启动网页和本地模型，子进程异常退出后按退避间隔恢复。启动完成后不需要保留终端窗口；未设置系统开机自启。重复启动会复用现有守护进程。网页每 5 秒更新服务状态，断线后自动尝试重连，模型未就绪时可检索原文。

服务仅监听本机。日志保存在 `artifacts/runtime/`，故障时查看 `supervisor.log` 与 `server.error.log`。本地地址不是赛事要求的公网演示地址。休眠或关机期间服务不能访问。

结束使用时可双击 `停止研证.cmd`，或运行 `node scripts/stop.mjs`，关闭本项目后台服务和模型。脚本会先核对进程路径与创建时间，避免误结束被复用 PID 的其他程序。

首次搭建（Python 3.12、Node.js 22+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
cd frontend
npm ci
npm run build
cd ..
```

将赛事压缩包中 `pdf/` 和赛项说明解压到 `data/competition/`，再运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/inspect_corpus.py
.\.venv\Scripts\python.exe -X utf8 scripts/import_corpus.py --all
.\.venv\Scripts\python.exe -X utf8 scripts/ocr_document.py data/competition/pdf/1706.03762v1_img.pdf
node scripts/start.mjs
```

模型准备与来源记录在 `scripts/probe_models.mjs`、`scripts/download_model.mjs`、`scripts/install_llama.mjs` 中。不要仅凭模型文件名信任文件；下载脚本核验指定 SHA-256。模型下载和运行不使用付费 API。

多语言向量模型运行 `python scripts/install_embeddings.py` 安装。公式组件运行 `python scripts/install_formula.py`，会建立隔离环境 `tools/formula-env`，按独立依赖锁安装并核验约 179 MB 模型；不改变主应用的 NumPy 版本。安装好后识别不需要网络。公式浏览器验收为 `node scripts/check_formula_ui.mjs`。

## 结构

```text
backend/              API、文献块、检索与版本审计
frontend/             React 阅读与证据工作台
scripts/              资料检查、导入、OCR、运行和验收脚本
tests/                使用真实赛事 PDF 的隔离数据库集成测试
docs/                 需求、规则差异、实施步骤与实测报告
data/                 本机原始资料和 SQLite 数据库（不入 Git）
models/               本机模型及许可（不入 Git）
tools/                本机推理程序（不入 Git）
artifacts/            运行日志、详细评测和截图（不入 Git）
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
cd ..
node scripts/browser_check.mjs
node scripts/check_reader_quality.mjs
node scripts/check_usability.mjs
node scripts/check_full_workbench.mjs
node scripts/check_completion_ui.mjs
node scripts/check_recovery.mjs
node scripts/check_lifecycle.mjs
```

浏览器检查脚本目前使用本机已有 Chrome 和 Codex 随附 Playwright；迁移时可通过 `CODEX_BROWSER_MODULE` 指定 Playwright 模块位置。测试过程会在本机文献库保存一条标明“验收样例”的证据笔记。单元/集成测试使用临时数据库，不覆盖正式数据。

`check_reader_quality.mjs` 检查长文目录、缩放、文字选择、刷新后恢复页码、断线重连和过期结果隔离。`check_recovery.mjs` 会实际结束本项目网页进程以验证自动恢复；`check_lifecycle.mjs` 会短暂关闭网页和模型，再验证完整重启。后两者会短暂中断访问，不应与演示同时运行。

`check_usability.mjs` 用键盘选中、Backspace 删除和逐字符输入复现页码编辑问题；检查 Enter 发送、换行模式、偏好保存、输入法组合事件防误发、首次教程、五个帮助入口以及手机布局。包含一次真实本地模型问答；其余键盘请求使用明确的测试响应隔离推理耗时。测试使用独立浏览器上下文，不改变用户浏览器中的教程或快捷键设置。

## 真实性、许可与协作

用户提供的 PDF 保持原样，未默认纳入公开仓库；文件来源、页数及校验值由检查脚本记录。PyMuPDF 等第三方组件有各自许可，公开发布前必须完成许可与分发核对。Qwen 模型和 llama.cpp 程序的许可说明随本机下载资料保留。

项目由蔡晨霖提出目标、约束和质量要求，AI 协助设计、编码、调试和记录。Git 历史和实际测试报告保留真实开发过程；文档中的计划、已实现能力和实测结果分别标注。


本轮研究流程增强、真实模型失败与复测、竞品对照和仍未验收的质量项，见 [产品深度改进与真实验收](docs/产品深度改进与真实验收_2026-10-12.md)。新增正文搜索与书签、分类阅读清单、术语表和译文校正、逐项证据矩阵、写作草稿版本、自然语言绘图以及发现筛选分页。
