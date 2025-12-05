#!/usr/bin/env python3
"""
Debug test to see raw Strands events
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import logger
from strands import Agent
from strands.models import BedrockModel
from utils.aws import get_aws_session
from core.config import env_config


async def test_raw_strands_events():
    """See what events Strands actually returns"""
    logger.info("=" * 60)
    logger.info("DEBUG: Raw Strands Events")
    logger.info("=" * 60)
    
    try:
        # Create model
        session = get_aws_session(region_name=env_config.bedrock_config['region_name'])
        model = BedrockModel(
            model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            boto_session=session
        )
        
        # Load tools
        from genai.tools.provider import tool_provider
        base_tools, _ = tool_provider.get_tools_and_contexts({
            'include_legacy': False,
            'mcp_tools_enabled': False,
            'strands_tools_enabled': True
        })
        
        # Create agent
        agent = Agent(
            tools=base_tools,
            system_prompt="You MUST use the calculator tool for any math.",
            model=model,
            messages=[],
            callback_handler=None
        )
        
        logger.info("Asking: What is 7 * 8? Use calculator.")
        
        event_count = 0
        async for event in agent.stream_async("What is 7 * 8? Use the calculator tool."):
            event_count += 1
            logger.info(f"\n--- Event {event_count} ---")
            logger.info(f"Keys: {list(event.keys())}")
            logger.info(f"Content: {event}")
            
            if event_count >= 20:
                logger.info("\n(Stopping after 20 events)")
                break
        
        return True
            
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False


async def main():
    result = await test_raw_strands_events()
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
