# 万物生花 Skill 包说明

本压缩包用于分发 `万物生花` 的一组可复用 Agent Skill。

包内包含：

- `wanwu-flower-core/`
- `wanwu-input-interpret/`
- `wanwu-bouquet-generate/`
- `wanwu-remake-plan/`
- `wanwu-share-workflow/`

每个目录下都包含必须文件：

- `SKILL.md`

## 1. 适用场景

这套 Skill 适用于以下任务：

- 将图片、场景、情绪、人像转译为花束表达
- 为输入内容生成 3 组可解释的花艺方案
- 将 AI 花束整理为现实可复刻的花店沟通稿
- 生成教程、分享卡、对比讲解材料

不适用于：

- 通用代码修复
- 通用文案写作
- 与花艺表达无关的图像生成任务

## 2. 如何选择 Skill

### 优先使用主 Skill 的情况

当用户需求跨越多个阶段，或者还在用产品语言描述时，优先使用：

- `wanwu-flower-core`

典型问法：

- “把这张图变成一束花”
- “先识别一下感觉，再给我三束花”
- “基于刚才结果继续做复刻和分享”

### 直接使用子 Skill 的情况

当用户只需要单一阶段时，直接选对应子 Skill：

- `wanwu-input-interpret`
  - 适合只做输入理解、主色提取、场景/气质判断
- `wanwu-bouquet-generate`
  - 适合只做生花方案输出
- `wanwu-remake-plan`
  - 适合只做现实复刻方案、替花建议、支数与包装说明
- `wanwu-share-workflow`
  - 适合只做教程、分享卡、评委展示材料

## 3. 推荐调用顺序

完整链路建议按以下顺序调用：

1. `wanwu-input-interpret`
2. `wanwu-bouquet-generate`
3. 选择某个方案后进入编辑或复刻
4. `wanwu-remake-plan`
5. `wanwu-share-workflow`

如果用户没有明确拆阶段，可以直接从：

- `wanwu-flower-core`

开始，由主 Skill 负责编排。

## 4. 阶段衔接建议

为保证结果可解释、可继续编辑，建议在阶段之间保留这些关键字段：

- `input_mode`
- `dominant_color_palette`
- `semantic_summary`
- `reference_strategy`
- `selected_reference_ids`
- `bouquet_variants`
- `selected_variant_id`
- `flowers`
- `recognized_flowers`
- `remake_plan`
- `image_status`

## 5. 与当前后端的推荐映射

若配合当前 `万物生花` 后端使用，建议映射如下：

### 输入理解

- `POST /api/input/analyze`

### 参考检索

- `POST /api/reference/search`

注意：

- 仅在判断参考图确实有帮助时再调用
- 对抽象科技、人像等输入，通常应弱参考或禁参考

### 生花

- `POST /api/bouquet/generate`

### 复刻

- `POST /api/emotion/build`
- `POST /api/emotion/remake-preview`

### 教程 / 分享 / 运行期恢复

- 教程工作流相关路由
- 分享卡相关路由
- 用户缓存相关路由

## 6. 当前产品约束

使用这套 Skill 时，建议同时遵守以下产品规则：

- 严禁在最终花图中出现任何人物或人体成分
- 对抽象或科技场景优先提取 1-2 个主色调
- 主花色调应尽量贴合 `dominant_color_palette`
- 对科技展演、人像拍摄类输入，默认弱参考或禁参考
- 复刻阶段相似度优先，不要因季节性过度损伤视觉相似度

## 7. 导入与分发说明

若目标环境支持目录型 Skill：

1. 将压缩包解压
2. 保持每个 Skill 独立目录结构不变
3. 确保每个目录内存在 `SKILL.md`
4. 放入目标环境的 Skill 搜索目录

若目标环境支持单文件包分发：

- 可直接使用 `.skill` 文件分发
- 其内容与 `.zip` 一致，仅扩展名不同

## 8. 包内容校验

本包至少应包含以下文件：

- `wanwu-flower-core/SKILL.md`
- `wanwu-input-interpret/SKILL.md`
- `wanwu-bouquet-generate/SKILL.md`
- `wanwu-remake-plan/SKILL.md`
- `wanwu-share-workflow/SKILL.md`
- `wanwu-flower-skills-README.md`

若缺少上述文件，则说明技能包不完整。
