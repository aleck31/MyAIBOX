# UI module for Gradio components
import gradio as gr
from common.logger import setup_logger, logger
from .modules.assistant.ui import tab_assistant
from .modules.persona.ui import tab_persona
from .modules.text.ui import tab_text
from .modules.summary.ui import tab_summary
from .modules.vision.ui import tab_vision
from .modules.coding.ui import tab_coding
from .modules.asking.ui import tab_asking
from .modules.draw.ui import tab_draw
from .setting.ui import tab_setting


def create_main_interface():
    """Create the main Gradio interface with all tabs"""
    # Log when interface is being created
    logger.debug("Creating main Gradio interface")
    
    interface = gr.TabbedInterface(
        [
            tab_assistant, tab_persona, tab_text,
            tab_summary, tab_vision, tab_asking,
            tab_coding, tab_draw, 
            tab_setting
        ],
        tab_names=[
            "Assistant 🤖", "Persona 🎭", "Text 📝", 
            "Summary 📰", "Vision 👀", "Asking 🤔",
            "Coding 💻", "Draw 🎨", 
            "Setting ⚙️"
        ],
        title="MyAIBOX - GenAI百宝箱",
        analytics_enabled=False,  # Disable analytics to prevent session issues
    ).queue(
        default_concurrency_limit=8
    )
    
    logger.debug("Main Gradio interface created successfully")
    return interface
