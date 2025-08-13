#!/usr/bin/env python3
"""
Strands Agent Sandbox tools
"""

import json
import logging
from typing import Optional, Dict, List, Any, Callable
from dataclasses import asdict
from strands import tool
from genai.sandbox.env import EC2SandboxEnv, SandboxConfig
from genai.sandbox.instance import ExecutionResult


logger = logging.getLogger(__name__)


def create_strands_tools(config: SandboxConfig) -> List[Callable[..., str]]:
    """创建Strands Agent工具"""

    # 创建沙盒环境（单例）
    sandbox_env = EC2SandboxEnv(config)
    
    @tool
    def execute_code_in_sandbox(
        code: str,
        runtime: str = "python3",
        task_id: Optional[str] = None,
        files: Optional[Dict[str, str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        create_filesystem: bool = True
    ) -> str:
        """
        在EC2沙箱中安全执行代码(最大代码长度: 70KB)
        
        Args:
            code: 要执行的代码 (必需)
            runtime: 运行时环境，可选值: "python3"(默认), "python", "node", "bash", "sh"
            task_id: 任务ID, 用于标识任务
            files: 需要创建的文件 {filename: content}
            env_vars: 可选的环境变量 {key: value}
            create_filesystem: 是否创建独立文件系统 (默认: True)
            
        Returns:
            执行结果的JSON字符串
        """
        try:
            # 检查代码长度
            code_size = len(code.encode('utf-8'))
            # 设置安全限制为70KB，为各种情况留出余量
            MAX_CODE_SIZE = 71680
            
            if code_size > MAX_CODE_SIZE:
                error_result = ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"代码过长 ({code_size:,} 字节 = {code_size/1024:.1f}KB)，超过安全限制。\n\n"
                           f"📏 限制详情：\n"
                           f"• AWS SSM实际限制：~99KB（总命令大小）\n"
                           f"• 最大代码限制：~72KB（实测边界）\n"
                           f"• 安全代码限制：70KB（推荐使用）\n"
                           f"• 当前代码大小：{code_size/1024:.1f}KB\n\n"
                           f"🔧 代码优化建议：\n"
                           f"1. 移除不必要的注释、空行和调试代码\n"
                           f"2. 使用更简洁的变量名和函数名\n"
                           f"3. 将复杂逻辑拆分为多个简单函数\n"
                           f"4. 避免重复代码，使用循环和函数复用\n"
                           f"5. 移除不必要的导入和依赖\n"
                           f"6. 考虑将大任务分解为多个小步骤执行\n"
                           f"7. 将大量数据改用文件输入而非硬编码",
                    return_code=1,
                    execution_time=0,
                    working_directory="",
                    files_created=[],
                    task_hash=None,
                    error_message=f"Code too long: {code_size} bytes ({code_size/1024:.1f}KB) exceeds {MAX_CODE_SIZE} bytes (70KB) safe limit"
                )
                return json.dumps(asdict(error_result), indent=2, ensure_ascii=False)
            
            # 创建沙盒实例
            sandbox_instance = sandbox_env.create_sandbox_instance(task_id)
            
            result = sandbox_instance.execute_code(
                code=code,
                runtime=runtime,
                files=files,
                env_vars=env_vars,
                create_filesystem=create_filesystem
            )
            
            return json.dumps(asdict(result), indent=2, ensure_ascii=False)
            
        except Exception as e:
            error_result = ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=1,
                execution_time=0,
                working_directory="",
                files_created=[],
                error_message=str(e)
            )
            return json.dumps(asdict(error_result), indent=2, ensure_ascii=False)
    
    @tool
    def get_task_files(task_hash: str, filename: Optional[str] = None) -> str:
        """
        获取任务目录中的文件内容
        
        Args:
            task_hash: 任务hash值
            filename: 特定文件名，不指定则获取所有文件
            
        Returns:
            文件内容的JSON字符串
        """
        try:
            files = sandbox_env._get_task_files_by_hash(task_hash, filename)
            return json.dumps(files, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    @tool
    def cleanup_expired_tasks(hours: Optional[int] = None) -> str:
        """
        清理过期的任务目录
        
        Args:
            hours: 清理多少小时前的任务，默认使用配置值
            
        Returns:
            清理结果
        """
        try:
            sandbox_env.cleanup_old_tasks(hours)
            return "清理完成"
        except Exception as e:
            return f"清理失败: {str(e)}"
    
    @tool
    def check_sandbox_status() -> str:
        """
        检查Sandbox底层环境(EC2实例)状态
        
        Returns:
            实例状态信息的JSON字符串
        """
        try:
            status = sandbox_env.check_instance_status()
            return json.dumps(status, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    # 收集所有工具到列表中
    tools_list = []
    
    # 添加工具到列表
    tools_list.append(execute_code_in_sandbox)
    tools_list.append(get_task_files)
    tools_list.append(cleanup_expired_tasks)
    tools_list.append(check_sandbox_status)
    
    return tools_list
