import os
import sys
import unittest
import asyncio
from PIL import Image
import tempfile

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.api_providers.google_gemini import GeminiProvider
from llm.api_providers import LLMParameters, LLMMessage, LLMResponse


class TestGeminiProviderReal(unittest.TestCase):
    """Test cases for the updated GeminiProvider with the new Google Gen AI SDK"""

    def setUp(self):
        """Set up test environment"""
        # Create LLM parameters
        self.llm_params = LLMParameters(
            max_tokens=100,
            temperature=0.7,
            top_p=0.95,
            top_k=40
        )
        
        # Create test messages
        self.test_message = LLMMessage(role="user", content="Hello, how are you?")
        self.system_prompt = "You are a helpful assistant that provides concise answers."
        
        # Create the provider - this will initialize a client using the environment variables
        self.provider = GeminiProvider('gemini-2.0-flash', self.llm_params)
        
        # Skip tests if no API key is available
        try:
            self.provider._initialize_client()
        except Exception as e:
            self.skipTest(f"Skipping test due to initialization error: {str(e)}")

    def test_generate_content(self):
        """Test content generation"""
        try:
            # Generate content
            result = asyncio.run(self.provider.generate_content([self.test_message]))
            
            # Verify the result
            self.assertIsInstance(result, LLMResponse)
            self.assertIsNotNone(result.content)
            self.assertIsInstance(result.content, str)
            self.assertTrue(len(result.content) > 0)
            
            # Verify metadata
            self.assertIsNotNone(result.metadata)
            self.assertEqual(result.metadata['model'], 'gemini-2.0-flash')
            self.assertIn('usage', result.metadata)
            self.assertIn('prompt_tokens', result.metadata['usage'])
            self.assertIn('completion_tokens', result.metadata['usage'])
            self.assertIn('total_tokens', result.metadata['usage'])
            
            print(f"\nGenerated content: {result.content[:100]}...")
            print(f"Tokens used: {result.metadata['usage']['total_tokens']}")
            
        except Exception as e:
            self.fail(f"Content generation failed: {str(e)}")

    def test_generate_content_with_system_prompt(self):
        """Test content generation with system prompt"""
        try:
            # Generate content with system prompt
            result = asyncio.run(self.provider.generate_content(
                [self.test_message], 
                system_prompt=self.system_prompt
            ))
            
            # Verify the result
            self.assertIsInstance(result, LLMResponse)
            self.assertIsNotNone(result.content)
            self.assertIsInstance(result.content, str)
            self.assertTrue(len(result.content) > 0)
            
            print(f"\nGenerated content with system prompt: {result.content[:100]}...")
            
        except Exception as e:
            self.fail(f"Content generation with system prompt failed: {str(e)}")

    def test_generate_stream(self):
        """Test streaming content generation"""
        try:
            # Create async test
            async def run_test():
                chunks = []
                content_chunks = []
                metadata_chunks = []
                
                async for chunk in self.provider.generate_stream([self.test_message]):
                    chunks.append(chunk)
                    if 'content' in chunk:
                        content_chunks.append(chunk['content']['text'])
                    elif 'metadata' in chunk:
                        metadata_chunks.append(chunk['metadata'])
                
                return chunks, content_chunks, metadata_chunks
            
            # Run the async test
            chunks, content_chunks, metadata_chunks = asyncio.run(run_test())
            
            # Verify the results
            self.assertTrue(len(chunks) > 0)
            self.assertTrue(len(content_chunks) > 0)
            self.assertTrue(len(metadata_chunks) > 0)
            
            # Verify that we have content
            full_content = ''.join(content_chunks)
            self.assertTrue(len(full_content) > 0)
            
            # Verify metadata
            self.assertEqual(metadata_chunks[0]['model'], 'gemini-2.0-flash')
            self.assertIn('usage', metadata_chunks[0])
            
            print(f"\nStreamed content: {full_content[:100]}...")
            print(f"Tokens used: {metadata_chunks[0]['usage']['total_tokens']}")
            
        except Exception as e:
            self.fail(f"Stream generation failed: {str(e)}")

    def test_generate_stream_with_system_prompt(self):
        """Test streaming content generation with system prompt"""
        try:
            # Create async test
            async def run_test():
                chunks = []
                content_chunks = []
                
                async for chunk in self.provider.generate_stream(
                    [self.test_message],
                    system_prompt=self.system_prompt
                ):
                    chunks.append(chunk)
                    if 'content' in chunk:
                        content_chunks.append(chunk['content']['text'])
                
                return chunks, content_chunks
            
            # Run the async test
            chunks, content_chunks = asyncio.run(run_test())
            
            # Verify the results
            self.assertTrue(len(chunks) > 0)
            self.assertTrue(len(content_chunks) > 0)
            
            # Verify that we have content
            full_content = ''.join(content_chunks)
            self.assertTrue(len(full_content) > 0)
            
            print(f"\nStreamed content with system prompt: {full_content[:100]}...")
            
        except Exception as e:
            self.fail(f"Stream generation with system prompt failed: {str(e)}")

    def test_multi_turn_generate(self):
        """Test multi-turn chat generation"""
        try:
            # Create history
            history = [
                LLMMessage(role="user", content="What is the capital of France?"),
                LLMMessage(role="assistant", content="The capital of France is Paris.")
            ]
            
            # Create current message
            current_message = LLMMessage(role="user", content="What is its population?")
            
            # Create async test
            async def run_test():
                chunks = []
                content_chunks = []
                
                async for chunk in self.provider.multi_turn_generate(
                    current_message,
                    history=history
                ):
                    chunks.append(chunk)
                    if 'content' in chunk:
                        content_chunks.append(chunk['content']['text'])
                
                return chunks, content_chunks
            
            # Run the async test
            chunks, content_chunks = asyncio.run(run_test())
            
            # Verify the results
            self.assertTrue(len(chunks) > 0)
            self.assertTrue(len(content_chunks) > 0)
            
            # Verify that we have content
            full_content = ''.join(content_chunks)
            self.assertTrue(len(full_content) > 0)
            
            print(f"\nMulti-turn chat response: {full_content[:100]}...")
            
        except Exception as e:
            self.fail(f"Multi-turn chat generation failed: {str(e)}")

    def test_multi_turn_generate_with_system_prompt(self):
        """Test multi-turn chat generation with system prompt"""
        try:
            # Create history
            history = [
                LLMMessage(role="user", content="What is the capital of France?"),
                LLMMessage(role="assistant", content="The capital of France is Paris.")
            ]
            
            # Create current message
            current_message = LLMMessage(role="user", content="What is its population?")
            
            # Create async test
            async def run_test():
                chunks = []
                content_chunks = []
                
                async for chunk in self.provider.multi_turn_generate(
                    current_message,
                    history=history,
                    system_prompt=self.system_prompt
                ):
                    chunks.append(chunk)
                    if 'content' in chunk:
                        content_chunks.append(chunk['content']['text'])
                
                return chunks, content_chunks
            
            # Run the async test
            chunks, content_chunks = asyncio.run(run_test())
            
            # Verify the results
            self.assertTrue(len(chunks) > 0)
            self.assertTrue(len(content_chunks) > 0)
            
            # Verify that we have content
            full_content = ''.join(content_chunks)
            self.assertTrue(len(full_content) > 0)
            
            print(f"\nMulti-turn chat response with system prompt: {full_content[:100]}...")
            
        except Exception as e:
            self.fail(f"Multi-turn chat generation with system prompt failed: {str(e)}")

    def test_message_with_context(self):
        """Test message with context information"""
        try:
            # Create message with context
            message_with_context = LLMMessage(
                role="user", 
                content="What should I wear?",
                context={
                    "location": "Paris",
                    "temperature": "15°C",
                    "weather_condition": "Rainy"
                }
            )
            
            # Generate content
            result = asyncio.run(self.provider.generate_content([message_with_context]))
            
            # Verify the result
            self.assertIsInstance(result, LLMResponse)
            self.assertIsNotNone(result.content)
            self.assertIsInstance(result.content, str)
            self.assertTrue(len(result.content) > 0)
            
            print(f"\nGenerated content with context: {result.content[:100]}...")
            
        except Exception as e:
            self.fail(f"Content generation with context failed: {str(e)}")


if __name__ == '__main__':
    unittest.main()
