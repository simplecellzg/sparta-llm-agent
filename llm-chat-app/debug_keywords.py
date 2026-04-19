#!/usr/bin/env python3
"""
调试：查看关键词提取和搜索过程
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'agent-dsmc'))

from error_fixer import SPARTAErrorFixer

fixer = SPARTAErrorFixer(
    sparta_path="/home/simplecellzg/sparta_llm_agent/agent_code/sparta",
    manual_dir="/home/simplecellzg/sparta_llm_agent/agent_code/sparta_manual_md"
)

error_message = "ERROR: Illegal compute grid command (../compute_grid.cpp:156)"

print("=" * 80)
print("🔍 调试关键词提取")
print("=" * 80)

# 测试关键词提取
keywords = fixer._extract_keywords(error_message)
print(f"\n错误消息: {error_message}")
print(f"\n提取的关键词: {keywords}")

# 手动搜索concepts
print("\n" + "=" * 80)
print("📖 手动搜索concepts中包含这些关键词的条目")
print("=" * 80)

from utils import load_json
index = load_json("/home/simplecellzg/sparta_llm_agent/agent_code/sparta_manual_md/index.json")

matches = []
for concept_key, info in index.get("concepts", {}).items():
    title = info.get("title", "")
    for keyword in keywords:
        if keyword.lower() in concept_key.lower() or keyword.lower() in title.lower():
            matches.append({
                "key": concept_key,
                "title": title,
                "line": info["line"],
                "matched_keyword": keyword
            })
            break

print(f"\n找到 {len(matches)} 个匹配:")
for i, match in enumerate(matches[:10], 1):
    print(f"\n{i}. 关键词: '{match['matched_keyword']}'")
    print(f"   概念键: {match['key'][:60]}")
    print(f"   标题: {match['title'][:60]}")
    print(f"   行号: {match['line']}")

# 特别检查compute grid
print("\n" + "=" * 80)
print("🎯 特别检查：是否匹配到 compute_grid_command")
print("=" * 80)

compute_grid_key = None
for concept_key, info in index.get("concepts", {}).items():
    if "compute_grid" in concept_key or "compute grid" in concept_key:
        compute_grid_key = concept_key
        print(f"\n✅ 找到compute_grid_command:")
        print(f"   键: {concept_key}")
        print(f"   标题: {info['title']}")
        print(f"   行号: {info['line']}")

        # 检查是否会被关键词匹配到
        matched = False
        matched_by = []
        for keyword in keywords:
            if keyword.lower() in concept_key.lower() or keyword.lower() in info['title'].lower():
                matched = True
                matched_by.append(keyword)

        if matched:
            print(f"\n   ✓ 会被匹配到！匹配的关键词: {matched_by}")
        else:
            print(f"\n   ✗ 不会被匹配到！")
            print(f"   原因：关键词 {keywords} 都不在:")
            print(f"     - concept_key: {concept_key}")
            print(f"     - title: {info['title']}")
        break

if not compute_grid_key:
    print("\n❌ 未找到compute_grid_command相关条目")
