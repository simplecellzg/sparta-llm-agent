#!/usr/bin/env python3
"""
测试LightRAG知识库中关于SPARTA的内容
"""
import requests
import json

LIGHTRAG_URL = "http://10.2.1.36:9627/query"

def query_lightrag(query: str, mode: str = "mix"):
    """查询LightRAG"""
    payload = {
        "query": query,
        "mode": mode,
        "only_need_context": True,
        "only_need_prompt": False,
        "response_type": "Multiple Paragraphs",
        "top_k": 40,
        "chunk_top_k": 20,
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
        print(f"\n🔍 查询: {query}")
        print("=" * 80)
        response = requests.post(LIGHTRAG_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()

        # 打印响应信息
        if 'response' in data:
            print("\n📄 响应内容:")
            print(data['response'][:2000])  # 打印前2000字符
            if len(data['response']) > 2000:
                print("\n... (内容已截断) ...")

        if 'references' in data:
            print(f"\n📚 引用文件数量: {len(data['references'])}")
            print("\n引用文件列表:")
            for i, ref in enumerate(data['references'][:10], 1):  # 只显示前10个
                print(f"  {i}. {ref.get('file_path', 'N/A')}")
            if len(data['references']) > 10:
                print(f"  ... 还有 {len(data['references']) - 10} 个文件")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ 查询失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

# 测试查询
print("=" * 80)
print("🧪 LightRAG 知识库测试")
print("=" * 80)

# 查询1: compute grid命令
print("\n\n【测试1】查询SPARTA compute grid命令的语法")
result1 = query_lightrag("SPARTA compute grid命令的正确语法是什么？需要哪些参数？", "mix")

# 查询2: 输入文件基本结构
print("\n\n【测试2】查询SPARTA输入文件的基本结构")
result2 = query_lightrag("SPARTA输入文件的基本结构是什么？必须包含哪些命令？", "mix")

# 查询3: 命令顺序
print("\n\n【测试3】查询SPARTA命令的执行顺序")
result3 = query_lightrag("SPARTA输入文件中命令的正确顺序是什么？", "mix")

# 查询4: 手册或代码示例
print("\n\n【测试4】查询知识库是否包含SPARTA手册或代码示例")
result4 = query_lightrag("SPARTA官方手册文档或代码示例", "mix")

print("\n\n" + "=" * 80)
print("✅ 测试完成")
print("=" * 80)
