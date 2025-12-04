"""
Logging configuration with rotating file handlers and automatic prefix tagging
"""
import logging
import inspect
from pathlib import Path
from logging.handlers import RotatingFileHandler
from core.config import app_config


class AutoPrefixLogger:
    """Logger wrapper that automatically adds caller name as prefix"""
    
    def __init__(self, base_logger):
        self.base_logger = base_logger
        self._log_methods = {'debug', 'info', 'warning', 'error', 'critical', 'exception'}
    
    def _get_caller_name(self):
        """Get caller name for automatic prefix"""
        try:
            # Get call stack: [current, log_method, __getattr__, actual_caller, ...]
            stack = inspect.stack()
            if len(stack) < 4:
                return None
            # Get the 4th frame (index 3) which is the actual caller
            caller_frame = stack[3].frame
            
            # Class method: use class name
            if 'self' in caller_frame.f_locals:
                return caller_frame.f_locals['self'].__class__.__name__
            
            # Static/class method: use class name
            elif 'cls' in caller_frame.f_locals:
                return caller_frame.f_locals['cls'].__name__
            
            # Regular function: use function name (skip <module>)
            else:
                func_name = caller_frame.f_code.co_name
                if func_name != '<module>':
                    return func_name
                return None
                
        except Exception:
            return None
    
    def _format_message(self, msg):
        """Format message with automatic prefix"""
        caller_name = self._get_caller_name()
        if caller_name:
            return f"[{caller_name}] {msg}"
        return msg
    
    def __getattr__(self, name):
        """Dynamically handle logging method calls"""
        if name in self._log_methods:
            base_method = getattr(self.base_logger, name)
            
            def log_method(msg, *args, **kwargs):
                formatted_msg = self._format_message(msg)
                return base_method(formatted_msg, *args, **kwargs)
            
            return log_method
        
        # For non-logging methods, delegate to base logger
        return getattr(self.base_logger, name)


def setup_logger(layer_name: str = 'app') -> AutoPrefixLogger:
    """
    Setup logger with console and rotating file handlers.
    
    Args:
        layer_name: Layer name for the logger (e.g., 'app', 'genai', 'service', 'core')
    
    Returns:
        AutoPrefixLogger instance with automatic prefix functionality
    """
    import os
    
    base_logger = logging.getLogger(layer_name)
    
    # Avoid duplicate handlers if logger already exists
    if base_logger.handlers:
        return AutoPrefixLogger(base_logger)
    
    # Determine log level from DEBUG setting
    debug_mode = app_config.server_config['debug']
    base_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Check if file logging is enabled (default: true for backward compatibility)
    log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler (shows all logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    base_logger.propagate = False  # Prevent propagation to avoid duplicate logs
    base_logger.addHandler(console_handler)
    
    # File handlers (only if LOG_TO_FILE=true)
    if log_to_file:
        # Create logs directory
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # Regular application log file (INFO and above)
        app_handler = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)
        base_logger.addHandler(app_handler)
        
        # Debug log file (DEBUG level only)
        if debug_mode:
            debug_handler = RotatingFileHandler(
                log_dir / 'debug.log',
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            debug_handler.setFormatter(formatter)
            debug_handler.setLevel(logging.DEBUG)
            # Only write DEBUG level messages to debug.log
            debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
            base_logger.addHandler(debug_handler)
    
    return AutoPrefixLogger(base_logger)

# Create default logger for backward compatibility
logger = setup_logger('app')
