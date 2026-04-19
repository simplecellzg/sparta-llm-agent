"""
SPARTA错误修复模块
==================

解析SPARTA错误日志，搜索解决方案，生成修复建议。
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Generator
from utils import call_llm, call_llm_stream, load_json, extract_code_block


class SPARTAErrorFixer:
    """SPARTA错误修复器"""

    # 常见错误模式
    ERROR_PATTERNS = {
        "unrecognized_command": {
            "pattern": r"ERROR: Unrecognized command[:\s]*(\S+)?",
            "description": "无法识别的命令",
            "severity": "high"
        },
        "unrecognized_fix_style": {
            "pattern": r"ERROR: Unrecognized fix style[:\s]*\(([^)]+)\)",
            "description": "无法识别的fix样式",
            "severity": "high"
        },
        "unrecognized_compute_style": {
            "pattern": r"ERROR: Unrecognized compute style[:\s]*\(([^)]+)\)",
            "description": "无法识别的compute样式",
            "severity": "high"
        },
        "invalid_syntax": {
            "pattern": r"ERROR: Invalid[^:]*syntax",
            "description": "语法错误",
            "severity": "high"
        },
        "illegal_command": {
            "pattern": r"ERROR: Illegal[^:]*command[:\s]*(\S+)?",
            "description": "非法命令",
            "severity": "high"
        },
        "file_not_found": {
            "pattern": r"ERROR: Cannot open[^:]*file[:\s]*(\S+)?",
            "description": "文件不存在",
            "severity": "medium"
        },
        "species_not_found": {
            "pattern": r"ERROR: Species[^:]*not found",
            "description": "气体种类未找到",
            "severity": "medium"
        },
        "dimension_mismatch": {
            "pattern": r"ERROR: Dimension.*mismatch",
            "description": "维度不匹配",
            "severity": "high"
        },
        "box_not_defined": {
            "pattern": r"ERROR: (Box|Grid).*not.*defined",
            "description": "模拟区域未定义",
            "severity": "high"
        },
        "missing_argument": {
            "pattern": r"ERROR: (Missing|Insufficient).*argument",
            "description": "缺少参数",
            "severity": "medium"
        },
        "invalid_value": {
            "pattern": r"ERROR: Invalid[^:]*value",
            "description": "无效的参数值",
            "severity": "medium"
        },
        "mixture_not_defined": {
            "pattern": r"ERROR: Mixture.*not.*defined",
            "description": "混合物未定义",
            "severity": "medium"
        },
        "collide_not_defined": {
            "pattern": r"ERROR: Collide.*not.*defined",
            "description": "碰撞模型未定义",
            "severity": "medium"
        }
    }

    # fix命令的正确样式映射
    FIX_STYLE_CORRECTIONS = {
        "grid": "ave/grid",
        "surf": "ave/surf",
        "time": "ave/time",
        "histo": "ave/histo"
    }

    def __init__(self, sparta_path: str = None, manual_dir: str = None):
        """
        初始化错误修复器

        Args:
            sparta_path: SPARTA安装目录
            manual_dir: SPARTA手册目录
        """
        base_dir = Path(__file__).parent.parent

        if sparta_path is None:
            self.sparta_path = base_dir / "sparta"
        else:
            self.sparta_path = Path(sparta_path)

        if manual_dir is None:
            self.manual_dir = base_dir / "sparta_manual_md"
        else:
            self.manual_dir = Path(manual_dir)

        self.sessions_dir = base_dir / "llm-chat-app" / "data" / "dsmc_sessions"

    def parse_error(self, log_content: str, stderr: str = "") -> Dict:
        """
        解析SPARTA错误日志

        Args:
            log_content: 日志文件内容
            stderr: 标准错误输出

        Returns:
            {
                "has_error": bool,
                "error_type": str,
                "error_message": str,
                "error_line": int,
                "error_context": str,
                "severity": str,
                "suggested_fix_type": str
            }
        """
        # 合并日志和stderr
        full_log = f"{log_content}\n{stderr}"

        result = {
            "has_error": False,
            "error_type": "unknown",
            "error_message": "",
            "error_line": None,
            "error_context": "",
            "severity": "unknown",
            "suggested_fix_type": None,
            "raw_error": ""
        }

        # 查找ERROR行
        error_lines = []
        lines = full_log.split('\n')
        for i, line in enumerate(lines):
            if 'ERROR' in line.upper():
                error_lines.append((i, line))

        if not error_lines:
            return result

        result["has_error"] = True
        result["raw_error"] = error_lines[0][1]

        # 匹配错误模式
        for error_type, pattern_info in self.ERROR_PATTERNS.items():
            for line_num, line in error_lines:
                match = re.search(pattern_info["pattern"], line, re.IGNORECASE)
                if match:
                    result["error_type"] = error_type
                    result["error_message"] = line.strip()
                    result["severity"] = pattern_info["severity"]

                    # 提取额外信息
                    if match.groups():
                        result["error_detail"] = match.group(1) if match.group(1) else ""

                    # 获取错误上下文（前后几行）
                    start = max(0, line_num - 3)
                    end = min(len(lines), line_num + 3)
                    result["error_context"] = '\n'.join(lines[start:end])

                    # 尝试找到输入文件中的错误行
                    result["error_line"] = self._find_error_line_in_input(log_content, line)

                    # 确定修复类型
                    result["suggested_fix_type"] = self._suggest_fix_type(error_type, result)

                    return result

        # 如果没有匹配到具体模式，使用通用错误
        result["error_type"] = "unknown_error"
        result["error_message"] = error_lines[0][1].strip()

        return result

    def _find_error_line_in_input(self, log_content: str, error_line: str) -> Optional[int]:
        """在日志中查找对应输入文件的行号"""
        # SPARTA日志通常会在错误前显示正在处理的命令
        lines = log_content.split('\n')
        for i, line in enumerate(lines):
            if 'ERROR' in line.upper():
                # 向前查找最近的命令行
                for j in range(i - 1, max(0, i - 10), -1):
                    # 检查是否是输入命令的回显
                    if lines[j].strip() and not lines[j].startswith(' '):
                        return j + 1
        return None

    def _suggest_fix_type(self, error_type: str, error_info: Dict) -> str:
        """根据错误类型建议修复方法"""
        fix_type_map = {
            "unrecognized_command": "replace_command",
            "unrecognized_fix_style": "fix_style_correction",
            "unrecognized_compute_style": "compute_style_correction",
            "invalid_syntax": "syntax_correction",
            "file_not_found": "file_path_correction",
            "species_not_found": "species_definition",
            "dimension_mismatch": "dimension_correction",
            "box_not_defined": "add_create_box",
            "missing_argument": "add_arguments",
            "invalid_value": "value_correction",
            "mixture_not_defined": "add_mixture",
            "collide_not_defined": "add_collide"
        }
        return fix_type_map.get(error_type, "general_fix")

    def search_solution(self, error_info: Dict) -> Dict:
        """
        搜索解决方案（集成LightRAG智能搜索）

        Args:
            error_info: 错误信息

        Returns:
            {
                "found": bool,
                "sources": [{"source": str, "content": str, "relevance": float}],
                "suggested_fix": str
            }
        """
        result = {
            "found": False,
            "sources": [],
            "suggested_fix": ""
        }

        error_type = error_info.get("error_type", "")
        error_message = error_info.get("error_message", "")

        # 1. 首先检查是否是已知的快速修复
        quick_fix = self._get_quick_fix(error_info)
        if quick_fix:
            result["found"] = True
            result["sources"].append({
                "source": "quick_fix_rules",
                "content": quick_fix["description"],
                "relevance": 1.0
            })
            result["suggested_fix"] = quick_fix["fix"]
            return result

        # 2. 【新增】优先使用LightRAG搜索SPARTA手册（知识图谱+语义检索）
        print("🔍 正在使用LightRAG搜索SPARTA手册知识库...")
        lightrag_results = self._search_lightrag(error_type, error_message)
        result["sources"].extend(lightrag_results)

        # 如果LightRAG返回高质量结果，直接返回
        if lightrag_results and lightrag_results[0].get("relevance", 0) > 0.7:
            result["found"] = True
            print(f"✅ LightRAG找到高质量解决方案（相关度: {lightrag_results[0]['relevance']:.2f}）")
            return result

        # 3. 如果LightRAG结果不足，补充传统手册搜索
        if len(result["sources"]) < 2:
            print("📖 补充传统手册索引搜索...")
            manual_results = self._search_manual(error_type, error_message)
            result["sources"].extend(manual_results)

        # 4. 搜索源代码（用于理解错误来源）
        code_results = self._search_code(error_message)
        result["sources"].extend(code_results)

        # 5. 如果本地搜索结果仍不足，使用网络搜索
        if len(result["sources"]) < 2:
            print("🌐 补充网络搜索...")
            web_results = self._search_web(error_message)
            result["sources"].extend(web_results)

        result["found"] = len(result["sources"]) > 0
        return result

    def _get_quick_fix(self, error_info: Dict) -> Optional[Dict]:
        """获取快速修复方案"""
        error_type = error_info.get("error_type", "")
        error_detail = error_info.get("error_detail", "")

        # fix样式修复
        if error_type == "unrecognized_fix_style":
            # 检查是否是常见的样式错误
            for wrong, correct in self.FIX_STYLE_CORRECTIONS.items():
                if wrong in error_detail.lower():
                    return {
                        "description": f"fix样式 '{wrong}' 应改为 '{correct}'",
                        "fix": f"将 'fix ... {wrong} ...' 替换为 'fix ... {correct} ...'"
                    }

        # 其他快速修复规则可以在这里添加
        return None

    def _search_manual(self, error_type: str, error_message: str) -> List[Dict]:
        """搜索SPARTA手册（改进：使用智能关键词匹配）"""
        results = []

        # 加载手册索引
        index_file = self.manual_dir / "index.json"
        if not index_file.exists():
            return results

        index = load_json(str(index_file))

        # 根据错误类型搜索相关命令
        keywords = self._extract_keywords(error_message)

        # 搜索commands部分（通用命令）
        for cmd, info in index.get("commands", {}).items():
            # 计算匹配分数：匹配的关键词越多，分数越高
            match_score = sum(1 for kw in keywords if kw.lower() in cmd.lower())
            if match_score > 0:
                content = self._read_manual_section(info["file"], info["line"])
                if content:
                    results.append({
                        "source": f"manual:commands:{cmd}",
                        "content": content[:1000],
                        "relevance": 0.6 + match_score * 0.1  # 基础分0.6，每匹配一个词+0.1
                    })

        # 搜索concepts部分（详细命令文档）- 使用改进的匹配算法
        for concept_key, info in index.get("concepts", {}).items():
            title = info.get("title", "")
            search_text = f"{concept_key} {title}".lower()

            # 计算匹配分数
            match_score = sum(1 for kw in keywords if kw.lower() in search_text)

            # 额外奖励：如果匹配了组合关键词（如compute_grid）
            combined_keywords = ["_".join(keywords[i:i+2]) for i in range(len(keywords)-1)]
            for combined in combined_keywords:
                if combined.lower() in search_text:
                    match_score += 2  # 组合匹配额外+2分

            if match_score > 0:
                content = self._read_manual_section(info["file"], info["line"])
                if content:
                    results.append({
                        "source": f"manual:concepts:{title[:40]}",
                        "content": content[:1500],  # concepts内容更详细
                        "relevance": 0.8 + match_score * 0.1  # 基础分0.8，每分+0.1
                    })

        # 按相关度排序，返回最相关的5个
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:5]

    def _search_code(self, error_message: str) -> List[Dict]:
        """搜索SPARTA源代码"""
        results = []
        src_dir = self.sparta_path / "src"

        if not src_dir.exists():
            return results

        # 从错误消息中提取关键词
        keywords = self._extract_keywords(error_message)

        # 在源代码中grep
        import subprocess
        for keyword in keywords[:3]:  # 限制搜索数量
            try:
                cmd = ["grep", "-rn", "-l", keyword, str(src_dir)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and result.stdout:
                    files = result.stdout.strip().split('\n')[:2]  # 最多2个文件
                    for f in files:
                        if f.endswith('.cpp') or f.endswith('.h'):
                            # 读取相关代码片段
                            code_snippet = self._read_code_context(f, keyword)
                            if code_snippet:
                                results.append({
                                    "source": f"code:{Path(f).name}",
                                    "content": code_snippet,
                                    "relevance": 0.6
                                })
            except:
                continue

        return results[:2]

    def _search_lightrag(self, error_type: str, error_message: str) -> List[Dict]:
        """
        使用LightRAG搜索SPARTA手册（知识图谱增强的语义检索）

        Args:
            error_type: 错误类型
            error_message: 错误消息

        Returns:
            搜索结果列表，包含知识图谱实体、关系和文档片段
        """
        results = []

        try:
            import requests

            # LightRAG API配置
            lightrag_url = "http://10.2.1.36:9627/query"

            # 构建查询：结合错误类型和错误消息
            query_parts = []
            if error_type and error_type != "unknown_error":
                # 将错误类型转换为可读的查询
                error_type_readable = error_type.replace("_", " ")
                query_parts.append(error_type_readable)

            # 从错误消息中提取关键词
            keywords = self._extract_keywords(error_message)
            query_parts.extend(keywords[:3])  # 最多3个关键词

            query = " ".join(query_parts)

            # 调用LightRAG API
            payload = {
                "query": query,
                "mode": "mix",  # 混合模式：知识图谱+文档片段
                "only_need_context": True,
                "top_k": 20,
                "chunk_top_k": 10,
                "max_entity_tokens": 3000,
                "max_relation_tokens": 4000,
                "max_total_tokens": 15000
            }

            response = requests.post(
                lightrag_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                print(f"⚠️ LightRAG API返回错误: {response.status_code}")
                return results

            data = response.json()

            # 解析LightRAG响应
            response_text = data.get("response", "")
            documents = data.get("documents", [])
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])

            # 1. 提取文档片段（优先级最高，包含具体解决方案）
            if documents:
                for i, doc in enumerate(documents[:3]):  # 取前3个最相关的文档
                    content = doc.get("content", "")
                    if content:
                        results.append({
                            "source": f"lightrag:document:{i+1}",
                            "content": content[:1500],  # 限制长度
                            "relevance": 0.85 - i * 0.05,  # 相关度递减
                            "type": "document"
                        })

            # 2. 提取知识图谱实体（帮助理解概念）
            if entities:
                entity_descriptions = []
                for entity in entities[:5]:  # 最多5个实体
                    entity_name = entity.get("entity", "")
                    entity_desc = entity.get("description", "")
                    if entity_name and entity_desc:
                        entity_descriptions.append(f"**{entity_name}**: {entity_desc}")

                if entity_descriptions:
                    results.append({
                        "source": "lightrag:entities",
                        "content": "\n".join(entity_descriptions),
                        "relevance": 0.75,
                        "type": "entities"
                    })

            # 3. 提取关系（帮助理解命令间的依赖）
            if relationships:
                rel_descriptions = []
                for rel in relationships[:5]:  # 最多5个关系
                    source = rel.get("source", "")
                    target = rel.get("target", "")
                    desc = rel.get("description", "")
                    if source and target and desc:
                        rel_descriptions.append(f"{source} → {target}: {desc}")

                if rel_descriptions:
                    results.append({
                        "source": "lightrag:relationships",
                        "content": "\n".join(rel_descriptions),
                        "relevance": 0.7,
                        "type": "relationships"
                    })

            # 4. 如果有LightRAG生成的响应，也包含进来
            if response_text and len(results) == 0:
                # 提取响应中的有用部分（排除元数据）
                import re
                # 移除JSON格式的知识图谱数据（已经单独提取）
                clean_response = re.sub(r'Knowledge Graph Data.*?```json.*?```', '', response_text, flags=re.DOTALL)
                clean_response = re.sub(r'Document Chunks.*?```json.*?```', '', clean_response, flags=re.DOTALL)
                clean_response = clean_response.strip()

                if clean_response and len(clean_response) > 100:
                    results.append({
                        "source": "lightrag:analysis",
                        "content": clean_response[:1000],
                        "relevance": 0.8,
                        "type": "analysis"
                    })

            if results:
                print(f"✅ LightRAG搜索成功: 找到{len(results)}个相关资源")
            else:
                print("⚠️ LightRAG未找到相关内容")

        except requests.exceptions.Timeout:
            print("⚠️ LightRAG API超时")
        except requests.exceptions.ConnectionError:
            print("⚠️ 无法连接到LightRAG服务（请确保LightRAG服务正在运行）")
        except Exception as e:
            print(f"⚠️ LightRAG搜索失败: {e}")

        return results

    def _search_web(self, error_message: str) -> List[Dict]:
        """网络搜索解决方案"""
        results = []

        try:
            from multi_source_retriever import BRAVESearcher
            searcher = BRAVESearcher()

            # 构建搜索查询
            query = f"SPARTA DSMC {error_message}"
            search_result = searcher.search(query, count=3)

            for item in search_result.get("results", []):
                results.append({
                    "source": f"web:{item.get('title', 'Unknown')[:30]}",
                    "content": item.get("description", ""),
                    "url": item.get("url", ""),
                    "relevance": 0.5
                })

        except Exception as e:
            print(f"网络搜索失败: {e}")

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 移除常见词
        stop_words = {'error', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'is', 'not', 'cannot'}

        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]

        return list(dict.fromkeys(keywords))[:5]  # 去重并限制数量

    def _read_manual_section(self, filename: str, line_num: int) -> str:
        """读取手册章节内容"""
        file_path = self.manual_dir / filename
        if not file_path.exists():
            return ""

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 读取指定行前后的内容
            start = max(0, line_num - 1)
            end = min(len(lines), line_num + 50)  # 读取50行

            return ''.join(lines[start:end])
        except:
            return ""

    def _read_code_context(self, filepath: str, keyword: str) -> str:
        """读取代码上下文"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 找到关键词所在行
            for i, line in enumerate(lines):
                if keyword in line:
                    start = max(0, i - 5)
                    end = min(len(lines), i + 10)
                    return ''.join(lines[start:end])

        except:
            pass
        return ""

    def generate_fix(self, input_file: str, error_info: Dict,
                     search_results: Dict) -> Generator:
        """
        使用LLM生成修复方案

        Args:
            input_file: 原始输入文件内容
            error_info: 错误信息
            search_results: 搜索结果

        Yields:
            生成事件
        """
        yield {"type": "status", "message": "🤖 正在使用AI生成修复方案..."}

        # 构建提示词
        prompt = self._build_fix_prompt(input_file, error_info, search_results)

        # 调用LLM生成修复
        fixed_content = ""
        explanation = ""

        full_response = ""
        for chunk in call_llm_stream(prompt, temperature=0.2):
            full_response += chunk

        # 解析LLM响应
        # 期望格式：修复后的代码块 + 解释
        fixed_code = extract_code_block(full_response, "sparta")
        if not fixed_code:
            fixed_code = extract_code_block(full_response)

        if fixed_code:
            fixed_content = fixed_code
            # 提取解释部分
            explanation = full_response.replace(f"```sparta\n{fixed_code}\n```", "")
            explanation = explanation.replace(f"```\n{fixed_code}\n```", "")
            explanation = explanation.strip()
        else:
            # 如果没有代码块，尝试直接修复
            fixed_content = input_file  # 返回原文件
            explanation = full_response

        yield {
            "type": "fix_generated",
            "fixed_content": fixed_content,
            "explanation": explanation,
            "changes": self._extract_changes(input_file, fixed_content),
            "confidence": 0.8 if fixed_code else 0.3
        }

    def _build_fix_prompt(self, input_file: str, error_info: Dict,
                          search_results: Dict) -> str:
        """构建修复提示词"""
        # 收集搜索到的参考信息
        reference_info = ""
        for source in search_results.get("sources", [])[:3]:
            reference_info += f"\n### 参考来源: {source['source']}\n"
            reference_info += f"{source['content'][:500]}\n"

        prompt = f"""你是SPARTA DSMC仿真专家。请修复以下SPARTA输入文件中的错误。

## 错误信息
- 错误类型: {error_info.get('error_type', '未知')}
- 错误消息: {error_info.get('error_message', '无')}
- 错误上下文:
```
{error_info.get('error_context', '无')}
```

## 原始输入文件
```sparta
{input_file}
```

## 参考信息
{reference_info if reference_info else "无额外参考信息"}

## 要求
1. 仔细分析错误原因
2. 修复输入文件中的问题
3. 保持文件其他部分不变
4. 在修改处添加中文注释说明修改原因

## 常见SPARTA修复规则
- fix样式应使用 ave/grid, ave/surf, ave/time 等格式，不是 grid, surf, time
- compute样式应使用正确的名称如 grid, surf, thermal/grid 等
- 命令顺序很重要：dimension → boundary → create_box → create_grid → species → mixture

请输出修复后的完整SPARTA输入文件（用```sparta代码块包裹），然后简要说明修改内容："""

        return prompt

    def _extract_changes(self, original: str, fixed: str) -> List[str]:
        """提取修改内容"""
        import difflib

        changes = []
        original_lines = original.splitlines()
        fixed_lines = fixed.splitlines()

        diff = difflib.unified_diff(original_lines, fixed_lines, lineterm='')

        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                changes.append(f"添加: {line[1:]}")
            elif line.startswith('-') and not line.startswith('---'):
                changes.append(f"删除: {line[1:]}")

        return changes[:10]  # 限制数量

    def apply_fix(self, session_id: str, fixed_content: str,
                  error_info: Dict, explanation: str) -> Dict:
        """
        应用修复并创建新版本

        Args:
            session_id: 会话ID
            fixed_content: 修复后的内容
            error_info: 错误信息
            explanation: 修复说明

        Returns:
            {
                "success": bool,
                "version": int,
                "message": str
            }
        """
        from version_manager import VersionManager

        vm = VersionManager()

        # 创建新版本
        changes = {
            "description": f"fix_{error_info.get('error_type', 'unknown')}",
            "fixes": [
                f"修复错误: {error_info.get('error_message', '未知错误')[:50]}",
                explanation[:100] if explanation else "自动修复"
            ],
            "source": "auto_fix_agent"
        }

        result = vm.create_version(session_id, fixed_content, changes, error_info)

        return result


# 测试代码
if __name__ == "__main__":
    fixer = SPARTAErrorFixer()

    # 测试错误解析
    test_log = """SPARTA (24 Sep 2025)
Running on 4 MPI task(s)
fix                avg grid all 10 100 1000 c_1[*]
ERROR: Unrecognized fix style (../modify.cpp:370)
"""

    print("测试错误解析")
    print("=" * 50)

    error_info = fixer.parse_error(test_log)
    print(f"错误信息: {json.dumps(error_info, indent=2, ensure_ascii=False)}")

    # 测试搜索解决方案
    print("\n测试搜索解决方案")
    print("=" * 50)

    search_result = fixer.search_solution(error_info)
    print(f"搜索结果: {json.dumps(search_result, indent=2, ensure_ascii=False)}")
