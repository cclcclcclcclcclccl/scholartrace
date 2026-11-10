---
license: apache-2.0
sdk: docker
app_port: 7860
---

# 墨衡 Moheng · 科研证据与版本复核

本实例包含 FastAPI、React、Qwen3-4B GGUF CPU 推理、MiniLM 多语言正文向量、PDF 原文阅读和证据复核。云端容器独立运行，不连接作者个人电脑，也不调用收费模型 API。

## 上线设置

1. 选择 Docker 和 **platform/2v-cpu-16g-mem 免费 CPU**；不要选择付费资源。
2. 在空间设置的环境变量中添加秘密变量 `MOHENG_REVIEW_PASSWORD`，值使用你自己生成的 16—200 字符评审专用密码。不要把密码写入仓库、README 或部署 JSON。登录名固定为 `reviewer`。
3. 上传本目录全部文件，根目录必须直接包含 Dockerfile、README.md、ms_deploy.json、backend、frontend、scripts 和 deploy。
4. 上线。首次构建会下载并校验约数 GB 的公开模型；服务端口固定 7860。若模型或论文哈希不符，构建应当失败，不绕过校验。
5. 等运行日志显示模型已加载，再检查 `/api/health` 的 `model_available` 为 true。首页能打开不等于模型已可用。
6. 在新浏览器窗口登录 reviewer，问 Attention Is All You Need v1 “训练用了哪些 GPU？”，检查引用原文，再用手机移动网络复测。

## 数据与资源边界

- 默认预置 Transformer 的 v1/v7 两篇公开来源论文，方便复核版本；可以登录后导入其他论文。
- 2 核 CPU 的模型速度与个人电脑不同，完整问答可能需要几分钟。云端普通发送默认创建后台任务，可看进度、离开后恢复；单次模型调用有 150 秒上限，整项问答包含多次调用。限定原文追问仍直接处理。本配置没有常驻 SLA，平台排队、重启或政策变化仍可能影响访问。
- 评审账号、任务和笔记优先写入 `/mnt/workspace/moheng-data` 持久化目录；空间重启后应保留这些数据。若普通 Docker 环境没有这个挂载，启动脚本会回退到容器内 `/app/data`，保证服务能启动，但重建容器后该回退目录可能丢失。空间转移、删除持久卷或平台策略变化仍可能导致持久数据丢失，因此重要笔记和成果应导出保存。重建后使用同一秘密变量恢复 reviewer 账号，旧会话需重新登录。
- 注册接口默认关闭。请通过比赛要求的私密渠道提供评审账号，不要在公开介绍页面发布密码。
- Docker 云端构建和模型验收记录见项目预指导改进说明；成功构建不代表当前空间已部署。空间实际可用性应在上线后另行验收。

## 第三方资源

Qwen3-4B 基础模型由 Qwen 发布，MiniLM 多语言向量来自 sentence-transformers，公式识别来自 RapidAI/RapidLaTeXOCR。下载来源与 SHA-256 位于 `deploy/assets.json`。软件依赖使用锁文件；论文原文版权属于各自权利人。应用输出需要结合引用原文复核。
