from __future__ import annotations

import json


TUTORIAL_PLANNER_SYSTEM_PROMPT = (
    "你是“万物生花”的花艺教学规划专家。"
    "你的职责不是直接输出教程文案，而是先决定这束花最适合怎样教学："
    "哪些步骤必须保留，哪些信息该省略，哪里要突出新手最容易出错的点。"
    "你要像资深花艺老师兼课程策划一样，优先保证步骤真实、克制、可执行。"
    "只输出严格 JSON。"
)


TUTORIAL_EXPERT_SYSTEM_PROMPT = (
    "你是“万物生花”的插花教学专家。"
    "你要根据已经确定的教学规划，把花束拆成适合新手跟做的真实制作步骤。"
    "不要堆砌花艺术语，不要为了显得丰富而增加无意义步骤。"
    "步骤必须符合真实插花顺序，并体现专业老师的判断。"
    "只输出严格 JSON。"
)


TUTORIAL_IMAGE_REVIEW_SYSTEM_PROMPT = (
    "你是“万物生花”的教程配图审核专家。"
    "你要判断教程步骤图是否真实、自然、符合给定步骤与参考花束。"
    "不要美化明显错误的图片，不要放过不合理结构。"
    "你的审核要偏严格，只要出现明显 AI 痕迹、主体截断、步骤动作不对，就应该判定不通过。"
    "只输出严格 JSON。"
)


SHARE_PLANNER_SYSTEM_PROMPT = (
    "你是“万物生花”的分享策划专家。"
    "你的职责是先规划这张卡片该如何表达：强调什么情绪、使用什么语气、"
    "更偏收藏感还是社交传播感，以及配乐应该走什么方向。"
    "你要像资深内容策划一样做取舍，而不是把所有情绪都塞进一条文案。"
    "只输出严格 JSON。"
)


SHARE_EXPERT_SYSTEM_PROMPT = (
    "你是“万物生花”的社交分享文案专家。"
    "请根据既定规划输出简洁、温柔、适合发布的分享文案和 BGM 建议。"
    "不要写成长文，不要用空泛套话，要体现花束被转译后的气质。"
    "只输出严格 JSON。"
)


def build_tutorial_planner_prompt(*, flowers: list[str], bouquet_image: str = "") -> str:
    flowers_text = "、".join(flowers)
    return (
        "请先为这束花规划一份教学策略，而不是直接写最终教程。\n"
        "目标：让后续教程既专业又克制，适合新手跟做，同时保持“万物生花”偏审美化、专家化的表达。\n"
        "要求：\n"
        "1. 优先判断这束花更适合强调骨架、层次、主花重心还是收口整理。\n"
        "2. 明确哪些花材动作必须讲，哪些细节可以省略，避免教程变成材料清单。\n"
        "3. 强调真实花艺顺序：醒花/修剪 -> 定骨架 -> 插主花 -> 补配花叶材 -> 调整收口。\n"
        "4. step_count 只能是 3 到 5。\n"
        "5. advice_for_generator 需要提醒后续教程专家保持克制、专业、可操作。\n"
        f"花材列表：{flowers_text}\n"
        f"花束图片：{bouquet_image or '未提供'}\n"
        '输出 JSON：{"teaching_focus":"...","bouquet_structure":"...","step_count":4,'
        '"must_include_actions":["..."],"optional_actions":["..."],"beginner_risks":["..."],'
        '"advice_for_generator":"..."}'
    )


def build_tutorial_generation_prompt(*, flowers: list[str], plan: dict[str, object]) -> str:
    flowers_text = "、".join(flowers)
    return (
        "请根据下面已经规划好的教学策略，生成最终教程步骤。\n"
        "要求：\n"
        "1. steps 含 3~5 步，step 从 1 开始连续编号。\n"
        "2. title 控制在 4~8 字，description 要具体、可操作。\n"
        "3. image_prompt 用于后续配图，必须突出本步关键动作，不要写抽象情绪词。\n"
        "4. 教程要体现花艺专家的判断：少而准，不要为了显得完整而加空步骤。\n"
        "5. image_prompt 必须说明镜头视角、手部动作、花材状态、画幅完整，不要裁掉花头或花瓶，不要出现不合理肢体。\n"
        "6. 每张步骤图只表现一个明确动作，不要做拼图、分镜、连环画，不要在一张图里塞多个步骤。\n"
        "7. 画面必须像真实花艺教学现场，工作台、工具、花材朝向和手势都要可执行。\n"
        f"花材：{flowers_text}\n"
        f"教学规划：{json.dumps(plan, ensure_ascii=False)}\n"
        '输出 JSON：{"steps":[{"step":1,"title":"醒花与修剪","description":"...","image_prompt":"..."}]}'
    )


def build_tutorial_image_review_prompt(
    *,
    step_title: str,
    step_description: str,
    step_image_prompt: str,
    flowers_text: str,
    has_bouquet_reference: bool,
) -> str:
    return (
        "请审核这张教程步骤图是否可以直接展示给用户。\n"
        "审核标准：\n"
        "1. 必须符合当前步骤动作，不可答非所问。\n"
        "2. 花材必须真实，不能出现不合理花型、奇怪花芯、错误肢体、漂浮工具等 AI 痕迹。\n"
        "3. 构图必须完整，不要把主体花头、手部关键动作或容器明显截断。\n"
        "4. 如果提供了成品参考花束，要判断当前步骤图是否与参考花束的主要花材和气质一致。\n"
        "5. 如果不合格，必须给出可执行的 retry_prompt_hint，帮助重新生成。\n"
        "6. blocking_issues 只填写必须直接判失败的问题，例如：主体截断、肢体错误、工具漂浮、花材失真、步骤动作错误。\n"
        "7. score 使用 0~1，0.75 以下视为不能直接给用户看。\n"
        f"步骤标题：{step_title}\n"
        f"步骤说明：{step_description}\n"
        f"步骤配图提示：{step_image_prompt}\n"
        f"花材列表：{flowers_text}\n"
        f"是否提供成品参考花束：{'是' if has_bouquet_reference else '否'}\n"
        '输出 JSON：{"pass":true,"score":0.82,"issues":["..."],"blocking_issues":["..."],'
        '"action_ok":true,"composition_ok":true,"botany_ok":true,"reference_consistency_ok":true,'
        '"review_summary":"...","retry_prompt_hint":"..."}'
    )


def build_share_planner_prompt(*, title: str, source_context: str = "", scene_reason: str = "") -> str:
    return (
        "请先规划这张分享卡片的表达策略。\n"
        "目标：让“万物生花”的分享文案更像经过策划的内容，而不是模板化 slogan。\n"
        "要求：\n"
        "1. 决定主表达轴：收藏感 / 礼物感 / 情绪转译感 三者取其一为主。\n"
        "2. 决定文案语气：克制 / 温柔 / 轻庆祝 / 轻治愈 中选择最合适的主语气。\n"
        "3. 决定 BGM mood，避免风格发散。\n"
        "4. 需要额外给出一句 why_it_fits_scene，说明这束花为什么适合当前素材场景。\n"
        "4. advice_for_copywriter 需要提醒后续文案专家保持简洁、有记忆点、不过度煽情。\n"
        f"花束标题：{title}\n"
        f"素材场景：{source_context or '未提供'}\n"
        f"已知适配原因：{scene_reason or '未提供'}\n"
        '输出 JSON：{"primary_angle":"...","tone":"...","bgm_mood":"...","why_it_fits_scene":"...","advice_for_copywriter":"..."}'
    )


def build_share_generation_prompt(*, title: str, plan: dict[str, object], source_context: str = "", scene_reason: str = "") -> str:
    return (
        "请根据已经确定的分享策略，生成最终社交分享结果。\n"
        "要求：\n"
        "1. share_text 一句话，温柔治愈，带 #万物生花，不超过 40 字。\n"
        "2. bgm_options 返回 3 首，id 只能是 bgm1/bgm2/bgm3。\n"
        "3. 不要套模板式空话，要体现“把画面转成花束”的独特感。\n"
        "4. 输出 scene_reason，一句话解释这束花为什么适合当前素材场景。\n"
        f"花束标题：{title}\n"
        f"素材场景：{source_context or '未提供'}\n"
        f"已知适配原因：{scene_reason or '未提供'}\n"
        f"分享规划：{json.dumps(plan, ensure_ascii=False)}\n"
        '输出 JSON：{"share_text":"...","scene_reason":"...","bgm_options":[{"id":"bgm1","name":"...","artist":"..."}]}'
    )
