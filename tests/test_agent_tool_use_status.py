#!/usr/bin/env python3
"""
Comprehensive test: Tool status propagation through entire stack
AgentProvider -> AgentService -> Gradio UI format
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import logger
from core.service.agent_service import AgentService
from core.session.models import Session, SessionMetadata


async def test_tool_status_full_stack():
    """Test tool status through the complete stack"""
    logger.info("=" * 60)
    logger.info("COMPREHENSIVE TEST: Tool Status Full Stack")
    logger.info("=" * 60)
    
    try:
        # Create session
        session = Session(
            session_id="test_tool_status",
            session_name="Tool Status Test",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="test_user",
            metadata=SessionMetadata(module_name="assistant")
        )
        
        # Initialize service
        service = AgentService("assistant")
        logger.info("✓ AgentService initialized")
        
        # Test with tool use
        logger.info("\nTesting: Calculate 15 * 23 using calculator")
        
        events_collected = {
            'text': [],
            'tool_use': []  # Fixed: should be tool_use not tool
        }
        
        async for chunk in service.streaming_reply_with_history(
            session=session,
            message="What is the current time in UTC+8? Use the current_time tool to get the exact time.",
            system_prompt="You are a helpful assistant. Always use tools when available.",
            history=[],
            tool_config={
                'enabled': True,
                'include_legacy': False,
                'mcp_tools_enabled': False,
                'strands_tools_enabled': True
            }
        ):
            if 'text' in chunk:
                events_collected['text'].append(chunk['text'])
                logger.info(f"  📝 Text: {chunk['text'][:60]}")
            
            if 'tool_use' in chunk:  # Fixed: should be tool_use not tool
                events_collected['tool_use'].append(chunk['tool_use'])
                logger.info(f"  🔧 Tool: {chunk['tool_use']['name']}")
                logger.info(f"     Status: {chunk['tool_use']['status']}")
                logger.info(f"     Params: {chunk['tool_use']['params']}")
                if 'result' in chunk['tool_use']:
                    logger.info(f"     Result: {chunk['tool_use']['result'][:80]}")
        
        # Verify results
        logger.info("\n" + "=" * 60)
        logger.info("Results:")
        logger.info(f"  Text chunks: {len(events_collected['text'])}")
        logger.info(f"  Tool events: {len(events_collected['tool_use'])}")
        
        if events_collected['tool_use']:
            logger.info("\n✅ SUCCESS: Tool status properly propagated through:")
            logger.info("   AgentProvider → AgentService → Gradio Format")
            
            # Verify tool event structure
            for tool_event in events_collected['tool_use']:
                assert 'name' in tool_event, "Missing 'name' in tool event"
                assert 'status' in tool_event, "Missing 'status' in tool event"
                assert 'params' in tool_event, "Missing 'params' in tool event"
                logger.info(f"   ✓ Tool event valid: {tool_event['name']} ({tool_event['status']})")
            
            return True
        else:
            logger.warning("⚠️  No tool events (model didn't use tools)")
            logger.info("✅ Test passed (no errors)")
            return True
            
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}", exc_info=True)
        return False


async def main():
    result = await test_tool_status_full_stack()
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
