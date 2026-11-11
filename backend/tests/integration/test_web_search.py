"""search_internet finds results for the kind of query users ask (real call).

Regression: the DuckDuckGo scraper found nothing for most queries from this server, Chinese ones especially, and
the model kept retrying with new wording for minutes.
"""
import pytest

from backend.genai.tools.legacy.search_tools import google_cache, search_internet

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("query", ["墨将烈风2 手柄 对比", "Amazon Bedrock pricing"])
def test_search_returns_results(query):
    google_cache.clear()
    result = search_internet(query)
    assert "error" not in result and len(result["results"]) >= 3, result
