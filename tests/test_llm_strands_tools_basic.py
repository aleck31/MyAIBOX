"""
Direct LLM Strands Tools Test
直接测试 LLM 调用 Strands Tools 的脚本
"""
import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from genai.agents.provider import AgentProvider
from genai.tools.provider import tool_provider


async def test_llm_with_strands_tools():
    """直接测试 LLM 调用 Strands 工具"""
    print("🤖 开始测试 LLM 直接调用 Strands Tools...")
    
    try:
        # 1. 获取 Strands 工具
        print("\n📦 获取 Strands 工具...")
        tools = await tool_provider.get_tools_for_agent(
            include_legacy=False,
            include_mcp=False,
            include_strands=True,
            tool_filter=['current_time', 'calculator', 'http_request']
        )
        
        print(f"✅ 成功获取 {len(tools)} 个 Strands 工具")
        
        # 2. 创建 AgentProvider
        print("\n🧠 创建 AgentProvider...")
        system_prompt = """You are a helpful assistant with access to tools. 
        Use the appropriate tools to answer user questions accurately.
        Always use tools when they can help provide better answers."""
        
        agent_provider = AgentProvider(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            system_prompt=system_prompt
        )
        print("✅ AgentProvider 创建成功")
        
        # 3. 配置工具
        tool_config = {
            'enabled': True,
            'include_legacy': False,
            'include_mcp': False,
            'include_strands': True,
            'tool_filter': ['current_time', 'calculator', 'http_request']
        }
        
        # 4. 测试时间工具
        print("\n⏰ 测试 current_time 工具...")
        try:
            response_chunks = []
            async for chunk in agent_provider.generate_stream(
                "What time is it now? Please use the current_time tool.", 
                tool_config
            ):
                response_chunks.append(chunk)
                # 限制响应数量
                if len(response_chunks) > 20:
                    break
            
            # 合并响应
            full_response = ""
            for chunk in response_chunks:
                if isinstance(chunk, dict) and 'content' in chunk:
                    if 'text' in chunk['content']:
                        full_response += chunk['content']['text']
            
            print(f"🕐 时间查询响应: {full_response[:200]}...")
            
        except Exception as e:
            print(f"❌ 时间工具测试失败: {e}")
        
        # 5. 测试计算器工具
        print("\n🧮 测试 calculator 工具...")
        try:
            response_chunks = []
            async for chunk in agent_provider.generate_stream(
                "Please calculate 25 * 17 using the calculator tool.", 
                tool_config
            ):
                response_chunks.append(chunk)
                if len(response_chunks) > 20:
                    break
            
            # 合并响应
            full_response = ""
            for chunk in response_chunks:
                if isinstance(chunk, dict) and 'content' in chunk:
                    if 'text' in chunk['content']:
                        full_response += chunk['content']['text']
            
            print(f"🔢 计算响应: {full_response[:200]}...")
            
        except Exception as e:
            print(f"❌ 计算器工具测试失败: {e}")
        
        # 6. 测试 HTTP 请求工具
        print("\n🌐 测试 http_request 工具...")
        try:
            response_chunks = []
            async for chunk in agent_provider.generate_stream(
                "Make a GET request to https://httpbin.org/json using the http_request tool.", 
                tool_config
            ):
                response_chunks.append(chunk)
                if len(response_chunks) > 20:
                    break
            
            # 合并响应
            full_response = ""
            for chunk in response_chunks:
                if isinstance(chunk, dict) and 'content' in chunk:
                    if 'text' in chunk['content']:
                        full_response += chunk['content']['text']
            
            print(f"📡 HTTP 请求响应: {full_response[:200]}...")
            
        except Exception as e:
            print(f"❌ HTTP 工具测试失败: {e}")
        
        print("\n🎉 所有基础工具测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


async def test_llm_with_media_tools():
    """测试 LLM 调用媒体工具"""
    print("\n🎨 开始测试 LLM 调用媒体工具...")
    
    try:
        # 获取媒体工具
        print("\n📦 获取媒体工具...")
        tools = await tool_provider.get_tools_for_agent(
            include_legacy=False,
            include_mcp=False,
            include_strands=True,
            tool_filter=['generate_image', 'speak']  # 先测试这两个
        )
        
        print(f"✅ 成功获取 {len(tools)} 个媒体工具")
        
        if len(tools) == 0:
            print("⚠️ 没有可用的媒体工具，跳过媒体测试")
            return
        
        # 创建专门的媒体 Agent
        print("\n🎭 创建媒体 Agent...")
        media_agent = Agent(
            system_prompt="""You are a creative assistant with access to media generation tools.
            When asked to create images, use the generate_image tool.
            When asked to create audio or speech, use the speak tool.
            Always try to use the appropriate tools for media creation requests.""",
            tools=tools
        )
        print("✅ 媒体 Agent 创建成功")
        
        # 测试图像生成工具
        print("\n🖼️ 测试 generate_image 工具...")
        try:
            response = media_agent("Please generate an image of a beautiful sunset over the ocean.")
            print(f"🎨 图像生成响应: {response}")
        except Exception as e:
            print(f"❌ 图像生成工具测试失败: {e}")
        
        # 测试语音工具
        print("\n🔊 测试 speak 工具...")
        try:
            response = media_agent("Please generate speech saying 'Hello, this is a test of the speak tool.'")
            print(f"🎙️ 语音生成响应: {response}")
        except Exception as e:
            print(f"❌ 语音工具测试失败: {e}")
        
        print("\n🎉 媒体工具测试完成！")
        
    except Exception as e:
        print(f"❌ 媒体工具测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


async def test_llm_complex_task():
    """测试 LLM 执行复杂任务（使用多个工具）"""
    print("\n🚀 开始测试 LLM 执行复杂任务...")
    
    try:
        # 获取所有可用的 Strands 工具
        print("\n📦 获取所有 Strands 工具...")
        tools = await tool_provider.get_tools_for_agent(
            include_legacy=False,
            include_mcp=False,
            include_strands=True
        )
        
        print(f"✅ 成功获取 {len(tools)} 个工具")
        
        # 创建全能 Agent
        print("\n🤖 创建全能 Agent...")
        super_agent = Agent(
            system_prompt="""You are a versatile AI assistant with access to various tools.
            You can:
            - Get current time information
            - Perform calculations
            - Make HTTP requests
            - Generate images (if available)
            - Generate speech (if available)
            
            Use the appropriate tools to complete user requests step by step.""",
            tools=tools
        )
        print("✅ 全能 Agent 创建成功")
        
        # 复杂任务测试
        print("\n🎯 执行复杂任务...")
        complex_task = """Please help me with the following tasks:
        1. Tell me what time it is now
        2. Calculate how many seconds are in a day (24 * 60 * 60)
        3. Make a request to https://httpbin.org/status/200 to check if it's working
        
        Complete each task using the appropriate tools and provide a summary."""
        
        try:
            response = super_agent(complex_task)
            print(f"🎯 复杂任务响应: {response}")
        except Exception as e:
            print(f"❌ 复杂任务执行失败: {e}")
        
        print("\n🎉 复杂任务测试完成！")
        
    except Exception as e:
        print(f"❌ 复杂任务测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 Strands Tools 直接 LLM 调用测试")
    print("=" * 60)
    
    # 检查环境
    print("\n🔍 检查环境配置...")
    
    # 检查 AWS 凭证
    aws_configured = (
        os.getenv('AWS_ACCESS_KEY_ID') or 
        os.getenv('AWS_PROFILE') or 
        os.path.exists(os.path.expanduser('~/.aws/credentials'))
    )
    
    if not aws_configured:
        print("⚠️ 警告: 未检测到 AWS 凭证配置")
        print("   某些功能可能无法正常工作")
    else:
        print("✅ AWS 凭证配置检测正常")
    
    # 运行核心测试
    await test_llm_with_strands_tools()
    
    print("\n" + "=" * 60)
    print("🏁 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
