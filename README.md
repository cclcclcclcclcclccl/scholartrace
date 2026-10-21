# 研证 · ScholarTrace

**让研究结论跟随证据一起更新。** 面向科研论文阅读、比较与版本跟踪的全栈科研助手，使用本地大模型，不依赖付费模型 API。

参赛者：蔡晨霖｜西安交通大学｜人工智能2501。个人参赛，AI 编程助手参与实现、调试与材料整理；详见 [协作说明](docs/答辩与AI协作说明_2026-10-21.md)。

## 评审入口与提交材料

- [项目与评审入口](https://cclcclcclcclcclccl.github.io/scholartrace/)
- [源码仓库](https://github.com/cclcclcclcclcclccl/scholartrace)
- [材料下载](https://github.com/cclcclcclcclcclccl/scholartrace/releases/tag/submission-20261021)
- [逐步使用教程](docs/评审使用指南_2026-10-21.md)
- [需求验收矩阵](docs/需求验收矩阵.md) 与 [历轮原始开发记录](docs/开发历史与历轮验收.md)

在线入口页为静态导航；完整应用通过独立评审服务运行。免费隧道和本机模型依赖主机开机联网，无长期可用性保证。评审账号另附于提交材料，不公开密码。链接的实际发布、连通及最终提交状态见随包清单。

## 六大模块

| 模块 | 功能 |
| --- | --- |
| 文献管理与解析 | PDF 批量导入、内容与版本候选、OCR、逐页覆盖检查、按页补识别 |
| 证据问答与比较 | 混合检索、多篇逐项问答、原文锚点、核对清单、限定原文追问 |
| 阅读与翻译 | PDF 原版阅读、目录与页码、正文搜索、双语段落联动、术语校正 |
| 发现与推荐 | 题名/主题/DOI-arXiv 搜索、关联推荐、开放全文下载、追踪与历史 |
| 引用与研究辅助 | 局部图谱、中心性、综述、证据对照、待补查任务、实验设计 |
| 写作与绘图 | 有来源的框架、可编辑图稿、CSV 统计图、图注与复现导出 |

主要特色：将原文块、笔记和研究成果连接起来，论文版本变化后提供两侧证据和待复核项；把漏答与比较缺项转为有出处的补问、补查流程。系统集成创新不等于新基础模型或已证实的原创科研算法。

## 技术架构

React + TypeScript + PDF.js / Mermaid → FastAPI 工具编排与持久任务 → SQLite 文献/证据/成果。
检索使用 BM25、多语言 MiniLM 和排名融合；生成使用 llama.cpp + Qwen3-4B Q4_K_M。本地兼容接口仅允许环回地址，不会自动切换付费云模型。来源检查、数值与语义条件约束、模型支持性初筛共同工作，仍不能保证零幻觉。

## Windows 安装运行

先安装 Python 3.12、Node.js 22.12+（开发实测 Node 24）、Git。以下命令在源码根目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
npm --prefix frontend ci
npm --prefix frontend run build
node scripts/install_llama.mjs
node scripts/download_model.mjs
.venv\Scripts\python scripts/install_embeddings.py
node scripts/start.mjs
```

打开 http://127.0.0.1:8765/ 。首次下载免费公开模型需要网络和数 GB 磁盘；实际速度取决于本机硬件。若缺少模型，界面会说明降级状态，不伪造生成结果。公式识别为可选安装：`.venv\Scripts\python scripts/install_formula.py`。停止运行：`node scripts/stop.mjs`。

环境变量模板见 `.env.example`；锁定依赖见 `requirements-lock.txt` 和 `frontend/package-lock.json`。使用系统环境变量设置选项；启动器不自动加载 `.env`。更完整的 CPU/Linux/Docker 边界见 [部署与复现](docs/部署与复现.md)。Docker 配置未在本机实跑，不标作已验收。

## 验证与复现

```powershell
.venv\Scripts\python -m pytest -q
npm --prefix frontend run build
```

真实论文集成测试需准备[官方PDF资料](docs/测试资料准备.md)；缺资料会明确跳过，不计为通过。

2026-10-21 产品后端完整回归为 **420 项通过**；前端类型检查与构建通过。测试数量不是科研正确率。最新选段开发检查包含 4 个已暴露问题、11 次真实模型调用：聚焦问题有据，复杂原题仍漏答，语言仍有重复或中英混杂。详见 [限定原文追问验收](docs/限定原文追问与验收_2026-10-21.md)。原始结果、失败和历轮哈希保留在本地独立证据包中，不覆盖旧版本记录；公开Release提供不含原始论文摘录的验收摘要。

模型权重、论文文件、个人数据库、评审密码和临时运行目录不进入公开仓库。评审实例使用独立账号和资料库。请勿将本机匿名空间直接暴露公网；公开模式设置 `SCHOLARTRACE_PUBLIC=1`、`SCHOLARTRACE_REGISTRATION=0` 并使用 HTTPS。

## 已知边界与第三方说明

复杂机制可能漏答，支持性初筛可能误判；扫描公式/表格需要原图核对，翻译需要专业复核；外部搜索受开放权限和限流影响；局部引用图不等于全领域图谱；未开展独立真人研究或模型权重训练。

组件与模型许可见 [第三方来源与分发说明](docs/第三方来源与分发说明.md)。公开源代码供评审核验，未另行授予本项目统一开源许可证；第三方组件仍遵循各自许可。保留已有真实 Git 历史，后续源码在实际整理时提交，不补造过去的开发日期。
