import inspect
import importlib
from typing import Dict, Any, List, Optional, Callable
from core.logger import logger


class BedrockToolRegistry:
    """Simplified registry for managing Bedrock tool specifications and execution"""
    
    def __init__(self):
        self.tools = {}
        self.tool_specs = {}
        self.tool_packages = {
            'get_weather': 'weather_tools',
            'get_text_from_url': 'web_tools',
            'search_wikipedia': 'search_tools',
            'search_internet': 'search_tools',
            'generate_image': 'draw_tools'
        }
        # Auto-load all tools on initialization
        self._load_all_tools()
        
    def _load_all_tools(self):
        """Load all tools from the package mapping"""
        for tool_name, package_name in self.tool_packages.items():
            self.load_local_tool(package_name, tool_name)
        
    def load_local_tool(self, package_name: str, tool_name: str) -> None:
        """Load a specific tool from a local package"""
        try:
            # Import tool module
            tool_module = importlib.import_module(f"genai.tools.legacy.{package_name}")

            # Load tool function
            if hasattr(tool_module, tool_name):
                func = getattr(tool_module, tool_name)
                if inspect.isfunction(func):
                    self.tools[tool_name] = func
                else:
                    logger.warning(f"{tool_name} in {package_name} is not a function")
                    return
            else:
                logger.warning(f"Tool function {tool_name} not found in module {package_name}")
                return

            # Load tool specification
            if hasattr(tool_module, 'list_of_tools_specs'):
                for spec in tool_module.list_of_tools_specs:
                    if spec.get('toolSpec', {}).get('name') == tool_name:
                        self.tool_specs[tool_name] = spec
                        logger.debug(f"[BedrockToolRegistry] Loaded tool: {tool_name}")
                        break
                else:
                    logger.warning(f"No tool specification found for {tool_name} in {package_name}")
                
        except ImportError as e:
            logger.error(f"Failed to import tool_module {package_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading tool {tool_name} from {package_name}: {str(e)}")
        
    def get_tool_spec(self, tool_name: str) -> Optional[Dict]:
        """Get Bedrock specification for a specific tool"""
        return self.tool_specs.get(tool_name)
    
    def get_tool_specs(self, tool_names: Optional[List[str]] = None) -> List[Dict]:
        """Get Bedrock specifications for multiple tools
        
        Args:
            tool_names: Optional list of specific tool names. If None, returns all specs
            
        Returns:
            List of Bedrock tool specifications
        """
        if tool_names is None:
            return list(self.tool_specs.values())
        
        specs = []
        for tool_name in tool_names:
            spec = self.get_tool_spec(tool_name)
            if spec:
                specs.append(spec)
        return specs
    
    def get_tool_function(self, tool_name: str) -> Optional[Callable]:
        """Get tool function for execution"""
        return self.tools.get(tool_name)
        
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a loaded tool"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
            
        try:
            tool_func = self.tools[tool_name]
            # Check if the tool function is async
            if inspect.iscoroutinefunction(tool_func):
                return await tool_func(**kwargs)
            else:
                return tool_func(**kwargs)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {"error": str(e)}
    
    def list_available_tools(self) -> List[str]:
        """Get list of all available tool names"""
        return list(self.tools.keys())
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if tool exists"""
        return tool_name in self.tools
    
    def reload_tools(self):
        """Reload all tools"""
        logger.info("[BedrockToolRegistry] Reloading all tools...")
        self.tools.clear()
        self.tool_specs.clear()
        self._load_all_tools()

# Create global registry instance
br_registry = BedrockToolRegistry()
