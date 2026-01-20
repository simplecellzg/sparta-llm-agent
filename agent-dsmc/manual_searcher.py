"""
SPARTA Manual Searcher using LightRAG
Performs targeted searches in SPARTA manual to find syntax and examples.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
import time
import requests
import json
import re

# Add lightrag agent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent-lightrag-app"))

try:
    from lightrag_agent import parse_lightrag_response, LIGHTRAG_URL
except ImportError:
    print("Warning: lightrag_agent not found, manual search will not work")
    parse_lightrag_response = None
    LIGHTRAG_URL = None


def query_lightrag_with_params(query: str, mode: str = "mix", topk: int = 40, chunk_topk: int = 20) -> Optional[str]:
    """
    Query LightRAG API with custom topk parameters

    NOTE: This function is necessary because the existing query_lightrag() in
    lightrag_agent.py (lines 20-58) does NOT accept topk/chunk_topk parameters.
    It hardcodes them as top_k=40, chunk_top_k=20 (lines 37-38).

    For topk optimization testing, we need dynamic control over these parameters,
    hence this separate implementation that mirrors query_lightrag() but adds
    topk/chunk_topk parameters.

    Args:
        query: User query
        mode: Retrieval mode (mix/local/global)
        topk: Top-k entities/relationships to retrieve
        chunk_topk: Top-k document chunks to retrieve

    Returns:
        API response as JSON string
    """
    if LIGHTRAG_URL is None:
        return None

    payload = {
        "query": query,
        "mode": mode,
        "only_need_context": True,
        "only_need_prompt": False,
        "response_type": "Multiple Paragraphs",
        "top_k": topk,
        "chunk_top_k": chunk_topk,
        "max_entity_tokens": 6000,
        "max_relation_tokens": 8000,
        "max_total_tokens": 30000,
        "hl_keywords": [],
        "ll_keywords": [],
        "conversation_history": [],
        "history_turns": 3
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(LIGHTRAG_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"LightRAG query failed: {e}")
        return None


class SPARTAManualSearcher:
    """Search SPARTA manual using LightRAG"""

    # Default topk parameters (will be optimized through testing)
    DEFAULT_TOPK = 25
    DEFAULT_CHUNK_TOPK = 12

    # Named constants for magic numbers
    SPEED_OF_SOUND_M_S = 340  # m/s at sea level, 15°C
    MAX_CONTENT_LENGTH = 2000  # Characters for LLM prompt

    # Required SPARTA commands
    REQUIRED_COMMANDS = [
        "dimension",
        "create_box",
        "create_grid",
        "species",
        "collide",
        "run"
    ]

    # Command patterns that need parameters
    COMMAND_PATTERNS = {
        "species": r"species\s+\S+\s+\S+",  # species file gas1 [gas2 ...]
        "collide": r"collide\s+\w+\s+\S+\s+\S+",  # collide vss air air.vss
        "create_grid": r"create_grid\s+\d+\s+\d+\s+\d+",  # create_grid nx ny nz
    }

    def __init__(self, topk: int = None, chunk_topk: int = None):
        """
        Initialize manual searcher

        Args:
            topk: Top-k entities/relationships to retrieve
            chunk_topk: Top-k document chunks to retrieve
        """
        if topk is not None and topk <= 0:
            raise ValueError(f"topk must be positive, got {topk}")
        if chunk_topk is not None and chunk_topk <= 0:
            raise ValueError(f"chunk_topk must be positive, got {chunk_topk}")
        self.topk = topk or self.DEFAULT_TOPK
        self.chunk_topk = chunk_topk or self.DEFAULT_CHUNK_TOPK

    def search(self, query: str, mode: str = "local") -> Optional[str]:
        """
        Search SPARTA manual with LightRAG

        Args:
            query: Search query
            mode: Search mode (local/global/hybrid/mix)

        Returns:
            Search result as string, or None if failed
        """
        try:
            # Query LightRAG with custom topk parameters
            result = query_lightrag_with_params(
                query=query,
                mode=mode,
                topk=self.topk,
                chunk_topk=self.chunk_topk
            )
            return result
        except Exception as e:
            print(f"Manual search failed: {e}")
            return None

    def search_geometry(self, geometry: str) -> Optional[str]:
        """Search for geometry setup commands"""
        query = f"create_box create_grid {geometry} surface geometry setup commands"
        return self.search(query, mode="local")

    def search_collision(self, collision_model: str, gas: str) -> Optional[str]:
        """Search for collision model and species setup"""
        query = f"{collision_model} collision model {gas} species mixture setup commands"
        return self.search(query, mode="local")

    def search_boundary(self, velocity: float) -> Optional[str]:
        """Search for boundary conditions"""
        query = f"boundary conditions freestream inlet outlet wall {velocity}m/s setup"
        return self.search(query, mode="local")

    def search_output(self) -> Optional[str]:
        """Search for output and stats commands"""
        query = "dump stats compute output commands frequency timestep"
        return self.search(query, mode="local")

    def search_example(self, geometry: str, flow_type: str = "supersonic") -> Optional[str]:
        """Search for complete example cases"""
        query = f"{geometry} {flow_type} flow SPARTA input file example complete setup"
        return self.search(query, mode="hybrid")

    def comprehensive_search(self, parameters: Dict) -> Dict[str, str]:
        """
        Perform all 5 pre-generation manual searches

        Args:
            parameters: User parameters dict with keys:
                - geometry: str
                - gas: str
                - collision_model: str (VSS/VHS/HS)
                - velocity: float
                - temperature: float
                - pressure: float

        Returns:
            Dict with keys: example, geometry, collision, boundary, output
        """
        geometry = parameters.get("geometry", "cylinder")
        gas = parameters.get("gas", "N2")
        collision_model = parameters.get("collision_model", "VSS")
        velocity = parameters.get("velocity", 1000)

        # Determine flow type from velocity
        flow_type = "supersonic" if velocity > self.SPEED_OF_SOUND_M_S else "subsonic"

        results = {}

        # Search 1: Example case (hybrid mode for broader context)
        results["example"] = self.search_example(geometry, flow_type)

        # Search 2: Geometry setup (local mode for precise syntax)
        results["geometry"] = self.search_geometry(geometry)

        # Search 3: Collision & species (local mode)
        results["collision"] = self.search_collision(collision_model, gas)

        # Search 4: Boundary conditions (local mode)
        results["boundary"] = self.search_boundary(velocity)

        # Search 5: Output commands (local mode)
        results["output"] = self.search_output()

        return results

    def _parse_document_chunks(self, response_text: str) -> List[str]:
        """Extract document chunk contents from LightRAG response"""
        chunks_match = re.search(
            r'Document Chunks.*?:.*?```json\s*(.*?)\s*```',
            response_text,
            re.DOTALL
        )
        if not chunks_match:
            return []

        contents = []
        for line in chunks_match.group(1).strip().split('\n'):
            try:
                chunk = json.loads(line.strip())
                contents.append(chunk.get('content', ''))
            except json.JSONDecodeError:
                continue
        return contents

    def extract_syntax(self, search_result: str) -> Dict:
        """
        Extract SPARTA command syntax from search result

        Args:
            search_result: Raw LightRAG search result

        Returns:
            Dict with extracted syntax patterns
        """
        if not search_result:
            return {"commands": []}

        if search_result is None:
            return {"commands": []}

        commands = []

        try:
            # Parse LightRAG JSON response
            data = json.loads(search_result)
            response_text = data.get('response', search_result)
        except json.JSONDecodeError:
            response_text = search_result

        # Extract document chunks content using helper method
        chunk_contents = self._parse_document_chunks(response_text)

        # Get full text to search (response + chunk contents)
        full_text = response_text + '\n' + '\n'.join(chunk_contents)

        # Extract commands from full text
        # Look for common SPARTA commands
        sparta_commands = [
            "dimension", "boundary", "create_box", "create_grid",
            "species", "mixture", "collide", "global", "timestep",
            "fix", "compute", "stats", "dump", "run",
            "surf_collide", "surf_react", "read_surf", "balance_grid",
            "collide_modify", "react"
        ]

        lines = full_text.split('\n')
        for line in lines:
            line_stripped = line.strip()
            for cmd in sparta_commands:
                if line_stripped.startswith(cmd):
                    commands.append(line_stripped)
                    break

        return {"commands": commands}

    def format_for_llm(self, search_results: Dict[str, str]) -> str:
        """
        Format search results for inclusion in LLM prompt

        Args:
            search_results: Dict from comprehensive_search()

        Returns:
            Formatted string for LLM prompt
        """
        sections = []

        section_titles = {
            "example": "参考案例 (Example Cases)",
            "geometry": "几何设置语法 (Geometry Setup Syntax)",
            "collision": "碰撞与物种设置 (Collision & Species Setup)",
            "boundary": "边界条件 (Boundary Conditions)",
            "output": "输出设置 (Output Configuration)"
        }

        for key, title in section_titles.items():
            if key in search_results and search_results[key]:
                # Extract just the relevant parts (not full JSON)
                content = self._extract_content(search_results[key])
                if content:
                    sections.append(f"### {title}\n\n{content}")

        return "\n\n".join(sections)

    def _extract_content(self, search_result: str, max_length: int = None) -> str:
        """Extract document chunks content from LightRAG result"""
        if max_length is None:
            max_length = self.MAX_CONTENT_LENGTH

        try:
            data = json.loads(search_result)
            response_text = data.get('response', '')

            # Use helper method to extract chunks
            chunk_contents = self._parse_document_chunks(response_text)

            if chunk_contents:
                full_content = '\n\n'.join(chunk_contents)
                # Truncate if too long
                if len(full_content) > max_length:
                    full_content = full_content[:max_length] + "\n\n[...更多内容已省略]"
                return full_content
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: return truncated raw result
        if len(search_result) > max_length:
            return search_result[:max_length] + "\n\n[...更多内容已省略]"
        return search_result

    def detect_syntax_errors(self, input_file: str) -> List[str]:
        """
        Detect syntax errors in SPARTA input file

        Args:
            input_file: SPARTA input file content

        Returns:
            List of error descriptions
        """
        errors = []
        lines = input_file.split('\n')
        found_commands = set()

        # Check each line
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Skip comments and empty lines
            if not line_stripped or line_stripped.startswith('#'):
                continue

            parts = line_stripped.split()
            if not parts:
                continue

            cmd = parts[0]
            found_commands.add(cmd)

            # Check command patterns
            if cmd in self.COMMAND_PATTERNS:
                pattern = self.COMMAND_PATTERNS[cmd]
                if not re.match(pattern, line_stripped):
                    errors.append(f"Line {i}: Incomplete {cmd} command - {line_stripped}")

        # Check for required commands
        for req_cmd in self.REQUIRED_COMMANDS:
            if req_cmd not in found_commands:
                errors.append(f"Missing required command: {req_cmd}")

        return errors

    def search_fix(self, error: str, input_file: str) -> Dict:
        """
        Search manual for fix to specific syntax error

        Args:
            error: Error description
            input_file: Current input file content

        Returns:
            Dict with search_result and suggested_fix
        """
        # Build search query from error
        if "create_grid" in error.lower():
            query = "create_grid command syntax parameters nx ny nz examples"
        elif "collide" in error.lower():
            query = "collide command vss vhs collision model syntax parameters"
        elif "species" in error.lower():
            query = "species command syntax mixture gas species file"
        elif "boundary" in error.lower():
            query = "boundary command periodic outflow syntax"
        else:
            # Generic command syntax search
            query = f"{error} SPARTA command syntax"

        # Search manual
        search_result = self.search(query, mode="local")

        # Extract suggested fix from search result
        suggested_fix = self._extract_fix_from_search(error, search_result)

        return {
            "error": error,
            "search_result": search_result or "",
            "suggested_fix": suggested_fix
        }

    def _extract_fix_from_search(self, error: str, search_result: str) -> str:
        """Extract specific fix suggestion from search result"""
        if not search_result:
            return ""

        # Extract commands from search result
        syntax = self.extract_syntax(search_result)
        commands = syntax.get("commands", [])

        # Find relevant command
        if "create_grid" in error.lower():
            grid_cmds = [c for c in commands if c.startswith("create_grid")]
            if grid_cmds:
                return grid_cmds[0]
            return "create_grid 20 10 10"

        elif "collide" in error.lower():
            collide_cmds = [c for c in commands if c.startswith("collide")]
            if collide_cmds:
                return collide_cmds[0]
            return "collide vss air air.vss"

        elif "species" in error.lower():
            species_cmds = [c for c in commands if c.startswith("species")]
            if species_cmds:
                return species_cmds[0]
            return "species air.species N2 O2"

        # Default: return first relevant command if found
        if commands:
            return commands[0]

        return ""

    def apply_fix(self, input_file: str, fix_info: Dict) -> str:
        """
        Apply suggested fix to input file

        Args:
            input_file: Current input file
            fix_info: Dict with error, suggested_fix, and optional insert_after

        Returns:
            Fixed input file
        """
        suggested_fix = fix_info.get("suggested_fix", "")
        if not suggested_fix:
            return input_file

        lines = input_file.split('\n')
        insert_after = fix_info.get("insert_after")

        if insert_after:
            # Insert after specific command
            for i, line in enumerate(lines):
                if insert_after in line:
                    lines.insert(i + 1, suggested_fix)
                    break
        else:
            # Append before run command or at end
            run_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith("run"):
                    run_idx = i
                    break

            if run_idx:
                lines.insert(run_idx, suggested_fix)
            else:
                lines.append(suggested_fix)

        return '\n'.join(lines)

    def fix_all_errors(self, input_file: str, max_iterations: int = 3) -> tuple:
        """
        Fix all detected syntax errors

        Args:
            input_file: Input file with errors
            max_iterations: Maximum fix attempts

        Returns:
            (fixed_input_file, fix_log)
        """
        current_file = input_file
        fix_log = []

        for iteration in range(max_iterations):
            errors = self.detect_syntax_errors(current_file)

            if not errors:
                break

            # Fix first error
            error = errors[0]
            fix_info = self.search_fix(error, current_file)

            if fix_info.get("suggested_fix"):
                # Determine where to insert
                if "create_grid" in error.lower():
                    fix_info["insert_after"] = "create_box"
                elif "collide" in error.lower():
                    fix_info["insert_after"] = "species"

                current_file = self.apply_fix(current_file, fix_info)

                fix_log.append({
                    "iteration": iteration + 1,
                    "error": error,
                    "fix": fix_info["suggested_fix"]
                })

        return current_file, fix_log


def search_with_params(query: str, topk: int, chunk_topk: int, mode: str = "local") -> Optional[str]:
    """
    Standalone function for testing different topk parameters

    Args:
        query: Search query
        topk: Top-k parameter
        chunk_topk: Chunk top-k parameter
        mode: Search mode

    Returns:
        Search result string or None
    """
    searcher = SPARTAManualSearcher(topk=topk, chunk_topk=chunk_topk)
    return searcher.search(query, mode=mode)
