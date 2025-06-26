import sys
import os
import time
from typing import Any, Dict, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from genai.tools.legacy.search_tools import search_wikipedia

def test_search_wikipedia_func(query: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """Test Wikipedia search with specified language"""
    # Access the original function directly from the module
    # Use type: ignore to suppress Pylance warnings about the decorated function
    try:
        # Call with positional arguments to avoid parameter name issues
        result = search_wikipedia(query, 3, language) # type: ignore
    except TypeError as e:
        print(f"Error calling search_wikipedia: {e}")
        return None
        
    print(f"Result for query '{query}' (language: {language}):")
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"URL: {result.get('url', 'N/A')}")
    print(f"Results: {result.get('results', [])}")
    print(f"Content: {result.get('content', 'No content')[:200]}...")
    print("\n")
    return result

def test_caching() -> None:
    """Test that caching works correctly"""
    query = "Python programming language"
    
    # First call should not be cached
    start_time = time.time()
    result1 = search_wikipedia(query)  # type: ignore
    first_call_time = time.time() - start_time
    print(f"First call took {first_call_time:.4f} seconds")
    print(f"Cached: {result1.get('cached', False)}")
    
    # Second call should be cached and faster
    start_time = time.time()
    result2 = search_wikipedia(query)  # type: ignore
    second_call_time = time.time() - start_time
    print(f"Second call took {second_call_time:.4f} seconds")
    print(f"Cached: {result2.get('cached', False)}")
    
    if second_call_time > 0:
        print(f"Speed improvement: {first_call_time / second_call_time:.2f}x faster")
    print("\n")

def test_multilingual() -> None:
    """Test Wikipedia search in multiple languages"""
    print("=== TESTING MULTILINGUAL SEARCH ===")
    
    # Test English
    test_search_wikipedia_func("Machine Learning", "en")
    
    # Test Chinese
    test_search_wikipedia_func("机器学习", "zh")
    
    # Test Spanish
    test_search_wikipedia_func("Aprendizaje automático", "es")
    
    # Test French
    test_search_wikipedia_func("Apprentissage automatique", "fr")
    
    # Test German
    test_search_wikipedia_func("Maschinelles Lernen", "de")
    
    print("=== MULTILINGUAL TESTING COMPLETE ===\n")

if __name__ == "__main__":
    # Test with a few different queries in English
    print("=== TESTING ENGLISH QUERIES ===")
    english_queries = [
        "Python programming language",
        "Artificial Intelligence", 
        "Machine Learning",
        "Natural Language Processing"
    ]
    
    for query in english_queries:
        result = test_search_wikipedia_func(query)
        if result is None:
            print(f"Failed to test query: {query}")
            break
    
    # Test multilingual search
    test_multilingual()
    
    # Test caching
    test_caching()
