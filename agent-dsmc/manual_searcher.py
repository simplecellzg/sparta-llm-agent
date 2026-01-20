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
