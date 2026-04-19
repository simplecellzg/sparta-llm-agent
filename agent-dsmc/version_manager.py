"""
版本管理模块
============

管理SPARTA输入文件的版本历史，支持版本创建、恢复和变更日志。
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from utils import ensure_dir, get_iso_timestamp


class VersionManager:
    """SPARTA输入文件版本管理器"""

    def __init__(self, sessions_dir: str = None):
        """
        初始化版本管理器

        Args:
            sessions_dir: 会话目录路径
        """
        if sessions_dir is None:
            base_dir = Path(__file__).parent.parent
            self.sessions_dir = base_dir / "llm-chat-app" / "data" / "dsmc_sessions"
        else:
            self.sessions_dir = Path(sessions_dir)

    def _get_versions_dir(self, session_id: str) -> Path:
        """获取版本目录路径"""
        return self.sessions_dir / session_id / "versions"

    def _get_changelog_path(self, session_id: str) -> Path:
        """获取变更日志路径"""
        return self._get_versions_dir(session_id) / "CHANGELOG.md"

    def get_current_version(self, session_id: str) -> int:
        """
        获取当前版本号

        Args:
            session_id: 会话ID

        Returns:
            当前版本号
        """
        metadata_file = self.sessions_dir / session_id / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                return metadata.get("version", 1)
        return 1

    def create_version(self, session_id: str, input_content: str,
                       changes: Dict, error_info: Dict = None) -> Dict:
        """
        创建新版本

        Args:
            session_id: 会话ID
            input_content: 新的输入文件内容
            changes: 变更信息 {"description": str, "fixes": [str], "source": str}
            error_info: 错误信息（可选）

        Returns:
            {
                "success": bool,
                "version": int,
                "version_dir": str,
                "message": str
            }
        """
        try:
            session_dir = self.sessions_dir / session_id
            versions_dir = self._get_versions_dir(session_id)
            ensure_dir(versions_dir)

            # 获取当前版本并递增
            current_version = self.get_current_version(session_id)
            new_version = current_version + 1

            # 如果是第一次创建版本，先保存原始版本
            if current_version == 1 and not (versions_dir / "v1_original").exists():
                original_input = session_dir / "input.sparta"
                if original_input.exists():
                    v1_dir = versions_dir / "v1_original"
                    ensure_dir(v1_dir)
                    shutil.copy(original_input, v1_dir / "input.sparta")
                    self._add_changelog_entry(session_id, 1, {
                        "description": "原始版本",
                        "fixes": [],
                        "source": "generated"
                    })

            # 创建版本目录名
            fix_name = self._sanitize_dirname(changes.get("description", "fix"))
            version_dirname = f"v{new_version}_{fix_name}"
            version_dir = versions_dir / version_dirname
            ensure_dir(version_dir)

            # 保存输入文件
            with open(version_dir / "input.sparta", 'w', encoding='utf-8') as f:
                f.write(input_content)

            # 保存变更元数据
            change_metadata = {
                "version": new_version,
                "timestamp": get_iso_timestamp(),
                "changes": changes,
                "error_info": error_info
            }
            with open(version_dir / "change_info.json", 'w', encoding='utf-8') as f:
                json.dump(change_metadata, f, ensure_ascii=False, indent=2)

            # 更新当前输入文件
            with open(session_dir / "input.sparta", 'w', encoding='utf-8') as f:
                f.write(input_content)

            # 更新会话元数据
            self._update_session_metadata(session_id, new_version, changes, error_info)

            # 添加变更日志条目
            self._add_changelog_entry(session_id, new_version, changes, error_info)

            return {
                "success": True,
                "version": new_version,
                "version_dir": str(version_dir),
                "message": f"已创建版本 v{new_version}"
            }

        except Exception as e:
            return {
                "success": False,
                "version": current_version,
                "version_dir": "",
                "message": f"创建版本失败: {str(e)}"
            }

    def _sanitize_dirname(self, name: str) -> str:
        """清理目录名"""
        import re
        # 替换非法字符
        name = re.sub(r'[<>:"/\\|?*\s]', '_', name)
        # 限制长度
        return name[:30].lower()

    def _update_session_metadata(self, session_id: str, version: int,
                                  changes: Dict, error_info: Dict = None):
        """更新会话元数据"""
        metadata_file = self.sessions_dir / session_id / "metadata.json"

        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {}

        # 更新版本号
        metadata["version"] = version

        # 更新版本历史
        if "version_history" not in metadata:
            metadata["version_history"] = []

        metadata["version_history"].append({
            "version": version,
            "timestamp": get_iso_timestamp(),
            "status": "fixed" if error_info else "updated",
            "description": changes.get("description", ""),
            "fixes": changes.get("fixes", []),
            "source": changes.get("source", "agent")
        })

        # 更新状态
        metadata["status"] = "ready"
        if error_info:
            metadata["last_error"] = error_info

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _add_changelog_entry(self, session_id: str, version: int,
                             changes: Dict, error_info: Dict = None):
        """添加变更日志条目"""
        changelog_path = self._get_changelog_path(session_id)
        ensure_dir(changelog_path.parent)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"\n## Version {version} - {timestamp}\n"
        entry += f"### 描述\n{changes.get('description', '无描述')}\n\n"

        if error_info:
            entry += f"### 修复的错误\n"
            entry += f"- 错误类型: {error_info.get('error_type', '未知')}\n"
            entry += f"- 错误信息: {error_info.get('message', '无')}\n"
            if error_info.get('line'):
                entry += f"- 错误位置: 第 {error_info.get('line')} 行\n"
            entry += "\n"

        if changes.get('fixes'):
            entry += "### 修改内容\n"
            for fix in changes['fixes']:
                entry += f"- {fix}\n"
            entry += "\n"

        entry += f"### 来源\n{changes.get('source', '自动修复')}\n"
        entry += "\n---\n"

        # 读取现有内容并追加
        if changelog_path.exists():
            with open(changelog_path, 'r', encoding='utf-8') as f:
                existing = f.read()
        else:
            existing = "# SPARTA输入文件版本历史\n\n本文件记录了输入文件的所有版本变更。\n\n---\n"

        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(existing + entry)

    def get_version_history(self, session_id: str) -> List[Dict]:
        """
        获取版本历史

        Args:
            session_id: 会话ID

        Returns:
            版本历史列表
        """
        versions_dir = self._get_versions_dir(session_id)
        history = []

        if not versions_dir.exists():
            return history

        # 遍历版本目录
        for version_dir in sorted(versions_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name.startswith('v'):
                version_info = {
                    "name": version_dir.name,
                    "path": str(version_dir),
                    "has_input": (version_dir / "input.sparta").exists()
                }

                # 读取变更信息
                change_info_file = version_dir / "change_info.json"
                if change_info_file.exists():
                    with open(change_info_file, 'r', encoding='utf-8') as f:
                        version_info["change_info"] = json.load(f)

                # 提取版本号
                try:
                    version_num = int(version_dir.name.split('_')[0][1:])
                    version_info["version"] = version_num
                except:
                    version_info["version"] = 0

                history.append(version_info)

        # 按版本号排序
        history.sort(key=lambda x: x["version"])
        return history

    def restore_version(self, session_id: str, version: int) -> Dict:
        """
        恢复到指定版本

        Args:
            session_id: 会话ID
            version: 要恢复的版本号

        Returns:
            {
                "success": bool,
                "message": str,
                "input_file": str (恢复的文件内容)
            }
        """
        try:
            versions_dir = self._get_versions_dir(session_id)
            session_dir = self.sessions_dir / session_id

            # 查找指定版本的目录
            version_dir = None
            for d in versions_dir.iterdir():
                if d.is_dir() and d.name.startswith(f'v{version}_'):
                    version_dir = d
                    break

            if not version_dir:
                return {
                    "success": False,
                    "message": f"版本 v{version} 不存在",
                    "input_file": ""
                }

            input_file = version_dir / "input.sparta"
            if not input_file.exists():
                return {
                    "success": False,
                    "message": f"版本 v{version} 的输入文件不存在",
                    "input_file": ""
                }

            # 读取版本内容
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 在恢复之前，保存当前版本
            current_input = session_dir / "input.sparta"
            if current_input.exists():
                current_version = self.get_current_version(session_id)
                # 只有当前版本没有被保存时才保存
                current_version_exists = any(
                    d.name.startswith(f'v{current_version}_')
                    for d in versions_dir.iterdir() if d.is_dir()
                )
                if not current_version_exists:
                    with open(current_input, 'r', encoding='utf-8') as f:
                        current_content = f.read()
                    self.create_version(session_id, current_content, {
                        "description": "恢复前自动保存",
                        "fixes": [],
                        "source": "auto_backup"
                    })

            # 恢复文件
            with open(current_input, 'w', encoding='utf-8') as f:
                f.write(content)

            # 添加恢复记录
            self._add_changelog_entry(session_id, version, {
                "description": f"恢复到版本 v{version}",
                "fixes": [],
                "source": "manual_restore"
            })

            return {
                "success": True,
                "message": f"已恢复到版本 v{version}",
                "input_file": content
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"恢复失败: {str(e)}",
                "input_file": ""
            }

    def get_changelog(self, session_id: str) -> str:
        """
        获取变更日志

        Args:
            session_id: 会话ID

        Returns:
            变更日志内容（Markdown格式）
        """
        changelog_path = self._get_changelog_path(session_id)
        if changelog_path.exists():
            with open(changelog_path, 'r', encoding='utf-8') as f:
                return f.read()
        return "# 变更日志\n\n暂无版本历史记录。"

    def get_version_content(self, session_id: str, version: int) -> Optional[str]:
        """
        获取指定版本的输入文件内容

        Args:
            session_id: 会话ID
            version: 版本号

        Returns:
            输入文件内容，如果版本不存在则返回None
        """
        versions_dir = self._get_versions_dir(session_id)

        for d in versions_dir.iterdir():
            if d.is_dir() and d.name.startswith(f'v{version}_'):
                input_file = d / "input.sparta"
                if input_file.exists():
                    with open(input_file, 'r', encoding='utf-8') as f:
                        return f.read()
        return None

    def compare_versions(self, session_id: str, version1: int, version2: int) -> Dict:
        """
        比较两个版本的差异

        Args:
            session_id: 会话ID
            version1: 版本1
            version2: 版本2

        Returns:
            {
                "success": bool,
                "diff": str (差异内容),
                "v1_content": str,
                "v2_content": str
            }
        """
        import difflib

        content1 = self.get_version_content(session_id, version1)
        content2 = self.get_version_content(session_id, version2)

        if content1 is None:
            return {"success": False, "diff": f"版本 v{version1} 不存在"}
        if content2 is None:
            return {"success": False, "diff": f"版本 v{version2} 不存在"}

        # 生成unified diff
        diff = difflib.unified_diff(
            content1.splitlines(keepends=True),
            content2.splitlines(keepends=True),
            fromfile=f'v{version1}/input.sparta',
            tofile=f'v{version2}/input.sparta'
        )

        return {
            "success": True,
            "diff": ''.join(diff),
            "v1_content": content1,
            "v2_content": content2
        }


# 测试代码
if __name__ == "__main__":
    vm = VersionManager()

    # 测试会话ID
    test_session = "test_version_manager"

    print("测试版本管理器")
    print("=" * 50)

    # 创建测试版本
    result = vm.create_version(
        test_session,
        "# Test SPARTA input\nrun 100\n",
        {
            "description": "test_fix",
            "fixes": ["Added run command"],
            "source": "test"
        }
    )
    print(f"创建版本: {result}")

    # 获取版本历史
    history = vm.get_version_history(test_session)
    print(f"版本历史: {history}")

    # 获取变更日志
    changelog = vm.get_changelog(test_session)
    print(f"变更日志:\n{changelog[:500]}...")
