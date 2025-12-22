import gradio as gr
from . import ChatbotHandlers
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
        buttons=["copy"],
        min_height='60vh',
        max_height='80vh',
        avatar_images=(None, "assets/avatars/chatbot.png"),
        allow_tags=True,
        render=False
    )

    option_model = gr.Dropdown(
        label="Chat Model:", 
        show_label=False,
        info="Select foundation model",
        choices=ChatbotHandlers.get_available_models(),
        interactive=True,
        render=False
    )

    # option_role = gr.Dropdown(
    #     label="Persona Role:", 
    #     show_label=False,
    #     info="Select persona role",
    #     choices={k: v["name"] for k, v in PERSONA_ROLES.items()},
    #     value="default",
    #     render=False
    # )
    option_role = gr.Radio(
        label="Chat Role:", 
        show_label=False,
        choices=[(v['display_name'], k) for k, v in PERSONA_ROLES.items()],
        value="default",
        info="Select persona role",
        render=False
    )

    with gr.Blocks(analytics_enabled=False) as chat_interface:
        gr.Markdown("Let's chat ...")

        # Create chat interface with history loading
        chat = gr.ChatInterface(
            fn=ChatbotHandlers.send_message,
            multimodal=True,
            chatbot=chatbot,
            textbox=mtextbox,
            stop_btn='🟥',
            additional_inputs_accordion=gr.Accordion(
                label='Options', 
                open=False,
                render=False
            ),
            additional_inputs=[option_role, option_model],
            # save_history=True,
            api_name=False
        )

        # Load chat history and session options on startup
        chat.load(
            fn=lambda: gr.Dropdown(choices=ChatbotHandlers.get_available_models()),  # Return new Dropdown with updated choices
            inputs=[],
            outputs=[option_model]
        ).then(
            fn=ChatbotHandlers.load_history_options,
            inputs=[],
            outputs=[chat.chatbot_value, option_model, option_role]  # Update chatbot_value and selected options
        )

        # Add model selection change handler
        option_model.change(
            fn=ChatbotHandlers.update_model_id,
            inputs=[option_model],
            outputs=None,
            api_name=False,
            queue=False
        )

        # Add persona role change handler
        option_role.change(
            fn=ChatbotHandlers.update_persona_role,
            inputs=[option_role],
            outputs=None,
            api_name=False,
            queue=False
        )

        # Add clear history handler for the clear button
        chat.chatbot.clear(ChatbotHandlers.clear_chat_history, queue=False)
        # Add undo handler for the undo and retry button
        chat.chatbot.undo(ChatbotHandlers.undo_last_message, queue=False)
        chat.chatbot.retry(ChatbotHandlers.undo_last_message, queue=False)

    return chat_interface

# Create interface
tab_persona = create_interface()
