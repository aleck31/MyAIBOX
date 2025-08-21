import gradio as gr
from . import AssistantHandlers


def create_interface() -> gr.Blocks:
    """Create chat interface with optimized handlers and error handling"""

    # Supported file types with specific extensions
    SUPPORTED_FILES = [
        'text', 'image',
        '.pdf', '.doc', '.docx', '.md'  # Additional document types
    ]

    mtextbox = gr.MultimodalTextbox(
        file_types=SUPPORTED_FILES,
        placeholder="Type a message or upload files (images/documents)",
        stop_btn=True,
        max_plain_text_length=2048,
        scale=13,
        min_width=90,
        render=False
    )
    
    chatbot = gr.Chatbot(
        type='messages',
        show_copy_button=True,
        min_height='60vh',
        max_height='80vh',
        avatar_images=(None, "assets/avatars/assistant.png"),
        show_label=False,
        allow_tags=True,
        render=False
    )

    # Initialize model dropdown
    input_model = gr.Dropdown(
        label="Chat Model:", 
        show_label=False,
        info="Select foundation model",
        choices=AssistantHandlers.get_available_models(),
        interactive=True,
        render=False
    )

    with gr.Blocks() as chat_interface:

        gr.Markdown("Let me help you with ... (Powered by Strands Agents)")

        # Create optimized chat interface
        chat = gr.ChatInterface(
            fn=AssistantHandlers.send_message,
            type='messages',
            multimodal=True,
            chatbot=chatbot,
            textbox=mtextbox,
            stop_btn='🟥',
            additional_inputs_accordion=gr.Accordion(
                label='Options', 
                open=False,
                render=False
            ),
            additional_inputs=[input_model],
            api_name=False
        )

        chat.load(
            fn=lambda: gr.Dropdown(choices=AssistantHandlers.get_available_models()),  # Return new Dropdown with updated choices
            inputs=[],
            outputs=[input_model]
        ).then(
            fn=AssistantHandlers.load_history_options,  # Load chat history and selected model
            inputs=[],
            outputs=[chat.chatbot_value, input_model]
        )

        # Add model selection change handler
        input_model.change(
            fn=AssistantHandlers.update_model_id,
            inputs=[input_model],
            outputs=None,
            api_name=False
        )

        # Add clear history handler for the clear button
        chat.chatbot.clear(AssistantHandlers.clear_chat_history)

        # Add undo handler for the undo and retry button
        chat.chatbot.undo(AssistantHandlers.undo_last_message)
        chat.chatbot.retry(AssistantHandlers.undo_last_message)

    return chat_interface

# Create interface
tab_assistant = create_interface()
