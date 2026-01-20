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
        flow_type = "supersonic" if velocity > 340 else "subsonic"

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

        import json
        import re

        commands = []

        try:
            # Parse LightRAG JSON response
            data = json.loads(search_result)
            response_text = data.get('response', search_result)
        except:
            response_text = search_result

        # Extract document chunks content
        chunks_match = re.search(
            r'Document Chunks.*?:.*?```json\s*(.*?)\s*```',
            response_text,
            re.DOTALL
        )

        # Get full text to search (response + chunk contents)
        full_text = response_text
        if chunks_match:
            chunks_text = chunks_match.group(1)
            # Parse each line as JSON and extract content
            for line in chunks_text.strip().split('\n'):
                try:
                    chunk = json.loads(line.strip())
                    full_text += '\n' + chunk.get('content', '')
                except:
                    pass

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

    def _extract_content(self, search_result: str, max_length: int = 2000) -> str:
        """Extract document chunks content from LightRAG result"""
        import json
        import re

        try:
            data = json.loads(search_result)
            response_text = data.get('response', '')

            # Extract document chunks section
            chunks_match = re.search(
                r'Document Chunks.*?:.*?```json\s*(.*?)\s*```',
                response_text,
                re.DOTALL
            )

            if chunks_match:
                chunks_text = chunks_match.group(1)
                # Parse each line as JSON and extract content
                contents = []
                for line in chunks_text.strip().split('\n'):
                    try:
                        chunk = json.loads(line.strip())
                        contents.append(chunk.get('content', ''))
                    except:
                        pass

                full_content = '\n\n'.join(contents)
                # Truncate if too long
                if len(full_content) > max_length:
                    full_content = full_content[:max_length] + "\n\n[...更多内容已省略]"
                return full_content
        except:
            pass

        # Fallback: return truncated raw result
        if len(search_result) > max_length:
            return search_result[:max_length] + "\n\n[...更多内容已省略]"
        return search_result


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
