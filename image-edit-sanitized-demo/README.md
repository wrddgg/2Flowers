# 局部涂抹改图 Demo

这是一个已脱敏的最小可运行 Demo，用来演示“上传图片、在画布上涂抹或框选局部区域、输入文字指令、调用阿里云百炼图片编辑模型生成修改图”的完整流程。

本包不包含真实 API Key。请接收方使用自己的阿里云百炼 / DashScope 配置后再运行。

## 功能范围

- 图片上传
- 图片预览画布
- 涂抹工具
- 框选工具
- 文本修改指令输入
- 调用后端 `/api/image/edit`
- 后端调用 `wan2.7-image-pro`
- 返回结果图并保存到本地 `uploads/results/`

当前涂抹区域会被转换成原图像素坐标的矩形框，并通过 `bbox_list` 传给模型。单张图最多保留最近 2 个区域。

## 运行前准备

1. 安装 Python 3.10 或更高版本。
2. 开通阿里云百炼，并准备 DashScope API Key。
3. 确认你的百炼业务空间域名，例如：

```text
https://your-workspace.cn-beijing.maas.aliyuncs.com
```

4. 复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

5. 编辑 `.env`，至少替换这些值：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com
QWEN_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
WAN_IMAGE_EDIT_ENDPOINT=https://your-workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

不要把填写了真实密钥的 `.env` 发给别人，也不要提交到代码仓库。

## 启动

Windows PowerShell：

```powershell
.\run.ps1
```

如果 PowerShell 阻止脚本执行，可以用：

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

或者直接运行：

```powershell
python app.py
```

启动后打开：

```text
http://127.0.0.1:8001
```

## 使用方式

1. 上传一张 PNG、JPEG、WEBP 或 BMP 图片。
2. 使用“涂抹”或“框选”标出要修改的区域。
3. 输入修改指令，例如：

```text
把涂抹区域改成一束白色玫瑰，保持背景和光照一致。
```

4. 点击“生成修改图”。
5. 结果图会显示在右侧，并保存到 `uploads/results/`。

## 后端接口

```http
POST /api/image/edit
Content-Type: application/json
```

请求体：

```json
{
  "imageDataUrl": "data:image/jpeg;base64,...",
  "prompt": "把涂抹区域改成一束白色玫瑰",
  "boxes": [[120, 80, 420, 360]]
}
```

响应：

```json
{
  "ok": true,
  "imageUrl": "/uploads/results/xxx.png",
  "remoteImageUrl": "https://...",
  "requestId": "..."
}
```

## 集成到完整项目的建议

如果要接入已有项目，不建议直接把整个 Demo 目录塞进生产代码。更推荐拆成两部分迁移：

- 后端：迁移 `app.py` 中的 `.env` 读取、`normalize_boxes`、`call_image_edit_api`、`save_remote_image` 和 `/api/image/edit` 处理逻辑。
- 前端：迁移 `static/app.js` 中的上传、画布绘制、涂抹/框选、坐标转换和提交请求逻辑。

如果已有项目使用 React、Vue、Next.js、FastAPI、Django、Flask 或 Express，建议保留接口协议不变，把当前 Demo 的逻辑改写成对应框架的组件和接口。

## 常见问题

### 页面提示 WinError 10013

这通常是运行环境禁止后端访问外网。请确认后端进程有访问阿里云百炼 HTTPS 接口的权限，必要时换到允许出站网络的终端或服务器运行。

### 页面提示缺少 DASHSCOPE_API_KEY

请确认已经把 `.env.example` 复制为 `.env`，并填写了真实 API Key。

### 页面提示百炼接口未返回图片 URL

请检查模型名称、业务空间域名、接口地址和账号权限是否匹配。不同地域或业务空间需要使用对应的专属域名。
