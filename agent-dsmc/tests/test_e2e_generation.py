"""
End-to-end test for SPARTA input generation with manual search
"""

import pytest
from dsmc_agent import DSMCAgent


class TestE2EGeneration:
    """End-to-end generation tests"""

    @pytest.fixture
    def agent(self):
        """Create agent instance"""
        return DSMCAgent()

    def test_complete_generation_pipeline(self, agent):
        """Test complete generation from parameters to validated input file"""
        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1500,
            "geometry": "cylinder",
            "gas": "N2",
            "collision_model": "VSS"
        }

        # Run generation
        events = list(agent.generate_input_file(parameters))

        # Verify pipeline stages
        status_messages = [e.get("message", "") for e in events if e.get("type") == "status"]

        # Should have manual search stage
        assert any("手册搜索" in msg for msg in status_messages)

        # Should have syntax validation stage
        assert any("验证语法" in msg or "语法" in msg for msg in status_messages)

        # Should complete successfully
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) > 0

        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        # Verify input file quality
        assert len(input_file) > 200  # Should be substantial

        # Check required commands
        required_cmds = ["dimension", "create_box", "create_grid", "species", "run"]
        for cmd in required_cmds:
            assert cmd in input_file, f"Missing command: {cmd}"

        # Verify timing info
        timing = result.get("timing", {})
        assert "total_time" in timing
        assert timing["total_time"] > 0

    @pytest.mark.parametrize("scenario", [
        {
            "name": "subsonic_cylinder",
            "params": {
                "temperature": 300,
                "pressure": 101325,
                "velocity": 200,
                "geometry": "cylinder",
                "gas": "Air"
            }
        },
        {
            "name": "supersonic_sphere",
            "params": {
                "temperature": 400,
                "pressure": 50000,
                "velocity": 2000,
                "geometry": "sphere",
                "gas": "Ar"
            }
        },
        {
            "name": "hypersonic_flatplate",
            "params": {
                "temperature": 300,
                "pressure": 10000,
                "velocity": 3000,
                "geometry": "flat_plate",
                "gas": "N2"
            }
        }
    ])
    def test_various_scenarios(self, agent, scenario):
        """Test generation for various physical scenarios"""
        params = scenario["params"]

        events = list(agent.generate_input_file(params))
        done_events = [e for e in events if e.get("type") == "done"]

        assert len(done_events) > 0, f"Generation failed for {scenario['name']}"

        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        # All scenarios should produce valid files
        assert len(input_file) > 0
        assert "dimension" in input_file

        # Save for manual inspection
        import os
        os.makedirs("test_outputs", exist_ok=True)
        with open(f"test_outputs/{scenario['name']}.sparta", 'w') as f:
            f.write(input_file)

    def test_search_timing_acceptable(self, agent):
        """Test that manual search doesn't slow generation too much"""
        import time

        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1000,
            "geometry": "cylinder",
            "gas": "N2"
        }

        start = time.time()
        events = list(agent.generate_input_file(parameters))
        total_time = time.time() - start

        # Complete generation should take < 60 seconds
        assert total_time < 60.0, f"Generation too slow: {total_time:.2f}s"

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) > 0

    def test_error_fix_iteration(self, agent):
        """Test that syntax errors are fixed automatically"""
        # Create parameters that might cause syntax issues
        parameters = {
            "temperature": 300,
            "pressure": 101325,
            "velocity": 1000,
            "geometry": "cylinder",
            "gas": "N2"
        }

        events = list(agent.generate_input_file(parameters))

        # Check if any fixes were applied
        fix_events = [e for e in events if "修复" in e.get("message", "")]

        # Final file should be syntax-clean
        done_events = [e for e in events if e.get("type") == "done"]
        result = done_events[0].get("result", {})
        input_file = result.get("input_file", "")

        from manual_searcher import SPARTAManualSearcher
        searcher = SPARTAManualSearcher()
        errors = searcher.detect_syntax_errors(input_file)

        # Should have 0-1 minor errors at most
        assert len(errors) <= 1, f"Still has errors after fix: {errors}"
