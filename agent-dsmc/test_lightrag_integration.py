#!/usr/bin/env python3
"""
测试LightRAG集成到错误修复流程
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from error_fixer import SPARTAErrorFixer


def test_lightrag_search():
    """测试LightRAG搜索功能"""
    print("=" * 80)
    print("🧪 测试LightRAG集成到错误修复流程")
    print("=" * 80)

    fixer = SPARTAErrorFixer()

    # 测试用例1: compute grid group ID错误（真实案例）
    print("\n\n【测试1】compute grid group ID不存在错误")
    print("-" * 80)

    error_info_1 = {
        "has_error": True,
        "error_type": "unknown_error",  # 模拟未知错误类型
        "error_message": "ERROR: Compute grid group ID does not exist",
        "error_context": "compute 1 grid air n nrho u v w temp press",
        "severity": "high"
    }

    print(f"错误消息: {error_info_1['error_message']}")
    print(f"错误上下文: {error_info_1['error_context']}")

    result_1 = fixer.search_solution(error_info_1)

    print(f"\n✅ 搜索结果:")
    print(f"  找到解决方案: {result_1['found']}")
    print(f"  来源数量: {len(result_1['sources'])}")

    if result_1['sources']:
        print(f"\n📚 搜索来源详情:")
        for i, source in enumerate(result_1['sources'][:3], 1):
            print(f"\n  [{i}] 来源: {source['source']}")
            print(f"      相关度: {source.get('relevance', 0):.2f}")
            print(f"      内容预览: {source['content'][:200]}...")

    # 测试用例2: fix样式错误
    print("\n\n【测试2】fix样式错误")
    print("-" * 80)

    error_info_2 = {
        "has_error": True,
        "error_type": "unrecognized_fix_style",
        "error_message": "ERROR: Unrecognized fix style: grid",
        "error_context": "fix avg grid all 10 100 1000 c_1[*]",
        "severity": "high"
    }

    print(f"错误消息: {error_info_2['error_message']}")
    print(f"错误上下文: {error_info_2['error_context']}")

    result_2 = fixer.search_solution(error_info_2)

    print(f"\n✅ 搜索结果:")
    print(f"  找到解决方案: {result_2['found']}")
    print(f"  来源数量: {len(result_2['sources'])}")

    if result_2['sources']:
        print(f"\n📚 搜索来源详情:")
        for i, source in enumerate(result_2['sources'][:3], 1):
            print(f"\n  [{i}] 来源: {source['source']}")
            print(f"      相关度: {source.get('relevance', 0):.2f}")
            print(f"      内容: {source['content'][:300]}")

    # 测试用例3: mixture未定义错误
    print("\n\n【测试3】mixture未定义错误")
    print("-" * 80)

    error_info_3 = {
        "has_error": True,
        "error_type": "mixture_not_defined",
        "error_message": "ERROR: Mixture air is not defined",
        "error_context": "fix in emit/face air xlo twopass",
        "severity": "high"
    }

    print(f"错误消息: {error_info_3['error_message']}")
    print(f"错误上下文: {error_info_3['error_context']}")

    result_3 = fixer.search_solution(error_info_3)

    print(f"\n✅ 搜索结果:")
    print(f"  找到解决方案: {result_3['found']}")
    print(f"  来源数量: {len(result_3['sources'])}")

    if result_3['sources']:
        print(f"\n📚 搜索来源详情:")
        for i, source in enumerate(result_3['sources'][:3], 1):
            print(f"\n  [{i}] 来源: {source['source']}")
            print(f"      相关度: {source.get('relevance', 0):.2f}")
            print(f"      内容预览: {source['content'][:200]}...")

    print("\n\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


def test_error_parsing():
    """测试错误解析功能"""
    print("\n\n" + "=" * 80)
    print("🧪 测试错误解析功能")
    print("=" * 80)

    fixer = SPARTAErrorFixer()

    # 真实的SPARTA日志
    test_log = """SPARTA (24 Sep 2025)
Running on 20 MPI task(s)
Created orthogonal box = (-0.05 -0.05 -0.05) to (0.15 0.05 0.05)
Created 250000 child grid cells
  816 triangles
WARNING: Created unexpected # of particles: 4049695 versus 4049701
Created 4049695 particles
  CPU time = 0.0667342 secs
ERROR: Compute grid group ID does not exist (../compute_grid.cpp:51)
"""

    print("\n真实SPARTA日志:")
    print("-" * 80)
    print(test_log)
    print("-" * 80)

    error_info = fixer.parse_error(test_log)

    print("\n解析结果:")
    print(f"  有错误: {error_info['has_error']}")
    print(f"  错误类型: {error_info['error_type']}")
    print(f"  错误消息: {error_info['error_message']}")
    print(f"  严重程度: {error_info['severity']}")

    if error_info['has_error']:
        print(f"\n✅ 成功解析错误")
    else:
        print(f"\n❌ 未能解析错误")


if __name__ == "__main__":
    # 测试错误解析
    test_error_parsing()

    # 测试LightRAG搜索
    test_lightrag_search()
