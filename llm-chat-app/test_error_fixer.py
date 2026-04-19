#!/usr/bin/env python3
"""
测试错误修复系统的手册搜索功能
"""
import sys
from pathlib import Path

# 添加agent-dsmc到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'agent-dsmc'))

from error_fixer import SPARTAErrorFixer

# 创建错误修复器
fixer = SPARTAErrorFixer(
    sparta_path="/home/simplecellzg/sparta_llm_agent/agent_code/sparta",
    manual_dir="/home/simplecellzg/sparta_llm_agent/agent_code/sparta_manual_md"
)

# 模拟错误信息
error_info = {
    "error_type": "illegal_command",
    "error_message": "ERROR: Illegal compute grid command (../compute_grid.cpp:156)",
    "error_detail": "compute grid command",
    "error_context": "compute            1 grid all air n nrho massrho u v w temp press"
}

print("=" * 80)
print("🧪 测试错误修复系统的搜索功能")
print("=" * 80)

# 测试搜索
print("\n📚 搜索解决方案...")
result = fixer.search_solution(error_info)

print(f"\n✅ 搜索成功: {result['found']}")
print(f"📊 找到的来源数量: {len(result['sources'])}")

print("\n📄 搜索结果详情：")
for i, source in enumerate(result['sources'], 1):
    print(f"\n{i}. 来源: {source['source']}")
    print(f"   相关度: {source['relevance']}")
    print(f"   内容预览: {source['content'][:200]}...")

if result.get('suggested_fix'):
    print(f"\n💡 建议修复: {result['suggested_fix']}")
else:
    print("\n⚠️ 没有找到建议的修复方案")

print("\n" + "=" * 80)
