"""Prompts for the summary module"""

# Language mapping for natural language prompts
LANG_MAP = {
    "original": "the original language",
    "Chinese": "Chinese",
    "English": "English",
    "zh_CN": "Simplified Chinese",
    "zh_TW": "Traditional Chinese",
    "en_US": "English"
}

SYSTEM_PROMPT = """You are a text summarization expert. Output only the summary content without meta-commentary.

Guidelines:
- If input contains URL starting with @, use get_text_from_url tool first
- Begin with a concise overview sentence
- Use clear structure: headings for sections, bullet points for key details
- Target length: 20-30% of original for long texts, 40-50% for short texts
- Preserve technical terms and key terminology exactly
- Maintain factual accuracy and original tone
- Output in {target_lang}
"""

def build_user_prompt(text: str, target_lang: str) -> str:
    """Build user prompt with language instruction
    
    Args:
        text: Text to summarize
        target_lang: Target language for summary
        
    Returns:
        str: Formatted user prompt
    """
    lang = LANG_MAP.get(target_lang, target_lang)
    
    return f"""Summarize the following text in {lang}:

<text>
{text}
</text>"""
