"""
Tool Management Tab for Settings
"""
import gradio as gr
from typing import Dict, Any


def create_tools_tab() -> Dict[str, Any]:
    """Create the tools management tab
    
    Returns:
        Dict containing all components for external access
    """
    
    with gr.Tab("Tool Management"):
        gr.Markdown("## MCP Server Management")
        gr.Markdown("Configure Model Context Protocol (MCP) servers and their tools.")
        
        with gr.Row():
            with gr.Column(scale=2):
                # MCP Servers List
                gr.Markdown("### MCP Servers")
                mcp_servers_list = gr.Dataframe(
                    headers=["Server Name", "Type", "Status", "URL", "Tools Count"],
                    datatype=["str", "str", "str", "str", "number"],
                    interactive=False,
                    wrap=True,
                    elem_id="mcp_servers_list"
                )
                
                with gr.Row():
                    refresh_servers_btn = gr.Button("🔄 Refresh", variant="secondary")
                    test_connection_btn = gr.Button("🔗 Test Connection", variant="secondary")
            
            with gr.Column(scale=1):
                # Server Details Panel
                gr.Markdown("### Server Details")
                
                selected_server = gr.Textbox(
                    label="Selected Server",
                    interactive=False,
                    visible=False
                )
                
                server_name_display = gr.Textbox(
                    label="Server Name",
                    interactive=False
                )
                
                server_type_display = gr.Textbox(
                    label="Server Type",
                    interactive=False
                )
                
                server_url_display = gr.Textbox(
                    label="Server URL",
                    interactive=False,
                    lines=2
                )
                
                server_status_display = gr.Textbox(
                    label="Status",
                    interactive=False
                )
                
                # Enable/Disable Controls
                with gr.Row():
                    enable_server_btn = gr.Button("✅ Enable", variant="primary")
                    disable_server_btn = gr.Button("❌ Disable", variant="stop")
        
        # Server Tools Section
        gr.Markdown("### Available Tools")
        server_tools_list = gr.Dataframe(
            headers=["Tool Name", "Description", "Server"],
            datatype=["str", "str", "str"],
            interactive=False,
            wrap=True,
            elem_id="server_tools_list"
        )
        
        # Add New MCP Server Section
        with gr.Accordion("➕ Add New MCP Server", open=False):
            with gr.Row():
                with gr.Column():
                    new_server_name = gr.Textbox(
                        label="Server Name",
                        placeholder="e.g., my-custom-server"
                    )
                    
                    new_server_type = gr.Dropdown(
                        label="Server Type",
                        choices=["http", "stdio", "sse"],
                        value="http"
                    )
                    
                    new_server_url = gr.Textbox(
                        label="Server URL (for HTTP/SSE)",
                        placeholder="e.g., https://api.example.com/mcp"
                    )
                    
                    new_server_args = gr.Textbox(
                        label="Arguments (for stdio, JSON array)",
                        placeholder='["arg1", "arg2"]',
                        lines=2
                    )
                    
                with gr.Column():
                    gr.Markdown("#### Server Type Guide")
                    gr.Markdown("""
                    - **HTTP**: Web-based MCP server (requires URL)
                    - **stdio**: Local command-line server (requires args)
                    - **SSE**: Server-Sent Events server (requires URL)
                    """)
                    
                    add_server_btn = gr.Button("➕ Add Server", variant="primary")
        
        # Status Messages
        status_message = gr.Textbox(
            label="Status",
            interactive=False,
            visible=True,
            value=""
        )
        
        # Connection Test Results
        connection_test_results = gr.JSON(
            label="Connection Test Results",
            visible=False
        )
        
        # Handle server selection - using inline function like model management
        def handle_server_select(evt: gr.SelectData, servers_data):
            """Handle server selection from the dataframe"""
            from .handler_tools import ToolHandlers
            
            try:
                # Check if servers_data is empty - handle both list and DataFrame
                if servers_data is None:
                    return "", "", "", "", "", "✗ No data available", []
                
                # Convert DataFrame to list if needed
                if hasattr(servers_data, 'values'):
                    # It's a DataFrame
                    if servers_data.empty:
                        return "", "", "", "", "", "✗ No servers available", []
                    servers_list = servers_data.values.tolist()
                else:
                    # It's already a list
                    if not servers_data:
                        return "", "", "", "", "", "✗ No servers available", []
                    servers_list = servers_data
                
                if evt.index[0] >= len(servers_list):
                    return "", "", "", "", "", "✗ Invalid selection", []
                
                row = servers_list[evt.index[0]]
                server_name = row[0]
                server_type = row[1]
                status = row[2]
                url = row[3]
                
                # Get full server config
                from genai.tools.mcp.mcp_server_manager import mcp_server_manager
                config = mcp_server_manager.get_mcp_tools(server_name)
                if config:
                    full_url = config.get('url', config.get('command', 'N/A'))
                    args = config.get('args', [])
                    if args and server_type == 'stdio':
                        full_url = f"Command: {config.get('command', 'N/A')}, Args: {args}"
                else:
                    full_url = 'Configuration not found'
                
                # Get server tools
                tools_data, _ = ToolHandlers.get_server_tools(server_name)
                
                return (
                    server_name,  # selected_server (hidden)
                    server_name,  # server_name_display
                    server_type,  # server_type_display
                    full_url,     # server_url_display
                    status,       # server_status_display
                    f"✓ Selected server: {server_name}",  # status_message
                    tools_data    # server_tools_list
                )
                
            except Exception as e:
                import traceback
                error_msg = f"✗ Error: {str(e)}"
                print(f"Selection error: {traceback.format_exc()}")
                return "", "", "", "", "", error_msg, []
        
        # Bind server selection event
        mcp_servers_list.select(
            fn=handle_server_select,
            inputs=[mcp_servers_list],
            outputs=[
                selected_server,
                server_name_display,
                server_type_display,
                server_url_display,
                server_status_display,
                status_message,
                server_tools_list
            ]
        )
    
    # Return components for external access
    return {
        'mcp_servers_list': mcp_servers_list,
        'server_tools_list': server_tools_list,
        'selected_server': selected_server,
        'server_name_display': server_name_display,
        'server_type_display': server_type_display,
        'server_url_display': server_url_display,
        'server_status_display': server_status_display,
        'new_server_name': new_server_name,
        'new_server_type': new_server_type,
        'new_server_url': new_server_url,
        'new_server_args': new_server_args,
        'status_message': status_message,
        'connection_test_results': connection_test_results,
        'buttons': {
            'refresh_servers': refresh_servers_btn,
            'test_connection': test_connection_btn,
            'enable_server': enable_server_btn,
            'disable_server': disable_server_btn,
            'add_server': add_server_btn
        }
    }
