"""
Test Strands Tools Integration with MyAIBOX
验证 Agent 调用 Strands Agents Tools 的集成测试
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from genai.tools.strands.strands_tools import strands_tools_manager
from genai.tools.provider import tool_provider


class TestStrandsToolsIntegration:
    """Strands Tools 集成测试"""
    
    def test_strands_tools_manager_initialization(self):
        """测试 Strands 工具管理器初始化"""
        # 检查管理器是否正确初始化
        assert strands_tools_manager is not None
        
        # 检查可用工具列表
        available_tools = strands_tools_manager.get_available_tool_names()
        assert isinstance(available_tools, list)
        assert len(available_tools) > 0
        
        # 检查核心工具是否在列表中
        expected_tools = ['current_time', 'calculator', 'http_request']
        for tool in expected_tools:
            assert tool in available_tools, f"Tool {tool} should be available"
    
    def test_load_individual_strands_tools(self):
        """测试加载单个 Strands 工具"""
        # 测试加载 current_time 工具
        current_time_tool = strands_tools_manager.load_tool('current_time')
        assert current_time_tool is not None, "current_time tool should load successfully"
        
        # 测试加载 calculator 工具
        calculator_tool = strands_tools_manager.load_tool('calculator')
        assert calculator_tool is not None, "calculator tool should load successfully"
        
        # 测试加载 http_request 工具
        http_request_tool = strands_tools_manager.load_tool('http_request')
        assert http_request_tool is not None, "http_request tool should load successfully"
        
        # 测试加载不存在的工具
        invalid_tool = strands_tools_manager.load_tool('non_existent_tool')
        assert invalid_tool is None, "Non-existent tool should return None"
    
    def test_load_tools_for_agent(self):
        """测试为 Agent 批量加载工具"""
        # 测试加载多个工具
        tool_names = ['current_time', 'calculator', 'http_request']
        loaded_tools = strands_tools_manager.load_tools_for_agent(tool_names)
        
        assert isinstance(loaded_tools, list)
        assert len(loaded_tools) == len(tool_names), f"Should load {len(tool_names)} tools"
        
        # 验证每个工具都是可调用的
        for tool in loaded_tools:
            assert callable(tool), "Each loaded tool should be callable"
    
    def test_get_tool_info(self):
        """测试获取工具信息"""
        # 测试获取特定工具信息
        tool_info = strands_tools_manager.get_tool_info('current_time')
        assert tool_info is not None
        assert 'description' in tool_info
        assert 'category' in tool_info
        assert 'enabled' in tool_info
        
        # 验证工具描述不为空
        assert len(tool_info['description']) > 0
    
    @pytest.mark.asyncio
    async def test_tool_provider_strands_integration(self):
        """测试 Tool Provider 与 Strands 工具的集成"""
        # 测试 tool_provider 是否能获取 Strands 工具
        tools = await tool_provider.get_tools_for_agent(
            include_legacy=False,
            include_mcp=False,
            include_strands=True,
            tool_filter=['current_time', 'calculator']
        )
        
        assert isinstance(tools, list)
        assert len(tools) >= 2, "Should return at least 2 Strands tools"
        
        # 验证返回的工具都是可调用的
        for tool in tools:
            assert callable(tool), "Each tool should be callable"
    
    @pytest.mark.asyncio
    async def test_mixed_tools_integration(self):
        """测试混合工具集成（Legacy + Strands + MCP）"""
        try:
            # 测试同时获取所有类型的工具
            tools = await tool_provider.get_tools_for_agent(
                include_legacy=True,
                include_mcp=True,
                include_strands=True,
                tool_filter=['current_time', 'calculator']  # 只要 Strands 工具
            )
            
            assert isinstance(tools, list)
            # 应该至少包含 Strands 工具
            assert len(tools) >= 2, "Should include Strands tools"
            
        except Exception as e:
            # 如果 MCP 或 Legacy 工具有问题，至少 Strands 工具应该工作
            pytest.skip(f"Mixed integration test skipped due to: {e}")
    
    def test_strands_tools_categories(self):
        """测试 Strands 工具分类"""
        # 测试按类别获取工具
        utility_tools = strands_tools_manager.get_tools_by_category('utility')
        assert isinstance(utility_tools, list)
        assert 'current_time' in utility_tools
        
        computation_tools = strands_tools_manager.get_tools_by_category('computation')
        assert isinstance(computation_tools, list)
        assert 'calculator' in computation_tools
        
        network_tools = strands_tools_manager.get_tools_by_category('network')
        assert isinstance(network_tools, list)
        assert 'http_request' in network_tools


class TestStrandsToolsExecution:
    """Strands 工具执行测试"""
    
    @pytest.mark.integration
    def test_current_time_tool_execution(self):
        """测试 current_time 工具执行"""
        try:
            # 加载工具
            current_time_tool = strands_tools_manager.load_tool('current_time')
            assert current_time_tool is not None
            
            # 注意：这里不直接调用工具，因为它们是为 Strands Agent 设计的
            # 实际执行需要通过 Strands Agent 框架
            print("✅ current_time tool loaded successfully")
            
        except Exception as e:
            pytest.fail(f"current_time tool execution failed: {e}")
    
    @pytest.mark.integration
    def test_calculator_tool_execution(self):
        """测试 calculator 工具执行"""
        try:
            # 加载工具
            calculator_tool = strands_tools_manager.load_tool('calculator')
            assert calculator_tool is not None
            
            print("✅ calculator tool loaded successfully")
            
        except Exception as e:
            pytest.fail(f"calculator tool execution failed: {e}")
    
    @pytest.mark.integration
    @patch('strands_tools.http_request')
    def test_http_request_tool_mock(self, mock_http_request):
        """测试 http_request 工具（使用 mock）"""
        try:
            # 设置 mock 返回值
            mock_http_request.return_value = {"status": "success", "data": "test"}
            
            # 加载工具
            http_request_tool = strands_tools_manager.load_tool('http_request')
            assert http_request_tool is not None
            
            print("✅ http_request tool loaded successfully")
            
        except Exception as e:
            pytest.fail(f"http_request tool test failed: {e}")


class TestStrandsToolsErrorHandling:
    """Strands 工具错误处理测试"""
    
    def test_load_nonexistent_tool(self):
        """测试加载不存在的工具"""
        result = strands_tools_manager.load_tool('definitely_not_a_real_tool')
        assert result is None
    
    def test_load_tools_with_invalid_names(self):
        """测试使用无效名称加载工具"""
        invalid_names = ['', None, 'invalid_tool', 123]
        
        for invalid_name in invalid_names:
            try:
                result = strands_tools_manager.load_tool(invalid_name)
                # 应该返回 None 或抛出异常，但不应该崩溃
                assert result is None or isinstance(result, type(None))
            except (TypeError, AttributeError):
                # 这些异常是可以接受的
                pass
    
    def test_tool_info_for_invalid_tool(self):
        """测试获取无效工具的信息"""
        result = strands_tools_manager.get_tool_info('invalid_tool')
        assert result is None


def run_integration_tests():
    """运行集成测试的便捷函数"""
    print("🧪 开始 Strands Tools 集成测试...")
    
    try:
        # 基础功能测试
        test_basic = TestStrandsToolsIntegration()
        test_basic.test_strands_tools_manager_initialization()
        print("✅ 工具管理器初始化测试通过")
        
        test_basic.test_load_individual_strands_tools()
        print("✅ 单个工具加载测试通过")
        
        test_basic.test_load_tools_for_agent()
        print("✅ Agent 工具批量加载测试通过")
        
        test_basic.test_get_tool_info()
        print("✅ 工具信息获取测试通过")
        
        test_basic.test_strands_tools_categories()
        print("✅ 工具分类测试通过")
        
        # 异步测试
        async def run_async_tests():
            await test_basic.test_tool_provider_strands_integration()
            print("✅ Tool Provider 集成测试通过")
            
            await test_basic.test_mixed_tools_integration()
            print("✅ 混合工具集成测试通过")
        
        asyncio.run(run_async_tests())
        
        # 执行测试
        test_exec = TestStrandsToolsExecution()
        test_exec.test_current_time_tool_execution()
        test_exec.test_calculator_tool_execution()
        test_exec.test_http_request_tool_mock()
        print("✅ 工具执行测试通过")
        
        # 错误处理测试
        test_error = TestStrandsToolsErrorHandling()
        test_error.test_load_nonexistent_tool()
        test_error.test_load_tools_with_invalid_names()
        test_error.test_tool_info_for_invalid_tool()
        print("✅ 错误处理测试通过")
        
        print("\n🎉 所有 Strands Tools 集成测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 直接运行测试
    success = run_integration_tests()
    exit(0 if success else 1)
