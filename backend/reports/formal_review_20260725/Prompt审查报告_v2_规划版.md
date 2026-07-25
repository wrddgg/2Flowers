# Prompt 审查报告 v2（规划版）

## 1. 为什么要升级

你这轮反馈把问题说得很准确：现在真正缺的不是“更用力的 prompt”，而是**先规划理解，再规划生花**。

旧版本的问题在于：

- 识图默认只有一个答案，缺少“这张图也可以从别的角度理解”的机制
- `life` 过于笼统，无法表达“纯人像/人物气质”这种特殊输入
- 生图虽然拆了 3 张，但仍然像同一上下文里的微调，差异来源不够本质
- 参考图过强时会把结果锁成模板

因此，本轮升级后的核心思想是：

1. **识图先识别元素，再生成解读候选**
2. **生图先做方案规划，再逐张独立生成**
3. **参考只是一种特征来源，不再是默认模板**

## 2. 识图 Prompt 的新目标

识图不再只回答“这是什么”，而是回答三件事：

1. 图里有哪些元素值得作为生花入口  
   例如：`scene / flower / person / portrait / gift_context / global`

2. 哪几种解读是真正合理的  
   例如同一张图可以同时支持：
   - 从场景氛围解读
   - 从人物气质解读
   - 从全局综合气质解读

3. 系统建议先走哪一种  
   这部分由 `planner_summary` 和 `recommended_interpretation_id` 表达

## 3. 识图侧已落地的结构升级

代码位置：

- `backend/app/schemas/input.py`
- `backend/app/services/semantic_recognizer.py`
- `backend/app/api/routes_input.py`

当前 `POST /api/input/analyze` 已新增以下能力：

- `detected_elements`
- `needs_user_choice`
- `interpretation_options`
- `planner_summary`
- `recommended_interpretation_id`

这意味着接口已经能承接“如果有多种合理理解，就把选择权交给用户”的产品逻辑。

## 4. 当前识图 Prompt 的设计要点

新版 prompt 已明确补入以下概念：

### 4.1 “万物生花”的定义

不是普通图像识别，而是：

> 把用户看到的人、场景、情绪和关系，转译成合适的花艺表达与生花方向。

### 4.2 `life` 的细化方式

本轮没有粗暴增加新的主 mode，而是保留：

- `scene`
- `flower`
- `life`

同时新增元素类型与视角：

- `person`
- `portrait`
- `global`

这样做的好处是：

- 不会打断现有检索和生成主链路
- 但可以清楚表达“纯人像生花”的语义入口

### 4.3 候选解读

当图像存在多视角时，模型必须返回 1 到 3 个 `interpretation_options`，每个选项都包含：

- `label`
- `perspective`
- `recommended_mode`
- `semantic_result`
- `explanation`
- `alignment_axes`

其中 `alignment_axes` 用来解释“为什么这套解读可以变成花”，例如：

- 色彩对齐
- 花语对齐
- 气质对齐
- 材质对齐
- 关系语境对齐

## 5. 当前识图输出样例

针对“窗边雨夜”输入，当前 mock 结构输出已经是这种形态：

```json
{
  "detected_elements": [
    {"element_type": "scene", "confidence": 0.9},
    {"element_type": "global", "confidence": 0.68}
  ],
  "needs_user_choice": true,
  "interpretation_options": [
    {
      "option_id": "option_scene",
      "label": "从当前主视角解读",
      "perspective": "scene",
      "recommended_mode": "scene",
      "alignment_axes": ["色彩对齐", "情绪气质对齐"]
    },
    {
      "option_id": "option_global",
      "label": "从整体气质解读",
      "perspective": "global",
      "recommended_mode": "scene",
      "alignment_axes": ["整体气质对齐", "色彩对齐"]
    }
  ],
  "planner_summary": "当前输入存在多种合理解读，建议先在两个主方向中选一个，再进入后续生花。"
}
```

## 6. 生图 Prompt 的新目标

生图现在不再假设“3 张图只需要 1 个 prompt 微调三次”，而是明确拆成：

1. **先规划 3 个不同侧重点**
2. **再按 3 个独立 prompt 分别生图**

这轮升级后的生图设计，允许不同次生花分别强调：

- 氛围还原
- 色调还原
- 人物气质
- 材料感
- 高级感
- 一致感
- 花语含义

## 7. 生图侧已落地的结构升级

代码位置：

- `backend/app/schemas/bouquet.py`
- `backend/app/schemas/provider_api.py`
- `backend/app/services/image_generation_provider.py`
- `backend/app/api/routes_generate.py`

当前已新增：

- `creative_mode`
- `generation_goals`
- `selected_interpretation_label`
- `variant_plans`
- `plan_used`
- `generation_focus`

### 7.1 `creative_mode`

支持：

- `commercial`
- `expressive`
- `mixed`

其中：

- `commercial` 偏现实落地
- `expressive` 允许更高级、更稀有、更发散
- `mixed` 取中间态

这正对应了你提出的：

> 这一阶段不一定要求花束真实存在，可售卖等现实含义。

### 7.2 生花规划器

当前 `ApiImageGenerationProvider` 已支持在正式模式下用同一套语义模型接口先做 `variant plan` 规划。

规划器会输出最多 3 个方案，每个方案包含：

- `variant_id`
- `title`
- `focus`
- `prompt_directive`
- `reference_strategy`

如果远端规划失败，则回退到本地默认方案：

1. 氛围还原
2. 气质表达
3. 花语对齐

## 8. 当前生图 Prompt 的设计要点

### 8.1 参考图只保留特征

`light` 参考现在不会再把参考图原图直接上传给生图模型。  
它只保留：

- 色彩方向
- 结构气质
- 包装感觉
- 情绪气质

并明确禁止：

- 复制外形
- 复制具体主花材组合
- 复制花材比例
- 复制包装版式

### 8.2 输入优先于参考

prompt 里已明确写入：

> 如果输入色调、氛围与参考冲突，必须优先服从输入语义。

这正是你提到的“黄白、昏暗、朦胧，不应该被蓝白参考强行带偏”的修正方向。

### 8.3 允许更高级、更稀有

当 `creative_mode=expressive` 时，当前 prompt 会明确告诉模型：

> 允许使用更稀有、更高级、现实中未必常见的花材来放大气质和象征意义。

这为之后再做“现实版优化/丐版回退”留出了空间。

## 9. 当前生图 Prompt 样例

以下是当前新版 prompt 的一个典型样例片段：

```text
“万物生花”的目标，是把用户输入的人、场景、关系和情绪转译成有审美表达的花艺结果。
当前选择的解读：从整体气质解读
本轮生成目标：强调高级感、允许适度稀有花材、三张图侧重点明显不同
创作模式：expressive
当前变体：plan_atmosphere
变体标题：氛围还原
变体焦点：atmosphere
变体要求：第一次次生花优先还原输入的氛围、光感、空气感和整体色调。
当前是轻参考：严禁直接复制参考花束的外形、具体主花材组合、花材比例和包装版式，只允许借用抽象特征。
当前是表达优先模式：允许使用更稀有、更高级、现实中未必常见的花材来放大气质和象征意义。
表达要求：可以优先还原氛围、色调、人物气质、材料感或花语含义中的某一个主轴，但必须让这一主轴足够鲜明。
```

## 10. 这轮升级解决了什么

### 已直接解决

- 识图 prompt 明确解释了“万物生花”是什么
- 识图能表达“场景 / 人 / 全局”多视角
- 接口层已经可以返回候选解读供用户选择
- 生图阶段已经引入“先规划，后逐张生成”
- `expressive` 模式允许更高级、更稀有、更发散的花材选择

### 还没有彻底解决

- 真正的正式模型是否会稳定产出足够好的多视角解读，还需要正式联调验证
- 规划器虽然已经接入，但还需要结合更多真实样例校正“哪三种次生花最有价值”
- 人像输入的素材库映射目前还偏弱，后面要补更多 `portrait` / `person` 样例

## 11. 下一步建议

按你的产品思路，最值得继续往下做的是三件事：

1. 选一张明确的人像输入，验证 `portrait` 视角是否成立
2. 给 `input/analyze` 增加“用户选择 interpretation_option”的前后端对接
3. 用正式模型跑一次“同图多解读 -> 各自检索 -> 各自生花”的完整实验
