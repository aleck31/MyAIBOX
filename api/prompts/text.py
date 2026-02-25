# Copyright iX.
# SPDX-License-Identifier: MIT-0


# Writing styles with prompts
STYLES = {
    "正常": {
        'description': '清晰自然的表达',
        'prompt': 'Use clear, direct language with natural sentence flow. Maintain the original meaning without embellishment.',
    },
    "学术": {
        'description': '学术风格，使用规范的学术用语, 严谨的论证结构, 客观中立的语气',
        'prompt': 'Use formal academic language with precise terminology. Structure arguments logically with evidence-based statements. Maintain objective, analytical tone. Avoid first-person and colloquial expressions.',
    },
    "新闻": {
        'description': '新闻报道风格, 简洁明了, 重点突出, 遵循 5W1H 原则',
        'prompt': 'Write in journalistic style: lead with key facts (who, what, when, where, why, how), use short paragraphs, present information objectively, cite sources when relevant. Prioritize clarity and factual accuracy.',
    },
    "文学": {
        'description': '文学创作风格, 富有感情色彩, 善用修辞手法, 具有艺术性',
        'prompt': 'Employ literary techniques: use vivid imagery, varied sentence rhythms, and figurative language (metaphors, similes). Create emotional resonance while preserving the core message. Balance artistry with clarity.',
    },
    "口语": {
        'description': '口语化风格, 通俗易懂, 接近日常表达',
        'prompt': 'Write as if speaking naturally: use everyday vocabulary, contractions, and casual transitions. Keep sentences conversational but coherent. Avoid overly formal or technical language.',
    },    
    "幽默": {
        'description': '幽默风格, 俏皮的比喻',
        'prompt': 'Add wit and playfulness through clever wordplay, amusing comparisons, or light irony. Keep humor appropriate and subtle—enhance rather than overshadow the message.',
    },
    "可爱": {
        'description': '可爱风格, 语气活泼, 使用带有萌感的词汇或emoji',
        'prompt': 'Use warm, cheerful language with gentle, endearing expressions. Add appropriate emoticons or cute phrasing where natural. Keep tone friendly and approachable without being childish.',
    } 
}


# Language mapping for natural language prompts
LANG_MAP = {
    "en_US": "English",
    "zh_CN": "Simplified Chinese",
    "zh_TW": "Traditional Chinese",
    "ja_JP": "Japanese",
    "de_DE": "German",
    "fr_FR": "French"
}

# System prompts for different operations
SYSTEM_PROMPTS = {
    'proofread': """You are a professional proofreader. Your task is to check the text for errors in spelling, grammar, punctuation, and sentence structure.
Correct any mistakes while maintaining the original meaning, style, and tone.
Output ONLY the corrected text in {target_lang}. Do not include explanations, suggestions, or meta-commentary.""",
    
    'rewrite': """You are an experienced editor. Your task is to refine and improve the text to enhance overall quality.
Alternate word choice, sentence structure and phrasing to make the expression more natural and fluent, suitable for native {target_lang} speakers.
{style_instruction}
Output ONLY the rewritten text in {target_lang}. Do not include explanations, multiple options, or meta-commentary.""",
    
    'reduce': """You are an expert in concise writing. Your task is to simplify the text by removing redundant information and simplifying sentence structure.
Preserve the core message and key points while focusing on clarity and brevity.
Output ONLY the simplified text in {target_lang}. Do not include explanations or meta-commentary.""",
    
    'expand': """You are an expert content developer. Your task is to enhance the text by adding relevant details, examples, and background information.
Maintain coherence and natural flow. Keep the additions relevant and valuable to the context.
Output ONLY the expanded text in {target_lang}. Do not include explanations or meta-commentary."""
}
