"""
Test search-based syntax fixing for SPARTA input files
"""

import pytest
from manual_searcher import SPARTAManualSearcher


class TestSyntaxFixing:
    """Test manual search-based syntax fixing"""

    def setup_method(self):
        """Setup searcher"""
        self.searcher = SPARTAManualSearcher()

    def test_detect_syntax_errors(self):
        """Test detecting syntax errors in input file"""
        input_file = """
dimension 3
create_box 0 10 0 5 0 5
# Missing create_grid!
species air.species N2 O2
collide vss
run 1000
"""

        errors = self.searcher.detect_syntax_errors(input_file)

        assert isinstance(errors, list)
        assert len(errors) > 0

        # Should detect missing create_grid
        assert any("create_grid" in err.lower() for err in errors)

        # Should detect incomplete collide command
        assert any("collide" in err.lower() for err in errors)

    def test_search_fix_for_error(self):
        """Test searching manual for fix to specific error"""
        error = "Missing create_grid command"
        input_file = """
dimension 3
create_box 0 10 0 5 0 5
"""

        fix_info = self.searcher.search_fix(error, input_file)

        assert isinstance(fix_info, dict)
        assert "search_result" in fix_info
        assert "suggested_fix" in fix_info

        # Search result should contain create_grid syntax
        assert "create_grid" in fix_info["search_result"].lower()

    def test_apply_fix_to_input(self):
        """Test applying suggested fix to input file"""
        input_file = """
dimension 3
create_box 0 10 0 5 0 5
species air.species N2 O2
"""

        fix_info = {
            "error": "Missing create_grid",
            "suggested_fix": "create_grid 20 10 10",
            "insert_after": "create_box"
        }

        fixed = self.searcher.apply_fix(input_file, fix_info)

        assert "create_grid" in fixed
        # Should be inserted after create_box
        lines = fixed.split('\n')
        create_box_idx = next(i for i, line in enumerate(lines) if 'create_box' in line)
        create_grid_idx = next(i for i, line in enumerate(lines) if 'create_grid' in line)
        assert create_grid_idx > create_box_idx

    def test_fix_all_errors(self):
        """Test fixing all detected errors in one pass"""
        input_file = """
dimension 3
create_box 0 10 0 5 0 5
species air.species N2 O2
run 1000
"""

        fixed, fix_log = self.searcher.fix_all_errors(input_file)

        assert isinstance(fixed, str)
        assert isinstance(fix_log, list)

        # Fixed file should have required commands
        assert "create_grid" in fixed
        assert "collide" in fixed or "collision" in fixed.lower()

        # Fix log should record what was changed
        assert len(fix_log) > 0
        for log_entry in fix_log:
            assert "error" in log_entry
            assert "fix" in log_entry
