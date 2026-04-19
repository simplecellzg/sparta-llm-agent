#!/usr/bin/env python3
"""
SPARTA手册处理器
================

下载SPARTA技术手册PDF并转换为Markdown格式，创建可搜索的索引。
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from utils import download_file, ensure_dir, save_json


class ManualProcessor:
    """SPARTA手册处理器"""

    # SPARTA手册URL
    MANUAL_URL = "https://sparta.github.io/doc/Manual.pdf"

    def __init__(self, base_dir: str = None):
        """
        初始化手册处理器

        Args:
            base_dir: 基础目录，默认为项目根目录
        """
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.manual_pdf = self.base_dir / "sparta" / "doc" / "Manual.pdf"
        self.manual_md_dir = self.base_dir / "sparta_manual_md"
        self.index_file = self.manual_md_dir / "index.json"

    def download_manual(self) -> Tuple[bool, str]:
        """
        下载SPARTA手册PDF

        Returns:
            (success: bool, message: str)
        """
        print(f"📥 正在下载SPARTA手册...")
        print(f"   URL: {self.MANUAL_URL}")
        print(f"   目标: {self.manual_pdf}")

        # 确保目录存在
        self.manual_pdf.parent.mkdir(parents=True, exist_ok=True)

        # 如果文件已存在，跳过下载
        if self.manual_pdf.exists():
            file_size = self.manual_pdf.stat().st_size
            if file_size > 100000:  # 大于100KB认为是有效文件
                print(f"✅ 手册已存在（{file_size / 1024 / 1024:.1f} MB）")
                return True, f"手册已存在: {self.manual_pdf}"

        # 下载文件
        success = download_file(self.MANUAL_URL, str(self.manual_pdf))

        if success:
            file_size = self.manual_pdf.stat().st_size
            print(f"✅ 下载成功（{file_size / 1024 / 1024:.1f} MB）")
            return True, "手册下载成功"
        else:
            return False, "手册下载失败"

    def convert_to_markdown(self) -> Tuple[bool, str]:
        """
        将PDF转换为Markdown格式

        Returns:
            (success: bool, message: str)
        """
        if not self.manual_pdf.exists():
            return False, "手册PDF不存在，请先下载"

        print(f"\n📝 正在转换PDF为Markdown...")

        # 尝试导入pymupdf4llm
        try:
            import pymupdf4llm
        except ImportError:
            print("⚠️  pymupdf4llm未安装，尝试使用简化转换...")
            return self._simple_conversion()

        try:
            # 使用pymupdf4llm转换
            md_text = pymupdf4llm.to_markdown(
                str(self.manual_pdf),
                page_chunks=False,
                write_images=False
            )

            # 确保输出目录存在
            ensure_dir(self.manual_md_dir)

            # 保存完整Markdown
            full_md_file = self.manual_md_dir / "sparta_manual_full.md"
            with open(full_md_file, 'w', encoding='utf-8') as f:
                f.write(md_text)

            print(f"✅ 转换成功: {full_md_file}")
            print(f"   大小: {len(md_text) / 1024:.1f} KB")

            # 按章节分割
            self._split_into_chapters(md_text)

            return True, "转换成功"

        except Exception as e:
            print(f"❌ 转换失败: {e}")
            return False, f"转换失败: {str(e)}"

    def _simple_conversion(self) -> Tuple[bool, str]:
        """简化的PDF转换（不依赖pymupdf4llm）"""
        try:
            import PyPDF2

            print("使用PyPDF2进行基础文本提取...")

            with open(self.manual_pdf, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)

                all_text = []
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    all_text.append(f"\n## Page {i + 1}\n\n{text}\n")

                    if (i + 1) % 10 == 0:
                        print(f"   处理进度: {i + 1}/{num_pages} 页")

            md_text = "\n".join(all_text)

            # 保存
            ensure_dir(self.manual_md_dir)
            full_md_file = self.manual_md_dir / "sparta_manual_full.md"
            with open(full_md_file, 'w', encoding='utf-8') as f:
                f.write(md_text)

            print(f"✅ 基础转换成功: {full_md_file}")
            return True, "基础转换成功"

        except Exception as e:
            return False, f"基础转换失败: {str(e)}"

    def _split_into_chapters(self, md_text: str):
        """将Markdown文本按章节分割"""
        print("\n📑 正在按章节分割...")

        # 查找章节标题（# Chapter 或 ## Chapter）
        chapter_pattern = r'^#{1,2}\s+(Chapter\s+\d+.*?)$'
        chapters = []
        current_chapter = {"title": "Introduction", "content": ""}

        lines = md_text.split('\n')
        for line in lines:
            match = re.match(chapter_pattern, line, re.IGNORECASE)
            if match:
                # 保存上一章节
                if current_chapter["content"]:
                    chapters.append(current_chapter)

                # 开始新章节
                current_chapter = {
                    "title": match.group(1).strip(),
                    "content": line + "\n"
                }
            else:
                current_chapter["content"] += line + "\n"

        # 保存最后一章
        if current_chapter["content"]:
            chapters.append(current_chapter)

        print(f"   找到 {len(chapters)} 个章节")

        # 保存各章节文件
        for i, chapter in enumerate(chapters):
            # 清理文件名
            filename = re.sub(r'[^\w\s-]', '', chapter["title"].lower())
            filename = re.sub(r'[-\s]+', '_', filename)
            chapter_file = self.manual_md_dir / f"chapter_{i:02d}_{filename}.md"

            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(chapter["content"])

            print(f"   ✅ {chapter_file.name}")

    def create_index(self) -> Tuple[bool, str]:
        """
        创建手册索引

        Returns:
            (success: bool, message: str)
        """
        print(f"\n🔍 正在创建索引...")

        if not self.manual_md_dir.exists():
            return False, "手册Markdown目录不存在，请先转换"

        index = {
            "commands": {},
            "concepts": {},
            "files": []
        }

        # 扫描所有Markdown文件
        md_files = list(self.manual_md_dir.glob("chapter_*.md"))

        for md_file in md_files:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            index["files"].append(md_file.name)

            # 提取命令（查找代码块或命令模式）
            for i, line in enumerate(lines):
                # 检测SPARTA命令（通常是单词加参数）
                # 例如: dimension, boundary, create_box等
                if re.match(r'^\s*(dimension|boundary|create_box|create_grid|species|mixture|collide|fix|compute|dump|stats|run)\s+', line):
                    cmd = line.strip().split()[0]
                    if cmd not in index["commands"]:
                        index["commands"][cmd] = {
                            "file": md_file.name,
                            "line": i + 1,
                            "example": line.strip()
                        }

                # 提取重要概念（标题）
                if line.startswith('##'):
                    concept = line.replace('##', '').strip()
                    # 跳过太通用的标题
                    if len(concept) > 5 and 'chapter' not in concept.lower():
                        concept_key = concept.lower().replace(' ', '_')
                        if concept_key not in index["concepts"]:
                            index["concepts"][concept_key] = {
                                "file": md_file.name,
                                "line": i + 1,
                                "title": concept
                            }

        # 保存索引
        save_json(index, str(self.index_file))

        print(f"✅ 索引创建成功: {self.index_file}")
        print(f"   命令数: {len(index['commands'])}")
        print(f"   概念数: {len(index['concepts'])}")
        print(f"   文件数: {len(index['files'])}")

        return True, "索引创建成功"

    def process(self) -> Dict:
        """
        执行完整处理流程：下载 + 转换 + 索引

        Returns:
            处理结果字典
        """
        result = {
            "success": False,
            "steps": {}
        }

        # 步骤1: 下载
        success, message = self.download_manual()
        result["steps"]["download"] = (success, message)
        if not success:
            return result

        # 步骤2: 转换
        success, message = self.convert_to_markdown()
        result["steps"]["convert"] = (success, message)
        if not success:
            return result

        # 步骤3: 创建索引
        success, message = self.create_index()
        result["steps"]["index"] = (success, message)

        result["success"] = success
        return result


def main():
    """命令行入口"""
    print("=" * 60)
    print("SPARTA Manual Processor")
    print("=" * 60)

    processor = ManualProcessor()
    result = processor.process()

    print("\n" + "=" * 60)
    print("处理总结")
    print("=" * 60)

    for step_name, (success, message) in result["steps"].items():
        status = "✅" if success else "❌"
        print(f"{status} {step_name}: {message}")

    if result["success"]:
        print(f"\n🎉 手册处理成功!")
        return 0
    else:
        print(f"\n❌ 手册处理失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
