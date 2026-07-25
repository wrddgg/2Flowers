# 万物生花后端

这是一个面向 Hackathon Demo 的 Python 后端，目标是把 `输入分析 -> 参考检索 -> 花束生成 -> 共创编辑 -> 情绪承接` 这条链路稳定跑通，并保持接口结构便于后续替换成真实模型与真实素材。

## 技术栈

- Python 3.10+
- FastAPI
- Pydantic v2
- Uvicorn

## 目录

```text
backend/
  app/
    api/
    data/
    repositories/
    schemas/
    services/
    utils/
    main.py
  tests/
  deploy.sh
  deploy.ps1
  deploy.bat
  requirements.txt
```

## 一键启动

在 Windows 下双击 `deploy.bat`，或执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

在 Linux 服务器上执行：

```bash
chmod +x ./deploy.sh
./deploy.sh
```

脚本会自动：

1. 创建 `.venv`
2. 安装依赖
3. 启动 `uvicorn`

默认地址：

- API: `http://127.0.0.1:8000`
- 文档: `http://127.0.0.1:8000/docs`

Linux 脚本默认以后台模式启动，并生成：

- 进程号文件：`uvicorn.pid`
- 日志文件：`logs/uvicorn.log`

常用方式：

```bash
# 只安装依赖，不启动
INSTALL_ONLY=1 ./deploy.sh

# 前台运行，便于调试
RUN_MODE=foreground ./deploy.sh

# 强制重启
FORCE_RESTART=1 ./deploy.sh
```

## 核心接口

- `POST /api/input/analyze`
- `POST /api/reference/search`
- `POST /api/bouquet/generate`
- `GET /api/bouquet/{result_id}/flowers/{flower_id}`
- `POST /api/bouquet/edit`
- `POST /api/emotion/build`

## 当前素材策略

当前版本使用本地 JSON 知识库和占位图片，便于前后端联调。后续替换真实素材时，优先更新：

1. `app/data/content_knowledge_base.json`
2. `app/data/mock_assets/`

## 推荐后续接入点

- 将 `ModeDetector` 替换为真实多模态分类
- 将 `SemanticParser` 替换为 LLM 或视觉理解服务
- 将 `ReferenceRetriever` 替换为向量检索
- 将 `BouquetGenerator` 替换为图像生成/编辑模型编排

## API 接入准备

当前项目已经预留了两类 provider 抽象：

- 多模态语义识别 provider
- 生图 provider

建议先通过统一运行模式控制是否允许调用大模型：

```bash
APP_RUNTIME_MODE=demo
```

- `demo`：演示模式，强制走 mock，不调用大模型 API
- `test`：测试模式，强制走 mock，不调用大模型 API
- `production`：正式模式，允许按 provider 配置启用真实模型 API

在 `production` 模式下，再通过环境变量指定具体 provider：

```bash
APP_RUNTIME_MODE=production
SEMANTIC_PROVIDER=mock
IMAGE_GENERATION_PROVIDER=mock
```

环境变量模板见：

- [`.env.example`](file:///e:/Hackthon/大区赛/backend/.env.example)
- [`.env.demo.example`](file:///e:/Hackthon/大区赛/backend/.env.demo.example)
- [`.env.test.example`](file:///e:/Hackthon/大区赛/backend/.env.test.example)
- [`.env.production.example`](file:///e:/Hackthon/大区赛/backend/.env.production.example)
- [`.env.production`](file:///e:/Hackthon/大区赛/backend/.env.production)

当前仓库本地默认会读取：

1. `.env`
2. 再按 `APP_RUNTIME_MODE` 读取 `.env.demo`、`.env.test` 或 `.env.production`

你刚才说“没找到参数填写在哪里”，正式参数现在放在：

- [`.env.production`](file:///e:/Hackthon/大区赛/backend/.env.production)

建议本地演示保持：

```bash
APP_RUNTIME_MODE=demo
```

正式环境再切到：

```bash
APP_RUNTIME_MODE=production
```

模型 API 的请求/响应契约和选型清单见：

- [模型API接入契约与选型清单.md](file:///e:/Hackthon/大区赛/backend/模型API接入契约与选型清单.md)
