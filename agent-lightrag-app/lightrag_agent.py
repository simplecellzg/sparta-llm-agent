#!/usr/bin/env python3
"""
LightRAG Agent - 大语言模型检索增强生成工具（流式输出版本）
支持知识图谱检索和文档片段检索，结合大语言模型生成回答
"""

import re
import json
import requests
import sys
from typing import Dict, List, Any, Optional, Generator

# ==================== 配置 ====================
LIGHTRAG_URL = "http://10.2.1.36:9627/query"
LLM_API_URL = "https://api.mjdjourney.cn"
LLM_API_KEY = "sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d"
LLM_MODEL = "claude-opus-4-5-20251101"
LLM_API_TYPE = "anthropic"  # 'openai' or 'anthropic'

# ==================== LightRAG 查询 ====================
def query_lightrag(query: str, mode: str = "mix") -> Optional[str]:
    """
    查询LightRAG API
    
    Args:
        query: 用户查询
        mode: 检索模式 (mix/local/global)
    
    Returns:
        API响应的JSON字符串
    """
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
        print(f"\n🔍 正在查询LightRAG: {query[:50]}...")
        response = requests.post(LIGHTRAG_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        print("✅ LightRAG查询成功")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ LightRAG查询失败: {e}")
        return None

# ==================== 解析LightRAG响应 ====================
def parse_lightrag_response(lightrag_response: str) -> Dict[str, Any]:
    """
    解析LightRAG响应，提取实体、关系和文档片段
    """
    kg_entities = []
    kg_entities_ref = []
    kg_relationships = []
    kg_relationships_ref = []
    dc_content = []
    dc_content_ref = []
    response_original = lightrag_response
    
    try:
        data = json.loads(lightrag_response)
        response_text = data.get('response', '')
        references = data.get('references', [])
    except json.JSONDecodeError:
        response_text = lightrag_response
        references = []
    
    # 创建引用映射
    ref_map = {}
    for ref in references:
        ref_map[ref.get('reference_id', '')] = ref.get('file_path', '')
    
    # 提取实体
    entities_match = re.search(
        r'Knowledge Graph Data \(Entity\):\s*```json\s*(.*?)\s*```', 
        response_text, re.DOTALL
    )
    if entities_match:
        entities_text = entities_match.group(1)
        idx = 0
        for line in entities_text.strip().split('\n'):
            line = line.strip()
            if line:
                try:
                    entity = json.loads(line)
                    entity_id = f"entity_{idx}"
                    kg_entities.append({
                        'id': entity_id,
                        'entity': entity.get('entity', ''),
                        'type': entity.get('type', ''),
                        'description': entity.get('description', '')
                    })
                    kg_entities_ref.append({
                        'id': entity_id,
                        'file_path': ''
                    })
                    idx += 1
                except json.JSONDecodeError:
                    pass
    
    # 提取关系
    relationships_match = re.search(
        r'Knowledge Graph Data \(Relationship\):\s*```json\s*(.*?)\s*```', 
        response_text, re.DOTALL
    )
    if relationships_match:
        relationships_text = relationships_match.group(1)
        idx = 0
        for line in relationships_text.strip().split('\n'):
            line = line.strip()
            if line:
                try:
                    rel = json.loads(line)
                    rel_id = f"relationship_{idx}"
                    kg_relationships.append({
                        'id': rel_id,
                        'source': rel.get('entity1', ''),
                        'target': rel.get('entity2', ''),
                        'description': rel.get('description', '')
                    })
                    kg_relationships_ref.append({
                        'id': rel_id,
                        'file_path': ''
                    })
                    idx += 1
                except json.JSONDecodeError:
                    pass
    
    # 提取文档片段
    chunks_match = re.search(
        r'Document Chunks.*?:\s*```json\s*(.*?)\s*```', 
        response_text, re.DOTALL
    )
    if chunks_match:
        chunks_text = chunks_match.group(1)
        for line in chunks_text.strip().split('\n'):
            line = line.strip()
            if line:
                try:
                    chunk = json.loads(line)
                    ref_id = chunk.get('reference_id', '')
                    chunk_id = f"source_{ref_id}"
                    dc_content.append({
                        'id': chunk_id,
                        'content': chunk.get('content', '')
                    })
                    file_path = ref_map.get(ref_id, '')
                    dc_content_ref.append({
                        'id': chunk_id,
                        'file_path': file_path
                    })
                except json.JSONDecodeError:
                    pass
    
    return {
        'kg_entities': kg_entities,
        'kg_entities_ref': kg_entities_ref,
        'kg_relationships': kg_relationships,
        'kg_relationships_ref': kg_relationships_ref,
        'dc_content': dc_content,
        'dc_content_ref': dc_content_ref,
        'response_original': response_original
    }

# ==================== 构建Prompt ====================
def build_context_prompt(parsed_data: Dict[str, Any], user_query: str) -> str:
    """
    构建包含上下文的系统提示词
    """
    system_prompt = """---角色---
您是一个严谨的学术助手，负责基于提供的上下文回答用户问题，并确保所有引用符合学术规范。

---目标---
基于数据源生成简洁的响应，并遵循回答规则，同时结合对话历史和当前问题。数据源包含两部分：知识图谱（KG）和文档片段（DC）。请总结数据源中的所有信息，并整合与数据源相关的常识性知识。不要包含数据源未提供的信息。

处理带时间戳的信息时：
- 每条信息（包括关系和内容）均带有"created_at"时间戳，表示获取该知识的时间
- 不要自动偏好最新信息——需根据上下文判断
- 对于时间敏感问题，优先考虑内容中的时间信息，再参考时间戳

---回答规则---
- 格式与长度：多段落，使用Markdown格式
- 语言：与用户问题语言一致（此处为中文）
- 连续性：保持与对话历史的连贯性
- 结构：按主题分节，每节一个核心点，标题需清晰描述内容
- 文中引用：在文中使用上标数字标注引用+原始文件id，如：
  $^{1}_{sources_{0}}$ $^{2}_{sources_{2}}$ $^{3}_{sources_{12}}$
- 不要引用entity和relationship
- 不要合并不同来源或相同来源的引用
- 不许再出现文末引用
- 禁止出现未引用的参考文献
- 未知答案：若数据源无相关信息，直接说明"无法回答"，禁止编造内容

---图片/公式引用---
- 如果上下文中有图片格式，请在回答中合适的位置上以markdown格式输出该图片
- 如果需要用到公式，保持文本中的公式格式并加深字体
- 如果需要输出表格，以markdown格式输出该表格

---注意事项---
1. 严格仅使用数据源提供的信息
2. 时间戳仅辅助判断，非决定性依据
3. 引用序号按首次出现顺序编号
4. 同一文献多次引用使用同一序号
5. 无法回答时明确说明"根据现有资料无法回答"
"""
    
    # 构建数据源上下文
    context_parts = []
    
    # 知识图谱实体
    if parsed_data['kg_entities']:
        context_parts.append("## 知识图谱 - 实体 (KG Entities)")
        for entity in parsed_data['kg_entities']:
            context_parts.append(
                f"- **{entity['entity']}** (类型: {entity['type']}): {entity['description']}"
            )
    
    # 知识图谱关系
    if parsed_data['kg_relationships']:
        context_parts.append("\n## 知识图谱 - 关系 (KG Relationships)")
        for rel in parsed_data['kg_relationships']:
            context_parts.append(
                f"- [{rel['source']}] → [{rel['target']}]: {rel['description']}"
            )
    
    # 文档片段
    if parsed_data['dc_content']:
        context_parts.append("\n## 文档片段 (Document Chunks)")
        for i, (content, ref) in enumerate(zip(parsed_data['dc_content'], parsed_data['dc_content_ref'])):
            file_info = f" (来源: {ref['file_path']})" if ref['file_path'] else ""
            context_parts.append(f"\n### [{content['id']}]{file_info}")
            context_parts.append(content['content'])
    
    context = "\n".join(context_parts)
    
    full_prompt = f"""{system_prompt}

---数据源---
{context}

---用户问题---
{user_query}
"""
    return full_prompt

# ==================== 流式调用LLM ====================
def stream_llm_response(prompt: str, user_query: str) -> Generator[str, None, None]:
    """
    流式调用大语言模型API
    
    Yields:
        每次生成的文本片段
    """
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_query}
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
        "stream": True  # 启用流式输出
    }
    
    try:
        print(f"\n🤖 正在调用LLM ({LLM_MODEL})...\n")
        print("=" * 60)
        print("📝 回答:")
        print("=" * 60 + "\n")
        
        response = requests.post(
            LLM_API_URL, 
            json=payload, 
            headers=headers, 
            timeout=120,
            stream=True  # 启用流式响应
        )
        response.raise_for_status()
        
        # 处理SSE流式响应
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                
                # 跳过空行和注释
                if line.startswith(':'):
                    continue
                
                # 处理data:前缀
                if line.startswith('data: '):
                    data = line[6:]  # 去掉 "data: " 前缀
                    
                    # 检查是否是结束标记
                    if data == '[DONE]':
                        break
                    
                    try:
                        json_data = json.loads(data)
                        
                        # 提取内容增量
                        choices = json_data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                                
                    except json.JSONDecodeError:
                        # 某些行可能不是有效JSON，跳过
                        continue
                        
    except requests.exceptions.RequestException as e:
        yield f"\n\n❌ LLM调用失败: {e}"
    except Exception as e:
        yield f"\n\n❌ 发生错误: {e}"

def call_llm_stream(prompt: str, user_query: str) -> str:
    """
    流式调用LLM并实时打印，返回完整回答
    """
    full_response = []
    
    for chunk in stream_llm_response(prompt, user_query):
        # 实时打印到终端
        print(chunk, end='', flush=True)
        full_response.append(chunk)
    
    print("\n")  # 结束后换行
    return ''.join(full_response)

# ==================== Agent主函数 ====================
def run_agent(query: str, mode: str = "mix") -> Dict[str, Any]:
    """
    运行Agent完整流程
    
    Args:
        query: 用户问题
        mode: LightRAG检索模式
    
    Returns:
        包含完整结果的字典
    """
    result = {
        "query": query,
        "lightrag_response": None,
        "parsed_data": None,
        "llm_answer": None,
        "success": False
    }
    
    # 步骤1: 查询LightRAG
    lightrag_response = query_lightrag(query, mode)
    if not lightrag_response:
        print("⚠️ 无法获取LightRAG响应，将使用空上下文")
        lightrag_response = "{}"
    
    result["lightrag_response"] = lightrag_response
    
    # 步骤2: 解析响应
    print("\n📊 正在解析LightRAG响应...")
    parsed_data = parse_lightrag_response(lightrag_response)
    result["parsed_data"] = parsed_data
    
    # 统计信息
    entity_count = len(parsed_data['kg_entities'])
    rel_count = len(parsed_data['kg_relationships'])
    doc_count = len(parsed_data['dc_content'])
    print(f"   - 实体数量: {entity_count}")
    print(f"   - 关系数量: {rel_count}")
    print(f"   - 文档片段数量: {doc_count}")
    
    # 步骤3: 构建Prompt并流式调用LLM
    prompt = build_context_prompt(parsed_data, query)
    
    # 流式输出回答
    llm_answer = call_llm_stream(prompt, query)
    
    if llm_answer and not llm_answer.startswith("❌"):
        result["llm_answer"] = llm_answer
        result["success"] = True
    
    print("=" * 60)
    
    return result


# ==================== Web接口流式函数（新增）====================
def run_agent_stream(query: str, mode: str = "mix", model: str = None, api_url: str = None, api_key: str = None, api_type: str = None) -> Generator[Dict[str, Any], None, None]:
    """
    流式运行Agent，供Web接口调用

    Args:
        query: 用户问题
        mode: LightRAG检索模式
        model: 可选的自定义模型
        api_url: 可选的自定义API URL
        api_key: 可选的自定义API Key
        api_type: 可选的API类型 ('openai' 或 'anthropic')

    Yields:
        状态更新和内容的字典
    """
    llm_model = model or LLM_MODEL
    llm_api_url = api_url or LLM_API_URL
    llm_api_key = api_key or LLM_API_KEY
    llm_api_type = api_type or LLM_API_TYPE

    # 步骤1: 发送状态 - 开始查询LightRAG
    yield {"type": "status", "stage": "lightrag_start", "message": "正在查询LightRAG知识库..."}

    # 查询LightRAG
    lightrag_response = query_lightrag(query, mode)

    if not lightrag_response:
        yield {"type": "status", "stage": "lightrag_error", "message": "LightRAG查询失败，将使用空上下文继续"}
        lightrag_response = "{}"
    else:
        yield {"type": "status", "stage": "lightrag_done", "message": "LightRAG查询完成"}

    # 步骤2: 解析响应
    yield {"type": "status", "stage": "parsing", "message": "正在解析检索结果..."}

    parsed_data = parse_lightrag_response(lightrag_response)

    entity_count = len(parsed_data['kg_entities'])
    rel_count = len(parsed_data['kg_relationships'])
    doc_count = len(parsed_data['dc_content'])

    yield {
        "type": "status",
        "stage": "parsing_done",
        "message": f"解析完成：{entity_count}个实体，{rel_count}个关系，{doc_count}个文档片段",
        "stats": {
            "entities": entity_count,
            "relationships": rel_count,
            "documents": doc_count
        }
    }

    # 步骤3: 构建Prompt
    yield {"type": "status", "stage": "building_prompt", "message": "正在构建增强提示词..."}

    prompt = build_context_prompt(parsed_data, query)

    # 步骤4: 流式调用LLM
    yield {"type": "status", "stage": "llm_start", "message": f"正在调用 {llm_model} 生成回答..."}

    try:
        # 根据API类型构建请求
        if llm_api_type == 'anthropic':
            # Anthropic API 格式
            endpoint = f"{llm_api_url.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": llm_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            payload = {
                "model": llm_model,
                "max_tokens": 4096,
                "system": prompt,
                "messages": [
                    {"role": "user", "content": query}
                ],
                "stream": True
            }
        else:
            # OpenAI 兼容格式
            endpoint = f"{llm_api_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {llm_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": llm_model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": query}
                ],
                "max_tokens": 4096,
                "temperature": 0.7,
                "stream": True
            }

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=120,
            stream=True
        )
        response.raise_for_status()

        full_response = []

        if llm_api_type == 'anthropic':
            # Anthropic 流式响应格式
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')

                    if line.startswith(':'):
                        continue

                    if line.startswith('data: '):
                        data_str = line[6:]

                        try:
                            event = json.loads(data_str)
                            event_type = event.get('type', '')

                            if event_type == 'content_block_delta':
                                delta = event.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    content = delta.get('text', '')
                                    if content:
                                        full_response.append(content)
                                        yield {"type": "content", "content": content}
                            elif event_type == 'message_stop':
                                break

                        except json.JSONDecodeError:
                            continue
        else:
            # OpenAI 流式响应格式
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')

                    if line.startswith(':'):
                        continue

                    if line.startswith('data: '):
                        data = line[6:]

                        if data == '[DONE]':
                            break

                        try:
                            json_data = json.loads(data)
                            choices = json_data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')

                                if content:
                                    full_response.append(content)
                                    yield {"type": "content", "content": content}

                        except json.JSONDecodeError:
                            continue

        # 完成
        yield {
            "type": "done",
            "message": "回答生成完成",
            "full_response": ''.join(full_response),
            "parsed_data": parsed_data
        }

    except requests.exceptions.RequestException as e:
        yield {"type": "error", "message": f"LLM调用失败: {str(e)}"}
    except Exception as e:
        yield {"type": "error", "message": f"发生错误: {str(e)}"}


# ==================== 主程序 ====================
def main():
    """主程序入口"""
    print("=" * 60)
    print("🚀 LightRAG Agent - 知识图谱增强检索生成系统")
    print("   （流式输出版本）")
    print("=" * 60)
    print(f"📡 LightRAG服务: {LIGHTRAG_URL}")
    print(f"🤖 LLM模型: {LLM_MODEL}")
    print("=" * 60)
    
    while True:
        try:
            # 获取用户输入
            print("\n" + "-" * 40)
            query = input("💬 请输入您的问题 (输入 'quit' 退出): ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 感谢使用，再见！")
                break
            
            if not query:
                print("⚠️ 问题不能为空，请重新输入")
                continue
            
            # 运行Agent（流式输出）
            result = run_agent(query)
            
            if not result["success"]:
                print("❌ 无法生成回答，请检查服务连接或稍后重试。")
            
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，程序退出")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            continue

if __name__ == "__main__":
    main()