# UI module for Gradio components
import gradio as gr
from modules.assistant.ui import tab_assistant
from modules.persona.ui import tab_persona
from modules.text.ui import tab_text
from modules.summary.ui import tab_summary
from modules.vision.ui import tab_vision
from modules.coding.ui import tab_coding
from modules.asking.ui import tab_asking
from modules.draw.ui import tab_draw
from modules.deepsearch.ui import tab_deepsearch
from common.setting.ui import tab_setting
from core.logger import logger


# The Svelte-generated class name that might change between versions
main_class = 'svelte-1tnkvm8'

css = f""" 
    footer {{visibility: hidden}}

    /* Reset base styles */
    .app.{main_class}.{main_class} {{
        padding: var(--size-3) var(--size-2);
        transition: width 0.3s, max-width 0.3s, padding 0.3s;
        max-width: none;
    }}

    /* Small screens (<=767px) */
    @media (min-width: 640px) {{
        .fillable.{main_class}.{main_class}:not(.fill_width) {{
            padding: var(--size-3) var(--size-0-5);
            width: 100% !important;
        }}
    }}

    /* Medium screens (768px-1023px) */
    @media (min-width: 768px) {{
        .fillable.{main_class}.{main_class}:not(.fill_width) {{
            padding: var(--size-3) var(--size-0-5);
            width: 100% !important;
            max-width: 920px !important;
        }}
    }}

    /* Large screens (1024px-1199px) */
    @media (min-width: 1024px) {{
        .fillable.{main_class}.{main_class}:not(.fill_width) {{
            padding: var(--size-3) var(--size-2);
            width: 90% !important;
            max-width: 960px !important;
        }}
    }}

    /* Extra large screens (≥1200px) */
    @media (min-width: 1200px) {{
        .fillable.{main_class}.{main_class}:not(.fill_width) {{
            padding: var(--size-3) var(--size-3);
            width: 80% !important;
            max-width: 1024px !important;
        }}
    }}
    """

def create_main_interface():
    """Create the main Gradio interface with all tabs"""
    # Log when interface is being created
    logger.debug("Creating main Gradio interface")
    
    interface = gr.TabbedInterface(
        [
            tab_assistant, tab_persona, tab_text,
            tab_summary, tab_vision, tab_deepsearch, tab_asking,
            tab_coding, tab_draw, 
            tab_setting
        ],
        tab_names=[
            "Assistant 🤖", "Persona 🎭", "Text 📝", 
            "Summary 📰", "Vision 👀", "DeepSearch 🔍", "Asking 🤔",
            "Coding 💻", "Draw 🎨", 
            "Setting ⚙️"
        ],
        title="MyAIBOX - GenAI百宝箱",
        theme="Ocean",
        css=css,
        analytics_enabled=False,  # Disable analytics to prevent session issues
    ).queue(
        default_concurrency_limit=8
    )
    
    logger.debug("Main Gradio interface created successfully")
    return interface
