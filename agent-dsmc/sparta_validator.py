"""
SPARTA Input File Validator

Validates SPARTA DSMC input files against manual rules.
"""

import re
from typing import Dict, List

class SpartaValidator:
    """Validate SPARTA input files"""

    # Required commands for valid SPARTA input
    REQUIRED_COMMANDS = ['dimension', 'create_box', 'create_grid', 'species']

    # Recommended command order
    COMMAND_ORDER = [
        'dimension',
        'create_box',
        'boundary',
        'create_grid',
        'balance_grid',
        'species',
        'mixture',
        'global',
        'collide',
        'create_particles',
        'fix',
        'compute',
        'stats',
        'dump',
        'run'
    ]

    def validate(self, content: str) -> Dict:
        """
        Validate SPARTA input content

        Args:
            content: SPARTA input file content as string

        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "suggestions": List[str]
            }
        """
        errors = []
        warnings = []
        suggestions = []

        # Check required commands
        for cmd in self.REQUIRED_COMMANDS:
            if not self._has_command(content, cmd):
                errors.append(f"Missing required command: {cmd}")

        # Check command order
        order_issues = self._check_order(content)
        warnings.extend(order_issues)

        # Validate parameters
        param_errors = self._validate_parameters(content)
        errors.extend(param_errors)

        # Generate suggestions if errors found
        if errors:
            suggestions = self._generate_suggestions(errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions
        }

    def _has_command(self, content: str, command: str) -> bool:
        """Check if content contains a command"""
        pattern = rf'^\s*{command}\s+'
        return bool(re.search(pattern, content, re.MULTILINE))

    def _check_order(self, content: str) -> List[str]:
        """Check if commands are in recommended order"""
        warnings = []

        # Extract commands with line numbers
        commands_found = []
        for i, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for cmd in self.COMMAND_ORDER:
                if line.startswith(cmd):
                    commands_found.append((cmd, i))
                    break

        # Check order
        last_index = -1
        for cmd, line_num in commands_found:
            if cmd in self.COMMAND_ORDER:
                cmd_index = self.COMMAND_ORDER.index(cmd)
                if cmd_index < last_index:
                    warnings.append(
                        f"Command '{cmd}' at line {line_num} appears out of "
                        f"recommended order (should come before earlier commands)"
                    )
                last_index = cmd_index

        return warnings

    def _validate_parameters(self, content: str) -> List[str]:
        """Validate parameter values"""
        errors = []

        # Check dimension (must be 2 or 3)
        dim_match = re.search(r'^\s*dimension\s+(\d+)', content, re.MULTILINE)
        if dim_match:
            dim = int(dim_match.group(1))
            if dim not in [2, 3]:
                errors.append(f"Invalid dimension: {dim} (must be 2 or 3)")

        # Check temperature in global command
        temp_match = re.search(r'global\s+.*temp\s+([\d.e+-]+)', content)
        if temp_match:
            temp = float(temp_match.group(1))
            if temp <= 0:
                errors.append(f"Invalid temperature: {temp}K (must be > 0)")

        # Check grid dimensions
        grid_match = re.search(r'create_grid\s+(\d+)\s+(\d+)\s+(\d+)', content)
        if grid_match:
            nx, ny, nz = map(int, grid_match.groups())
            if nx < 10 or ny < 10 or nz < 10:
                errors.append(
                    f"Grid dimensions too small: {nx}x{ny}x{nz} "
                    f"(each dimension should be >= 10)"
                )

        return errors

    def _generate_suggestions(self, errors: List[str]) -> List[str]:
        """Generate helpful suggestions based on errors"""
        suggestions = []

        for error in errors:
            if 'Missing required command: dimension' in error:
                suggestions.append("Add 'dimension 3' or 'dimension 2' at the beginning of the file")
            elif 'Missing required command: create_box' in error:
                suggestions.append("Add 'create_box xlo xhi ylo yhi zlo zhi' to define simulation domain")
            elif 'Missing required command: create_grid' in error:
                suggestions.append("Add 'create_grid nx ny nz' to define grid cells")
            elif 'Missing required command: species' in error:
                suggestions.append("Add 'species air.species N2 O2' or similar to define gas species")

        return suggestions
