"""
Test integrated SPARTA input generation with manual search
"""

import pytest
from dsmc_agent import DSMCAgent


class TestIntegratedGeneration:
    """Test full generation pipeline with manual search"""

    def setup_method(self):
        """Setup agent"""
        self.agent = DSMCAgent()

    def test_generation_includes_manual_search(self):
        """Test that generation performs manual searches"""
        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1000,
            "geometry": "cylinder",
            "gas": "N2",
            "collision_model": "VSS"
        }

        # Generate with manual search
        events = list(self.agent.generate_input_file(parameters))

        # Should have status events for manual search
        status_messages = [e.get("message", "") for e in events if e.get("type") == "status"]

        assert any("手册搜索" in msg or "manual search" in msg.lower() for msg in status_messages)

        # Final result should have input file
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) > 0

        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        assert len(input_file) > 0
        assert "dimension" in input_file
        assert "create_grid" in input_file

    def test_generated_file_passes_syntax_check(self):
        """Test that generated file has no syntax errors"""
        parameters = {
            "temperature": 400,
            "pressure": 50000,
            "velocity": 2000,
            "geometry": "sphere",
            "gas": "Ar",
            "collision_model": "VHS"
        }

        events = list(self.agent.generate_input_file(parameters))
        done_events = [e for e in events if e.get("type") == "done"]

        assert len(done_events) > 0

        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        # Check syntax with manual searcher
        from manual_searcher import SPARTAManualSearcher
        searcher = SPARTAManualSearcher()

        errors = searcher.detect_syntax_errors(input_file)

        # Should have minimal or no errors
        assert len(errors) <= 2, f"Too many syntax errors: {errors}"

    def test_manual_search_results_in_prompt(self):
        """Test that manual search results are included in LLM prompt"""
        # This tests the internal prompt building
        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1000,
            "geometry": "cylinder",
            "gas": "N2"
        }

        # First do the manual search
        manual_search_results = self.agent.manual_searcher.comprehensive_search(parameters)

        # Build prompt with manual search
        prompt = self.agent._build_input_generation_prompt_with_manual_search(
            parameters, manual_search_results
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 1000  # Should be substantial

        # Should include search result sections
        assert "参考案例" in prompt or "Example" in prompt
        assert "几何设置" in prompt or "Geometry" in prompt
        assert "碰撞" in prompt or "Collision" in prompt

    @pytest.mark.parametrize("geometry", ["cylinder", "sphere", "flat_plate"])
    def test_different_geometries(self, geometry):
        """Test generation works for all geometry types"""
        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1000,
            "geometry": geometry,
            "gas": "N2"
        }

        events = list(self.agent.generate_input_file(parameters))
        done_events = [e for e in events if e.get("type") == "done"]

        assert len(done_events) > 0

        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        assert len(input_file) > 0
        # Different geometries might have different commands
        if geometry in ["cylinder", "sphere"]:
            # Likely to have surf commands
            assert "create_box" in input_file or "read_surf" in input_file
