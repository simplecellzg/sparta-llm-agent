#!/usr/bin/env python3
"""
SPARTA Installer
================

下载、编译和验证SPARTA DSMC软件安装。
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple


class SPARTAInstaller:
    """SPARTA安装器"""

    # SPARTA官方仓库
    SPARTA_REPO = "https://github.com/sparta/sparta.git"

    def __init__(self, install_dir: str = None):
        """
        初始化SPARTA安装器

        Args:
            install_dir: 安装目录，默认为 ../sparta
        """
        if install_dir is None:
            # 默认安装到agent_code/sparta
            self.install_dir = Path(__file__).parent.parent / "sparta"
        else:
            self.install_dir = Path(install_dir)

        self.src_dir = self.install_dir / "src"
        self.executable = None

    def download_sparta(self) -> Tuple[bool, str]:
        """
        从GitHub克隆SPARTA仓库

        Returns:
            (success: bool, message: str)
        """
        print(f"📥 正在从GitHub下载SPARTA...")
        print(f"   仓库: {self.SPARTA_REPO}")
        print(f"   目标目录: {self.install_dir}")

        # 如果目录已存在，检查是否为git仓库
        if self.install_dir.exists():
            if (self.install_dir / ".git").exists():
                print("⚠️  SPARTA目录已存在，正在更新...")
                try:
                    result = subprocess.run(
                        ["git", "pull"],
                        cwd=self.install_dir,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode == 0:
                        return True, "SPARTA已成功更新到最新版本"
                    else:
                        return False, f"Git更新失败: {result.stderr}"
                except Exception as e:
                    return False, f"更新失败: {str(e)}"
            else:
                return False, f"目录 {self.install_dir} 已存在但不是git仓库，请手动删除或指定其他目录"

        # 克隆仓库
        try:
            result = subprocess.run(
                ["git", "clone", self.SPARTA_REPO, str(self.install_dir)],
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            if result.returncode == 0:
                print("✅ SPARTA下载成功")
                return True, "SPARTA下载成功"
            else:
                error_msg = result.stderr or result.stdout
                return False, f"Git克隆失败: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "下载超时（超过10分钟），请检查网络连接"
        except FileNotFoundError:
            return False, "Git未安装，请先安装Git: sudo apt-get install git"
        except Exception as e:
            return False, f"下载失败: {str(e)}"

    def compile_sparta(self, mode: str = "serial") -> Tuple[bool, str]:
        """
        编译SPARTA

        Args:
            mode: 编译模式，可选 'serial'（单核）或 'mpi'（并行）

        Returns:
            (success: bool, message: str)
        """
        if not self.src_dir.exists():
            return False, f"源代码目录不存在: {self.src_dir}"

        print(f"\n🔨 正在编译SPARTA（{mode}模式）...")
        print(f"   源目录: {self.src_dir}")

        # 确定make目标
        if mode == "serial":
            make_target = "linux"  # 串行版本
            executable_name = "spa_linux"
        elif mode == "mpi":
            make_target = "mpi"  # MPI并行版本
            executable_name = "spa_mpi"
        else:
            return False, f"不支持的编译模式: {mode}，请使用 'serial' 或 'mpi'"

        try:
            # 清理之前的编译
            print("   清理之前的编译文件...")
            subprocess.run(
                ["make", "clean-all"],
                cwd=self.src_dir,
                capture_output=True,
                timeout=60
            )

            # 编译SPARTA
            print(f"   执行: make {make_target}")
            result = subprocess.run(
                ["make", "-j4", make_target],  # 使用4核并行编译
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            # 检查可执行文件是否生成
            self.executable = self.src_dir / executable_name

            if self.executable.exists():
                print(f"✅ SPARTA编译成功: {self.executable}")
                return True, f"编译成功: {executable_name}"
            else:
                # 编译失败，显示错误信息
                error_output = result.stderr or result.stdout
                print(f"❌ 编译失败")
                print(f"输出:\n{error_output[:500]}")  # 只显示前500字符
                return False, f"编译失败，未生成可执行文件\n错误信息:\n{error_output[:200]}"

        except subprocess.TimeoutExpired:
            return False, "编译超时（超过10分钟）"
        except FileNotFoundError:
            return False, "Make工具未安装，请先安装: sudo apt-get install build-essential"
        except Exception as e:
            return False, f"编译过程出错: {str(e)}"

    def verify_installation(self) -> Tuple[bool, str]:
        """
        验证SPARTA安装

        Returns:
            (success: bool, message: str)
        """
        if self.executable is None:
            # 尝试查找已编译的可执行文件
            for name in ["spa_linux", "spa_mpi"]:
                exe_path = self.src_dir / name
                if exe_path.exists():
                    self.executable = exe_path
                    break

        if self.executable is None or not self.executable.exists():
            return False, "找不到SPARTA可执行文件"

        print(f"\n✅ 正在验证安装...")
        print(f"   可执行文件: {self.executable}")

        try:
            # 运行SPARTA并获取版本信息
            result = subprocess.run(
                [str(self.executable), "-h"],  # 显示帮助信息
                capture_output=True,
                text=True,
                timeout=10
            )

            # 检查输出
            output = result.stdout + result.stderr
            if "SPARTA" in output or "sparta" in output.lower():
                version_info = output.split('\n')[0] if output else "未知版本"
                print(f"✅ SPARTA安装验证成功")
                print(f"   版本信息: {version_info}")
                return True, f"安装验证成功\n{version_info}"
            else:
                return False, "可执行文件存在但无法识别为SPARTA"

        except subprocess.TimeoutExpired:
            return False, "验证超时"
        except Exception as e:
            return False, f"验证失败: {str(e)}"

    def get_executable_path(self) -> str:
        """
        获取SPARTA可执行文件路径

        Returns:
            可执行文件的绝对路径
        """
        if self.executable and self.executable.exists():
            return str(self.executable.absolute())
        return None

    def install(self, mode: str = "serial") -> Dict[str, any]:
        """
        执行完整的安装流程：下载 + 编译 + 验证

        Args:
            mode: 编译模式（'serial' 或 'mpi'）

        Returns:
            {
                'success': bool,
                'steps': {
                    'download': (success, message),
                    'compile': (success, message),
                    'verify': (success, message)
                },
                'executable': str or None
            }
        """
        result = {
            'success': False,
            'steps': {},
            'executable': None
        }

        # 步骤1: 下载
        success, message = self.download_sparta()
        result['steps']['download'] = (success, message)
        if not success:
            return result

        # 步骤2: 编译
        success, message = self.compile_sparta(mode)
        result['steps']['compile'] = (success, message)
        if not success:
            return result

        # 步骤3: 验证
        success, message = self.verify_installation()
        result['steps']['verify'] = (success, message)
        if not success:
            return result

        # 所有步骤成功
        result['success'] = True
        result['executable'] = self.get_executable_path()

        return result


def main():
    """
    命令行入口
    """
    print("=" * 60)
    print("SPARTA DSMC Installer")
    print("=" * 60)

    installer = SPARTAInstaller()

    # 执行安装
    result = installer.install(mode="serial")

    print("\n" + "=" * 60)
    print("安装总结")
    print("=" * 60)

    for step_name, (success, message) in result['steps'].items():
        status = "✅" if success else "❌"
        print(f"{status} {step_name}: {message}")

    if result['success']:
        print(f"\n🎉 SPARTA安装成功!")
        print(f"   可执行文件: {result['executable']}")
        return 0
    else:
        print(f"\n❌ SPARTA安装失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
