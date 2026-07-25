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
        f"花材：{flowers_text}\n"
        f"教学规划：{json.dumps(plan, ensure_ascii=False)}\n"
        '输出 JSON：{"steps":[{"step":1,"title":"醒花与修剪","description":"...","image_prompt":"..."}]}'
    )


def build_share_planner_prompt(*, title: str) -> str:
    return (
        "请先规划这张分享卡片的表达策略。\n"
        "目标：让“万物生花”的分享文案更像经过策划的内容，而不是模板化 slogan。\n"
        "要求：\n"
        "1. 决定主表达轴：收藏感 / 礼物感 / 情绪转译感 三者取其一为主。\n"
        "2. 决定文案语气：克制 / 温柔 / 轻庆祝 / 轻治愈 中选择最合适的主语气。\n"
        "3. 决定 BGM mood，避免风格发散。\n"
        "4. advice_for_copywriter 需要提醒后续文案专家保持简洁、有记忆点、不过度煽情。\n"
        f"花束标题：{title}\n"
        '输出 JSON：{"primary_angle":"...","tone":"...","bgm_mood":"...","advice_for_copywriter":"..."}'
    )


def build_share_generation_prompt(*, title: str, plan: dict[str, object]) -> str:
    return (
        "请根据已经确定的分享策略，生成最终社交分享结果。\n"
        "要求：\n"
        "1. share_text 一句话，温柔治愈，带 #万物生花，不超过 40 字。\n"
        "2. bgm_options 返回 3 首，id 只能是 bgm1/bgm2/bgm3。\n"
        "3. 不要套模板式空话，要体现“把画面转成花束”的独特感。\n"
        f"花束标题：{title}\n"
        f"分享规划：{json.dumps(plan, ensure_ascii=False)}\n"
        '输出 JSON：{"share_text":"...","bgm_options":[{"id":"bgm1","name":"...","artist":"..."}]}'
    )
