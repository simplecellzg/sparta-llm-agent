#!/usr/bin/env python3
"""
测试修复后的手册搜索功能 - 添加对concepts的搜索
"""
import sys
from pathlib import Path
import json

# 添加agent-dsmc到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'agent-dsmc'))

# 模拟修复后的搜索逻辑
manual_dir = Path("/home/simplecellzg/sparta_llm_agent/agent_code/sparta_manual_md")
index_file = manual_dir / "index.json"

with open(index_file, 'r') as f:
    index = json.load(f)

# 测试搜索关键词
test_keywords = ["grid", "compute", "illegal"]

print("=" * 80)
print("🧪 测试修复后的手册搜索（包含concepts部分）")
print("=" * 80)

results = []

for keyword in test_keywords:
    print(f"\n🔍 搜索关键词: '{keyword}'")

    # 搜索commands
    print("\n  在commands部分搜索:")
    for cmd, info in index.get("commands", {}).items():
        if keyword.lower() in cmd.lower():
            print(f"    ✓ 找到: {cmd} (line {info['line']})")
            results.append({"source": f"commands:{cmd}", "line": info["line"]})

    # 搜索concepts (修复：之前没有搜索这里！)
    print("\n  在concepts部分搜索:")
    for concept_key, info in index.get("concepts", {}).items():
        title = info.get("title", "")
        if keyword.lower() in concept_key.lower() or keyword.lower() in title.lower():
            print(f"    ✓ 找到: {title[:50]}... (line {info['line']})")
            results.append({"source": f"concepts:{title[:30]}", "line": info["line"]})

# 特别测试compute grid
print("\n" + "=" * 80)
print("📖 特别测试：搜索 'compute grid' 命令")
print("=" * 80)

compute_grid_found = False
for concept_key, info in index.get("concepts", {}).items():
    if "compute_grid" in concept_key.lower() or "compute grid" in concept_key.lower():
        print(f"\n✅ 在concepts中找到: {info['title']}")
        print(f"   文件: {info['file']}")
        print(f"   行号: {info['line']}")

        # 读取实际内容验证
        manual_file = manual_dir / info['file']
        with open(manual_file, 'r') as f:
            lines = f.readlines()

        start = max(0, info['line'] - 1)
        end = min(len(lines), info['line'] + 20)
        content = ''.join(lines[start:end])

        print(f"\n   内容预览:")
        print("   " + "-" * 60)
        for line in content.split('\n')[:10]:
            print(f"   {line}")
        print("   " + "-" * 60)

        compute_grid_found = True
        break

if not compute_grid_found:
    print("\n❌ 未找到compute grid命令文档")

print("\n" + "=" * 80)
print(f"✅ 测试完成，共找到 {len(results)} 个结果")
print("=" * 80)
