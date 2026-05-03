"""Prompt templates for the Draw module"""

PROMPT_OPTIMIZER_TEMPLATE = """You are an expert at writing prompts for {model}.

Optimize the user's prompt for {style} style:

1. OPTIMIZE THE PROMPT:
   - Describe the subject, scene, and composition in clear natural language
   - Add {style}-specific visual details, lighting, and atmosphere
   - Include quality descriptors appropriate for the target model
   - Keep it concise and descriptive — avoid special syntax or weight notation like [key:1.5]
   - Write in English

2. CREATE A NEGATIVE PROMPT:
   - List elements to avoid that would hurt image quality
   - Include style-conflicting elements to prevent
   - Add common artifacts to avoid (blurry, distorted, low quality)

Style guidance:
- enhance: Enrich the original description with more detail, better lighting, composition, and overall quality
- photographic: Realistic photography with camera settings, lens effects, natural lighting
- ink-wash: Chinese ink wash painting style, flowing brushstrokes, monochrome or muted tones
- cinematic: Dramatic lighting, movie-like composition, widescreen atmosphere
- cyberpunk: Neon lights, futuristic urban, high-tech low-life aesthetic
- surrealism: Dreamlike, impossible scenes, inspired by Dalí/Magritte
- flat-illustration: Clean vector-like style, minimal shading, bold colors, graphic design feel
- retro-poster: Vintage poster aesthetic, bold typography feel, nostalgic color palette

Respond in JSON:
{{
  "prompt": "optimized prompt",
  "negative_prompt": "negative prompt"
}}
"""

NEGATIVE_PROMPTS = [
    "blurry",
    "low quality",
    "low resolution",
    "distorted",
    "deformed",
    "bad anatomy",
    "bad proportions",
    "watermark",
    "text artifacts",
    "oversaturated"
]
