"""
多源检索器
==========

整合SPARTA手册、LightRAG文献、SPARTA源代码和BRAVE网络搜索的级联检索系统。
"""

import re
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional
from utils import load_json


class ManualSearcher:
    """SPARTA手册搜索器"""

    def __init__(self, manual_dir: str = None):
        """
        初始化手册搜索器

        Args:
            manual_dir: 手册Markdown目录
        """
        if manual_dir is None:
            base_dir = Path(__file__).parent.parent
            self.manual_dir = base_dir / "sparta_manual_md"
        else:
            self.manual_dir = Path(manual_dir)

        self.index_file = self.manual_dir / "index.json"
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """加载手册索引"""
        if self.index_file.exists():
            return load_json(str(self.index_file))
        return {"commands": {}, "concepts": {}, "files": []}

    def search(self, query: str) -> Dict:
        """
        搜索手册

        Args:
            query: 查询字符串

        Returns:
            {
                "score": float (0-1),
                "results": [...],
                "source": "manual"
            }
        """
        results = []
        query_lower = query.lower()

        # 1. 精确命令匹配
        for cmd, info in self.index.get("commands", {}).items():
            if cmd.lower() in query_lower:
                results.append({
                    "type": "command",
                    "command": cmd,
                    "file": info["file"],
                    "line": info["line"],
                    "example": info.get("example", ""),
                    "relevance": 1.0
                })

        # 2. 概念匹配
        for concept_key, info in self.index.get("concepts", {}).items():
            if concept_key in query_lower or any(word in query_lower for word in concept_key.split('_')):
                results.append({
                    "type": "concept",
                    "concept": info["title"],
                    "file": info["file"],
                    "line": info["line"],
                    "relevance": 0.8
                })

        # 3. 全文搜索（在Markdown文件中grep）
        if not results or len(results) < 3:
            grep_results = self._grep_manual(query)
            results.extend(grep_results)

        # 计算得分
        score = min(len(results) * 0.3, 1.0) if results else 0.0

        return {
            "score": score,
            "results": results[:5],  # 最多返回5个结果
            "source": "manual"
        }

    def _grep_manual(self, query: str) -> List[Dict]:
        """在手册文件中搜索关键词"""
        results = []

        if not self.manual_dir.exists():
            return results

        # 分词
        keywords = query.lower().split()

        for md_file in self.manual_dir.glob("chapter_*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    # 检查是否包含任何关键词
                    if any(kw in line_lower for kw in keywords):
                        results.append({
                            "type": "text",
                            "file": md_file.name,
                            "line": i + 1,
                            "content": line.strip()[:200],  # 限制长度
                            "relevance": 0.5
                        })

                        if len(results) >= 10:
                            return results

            except Exception as e:
                continue

        return results


class LightRAGSearcher:
    """LightRAG文献搜索器"""

    def __init__(self, lightrag_url: str = "http://10.2.1.36:9627/query"):
        """
        初始化LightRAG搜索器

        Args:
            lightrag_url: LightRAG API地址
        """
        self.lightrag_url = lightrag_url

    def search(self, query: str) -> Dict:
        """
        查询LightRAG

        Args:
            query: 查询字符串

        Returns:
            {
                "score": float (0-1),
                "results": {...},
                "source": "lightrag"
            }
        """
        try:
            payload = {
                "query": query,
                "mode": "mix",
                "only_need_context": True,
                "top_k": 20,
                "chunk_top_k": 10
            }

            response = requests.post(
                self.lightrag_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # 解析结果
            doc_count = len(data.get("documents", []))
            entity_count = len(data.get("entities", []))

            score = min((doc_count + entity_count) * 0.1, 1.0)

            return {
                "score": score,
                "results": data,
                "doc_count": doc_count,
                "entity_count": entity_count,
                "source": "lightrag"
            }

        except Exception as e:
            print(f"LightRAG查询失败: {e}")
            return {
                "score": 0.0,
                "results": {},
                "source": "lightrag",
                "error": str(e)
            }


class BRAVESearcher:
    """BRAVE网络搜索器"""

    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str = "BSA7B1H19aj4yatgFIWRjd3JszFVluQ"):
        """
        初始化BRAVE搜索器

        Args:
            api_key: BRAVE API密钥
        """
        self.api_key = api_key

    def search(self, query: str, count: int = 5) -> Dict:
        """
        使用BRAVE搜索

        Args:
            query: 查询字符串
            count: 返回结果数量

        Returns:
            {
                "score": float (0-1),
                "results": [...],
                "source": "brave"
            }
        """
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            }

            params = {
                "q": f"{query} SPARTA DSMC",  # 添加SPARTA DSMC关键词
                "count": count,
                "search_lang": "en"
            }

            response = requests.get(
                self.API_URL,
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            web_results = data.get("web", {}).get("results", [])

            results = []
            for item in web_results:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "relevance": 0.7
                })

            score = min(len(results) * 0.2, 1.0) if results else 0.0

            return {
                "score": score,
                "results": results,
                "source": "brave"
            }

        except Exception as e:
            print(f"BRAVE搜索失败: {e}")
            return {
                "score": 0.0,
                "results": [],
                "source": "brave",
                "error": str(e)
            }


class SPARTACodeSearcher:
    """SPARTA源代码搜索器 - 用于错误诊断和修复"""

    def __init__(self, sparta_src_dir: str = None):
        """
        初始化SPARTA代码搜索器

        Args:
            sparta_src_dir: SPARTA源代码目录
        """
        if sparta_src_dir is None:
            base_dir = Path(__file__).parent.parent
            self.src_dir = base_dir / "sparta" / "src"
        else:
            self.src_dir = Path(sparta_src_dir)

    def search_error(self, error_message: str) -> Dict:
        """
        在源代码中搜索错误相关代码

        Args:
            error_message: 错误消息

        Returns:
            {
                "score": float (0-1),
                "results": [...],
                "source": "sparta_code"
            }
        """
        results = []

        if not self.src_dir.exists():
            return {
                "score": 0.0,
                "results": [],
                "source": "sparta_code",
                "error": "SPARTA源代码目录不存在"
            }

        # 从错误消息中提取关键词
        keywords = self._extract_error_keywords(error_message)

        for keyword in keywords[:3]:
            matches = self._grep_source(keyword)
            results.extend(matches)

        # 去重
        seen_files = set()
        unique_results = []
        for r in results:
            if r["file"] not in seen_files:
                seen_files.add(r["file"])
                unique_results.append(r)

        score = min(len(unique_results) * 0.2, 1.0) if unique_results else 0.0

        return {
            "score": score,
            "results": unique_results[:5],
            "source": "sparta_code"
        }

    def search_command(self, command: str) -> Dict:
        """
        搜索特定命令的实现代码

        Args:
            command: SPARTA命令名称

        Returns:
            搜索结果
        """
        results = []

        # 搜索命令文件（通常命名为 command_xxx.cpp）
        command_file_pattern = f"*{command}*.cpp"
        for cpp_file in self.src_dir.glob(command_file_pattern):
            content = self._read_file_preview(cpp_file)
            if content:
                results.append({
                    "file": cpp_file.name,
                    "path": str(cpp_file),
                    "content": content,
                    "relevance": 0.9
                })

        # 在所有文件中搜索命令关键词
        grep_results = self._grep_source(command)
        results.extend(grep_results)

        score = min(len(results) * 0.25, 1.0) if results else 0.0

        return {
            "score": score,
            "results": results[:5],
            "source": "sparta_code"
        }

    def get_valid_styles(self, style_type: str) -> List[str]:
        """
        获取有效的样式列表（如fix样式、compute样式）

        Args:
            style_type: 样式类型 (fix, compute, dump等)

        Returns:
            有效样式列表
        """
        styles = []

        # 搜索样式定义文件
        style_pattern = f"{style_type}_*.cpp"
        for cpp_file in self.src_dir.glob(style_pattern):
            # 从文件名提取样式名
            filename = cpp_file.stem
            if filename.startswith(f"{style_type}_"):
                style_name = filename[len(f"{style_type}_"):]
                # 转换为SPARTA命令格式（下划线转斜杠）
                style_name = style_name.replace('_', '/')
                styles.append(style_name)

        return sorted(styles)

    def _extract_error_keywords(self, error_message: str) -> List[str]:
        """从错误消息中提取关键词"""
        # 移除常见词
        stop_words = {'error', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'is', 'not'}

        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', error_message)
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]

        return list(dict.fromkeys(keywords))[:5]

    def _grep_source(self, keyword: str) -> List[Dict]:
        """在源代码中搜索关键词"""
        results = []

        try:
            cmd = [
                "grep", "-rn", "-l",
                "--include=*.cpp", "--include=*.h",
                keyword, str(self.src_dir)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout:
                files = result.stdout.strip().split('\n')[:5]

                for filepath in files:
                    if filepath:
                        # 获取匹配的行
                        context = self._get_grep_context(filepath, keyword)
                        results.append({
                            "file": Path(filepath).name,
                            "path": filepath,
                            "content": context,
                            "relevance": 0.6,
                            "keyword": keyword
                        })

        except subprocess.TimeoutExpired:
            print(f"搜索超时: {keyword}")
        except Exception as e:
            print(f"搜索错误: {e}")

        return results

    def _get_grep_context(self, filepath: str, keyword: str) -> str:
        """获取关键词上下文"""
        try:
            cmd = ["grep", "-n", "-B2", "-A2", keyword, filepath]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # 只返回前500个字符
                return result.stdout[:500]

        except:
            pass
        return ""

    def _read_file_preview(self, filepath: Path) -> str:
        """读取文件预览（前100行）"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:100]
            return ''.join(lines)
        except:
            return ""


class MultiSourceRetriever:
    """多源检索器 - 级联查询策略"""

    def __init__(self):
        """初始化多源检索器"""
        self.manual_searcher = ManualSearcher()
        self.lightrag_searcher = LightRAGSearcher()
        self.brave_searcher = BRAVESearcher()
        self.code_searcher = SPARTACodeSearcher()

    def retrieve(self, query: str, intent: str = "unknown") -> Dict:
        """
        多源级联检索

        Args:
            query: 查询字符串
            intent: 用户意图

        Returns:
            {
                "sources": {
                    "manual": {...},
                    "literature": {...},
                    "web": {...}
                },
                "primary_source": "manual|literature|web",
                "confidence": float (0-1)
            }
        """
        result = {
            "sources": {},
            "primary_source": None,
            "confidence": 0.0,
            "query": query,
            "intent": intent
        }

        # 优先级1: 手册搜索
        print("🔍 搜索SPARTA技术手册...")
        manual_result = self.manual_searcher.search(query)
        result["sources"]["manual"] = manual_result

        if manual_result["score"] > 0.7:
            result["primary_source"] = "manual"
            result["confidence"] = manual_result["score"]
            print(f"✅ 手册搜索成功（得分: {manual_result['score']:.2f}）")
            return result

        # 优先级2: LightRAG文献搜索
        print("📚 搜索LightRAG文献库...")
        lightrag_result = self.lightrag_searcher.search(query)
        result["sources"]["literature"] = lightrag_result

        if lightrag_result["score"] > 0.5:
            if result["primary_source"] is None:
                result["primary_source"] = "literature"
                result["confidence"] = lightrag_result["score"]
            print(f"✅ 文献搜索成功（得分: {lightrag_result['score']:.2f}）")

        # 优先级3: BRAVE网络搜索
        if result["confidence"] < 0.6:
            print("🌐 搜索在线资源...")
            brave_result = self.brave_searcher.search(query)
            result["sources"]["web"] = brave_result

            if brave_result["score"] > 0.3:
                if result["primary_source"] is None:
                    result["primary_source"] = "web"
                    result["confidence"] = brave_result["score"]
                print(f"✅ 网络搜索成功（得分: {brave_result['score']:.2f}）")

        # 如果仍然没有主要来源，选择得分最高的
        if result["primary_source"] is None:
            scores = {
                "manual": manual_result["score"],
                "literature": lightrag_result["score"],
                "web": result["sources"].get("web", {}).get("score", 0.0)
            }
            result["primary_source"] = max(scores, key=scores.get)
            result["confidence"] = scores[result["primary_source"]]

        return result

    def retrieve_for_error_fix(self, error_message: str, error_type: str = "") -> Dict:
        """
        专门用于错误修复的多源检索

        Args:
            error_message: 错误消息
            error_type: 错误类型

        Returns:
            {
                "sources": {...},
                "primary_source": str,
                "confidence": float,
                "suggested_fixes": [...]
            }
        """
        result = {
            "sources": {},
            "primary_source": None,
            "confidence": 0.0,
            "error_message": error_message,
            "error_type": error_type,
            "suggested_fixes": []
        }

        # 1. 搜索SPARTA源代码
        print("🔍 搜索SPARTA源代码...")
        code_result = self.code_searcher.search_error(error_message)
        result["sources"]["code"] = code_result

        if code_result["score"] > 0.5:
            result["primary_source"] = "code"
            result["confidence"] = code_result["score"]
            print(f"✅ 代码搜索成功（得分: {code_result['score']:.2f}）")

        # 2. 搜索手册
        print("📖 搜索SPARTA手册...")
        manual_result = self.manual_searcher.search(error_message)
        result["sources"]["manual"] = manual_result

        if manual_result["score"] > result["confidence"]:
            result["primary_source"] = "manual"
            result["confidence"] = manual_result["score"]
            print(f"✅ 手册搜索成功（得分: {manual_result['score']:.2f}）")

        # 3. 如果是样式相关错误，获取有效样式列表
        if "style" in error_type.lower() or "style" in error_message.lower():
            style_type = self._extract_style_type(error_message)
            if style_type:
                valid_styles = self.code_searcher.get_valid_styles(style_type)
                result["suggested_fixes"].append({
                    "type": "valid_styles",
                    "style_type": style_type,
                    "valid_styles": valid_styles[:10]  # 最多10个
                })

        # 4. 如果本地结果不足，使用网络搜索
        if result["confidence"] < 0.6:
            print("🌐 搜索在线资源...")
            brave_result = self.brave_searcher.search(f"SPARTA error: {error_message}", count=3)
            result["sources"]["web"] = brave_result

            if brave_result["score"] > result["confidence"]:
                result["primary_source"] = "web"
                result["confidence"] = brave_result["score"]
                print(f"✅ 网络搜索成功（得分: {brave_result['score']:.2f}）")

        # 如果没有主要来源，选择得分最高的
        if result["primary_source"] is None:
            scores = {
                "code": code_result["score"],
                "manual": manual_result["score"],
                "web": result["sources"].get("web", {}).get("score", 0.0)
            }
            result["primary_source"] = max(scores, key=scores.get)
            result["confidence"] = scores[result["primary_source"]]

        return result

    def _extract_style_type(self, text: str) -> Optional[str]:
        """从文本中提取样式类型"""
        style_types = ["fix", "compute", "dump", "region", "collide"]
        text_lower = text.lower()

        for style in style_types:
            if style in text_lower:
                return style
        return None


# 测试代码
if __name__ == "__main__":
    retriever = MultiSourceRetriever()

    test_queries = [
        "compute command",
        "VSS collision model",
        "boundary conditions"
    ]

    print("=" * 60)
    print("多源检索测试")
    print("=" * 60)

    for query in test_queries:
        print(f"\n查询: {query}")
        result = retriever.retrieve(query)
        print(f"主要来源: {result['primary_source']}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"手册: {len(result['sources']['manual']['results'])} 条结果")
