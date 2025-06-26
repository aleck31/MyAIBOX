import gradio as gr
from .tab_account import create_account_tab
from .tab_module import create_module_tab
from .tab_model import create_model_tab
from .tab_tools import create_tools_tab
from .handler_modules import ModuleHandlers
from .handler_account import AccountHandlers
from .handler_models import ModelHandlers
from .handler_tools import ToolHandlers

with gr.Blocks() as tab_setting:
    # State to store current model choices
    model_choices_state = gr.State()

    # Create tabs using the component functions
    user_name, sessions_list = create_account_tab()
    module_components = create_module_tab()
    models_list, _ = create_model_tab(model_choices_state)  # Properly unpack tuple
    tools_components = create_tools_tab()

    # Initial load with request context
    tab_setting.load(
        # First get username
        fn=AccountHandlers.get_display_username,  # This will receive gr.Request automatically
        inputs=[],
        outputs=[user_name]
    ).success(
        # Then list sessions
        fn=AccountHandlers.list_active_sessions,
        inputs=[user_name],
        outputs=[sessions_list]
    ).success(
        # Initialize model choices state
        fn=ModelHandlers.get_model_choices,
        inputs=[],
        outputs=[model_choices_state]
    ).success(
        # Initialize/update module dropdowns with choices
        fn=lambda choices: [gr.update(choices=choices) for _ in module_components['models'].values()],
        inputs=[model_choices_state],
        outputs=[*module_components['models'].values()]
    ).success(
        # Initialize/refresh module configurations
        fn=ModuleHandlers.refresh_module_configs,
        inputs=[],
        outputs=[
            *module_components['models'].values(),
            *module_components['params'].values(),
            *module_components['tools'].values()
        ]
    ).success(
        # Initialize MCP servers list with tool counts
        fn=ToolHandlers.refresh_mcp_servers_with_tools,
        inputs=[],
        outputs=[tools_components['mcp_servers_list'], tools_components['status_message']]
    ).success(
        # Show status message
        fn=lambda: gr.update(visible=True),
        outputs=[tools_components['status_message']]
    ).then(
        # Then refresh models list
        fn=ModelHandlers.refresh_models,
        inputs=[],
        outputs=[models_list]
    )

    # Update model choices state when models list changes
    models_list.change(
        fn=ModelHandlers.get_model_choices,
        outputs=[model_choices_state]
    ).success(
        # Then update module dropdowns with new choices
        fn=lambda choices: [gr.update(choices=choices) for _ in module_components['models'].values()],
        inputs=[model_choices_state],
        outputs=[*module_components['models'].values()]
    )

    # Tool Management Event Handlers
    
    # Refresh MCP servers with tool counts
    tools_components['buttons']['refresh_servers'].click(
        fn=ToolHandlers.refresh_mcp_servers_with_tools,
        inputs=[],
        outputs=[tools_components['mcp_servers_list'], tools_components['status_message']]
    )
    
    # Enable server
    tools_components['buttons']['enable_server'].click(
        fn=ToolHandlers.enable_server,
        inputs=[tools_components['selected_server']],
        outputs=[tools_components['mcp_servers_list'], tools_components['status_message']]
    )
    
    # Disable server
    tools_components['buttons']['disable_server'].click(
        fn=ToolHandlers.disable_server,
        inputs=[tools_components['selected_server']],
        outputs=[tools_components['mcp_servers_list'], tools_components['status_message']]
    )
    
    # Test connection
    tools_components['buttons']['test_connection'].click(
        fn=ToolHandlers.test_server_connection,
        inputs=[tools_components['selected_server']],
        outputs=[tools_components['connection_test_results'], tools_components['status_message']]
    ).success(
        # Show test results
        fn=lambda: gr.update(visible=True),
        outputs=[tools_components['connection_test_results']]
    )
    
    # Add new server
    tools_components['buttons']['add_server'].click(
        fn=ToolHandlers.add_mcp_server,
        inputs=[
            tools_components['new_server_name'],
            tools_components['new_server_type'],
            tools_components['new_server_url'],
            tools_components['new_server_args']
        ],
        outputs=[tools_components['mcp_servers_list'], tools_components['status_message']]
    ).success(
        # Clear form after successful addition
        fn=lambda: ("", "http", "", ""),
        outputs=[
            tools_components['new_server_name'],
            tools_components['new_server_type'],
            tools_components['new_server_url'],
            tools_components['new_server_args']
        ]
    )
