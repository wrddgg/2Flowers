# 模型 API 接入契约与选型清单

## 1. 目标

这份文档用于约束《万物生花》后端未来接入：

- 多模态语义识别 API
- 生图 / 图像编辑 API

当前后端里的 mock 逻辑只是兜底方案，最终目标是：

1. 由多模态模型输出结构化语义
2. 后端用匹配算法完成参考检索和候选排序
3. 由生图模型 API 生成三版花束图或编辑结果图

## 2. 当前代码中的接入点

- 语义识别 provider：
  [semantic_recognizer.py](file:///e:/Hackthon/大区赛/backend/app/services/semantic_recognizer.py)
- 生图 provider：
  [image_generation_provider.py](file:///e:/Hackthon/大区赛/backend/app/services/image_generation_provider.py)
- API 契约 schema：
  [provider_api.py](file:///e:/Hackthon/大区赛/backend/app/schemas/provider_api.py)

默认环境变量：

```bash
APP_RUNTIME_MODE=demo
```

- `APP_RUNTIME_MODE=demo`：演示模式，强制走本地 mock，不调用大模型
- `APP_RUNTIME_MODE=test`：测试模式，强制走本地 mock，不调用大模型
- `APP_RUNTIME_MODE=production`：正式模式，允许启用真实模型 API

在正式模式下，再配置具体 provider：

```bash
SEMANTIC_PROVIDER=mock
IMAGE_GENERATION_PROVIDER=mock
```

未来接真实 API 时，建议至少补：

```bash
APP_RUNTIME_MODE=production
SEMANTIC_PROVIDER=api
SEMANTIC_API_URL=
SEMANTIC_API_KEY=
SEMANTIC_MODEL=

IMAGE_GENERATION_PROVIDER=api
IMAGE_GENERATION_API_URL=
IMAGE_GENERATION_API_KEY=
IMAGE_GENERATION_MODEL=
```

## 3. 多模态语义识别 API 契约

### 3.1 请求目标

输入：

- 用户图片
- 选区框
- 用户语音文本
- 当前产品允许的标签体系

输出：

- `scene / flower / life`
- 结构化标签
- 可选的原始描述文本

### 3.2 建议请求体

字段定义已在：
[SemanticRecognitionApiRequest](file:///e:/Hackthon/大区赛/backend/app/schemas/provider_api.py)

建议 JSON 形态：

```json
{
  "request_id": "semantic_api_xxx",
  "image_url": "https://...",
  "selection_box": {
    "x": 10,
    "y": 12,
    "width": 120,
    "height": 90
  },
  "voice_text": "把这种安静的窗边雨感变成花",
  "allowed_modes": ["scene", "flower", "life"],
  "candidate_tags": ["窗边", "雨天", "轻治愈", "蓝白", "留白"],
  "taxonomy": {
    "modes": ["scene", "flower", "life"],
    "scene_tags": ["窗边", "雨天", "海边", "房间"],
    "emotion_tags": ["轻治愈", "克制", "温暖"],
    "visual_tags": ["蓝白", "留白", "清透"],
    "relation_tags": ["朋友", "同事", "领导"],
    "use_intents": ["表达氛围", "gift", "self", "decorate", "celebrate"]
  },
  "return_raw_caption": true
}
```

### 3.3 建议响应体

字段定义已在：
[SemanticRecognitionApiResponse](file:///e:/Hackthon/大区赛/backend/app/schemas/provider_api.py)

建议 JSON 形态：

```json
{
  "request_id": "semantic_api_xxx",
  "provider_name": "your-provider",
  "model_name": "your-multimodal-model",
  "mode_result": {
    "detected_mode": "scene",
    "confidence": 0.91,
    "evidence": ["雨滴", "窗边", "室内", "安静"]
  },
  "semantic_result": {
    "mode": "scene",
    "subject_tags": ["窗边雨幕"],
    "scene_tags": ["窗边", "雨天", "室内"],
    "emotion_tags": ["轻治愈", "安静", "克制"],
    "visual_tags": ["蓝白", "留白", "清透"],
    "color_palette": ["#AFC6DE", "#FFFFFF", "#7D8DA3"],
    "relation_tags": [],
    "use_intent": "表达氛围",
    "semantic_summary": "一个偏冷感、安静、适合转换为留白花艺的场景。"
  },
  "raw_caption": "窗边玻璃上的雨滴，室内暖光，整体安静克制。",
  "raw_labels": ["rain", "window", "indoor", "calm"],
  "latency_ms": 850
}
```

### 3.4 我们对这个 API 的真实要求

不是简单“能看图”就够，而是要满足：

1. 能输出**结构化标签**
2. 能做**模式分类**
3. 能处理**图片 + 文本联合输入**
4. 能对同一张图的**局部选区**做判断
5. 最好能返回**颜色 / 风格 / 情绪**类信息

## 4. 生图 API 契约

### 4.1 请求目标

输入：

- 结构化语义
- 参考素材
- 参考强度
- 输出张数与比例

输出：

- 3 张候选花束图
- 每张图的 URL
- 可选 revised prompt / seed / 元数据

### 4.2 建议请求体

字段定义已在：
[ImageGenerationApiRequest](file:///e:/Hackthon/大区赛/backend/app/schemas/provider_api.py)

建议 JSON 形态：

```json
{
  "request_id": "image_api_xxx",
  "mode": "scene",
  "semantic_result": {
    "mode": "scene",
    "subject_tags": ["窗边雨幕"],
    "scene_tags": ["窗边", "雨天"],
    "emotion_tags": ["克制", "轻治愈"],
    "visual_tags": ["蓝白", "留白"],
    "color_palette": [],
    "relation_tags": [],
    "use_intent": "表达氛围",
    "semantic_summary": "一个偏冷感、克制、治愈的场景输入。"
  },
  "reference_strategy": "light",
  "selected_references": [
    {
      "reference_id": "flower_blue_white",
      "title": "蓝白克制花束",
      "cover_url": "/library/assets/flower_blue_white_01.png",
      "mode": "flower",
      "score": 108,
      "matched_tags": ["克制", "轻治愈", "蓝白"]
    }
  ],
  "generation_constraints": {
    "output_count": 3,
    "aspect_ratio": "3:4",
    "preserve_reference_strength": "light",
    "allow_text_overlay": false,
    "return_revised_prompt": true
  },
  "style_prompt": "mode=scene | summary=一个偏冷感、克制、治愈的场景输入。",
  "negative_prompt": "避免文字、水印、畸形花头、重复花材、低清晰度、过度塑料感包装"
}
```

### 4.3 建议响应体

字段定义已在：
[ImageGenerationApiResponse](file:///e:/Hackthon/大区赛/backend/app/schemas/provider_api.py)

建议 JSON 形态：

```json
{
  "request_id": "image_api_xxx",
  "provider_name": "your-provider",
  "model_name": "your-image-model",
  "images": [
    {
      "image_url": "https://cdn/.../result-1.png",
      "prompt_summary": "蓝白留白、轻治愈、窗边雨感花束",
      "revised_prompt": "a bouquet with soft blue and white tone...",
      "seed": "123456",
      "provider_metadata": {
        "style": "photorealistic",
        "quality": "high"
      }
    }
  ],
  "latency_ms": 3400
}
```

### 4.4 我们对这个 API 的真实要求

不是简单“能出花图”就够，而是要满足：

1. 支持**参考图或风格参考**
2. 支持一次返回**多候选结果**
3. 成图风格要偏**真实商品图 / 花店成品图**
4. 最好支持**后续编辑能力**
   - 局部重绘
   - 替换花材
   - 改包装
   - 保持主体结构

## 5. 你要找什么样的多模态语义模型 API

### 必须具备

1. **图片 + 文本联合输入**
2. **输出结构化 JSON**
3. **支持中文提示**
4. **能识别风格 / 情绪 / 场景**
5. **延迟可接受**
   - 理想：`1-3s`
   - Demo 可接受：`5-8s`

### 强烈建议具备

1. 支持局部图理解或裁剪区域理解
2. 支持返回标签置信度
3. 支持颜色 / 构图 / 物体层级描述
4. 稳定的 API 限流和错误码
5. 价格适合在多轮交互中频繁调用

### 最好具备

1. 可以做函数调用或强 JSON 模式
2. 可指定枚举标签范围
3. 对中文生活方式图、花束图、场景图理解较好
4. 有企业级可用 SLA

## 6. 你要找什么样的生图模型 API

### 必须具备

1. **写实风格强**
2. **支持参考图 / image-to-image / style reference**
3. **支持一次生成多张候选**
4. **支持稳定 URL 或可下载结果**
5. **允许商业原型 / Demo 使用**

### 强烈建议具备

1. 支持局部编辑 / inpainting
2. 支持保持主体构图
3. 支持负面提示词
4. 支持返回 seed / revised prompt
5. 出图分辨率能满足移动端展示

### 最好具备

1. 支持角色一致性或主体一致性
2. 支持多参考融合
3. 对商品图、静物图、花艺图表现稳定
4. 有可控的审核策略，不会频繁误杀普通花束图

## 7. 供应商筛选清单

你后面可以按这张表去问供应商：

### 多模态语义 API

- 是否支持图片 + 文本联合输入？
- 是否支持强制 JSON 输出？
- 是否支持中文提示词？
- 是否支持传图片 URL，而不是必须先上传文件？
- 是否支持局部区域理解或 crop 参数？
- 是否支持返回标签置信度？
- 平均响应时间是多少？
- 有无 QPS / TPM 限制？
- 如何计费？
- 是否允许商业 Demo 和比赛场景使用？

### 生图 API

- 是否支持 text-to-image？
- 是否支持 image-to-image？
- 是否支持参考图 / 风格参考？
- 是否支持 inpainting / 局部编辑？
- 是否支持一次返回 3 张候选？
- 是否返回 revised prompt / seed？
- 结果图 URL 保留多久？
- 是否允许下载原图？
- 模型更偏写实还是插画？
- 对中文 prompt 的表现如何？
- 是否允许商品展示类图片生成？

## 8. 当前建议的选型优先级

如果以《万物生花》当前阶段为目标，我建议优先这样找：

1. **先找多模态语义 API**
   - 能稳定输出 JSON
   - 能识别情绪 / 风格 / 场景
   - 中文表现稳定

2. **再找写实生图 API**
   - 重点看花束、静物、商品图质量
   - 必须支持参考图或 image-to-image

3. **最后再考虑编辑型 API**
   - 用于共创阶段的删花、改包装、局部重绘

## 9. 当前代码落地建议

你找到供应商后，优先做这两件事：

1. 在 [semantic_recognizer.py](file:///e:/Hackthon/大区赛/backend/app/services/semantic_recognizer.py) 里实现真实 HTTP 调用
2. 在 [image_generation_provider.py](file:///e:/Hackthon/大区赛/backend/app/services/image_generation_provider.py) 里实现真实 HTTP 调用

然后通过环境变量切换：

```bash
SEMANTIC_PROVIDER=api
IMAGE_GENERATION_PROVIDER=api
```
