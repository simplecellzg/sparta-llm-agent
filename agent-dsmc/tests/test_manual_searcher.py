"""
Test SPARTA Manual Searcher comprehensive search functionality
"""

import pytest
from manual_searcher import SPARTAManualSearcher


class TestSPARTAManualSearcher:
    """Test comprehensive manual search functionality"""

    def setup_method(self):
        """Setup test searcher with medium config"""
        self.searcher = SPARTAManualSearcher(topk=25, chunk_topk=12)

    def test_comprehensive_search_returns_all_results(self):
        """Test that comprehensive search returns all 5 search results"""
        parameters = {
            "geometry": "cylinder",
            "gas": "N2",
            "collision_model": "VSS",
            "velocity": 1000,
            "temperature": 300,
            "pressure": 101325
        }

        results = self.searcher.comprehensive_search(parameters)

        # Should return dict with 5 keys
        assert isinstance(results, dict)
        assert "example" in results
        assert "geometry" in results
        assert "collision" in results
        assert "boundary" in results
        assert "output" in results

        # All results should be non-empty strings
        for key, value in results.items():
            assert value is not None
            assert len(value) > 0
            assert isinstance(value, str)

    def test_comprehensive_search_timing(self):
        """Test that all 5 searches complete in reasonable time"""
        import time

        parameters = {
            "geometry": "sphere",
            "gas": "Ar",
            "collision_model": "VHS",
            "velocity": 2000,
            "temperature": 400,
            "pressure": 50000
        }

        start = time.time()
        results = self.searcher.comprehensive_search(parameters)
        elapsed = time.time() - start

        # Should complete in < 15 seconds (5 searches * ~3s each)
        assert elapsed < 15.0, f"Search too slow: {elapsed:.2f}s"
        assert len(results) == 5

    def test_extract_syntax_from_search(self):
        """Test extracting specific SPARTA syntax from search results"""
        # Search for collision syntax
        result = self.searcher.search_collision("VSS", "N2")

        # Should be able to extract syntax patterns
        syntax = self.searcher.extract_syntax(result)

        assert isinstance(syntax, dict)
        assert "commands" in syntax
        assert len(syntax["commands"]) > 0

        # Should have collision-related commands
        commands = syntax["commands"]
        assert any("collide" in cmd.lower() for cmd in commands)

    def test_format_for_llm_prompt(self):
        """Test formatting search results for LLM prompt"""
        results = {
            "example": "Example case with run command...",
            "geometry": "create_box 0 10 0 5...",
            "collision": "collide vss air.vss...",
            "boundary": "boundary p p p...",
            "output": "dump 1 grid..."
        }

        formatted = self.searcher.format_for_llm(results)

        assert isinstance(formatted, str)
        assert "Example" in formatted or "example" in formatted
        assert "geometry" in formatted or "Geometry" in formatted
        assert len(formatted) > 100  # Should be substantial

    def test_extract_syntax_with_none(self):
        """Test extract_syntax handles None input"""
        syntax = self.searcher.extract_syntax(None)
        assert syntax == {"commands": []}

    def test_extract_syntax_with_malformed_json(self):
        """Test extract_syntax handles malformed JSON gracefully"""
        syntax = self.searcher.extract_syntax("not valid json {{{")
        assert isinstance(syntax, dict)
        assert isinstance(syntax["commands"], list)
