"""
SPARTA执行器
============

执行SPARTA仿真并解析输出结果，支持自动错误修复。
"""

import subprocess
import time
import re
from pathlib import Path
from typing import Dict, List, Callable, Optional, Generator
from utils import ensure_dir, save_json, get_iso_timestamp


class SPARTARunner:
    """SPARTA执行器"""

    # 类变量：存储所有运行中的进程 {session_id: process}
    _running_processes = {}

    def __init__(self, sparta_path: str = None):
        """
        初始化SPARTA执行器

        Args:
            sparta_path: SPARTA安装目录
        """
        if sparta_path is None:
            base_dir = Path(__file__).parent.parent
            self.sparta_path = base_dir / "sparta"
        else:
            self.sparta_path = Path(sparta_path)

        self.src_dir = self.sparta_path / "src"
        self.executable = self._find_executable()

    @classmethod
    def stop_simulation(cls, session_id: str) -> Dict:
        """
        停止正在运行的仿真

        Args:
            session_id: 会话ID

        Returns:
            {"success": bool, "message": str}
        """
        if session_id not in cls._running_processes:
            return {"success": False, "message": "没有正在运行的仿真"}

        process = cls._running_processes[session_id]

        try:
            # 首先尝试优雅终止
            process.terminate()

            # 等待最多5秒让进程终止
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 如果进程没有终止，强制杀死
                process.kill()
                process.wait()

            # 从运行进程列表中移除
            del cls._running_processes[session_id]

            return {"success": True, "message": "仿真已停止"}

        except Exception as e:
            # 即使出错也尝试移除记录
            if session_id in cls._running_processes:
                del cls._running_processes[session_id]
            return {"success": False, "message": f"停止仿真时出错: {str(e)}"}

    @classmethod
    def is_running(cls, session_id: str) -> bool:
        """检查仿真是否正在运行"""
        if session_id not in cls._running_processes:
            return False

        process = cls._running_processes[session_id]
        # 检查进程是否还在运行
        if process.poll() is None:
            return True
        else:
            # 进程已结束，清理记录
            del cls._running_processes[session_id]
            return False

    @classmethod
    def get_running_sessions(cls) -> List[str]:
        """获取所有正在运行的会话ID列表"""
        # 清理已结束的进程
        finished = []
        for session_id, process in cls._running_processes.items():
            if process.poll() is not None:
                finished.append(session_id)
        for session_id in finished:
            del cls._running_processes[session_id]

        return list(cls._running_processes.keys())

    def _find_executable(self) -> Path:
        """查找SPARTA可执行文件"""
        # 尝试查找可能的可执行文件名
        possible_names = ["spa_linux", "spa_mpi", "spa_serial", "spa"]

        for name in possible_names:
            exe_path = self.src_dir / name
            if exe_path.exists():
                return exe_path

        return None

    def run(self, input_file_path: str, session_id: str, timeout: int = 300, num_cores: int = 1, max_steps: int = None, max_memory_gb: float = None) -> Dict:
        """
        执行SPARTA仿真

        Args:
            input_file_path: 输入文件路径
            session_id: 会话ID
            timeout: 超时时间（秒）
            num_cores: CPU核数（默认1，即串行运行）
            max_steps: 最大步数（如果指定，将覆盖输入文件中的run命令）
            max_memory_gb: 最大内存限制（GB），如果指定，将限制进程的内存使用

        Returns:
            {
                "status": "success|failed",
                "stdout": str,
                "stderr": str,
                "output_files": [...],
                "execution_time": float,
                "session_dir": str,
                "summary": {...}
            }
        """
        result = {
            "status": "failed",
            "stdout": "",
            "stderr": "",
            "output_files": [],
            "execution_time": 0.0,
            "session_dir": "",
            "summary": {}
        }

        # 检查可执行文件
        if self.executable is None or not self.executable.exists():
            result["stderr"] = "SPARTA可执行文件不存在，请先安装SPARTA"
            return result

        # 创建会话目录
        base_dir = Path(__file__).parent.parent
        session_dir = base_dir / "llm-chat-app" / "data" / "dsmc_sessions" / session_id
        ensure_dir(session_dir)
        result["session_dir"] = str(session_dir)

        # 复制输入文件
        input_path = Path(input_file_path)
        session_input = session_dir / "input.sparta"

        if input_path.exists():
            # 检查源和目标是否是同一个文件
            if input_path.resolve() != session_input.resolve():
                import shutil
                shutil.copy(input_path, session_input)
            # 如果是同一个文件，不需要复制
        else:
            # 如果input_file_path是内容而不是路径，直接写入
            with open(session_input, 'w') as f:
                f.write(input_file_path)

        # 复制输入文件所需的数据文件（species, vss, surf等）
        self._copy_data_files(session_input, session_dir, input_path.parent if input_path.exists() else None)

        # 如果指定了max_steps，修改输入文件中的run命令
        if max_steps is not None:
            self._update_run_steps(session_input, max_steps)

        print(f"🚀 正在运行SPARTA...")
        print(f"   可执行文件: {self.executable}")
        print(f"   工作目录: {session_dir}")
        print(f"   CPU核数: {num_cores}")
        if max_memory_gb:
            print(f"   内存限制: {max_memory_gb} GB")
        if max_steps:
            print(f"   最大步数: {max_steps}")

        # 准备命令
        if num_cores > 1:
            # 使用MPI并行运行
            mpirun = self._find_mpirun()
            if mpirun:
                # 简单的 mpirun 命令，通过环境变量禁用 X11
                # 使用 -echo none 禁用输入文件命令回显，log.sparta 只保留运行结果
                cmd = [
                    mpirun,
                    "-np", str(num_cores),
                    str(self.executable),
                    "-echo", "none",
                    "-in", "input.sparta"
                ]
            else:
                print(f"⚠️ 未找到mpirun，将使用单核运行")
                cmd = [str(self.executable), "-echo", "none", "-in", "input.sparta"]
        else:
            cmd = [str(self.executable), "-echo", "none", "-in", "input.sparta"]

        # 执行SPARTA
        start_time = time.time()

        # 设置环境变量，完全禁用X11和图形相关功能
        import os
        import resource
        env = os.environ.copy()
        # 移除所有X11相关变量，确保无头模式运行
        for var in ['DISPLAY', 'XAUTHORITY', 'XDG_SESSION_TYPE', 'WAYLAND_DISPLAY']:
            env.pop(var, None)
        # 禁用GTK和Qt图形
        env['GTK_A11Y'] = 'none'
        env['QT_QPA_PLATFORM'] = 'offscreen'
        env['HWLOC_HIDE_ERRORS'] = '1'
        # 确保无头模式运行
        env['TERM'] = 'dumb'
        # MPICH 特定设置
        env['HYDRA_TOPO_DEBUG'] = '0'

        # 创建内存限制函数
        def set_memory_limit():
            """设置子进程的内存限制"""
            if max_memory_gb and max_memory_gb > 0:
                # 计算内存限制（字节）
                # 对于 MPI 进程，将总内存限制分配给每个核心
                memory_per_core_bytes = int(max_memory_gb * 1024 * 1024 * 1024 / num_cores)
                try:
                    # 设置虚拟内存限制（RLIMIT_AS）
                    resource.setrlimit(resource.RLIMIT_AS, (memory_per_core_bytes, memory_per_core_bytes))
                    # 设置数据段大小限制（RLIMIT_DATA）
                    resource.setrlimit(resource.RLIMIT_DATA, (memory_per_core_bytes, memory_per_core_bytes))
                except Exception as e:
                    print(f"   ⚠️ 设置内存限制失败: {e}")

        try:
            # 将输出直接写入log.sparta文件
            log_file_path = session_dir / "log.sparta"
            log_file_handle = open(log_file_path, 'w', encoding='utf-8')

            # 使用 Popen 启动进程以便可以中途停止
            process = subprocess.Popen(
                cmd,
                cwd=session_dir,
                stdout=log_file_handle,
                stderr=subprocess.STDOUT,  # 将stderr也重定向到同一个文件
                text=True,
                env=env,
                preexec_fn=set_memory_limit if max_memory_gb else None
            )

            # 记录运行中的进程
            SPARTARunner._running_processes[session_id] = process

            try:
                # 等待进程完成或超时
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 超时，终止进程
                process.kill()
                process.wait()
                log_file_handle.close()
                # 清理进程记录
                if session_id in SPARTARunner._running_processes:
                    del SPARTARunner._running_processes[session_id]
                execution_time = time.time() - start_time
                result["execution_time"] = execution_time
                result["stderr"] = f"执行超时（超过{timeout}秒）"
                print(f"⏱️ 执行超时")
                return result
            finally:
                log_file_handle.close()
                # 清理进程记录
                if session_id in SPARTARunner._running_processes:
                    del SPARTARunner._running_processes[session_id]

            execution_time = time.time() - start_time
            result["execution_time"] = execution_time

            # 读取log.sparta获取输出内容
            if log_file_path.exists():
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    log_content = f.read()
                result["stdout"] = log_content
            else:
                result["stdout"] = ""

            result["stderr"] = ""  # stderr已合并到log.sparta

            # 检查执行状态
            if return_code == 0:
                result["status"] = "success"
                print(f"✅ SPARTA运行成功（{execution_time:.1f}秒）")
            elif return_code == -15 or return_code == -9:
                # SIGTERM (-15) 或 SIGKILL (-9) 表示被停止
                result["status"] = "stopped"
                result["stderr"] = "仿真已被用户停止"
                print(f"⏹️ SPARTA仿真已停止")
            else:
                result["status"] = "failed"
                print(f"❌ SPARTA运行失败（返回码: {return_code}）")

        except Exception as e:
            # 确保清理进程记录
            if session_id in SPARTARunner._running_processes:
                del SPARTARunner._running_processes[session_id]
            result["stderr"] = f"执行错误: {str(e)}"
            print(f"❌ 执行错误: {e}")
            return result

        # 收集输出文件
        output_files = []
        for pattern in ["*.dat", "*.dump", "*.log", "*.grid"]:
            output_files.extend(session_dir.glob(pattern))

        result["output_files"] = [str(f) for f in output_files]

        # 解析日志文件
        log_file = session_dir / "log.sparta"
        if log_file.exists():
            result["summary"] = self._parse_log(log_file)

        # 保存元数据
        metadata = {
            "session_id": session_id,
            "timestamp": get_iso_timestamp(),
            "input_file": "input.sparta",
            "status": result["status"],
            "execution_time": result["execution_time"],
            "output_files": result["output_files"],
            "summary": result["summary"]
        }
        save_json(metadata, str(session_dir / "metadata.json"))

        return result

    def _find_mpirun(self) -> str:
        """查找mpirun或mpiexec可执行文件"""
        import shutil
        for cmd in ['mpirun', 'mpiexec']:
            path = shutil.which(cmd)
            if path:
                return path
        return None

    def _update_run_steps(self, input_file: Path, max_steps: int):
        """更新输入文件中的run命令步数"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 使用正则表达式替换run命令中的步数
            # 匹配 "run N" 格式，其中N是数字
            import re
            new_content = re.sub(
                r'^(\s*run\s+)\d+',
                rf'\g<1>{max_steps}',
                content,
                flags=re.MULTILINE
            )

            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            print(f"   已更新run步数为: {max_steps}")
        except Exception as e:
            print(f"⚠️ 更新run步数失败: {e}")

    def _parse_log(self, log_file: Path) -> Dict:
        """解析SPARTA日志文件"""
        summary = {
            "particles": 0,
            "timesteps": 0,
            "cells": 0,
            "final_time": 0.0
        }

        try:
            with open(log_file, 'r') as f:
                content = f.read()

            # 提取粒子数
            particle_match = re.search(r'(\d+)\s+particles', content, re.IGNORECASE)
            if particle_match:
                summary["particles"] = int(particle_match.group(1))

            # 提取时间步
            # SPARTA日志格式: 数据行以步数开头，后面是CPU时间和粒子数等
            # 例如: "  1000    16.247898     6027   366100   270393        0      106"
            # 匹配: 行首的步数(第一列数字) + CPU时间 + 粒子数
            step_pattern = r'^\s*(\d+)\s+[\d.]+\s+\d+'
            step_matches = re.findall(step_pattern, content, re.MULTILINE)
            if step_matches:
                # 取最后一个匹配的步数值（即仿真完成时的步数）
                summary["timesteps"] = int(step_matches[-1])

            # 提取网格数
            cell_match = re.search(r'(\d+)\s+cells', content, re.IGNORECASE)
            if cell_match:
                summary["cells"] = int(cell_match.group(1))

            # 提取最后时间
            time_match = re.findall(r'CPU\s+time\s+=\s+([\d.]+)', content)
            if time_match:
                summary["final_time"] = float(time_match[-1])

        except Exception as e:
            print(f"日志解析警告: {e}")

        return summary

    def _copy_data_files(self, input_file: Path, session_dir: Path, source_dir: Path = None):
        """复制输入文件中引用的数据文件到工作目录"""
        import shutil

        # SPARTA数据文件目录
        sparta_data_dir = self.sparta_path / "data"

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 需要查找的文件模式
            # species 文件: species <filename> ...
            # vss 文件: collide vss <mixture> <filename>
            # surf 文件: read_surf <filename>

            data_files = set()

            # 匹配 species 命令中的文件
            species_matches = re.findall(r'^\s*species\s+(\S+)', content, re.MULTILINE)
            data_files.update(species_matches)

            # 匹配 collide vss 命令中的文件
            vss_matches = re.findall(r'^\s*collide\s+vss\s+\S+\s+(\S+)', content, re.MULTILINE)
            data_files.update(vss_matches)

            # 匹配 read_surf 命令中的文件
            surf_matches = re.findall(r'^\s*read_surf\s+(\S+)', content, re.MULTILINE)
            data_files.update(surf_matches)

            # 复制找到的数据文件
            for filename in data_files:
                dest_file = session_dir / filename
                if dest_file.exists():
                    continue

                # 查找源文件的优先级：
                # 1. 输入文件所在目录
                # 2. SPARTA data 目录
                # 3. SPARTA examples 目录
                source_file = None

                if source_dir and (source_dir / filename).exists():
                    source_file = source_dir / filename
                elif (sparta_data_dir / filename).exists():
                    source_file = sparta_data_dir / filename
                else:
                    # 在 examples 目录中搜索
                    examples_dir = self.sparta_path / "examples"
                    for example_file in examples_dir.rglob(filename):
                        source_file = example_file
                        break

                if source_file:
                    shutil.copy(source_file, dest_file)
                    print(f"   已复制数据文件: {filename}")
                else:
                    print(f"   ⚠️ 未找到数据文件: {filename}")

        except Exception as e:
            print(f"复制数据文件时出错: {e}")

    def run_with_auto_fix(self, input_file_path: str, session_id: str,
                          timeout: int = 300, num_cores: int = 1,
                          max_steps: int = None, max_fix_attempts: int = 10,
                          on_fix_callback: Callable = None, max_memory_gb: float = None) -> Generator:
        """
        运行SPARTA，失败时自动尝试修复

        Args:
            input_file_path: 输入文件路径
            session_id: 会话ID
            timeout: 超时时间（秒）
            num_cores: CPU核数
            max_steps: 最大步数
            max_fix_attempts: 最大修复尝试次数
            on_fix_callback: 修复回调函数，接收(error_info, attempt)返回fix_result
            max_memory_gb: 最大内存限制（GB）

        Yields:
            执行事件
        """
        from error_fixer import SPARTAErrorFixer
        from version_manager import VersionManager

        fixer = SPARTAErrorFixer()
        vm = VersionManager()

        attempt = 0
        last_result = None

        while attempt <= max_fix_attempts:
            yield {
                "type": "status",
                "message": f"🚀 执行SPARTA (尝试 {attempt + 1}/{max_fix_attempts + 1})..."
            }

            # 运行SPARTA
            result = self.run(input_file_path, session_id, timeout, num_cores, max_steps, max_memory_gb)
            last_result = result

            if result["status"] == "success":
                yield {
                    "type": "success",
                    "message": f"✅ SPARTA执行成功 (尝试 {attempt + 1}次)",
                    "result": result
                }
                return

            # 执行失败，尝试修复
            if attempt >= max_fix_attempts:
                yield {
                    "type": "error",
                    "message": f"❌ 达到最大修复尝试次数 ({max_fix_attempts})，无法自动修复",
                    "result": result
                }
                return

            # 读取日志文件
            session_dir = self.sessions_dir / session_id if hasattr(self, 'sessions_dir') else Path(result.get("session_dir", ""))
            log_file = session_dir / "log.sparta"
            log_content = ""
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()

            # 解析错误
            yield {"type": "status", "message": "🔍 分析错误原因..."}
            error_info = fixer.parse_error(log_content, result.get("stderr", ""))

            if not error_info.get("has_error"):
                yield {
                    "type": "error",
                    "message": "❌ 无法识别错误类型，无法自动修复",
                    "result": result
                }
                return

            yield {
                "type": "error_detected",
                "message": f"🔧 检测到错误: {error_info.get('error_type')}",
                "error_info": error_info
            }

            # 搜索解决方案
            yield {"type": "status", "message": "📖 搜索解决方案..."}
            search_results = fixer.search_solution(error_info)

            # 读取当前输入文件
            input_file = session_dir / "input.sparta"
            with open(input_file, 'r', encoding='utf-8') as f:
                current_input = f.read()

            # 生成修复
            yield {"type": "status", "message": "🤖 生成修复方案..."}
            fix_result = None

            for event in fixer.generate_fix(current_input, error_info, search_results):
                if event.get("type") == "fix_generated":
                    fix_result = event
                elif event.get("type") == "status":
                    yield event

            if not fix_result or not fix_result.get("fixed_content"):
                yield {
                    "type": "error",
                    "message": "❌ 无法生成修复方案",
                    "result": result
                }
                return

            # 应用修复
            yield {"type": "status", "message": "📝 应用修复并创建新版本..."}
            apply_result = fixer.apply_fix(
                session_id,
                fix_result["fixed_content"],
                error_info,
                fix_result.get("explanation", "")
            )

            if not apply_result.get("success"):
                yield {
                    "type": "error",
                    "message": f"❌ 应用修复失败: {apply_result.get('message')}",
                    "result": result
                }
                return

            yield {
                "type": "fix_applied",
                "message": f"✅ 已创建版本 v{apply_result.get('version')}",
                "version": apply_result.get("version"),
                "changes": fix_result.get("changes", []),
                "input_file": fix_result.get("fixed_content", "")  # 传递更新后的输入文件内容
            }

            # 如果有外部回调，调用它
            if on_fix_callback:
                callback_result = on_fix_callback(error_info, attempt)
                if callback_result and not callback_result.get("continue", True):
                    yield {
                        "type": "error",
                        "message": "❌ 修复被外部回调中止",
                        "result": result
                    }
                    return

            attempt += 1

        # 不应该到达这里
        yield {
            "type": "error",
            "message": "❌ 自动修复失败",
            "result": last_result
        }

    def get_log_content(self, session_id: str) -> str:
        """获取会话的日志内容"""
        base_dir = Path(__file__).parent.parent
        session_dir = base_dir / "llm-chat-app" / "data" / "dsmc_sessions" / session_id
        log_file = session_dir / "log.sparta"

        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""


# 测试代码
if __name__ == "__main__":
    # 创建测试输入文件
    test_input = """# Simple 2D DSMC test
dimension       2
boundary        p p p
create_box      0 10 0 10 -0.5 0.5
create_grid     20 20 1
species         air.species N2
mixture         air N2 vstream 0.0 0 0 temp 300.0
global          fnum 1e20
collide         vss air air.vss
stats           10
run             100
"""

    runner = SPARTARunner()

    if runner.executable:
        print(f"找到SPARTA可执行文件: {runner.executable}")
        print("\n提示：实际运行需要有效的输入文件和species数据文件")
    else:
        print("未找到SPARTA可执行文件")
        print("请先运行: python sparta_installer.py")
