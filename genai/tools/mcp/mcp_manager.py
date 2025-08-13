#!/usr/bin/env python3
"""
MCP 连接管理器 - 混合模式实现
结合持久化连接和装饰器模式的优势
"""

import time
import asyncio
import threading
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager
import logging
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

class MCPConnectionManager:
    """MCP 连接管理器 - 智能连接池"""
    
    def __init__(self, cleanup_interval: int = 300):
        self._connections: Dict[str, MCPClient] = {}
        self._connection_configs: Dict[str, Dict[str, Any]] = {}
        self._last_used: Dict[str, float] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    def register_service(self, service_key: str, config: Dict[str, Any]):
        """注册 MCP 服务配置"""
        self._connection_configs[service_key] = config
        self._locks[service_key] = threading.Lock()
        logger.info(f"注册 MCP 服务: {service_key}")
    
    def start_cleanup_task(self):
        """启动清理任务"""
        if not self._is_running:
            self._is_running = True
            # 在后台启动清理任务
            threading.Thread(target=self._run_cleanup_loop, daemon=True).start()
            logger.info("MCP 连接管理器清理任务已启动")
    
    def _run_cleanup_loop(self):
        """清理循环 - 在独立线程中运行"""
        while self._is_running:
            try:
                self._cleanup_idle_connections()
                time.sleep(self._cleanup_interval)
            except Exception as e:
                logger.error(f"MCP 连接清理失败: {e}")
    
    def _cleanup_idle_connections(self):
        """清理空闲连接"""
        current_time = time.time()
        to_remove = []
        
        for service_key, last_used in self._last_used.items():
            if current_time - last_used > self._cleanup_interval:
                to_remove.append(service_key)
        
        for service_key in to_remove:
            self._close_connection(service_key)
            logger.info(f"清理空闲 MCP 连接: {service_key}")
    
    def get_connection(self, service_key: str) -> Optional[MCPClient]:
        """获取 MCP 连接 (同步方法)"""
        if service_key not in self._connection_configs:
            logger.error(f"未注册的 MCP 服务: {service_key}")
            return None
        
        with self._locks[service_key]:
            # 检查现有连接
            if service_key in self._connections:
                connection = self._connections[service_key]
                # 简单的连接健康检查
                try:
                    # 更新使用时间
                    self._last_used[service_key] = time.time()
                    return connection
                except Exception as e:
                    logger.warning(f"MCP 连接不健康，重新创建: {e}")
                    self._close_connection(service_key)
            
            # 创建新连接
            return self._create_connection(service_key)
    
    def _create_connection(self, service_key: str) -> Optional[MCPClient]:
        """创建新的 MCP 连接"""
        try:
            config = self._connection_configs[service_key]
            
            if config['type'] == 'stdio':
                client = MCPClient(lambda: stdio_client(
                    StdioServerParameters(
                        command=config['command'],
                        args=config['args'],
                        env=config.get('env', {})
                    )
                ))
            else:
                logger.error(f"不支持的 MCP 连接类型: {config['type']}")
                return None
            
            self._connections[service_key] = client
            self._last_used[service_key] = time.time()
            
            logger.info(f"创建 MCP 连接成功: {service_key}")
            return client
            
        except Exception as e:
            logger.error(f"创建 MCP 连接失败 {service_key}: {e}")
            return None
    
    def _close_connection(self, service_key: str):
        """关闭连接"""
        if service_key in self._connections:
            try:
                # MCP 客户端会在 context manager 退出时自动关闭
                del self._connections[service_key]
                if service_key in self._last_used:
                    del self._last_used[service_key]
            except Exception as e:
                logger.error(f"关闭 MCP 连接失败 {service_key}: {e}")
    
    def shutdown(self):
        """关闭管理器"""
        self._is_running = False
        for service_key in list(self._connections.keys()):
            self._close_connection(service_key)
        logger.info("MCP 连接管理器已关闭")

# 全局连接管理器实例
mcp_manager = MCPConnectionManager()

class MCPContextWrapper:
    """MCP 上下文包装器"""
    
    def __init__(self, service_key: str):
        self.service_key = service_key
    
    def __enter__(self):
        self.client = mcp_manager.get_connection(self.service_key)
        if self.client:
            self.context = self.client.__enter__()
            return self.client
        return None
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'context') and self.client:
            return self.client.__exit__(exc_type, exc_val, exc_tb)

def with_mcp(service_key: str):
    """MCP 装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with MCPContextWrapper(service_key) as client:
                if client:
                    return func(client, *args, **kwargs)
                else:
                    raise RuntimeError(f"无法获取 MCP 连接: {service_key}")
        return wrapper
    return decorator

# 便捷函数
def setup_exa_mcp(api_key: str):
    """设置 Exa MCP 服务"""
    mcp_manager.register_service('exa', {
        'type': 'stdio',
        'command': 'npx',
        'args': ['-y', 'exa-mcp-server'],
        'env': {'EXA_API_KEY': api_key}
    })
    mcp_manager.start_cleanup_task()

def get_exa_connection():
    """获取 Exa MCP 连接"""
    return MCPContextWrapper('exa')
