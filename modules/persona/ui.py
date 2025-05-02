import gradio as gr
from .handlers import ChatbotHandlers
from .prompts import PERSONA_ROLES


def create_interface() -> gr.Blocks:
    """Create chat interface with handlers"""

    # Supported file types with specific extensions
    SUPPORTED_FILES = [
        'text', 'image', 'audio', 'video'
        '.pdf', '.doc', '.docx', '.md'  # Additional document types
    ]

    mtextbox=gr.MultimodalTextbox(
                file_types=SUPPORTED_FILES,
                file_count='multiple',
                placeholder="Type a message or upload image(s)",
                stop_btn=True,
                max_plain_text_length=2048,
                scale=13,
                min_width=90,
                render=False
            )

    chatbot=gr.Chatbot(
        type='messages',
        show_copy_button=True,
        min_height='60vh',
        max_height='80vh',
        avatar_images=(None, "modules/persona/avata_bot.png"),
        allow_tags=True,
        render=False
    )

    option_model = gr.Dropdown(
        label="Chat Model:", 
        show_label=False,
        info="Select chat model",
        choices=ChatbotHandlers.get_available_models(),
        interactive=True,
        render=False
    )

    # option_role = gr.Dropdown(
    #     label="Chat Style:", 
    #     show_label=False,
    #     info="Select conversation style",
    #     choices={k: v["name"] for k, v in PERSONA_ROLES.items()},
    #     value="default",
    #     render=False
    # )
    option_role = gr.Radio(
        label="Chat Role:", 
        show_label=False,
        choices=[(v['display_name'], k) for k, v in PERSONA_ROLES.items()],
        value="default",
        info="Select conversation style",
        render=False
    )

    with gr.Blocks(analytics_enabled=False) as chat_interface:
        gr.Markdown("Let's chat ...")

        # Create chat interface with history loading
        chat = gr.ChatInterface(
            fn=ChatbotHandlers.send_message,
            type='messages',
            multimodal=True,
            chatbot=chatbot,
            textbox=mtextbox,
            stop_btn='🟥',
            additional_inputs_accordion=gr.Accordion(
                label='Chat Options', 
                open=False,
                render=False
            ),
            additional_inputs=[option_role, option_model]
        )

        # Load chat history and configuration on startup
        chat.load(
            fn=lambda: gr.Dropdown(choices=ChatbotHandlers.get_available_models()),  # Return new Dropdown with updated choices
            inputs=[],
            outputs=[option_model]
        ).then(  # Load chat history and selected model
            fn=ChatbotHandlers.load_history_confs,
            inputs=[],
            outputs=[chat.chatbot, chat.chatbot_state, option_model]  # Update history and selected model
        )

        # Add model selection change handler
        option_model.change(
            fn=ChatbotHandlers.update_model_id,
            inputs=[option_model],
            outputs=None,
            api_name=False
        )

        # Add clear history handler for the clear button
        chat.chatbot.clear(ChatbotHandlers.clear_chat_history)

        # Add undo handler for the undo and retry button
        chat.chatbot.undo(ChatbotHandlers.undo_last_message)
        chat.chatbot.retry(ChatbotHandlers.undo_last_message)

    return chat_interface

# Create interface
tab_persona = create_interface()
