"""
Module configuration management
"""
from typing import Dict, Optional, Any, List
from decimal import Decimal
from botocore.exceptions import ClientError
from backend.core.config import env_config
from backend.common.logger import logger
from backend.utils.aws import get_aws_session


class AppConf:
    """
    A class to store and manage configuration. [Legacy]

    """
    
    # The list of style presets for Stable Diffusion
    # https://docs.aws.amazon.com/zh_cn/bedrock/latest/userguide/model-parameters-diffusion-1-0-text-image.html
    PICSTYLES = [
        "增强(enhance)", "照片(photographic)", "模拟胶片(analog-film)", "电影(cinematic)",
        "数字艺术(digital-art)",  "美式漫画(comic-book)",  "动漫(anime)", "3D模型(3d-model)", "低多边形(low-poly)",
        "线稿(line-art)", "等距插画(isometric)", "霓虹朋克(neon-punk)", "复合建模(modeling-compound)",  
        "奇幻艺术(fantasy-art)", "像素艺术(pixel-art)", "折纸艺术(origami)", "瓷砖纹理(tile-texture)"
    ]

    def update(self, key, value):
        # Update the value of a variable.
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise AttributeError(f"Invalid configuration variable: {key}")


class ModuleConfig:
    def __init__(self):
        session = get_aws_session(region_name=env_config.aws_region)
        self.dynamodb = session.resource('dynamodb')
        # Use getattr to avoid static type checking issues
        table_method = getattr(self.dynamodb, 'Table')
        self.table = table_method(env_config.database_config['setting_table'])
        self._config_cache = {}  # Cache for module configurations

    def _decimal_to_numeric(self, obj: Any) -> Any:
        """Helper function to convert Decimal values to appropriate numeric types (int or float) in nested structures"""
        if isinstance(obj, dict):
            return {key: self._decimal_to_numeric(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._decimal_to_numeric(item) for item in obj]
        elif isinstance(obj, Decimal):
            # Convert to float first
            float_val = float(obj)
            # If the float is equivalent to an integer (no decimal part), convert to int
            if float_val.is_integer():
                return int(float_val)
            return float_val
        return obj

    def _numeric_to_decimal(self, obj: Any) -> Any:
        """Helper function to convert numeric values to Decimal for DynamoDB storage"""
        if isinstance(obj, dict):
            return {key: self._numeric_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._numeric_to_decimal(item) for item in obj]
        # bool is a subclass of int — keep it native (DynamoDB stores bools directly);
        # Decimal(str(True)) would raise ConversionSyntax. e.g. thinking.enabled.
        elif isinstance(obj, bool):
            return obj
        elif isinstance(obj, (float, int)):
            return Decimal(str(obj))
        return obj

    def get_module_config(self, module_name: str, sub_module: Optional[str] = None) -> Optional[Dict]:
        """
        Get configuration for a specific module
        
        Args:
            module_name: Name of the module
            sub_module: Optional sub-module name
            
        Returns:
            dict: Module configuration or None if not found
        """
        # Check cache first
        cache_key = f"{module_name}:{sub_module}" if sub_module else module_name
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        try:
            logger.debug(f"Getting config for module: {module_name}")
            response = self.table.get_item(
                Key={
                    'setting_name': module_name,
                    'type': 'module'
                }
            )
            logger.debug(f"Raw response from DB: {response}")

            if 'Item' in response:
                config = self._decimal_to_numeric(response['Item'])
                self._config_cache[cache_key] = config
                return config
            else:
                logger.debug(f"No config found for {module_name}, initializing default")
                if config := self.init_module_config(module_name):
                    self._config_cache[cache_key] = config
                return config

        except ClientError as e:
            logger.error(f"Error getting module config: {str(e)}")
            return None

    def update_module_config(self, module_name: str, config: Dict) -> bool:
        """
        Update configuration for a specific module
        
        Args:
            module_name: Name of the module
            config: New configuration dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure required fields
            config['setting_name'] = module_name
            config['type'] = 'module'
            
            # Convert numeric values to Decimal for DynamoDB
            config = self._numeric_to_decimal(config)
            
            self.table.put_item(Item=config)
            
            # Clear cache entries for this module
            cache_keys_to_remove = [k for k in self._config_cache if k.startswith(f"{module_name}:") or k == module_name]
            for key in cache_keys_to_remove:
                self._config_cache.pop(key, None)
                
            logger.info(f"Updated config for module: {module_name}")
            return True
        except Exception as e:
            logger.error(f"Error updating module config: {str(e)}")
            raise

    # Each module's model-eligibility filter — the single source of truth shared by the
    # module's config endpoint (dropdown choices) and get_default_model's fallback
    # None = no filter (all models).
    MODULE_MODEL_FILTER = {
        'text': {'output_modality': ['text']},
        'asking': {'reasoning': True},
        'vision': {'category': 'vision'},
        'summary': {'tool_use': True},
        'draw': {'category': 'image'},
        # Chat agents: tool-using conversational models (excludes image/video generators).
        'chat': {'tool_use': True},
        # Talk with Agent: realtime speech-to-speech models only.
        'talk': {'category': 'realtime'},
    }

    def get_model_filter(self, module_name: str) -> Optional[Dict]:
        """The model-eligibility filter for a module (None = all models)."""
        return self.MODULE_MODEL_FILTER.get(module_name)

    def get_default_model(self, module_name: str) -> str:
        """A module's configured default model, else the first eligible enabled model
        (same filter the dropdown uses), so selectable and fallback can't diverge."""
        try:
            config = self.get_module_config(module_name)
            if config and config.get('default_model'):
                return config['default_model']
            from backend.genai.models.model_manager import model_manager
            models = model_manager.get_models(filter=self.get_model_filter(module_name)) or []
            if not models:
                raise ValueError(f"No eligible model for module {module_name}")
            logger.warning(f"No default model for module {module_name}; using first eligible: {models[0].model_id}")
            return models[0].model_id
        except Exception as e:
            logger.error(f"Error getting default model for module {module_name}: {str(e)}")
            raise

    def get_inference_params(self, module_name: str) -> Optional[Dict]:
        """Get inference parameters from module configuration"""
        config = self.get_module_config(module_name)
        if config and 'parameters' in config:
            return config['parameters']
        return None

    def get_enabled_tools(self, module_name: str) -> List[str]:
        """
        Get the list of enabled tools for a specific module
        
        Args:
            module_name: Name of the module
            
        Returns:
            List[str]: List of enabled tool module names
        """
        try:
            config = self.get_module_config(module_name)
            if config:
                return config.get('enabled_tools', [])
            return []
        except Exception as e:
            logger.error(f"Error getting enabled tools for module {module_name}: {str(e)}")
            return []


    def init_module_config(self, module_name: str) -> Optional[Dict]:
        """Initialize default configuration for a module"""
        default_configs = {
            'text': {
                'setting_name': 'text',
                'type': 'module',
                'description': 'Text Module',
                'default_model': 'global.anthropic.claude-sonnet-4-6',
                'parameters': {
                    'temperature': Decimal('0.7'),
                    'max_tokens': 2000,
                    'top_k': 100
                }
            },
            'summary': {
                'setting_name': 'summary',
                'type': 'module',
                'description': 'Summary Module',
                'default_model': 'global.anthropic.claude-sonnet-4-6',
                'parameters': {
                    'temperature': Decimal('0.2'),
                    'max_tokens': 2000
                },
                'enabled_tools': [
                    'get_text_from_url'     # Get text content from webpage URL
                ]
            },
            'vision': {
                'setting_name': 'vision',
                'type': 'module',
                'description': 'Vision Module',
                'default_model': 'global.anthropic.claude-sonnet-4-6',
                'parameters': {
                    'temperature': Decimal('0.7'),
                    'max_tokens': 2048,
                    'top_p': Decimal('0.8'),
                    'top_k': 100
                }
            },
            'asking': {
                'setting_name': 'asking',
                'type': 'module',
                'description': 'Asking Module',
                'default_model': 'global.anthropic.claude-sonnet-4-6',
                'parameters': {
                    'temperature': Decimal('0.7'),
                    'max_tokens': 4096
                },
                'enabled_tools': [
                    'get_text_from_url'     # Get text content from webpage URL
                ],
                # effort='high': 'medium' lets adaptive models skip thinking on simple queries.
                'thinking': {
                    'enabled': True,
                    'effort': 'high'
                }
            },
            'draw': {
                'setting_name': 'draw',
                'type': 'module',
                'description': 'Draw Module',
                'default_model': 'stability.stable-image-ultra-v1:0',
                # basic parameters for generative models
                'parameters': {
                    'height': 1152,
                    'width': 896,
                    'aspect_ratio': '9:16'
                }
            },
            'talk': {
                'setting_name': 'talk',
                'type': 'module',
                'description': 'Talk with Agent (realtime voice)',
                'default_model': 'amazon.nova-2-sonic-v1:0',
                'parameters': {
                    'voice_id': 'matthew'
                },
                'enabled_tools': []  # MVP: pure conversation, no tools
            },
            'creative': {
                'setting_name': 'creative',
                'type': 'module',
                'description': 'Creative Module',
                'default_model': 'amazon.nova-canvas-v1:0',
                # basic parameters for generative models
                'parameters': {
                    'height': 1152,
                    'width': 896,
                    'cfg_scale': 7,
                    'steps': 50
                }
            }
        }
        
        if module_name in default_configs:
            config = default_configs[module_name]
            try:
                self.table.put_item(Item=config)
                logger.info(f"Initialized config for module: {module_name}")
                return self._decimal_to_numeric(config)
            except Exception as e:
                logger.error(f"Error initializing module config: {str(e)}")
                return None
        return None

# Create a singleton instance
module_config = ModuleConfig()
