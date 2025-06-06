# Copyright iX.
# SPDX-License-Identifier: MIT-0
import gradio as gr
from .handlers import DeepSearchHandlers


def create_interface() -> gr.Blocks:
    """Create Deep Search interface with handlers"""
    
    # Create interface
    interface = gr.Blocks(theme=gr.themes.Soft())
    
    with interface:
        # Header
        gr.Markdown("Search the internet for comprehensive information using MCP Tools")

        output_text = gr.Markdown(
            value="Results will appear here...",
            label='Search Results',
            show_label=False,
            header_links=True,
            line_breaks=True,
            min_height=128,
            render=False
        )

        # Main layout
        with gr.Row():
            # Input column
            with gr.Column(scale=2):
                # Search input
                input_query = gr.MultimodalTextbox(
                    info="Search Query",
                    placeholder="Enter your search query here...",
                    show_label=False,
                    file_types=['image', 'text', '.pdf'],
                    file_count='multiple',
                    lines=5,
                    submit_btn=None,
                    max_plain_text_length=2500
                )

                # Options accordion
                with gr.Accordion(label="Options", open=False):
                    # Model selection dropdown
                    option_model = gr.Dropdown(
                        info="Select model",
                        show_label=False,
                        choices=DeepSearchHandlers.get_available_models(),
                        interactive=True,
                        min_width=120
                    )
                
                # Action buttons
                with gr.Row():
                    btn_clear = gr.ClearButton(
                        value="🗑️ Clear",
                        components=[input_query, output_text]
                    )
                    btn_submit = gr.Button("🔍 Search", variant="primary")

                # Examples section
                gr.Examples(
                    examples=[
                        # English examples
                        ["中国2025年的GDP预测是多少？"],
                        ["Explain the impact of AI on healthcare"],
                        ["详细介绍新加坡的教育体系有什么特点"],
                        ["What are the latest developments in quantum computing?"]
                    ],
                    inputs=[input_query]
                )

            # Output column
            with gr.Column(scale=3):
                with gr.Accordion(label="Result", open=True):
                    # Use the pre-defined component
                    output_text.render()

        # Handle submit button click
        btn_submit.click(
            fn=DeepSearchHandlers.search,
            inputs=[input_query],
            outputs=[output_text],
            api_name="deepsearch"
        )
        
        # Add model selection change handler
        option_model.change(
            fn=DeepSearchHandlers.update_model_id,
            inputs=[option_model],
            outputs=None,
            api_name=False
        )

        # Add model list refresh on load
        interface.load(
            fn=lambda: gr.Dropdown(choices=DeepSearchHandlers.get_available_models()),
            inputs=[],
            outputs=[option_model]
        ).then(  # set selected model 
            fn=DeepSearchHandlers.get_model_id,
            inputs=[],
            outputs=[option_model]  # Update selected model
        )
    
    return interface

# Create interface
tab_deepsearch = create_interface()
