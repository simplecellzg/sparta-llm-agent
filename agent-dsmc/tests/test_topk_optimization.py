"""
Test optimal topk parameters for LightRAG SPARTA manual search.
Tests different topk combinations and measures quality vs speed.
"""

import pytest
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-lightrag-app"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_agent import query_lightrag
from manual_searcher import search_with_params as real_search_with_params


class TestTopkOptimization:
    """Test different topk parameters for SPARTA manual searches"""

    # Maximum acceptable query time in seconds
    MAX_QUERY_TIME_SECONDS = 5.0

    # Test configurations: (topk, chunk_topk, description)
    TOPK_CONFIGS = [
        (15, 8, "small"),
        (25, 12, "medium"),
        (40, 20, "large"),
        (60, 30, "extra_large")
    ]

    # Test queries representing different search types
    TEST_QUERIES = {
        "geometry": "create_box create_grid cylinder surface geometry setup",
        "collision": "VSS collision model N2 species mixture setup",
        "boundary": "boundary conditions freestream inlet outlet wall",
        "output": "dump stats compute output commands frequency",
        "example": "cylinder flow SPARTA input file example"
    }

    @pytest.mark.parametrize("topk,chunk_topk,config_name", TOPK_CONFIGS)
    def test_topk_speed(self, topk, chunk_topk, config_name) -> None:
        """Test search speed for different topk values"""
        query = self.TEST_QUERIES["geometry"]

        start = time.time()
        result = self._search_with_params(query, topk, chunk_topk)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < self.MAX_QUERY_TIME_SECONDS, f"Search too slow: {elapsed:.2f}s"

        # Should return results
        assert result is not None
        assert len(result) > 0

        print(f"\n{config_name}: topk={topk}, chunk_topk={chunk_topk}, time={elapsed:.3f}s")

    @pytest.mark.parametrize("query_type", ["geometry", "collision", "boundary", "output", "example"])
    def test_search_quality(self, query_type) -> None:
        """Test if searches return relevant content for each query type"""
        query = self.TEST_QUERIES[query_type]

        # Test with medium config (25, 12)
        result = self._search_with_params(query, 25, 12)

        # Parse result and check for relevant keywords
        assert result is not None
        result_lower = result.lower()

        # Each query type should have specific keywords
        if query_type == "geometry":
            assert any(kw in result_lower for kw in ["create_box", "create_grid", "dimension"])
        elif query_type == "collision":
            assert any(kw in result_lower for kw in ["collide", "species", "vss", "vhs"])
        elif query_type == "boundary":
            assert any(kw in result_lower for kw in ["boundary", "inlet", "outlet", "wall"])
        elif query_type == "output":
            assert any(kw in result_lower for kw in ["dump", "stats", "compute"])
        elif query_type == "example":
            assert any(kw in result_lower for kw in ["example", "input", "run"])

    def _search_with_params(self, query: str, topk: int, chunk_topk: int, mode: str = "local"):
        """Helper to search with specific parameters"""
        return real_search_with_params(query, topk, chunk_topk, mode)

    def test_compare_all_configs(self) -> None:
        """Compare all topk configs across all query types and recommend best"""
        results = []

        for topk, chunk_topk, config_name in self.TOPK_CONFIGS:
            total_time = 0
            for query_type, query in self.TEST_QUERIES.items():
                start = time.time()
                result = self._search_with_params(query, topk, chunk_topk)
                elapsed = time.time() - start
                total_time += elapsed

            avg_time = total_time / len(self.TEST_QUERIES)
            results.append({
                "config": config_name,
                "topk": topk,
                "chunk_topk": chunk_topk,
                "avg_time": avg_time
            })

        # Print comparison
        print("\n\n=== TopK Configuration Comparison ===")
        for r in results:
            print(f"{r['config']:12} | topk={r['topk']:2}, chunk_topk={r['chunk_topk']:2} | avg_time={r['avg_time']:.3f}s")

        # Recommend based on balance of speed and completeness
        # Small config should be fastest
        assert results[0]["avg_time"] <= results[-1]["avg_time"]
