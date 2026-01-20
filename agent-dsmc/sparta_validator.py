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

    def extract_parameters(self, content: str) -> Dict:
        """
        Extract parameters from SPARTA input file

        Returns:
            {
                'dimension': str,
                'geometry': str,
                'grid_size': List[int],
                'temperature': float,
                'pressure': float,
                'velocity': float,
                'gas': str,
                'timestep': float,
                'num_steps': int,
                'collision_model': str
            }
        """
        params = {}

        # Dimension
        dim_match = re.search(r'^\s*dimension\s+(\d+)', content, re.MULTILINE)
        if dim_match:
            dim = dim_match.group(1)
            params['dimension'] = f"{dim}d"

        # Grid size
        grid_match = re.search(r'create_grid\s+(\d+)\s+(\d+)\s+(\d+)', content)
        if grid_match:
            params['grid_size'] = [int(grid_match.group(i)) for i in range(1, 4)]

        # Temperature from global command
        temp_match = re.search(r'global\s+.*temp\s+([\d.e+-]+)', content)
        if temp_match:
            params['temperature'] = float(temp_match.group(1))

        # Pressure - estimate from number density if available
        # (SPARTA uses fnum, need to reverse engineer)
        fnum_match = re.search(r'global\s+.*fnum\s+([\d.e+-]+)', content)
        if fnum_match:
            # Rough estimate: P ~ n * kB * T
            # This is simplified - real extraction would be more complex
            pass

        # Velocity from stream command
        vel_match = re.search(r'global\s+.*vstream\s+([\d.e+-]+)', content)
        if vel_match:
            params['velocity'] = abs(float(vel_match.group(1)))
        else:
            params['velocity'] = 0

        # Gas species
        species_match = re.search(r'species\s+([\w.]+)', content)
        if species_match:
            species_file = species_match.group(1)
            if 'N2' in species_file or 'n2' in species_file.lower():
                params['gas'] = 'N2'
            elif 'air' in species_file.lower():
                params['gas'] = 'Air'
            elif 'ar' in species_file.lower():
                params['gas'] = 'Ar'
            elif 'co2' in species_file.lower():
                params['gas'] = 'CO2'
            else:
                params['gas'] = 'Unknown'

        # Timestep
        timestep_match = re.search(r'timestep\s+([\d.e+-]+)', content)
        if timestep_match:
            params['timestep'] = float(timestep_match.group(1))

        # Steps from run command
        run_match = re.search(r'^\s*run\s+(\d+)', content, re.MULTILINE)
        if run_match:
            params['num_steps'] = int(run_match.group(1))

        # Collision model
        collide_match = re.search(r'collide\s+(\w+)', content)
        if collide_match:
            model = collide_match.group(1).upper()
            params['collision_model'] = model if model in ['VSS', 'VHS', 'HS'] else 'VSS'

        # Geometry - infer from create_box
        box_match = re.search(r'create_box\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)', content)
        if box_match:
            # Simple heuristic: if box is roughly cubic, it's a box, otherwise cylinder
            # This is simplified - real detection would check surf commands
            params['geometry'] = 'box'

        return params

