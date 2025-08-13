"""
Strands Tools Integration for MyAIBOX
Selected core tools from strands-agents-tools package
"""
from typing import Dict, List, Optional, Any, Callable
from core.logger import logger


class StrandsToolsManager:
    """Manager for selected Strands tools"""
    
    def __init__(self):
        self.available_tools = {
            # Core utility tools
            'http_request': {
                'description': 'Make HTTP requests with authentication support',
                'category': 'network',
                'enabled': True,
                'function': None
            },
            'current_time': {
                'description': 'Get current time in various formats and timezones',
                'category': 'utility', 
                'enabled': True,
                'function': None
            },
            'calculator': {
                'description': 'Perform mathematical calculations and symbolic math',
                'category': 'computation',
                'enabled': True,
                'function': None
            },
            'sleep': {
                'description': 'Pause execution for specified duration',
                'category': 'utility',
                'enabled': True,
                'function': None
            },
            
            # System tools (Linux/macOS only)
            'shell': {
                'description': 'Execute shell commands securely',
                'category': 'system',
                'enabled': True,
                'function': None,
                'platform_restricted': True  # Not available on Windows
            },
            'python_repl': {
                'description': 'Execute Python code with state persistence',
                'category': 'code',
                'enabled': True,
                'function': None,
                'platform_restricted': True  # Not available on Windows
            },
            
            # Multimedia tools
            'generate_image': {
                'description': 'Generate images using AI models',
                'category': 'multimedia',
                'enabled': True,
                'function': None
            },
            'nova_reels': {
                'description': 'Generate videos using Amazon Nova Reel',
                'category': 'multimedia',
                'enabled': True,
                'function': None,
                'requires_aws': True
            },
            'speak': {
                'description': 'Generate audio and speech output',
                'category': 'multimedia',
                'enabled': True,
                'function': None
            }
        }
        self.loaded_tools: Dict[str, Any] = {}
    
    def load_tool(self, tool_name: str) -> Optional[Callable]:
        """Load a specific Strands tool"""
        if tool_name not in self.available_tools:
            logger.warning(f"Tool {tool_name} not in available tools list")
            return None
        
        if not self.available_tools[tool_name]['enabled']:
            logger.info(f"Tool {tool_name} is disabled")
            return None
        
        # Return cached tool if already loaded
        if tool_name in self.loaded_tools:
            return self.loaded_tools[tool_name]
        
        try:
            # Import the specific tool from strands_tools
            tool_module = __import__(f'strands_tools.{tool_name}', fromlist=[tool_name])
            
            # The tool function is typically the main function in the module
            # or has the same name as the module
            if hasattr(tool_module, tool_name):
                tool_function = getattr(tool_module, tool_name)
            elif hasattr(tool_module, 'main'):
                tool_function = getattr(tool_module, 'main')
            else:
                # Get the first callable that's not a private method
                callables = [attr for attr in dir(tool_module) 
                           if not attr.startswith('_') and callable(getattr(tool_module, attr))]
                if callables:
                    tool_function = getattr(tool_module, callables[0])
                else:
                    logger.warning(f"No callable function found in {tool_name} module")
                    return None
            
            # Cache the loaded tool
            self.loaded_tools[tool_name] = tool_function
            self.available_tools[tool_name]['function'] = tool_function
            
            logger.info(f"Successfully loaded Strands tool: {tool_name}")
            return tool_function
                
        except ImportError as e:
            logger.warning(f"strands_tools.{tool_name} not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading tool {tool_name}: {e}")
            return None
    
    def get_available_tool_names(self) -> List[str]:
        """Get list of available tool names"""
        return [name for name, info in self.available_tools.items() 
                if info['enabled']]
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tools filtered by category"""
        return [name for name, info in self.available_tools.items()
                if info['enabled'] and info['category'] == category]
    
    def load_tools_for_agent(self, tool_names: List[str]) -> List[Callable]:
        """Load multiple tools for agent use"""
        tools = []
        for tool_name in tool_names:
            tool = self.load_tool(tool_name)
            if tool:
                tools.append(tool)
        return tools
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """Get information about a specific tool"""
        return self.available_tools.get(tool_name)


# Create singleton instance
strands_tools_manager = StrandsToolsManager()
