# 研证 · ScholarTrace

面向研究证据更新审计的科研助手。参赛者：蔡晨霖，西安交通大学人工智能 2501 班。

本项目围绕“保存结论与出处 → 对比论文版本 → 找出需要重新核验的内容”建立特色，同时逐步实现赛题要求的六大科研模块。当前为第一阶段原型，不能代表全部赛事要求已经完成。

## 第一阶段实现

- React/TypeScript 前端和 FastAPI 后端，原生 PDF.js 阅读、换页与证据块坐标高亮。
- 本机 SQLite 文献库与 FTS5/BM25 原文检索，持久保存页码、坐标及版本。
- 上传 PDF、内容哈希去重；正文标识符/标题与文本相似度辅助识别版本，不依赖文件名。
- 保存研究笔记及原始引文，用文本对齐基线检查另一版本中需要复核的内容。
- 本地 OpenAI-compatible 推理接口；模型不可用时明确显示证据检索模式，不伪造生成回答。
- 资料检查、扫描件 OCR、真实 PDF 集成测试和浏览器验收脚本。

当前检索为词法基线，中文问题使用显式术语映射，尚未实现完整语义检索与重排。版本审计为文本变化提示，不能直接判断科学结论是否被推翻。全文翻译、多文推理、检索推荐、图谱与写作模块仍待后续开发。

## 本机使用

已配置环境时，双击根目录 `启动研证.cmd`，或在项目根目录运行：

```powershell
node scripts/start.mjs --open
```

访问 `http://127.0.0.1:8765`。启动脚本仅监听本机；若已存在模型权重和推理程序，会同时尝试启动本地模型。日志保存在 `artifacts/runtime/`。本地地址不是赛事要求的公网演示地址。

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
```

浏览器检查脚本目前使用本机已有 Chrome 和 Codex 随附 Playwright；迁移时可通过 `CODEX_BROWSER_MODULE` 指定 Playwright 模块位置。测试过程会在本机文献库保存一条标明“验收样例”的证据笔记。单元/集成测试使用临时数据库，不覆盖正式数据。

## 真实性、许可与协作

用户提供的 PDF 保持原样，未默认纳入公开仓库；文件来源、页数及校验值由检查脚本记录。PyMuPDF 等第三方组件有各自许可，公开发布前必须完成许可与分发核对。Qwen 模型和 llama.cpp 程序的许可说明随本机下载资料保留。

项目由蔡晨霖提出目标、约束和质量要求，AI 协助设计、编码、调试和记录。Git 历史和实际测试报告保留真实开发过程；文档中的计划、已实现能力和实测结果分别标注。
