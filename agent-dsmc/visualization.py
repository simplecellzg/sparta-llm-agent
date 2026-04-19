"""
结果可视化器
============

解析SPARTA输出并生成可视化图表。
所有图形标注使用英文以避免中文字体乱码问题。
"""

import base64
import io
from pathlib import Path
from typing import Dict, List
import numpy as np


class DSMCVisualizer:
    """DSMC结果可视化器"""

    def __init__(self):
        """初始化可视化器"""
        self._setup_matplotlib()

    def _setup_matplotlib(self):
        """配置matplotlib"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # 非交互式后端
            import matplotlib.pyplot as plt

            # 使用英文字体，避免中文乱码
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
            plt.rcParams['axes.unicode_minus'] = False

        except Exception as e:
            print(f"⚠️ matplotlib配置失败: {e}")

    def process_output(self, run_result: Dict) -> Dict:
        """
        处理SPARTA输出并生成可视化

        Args:
            run_result: SPARTA运行结果

        Returns:
            {
                "summary": {...},
                "plots": [...],
                "data_tables": [...],
                "interpretation": str
            }
        """
        result = {
            "summary": run_result.get("summary", {}),
            "plots": [],
            "data_tables": [],
            "interpretation": ""
        }

        session_dir = Path(run_result["session_dir"])

        # 生成图表
        try:
            import matplotlib
            matplotlib.use('Agg')  # 非交互式后端
            import matplotlib.pyplot as plt

            # 1. 生成执行时间图
            if run_result.get("execution_time"):
                fig = self._plot_execution_time(run_result)
                if fig:
                    plot_idx = len(result["plots"])
                    image_url = self._fig_to_file(fig, session_dir, plot_idx)
                    result["plots"].append({
                        "title": "执行时间",
                        "image_url": image_url
                    })
                    plt.close(fig)

            # 2. 生成粒子统计图（如果有数据）
            if result["summary"].get("particles"):
                fig = self._plot_particle_stats(result["summary"])
                if fig:
                    plot_idx = len(result["plots"])
                    image_url = self._fig_to_file(fig, session_dir, plot_idx)
                    result["plots"].append({
                        "title": "仿真统计",
                        "image_url": image_url
                    })
                    plt.close(fig)

        except ImportError:
            print("⚠️ matplotlib未安装，跳过图表生成")

        # 生成LLM解释
        result["interpretation"] = self._generate_interpretation(result["summary"], run_result)

        return result

    def _plot_execution_time(self, run_result: Dict):
        """绘制执行时间图"""
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 4))

            exec_time = run_result.get("execution_time", 0)
            timesteps = run_result.get("summary", {}).get("timesteps", 1)

            if exec_time > 0:
                # 使用英文标签
                categories = ['Total Time', 'Avg Time/Step']
                xlabel = 'Time (seconds)'
                title = 'SPARTA Execution Time Analysis'

                values = [exec_time, exec_time / max(timesteps, 1)]

                ax.barh(categories, values, color=['#4CAF50', '#2196F3'])
                ax.set_xlabel(xlabel)
                ax.set_title(title)
                ax.grid(axis='x', alpha=0.3)

                # 添加数值标签
                for i, v in enumerate(values):
                    ax.text(v, i, f' {v:.4f}s', va='center')

                plt.tight_layout()
                return fig

        except Exception as e:
            print(f"绘图错误: {e}")

        return None

    def _plot_particle_stats(self, summary: Dict):
        """绘制粒子统计图"""
        try:
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

            # 左图：关键指标
            metrics = []
            values = []

            if summary.get("particles"):
                metrics.append('Particles')
                values.append(summary["particles"])

            if summary.get("cells"):
                metrics.append('Cells')
                values.append(summary["cells"])

            if summary.get("timesteps"):
                metrics.append('Timesteps')
                values.append(summary["timesteps"])

            if metrics:
                ax1.barh(metrics, values, color=['#FF9800', '#9C27B0', '#00BCD4'])
                ax1.set_title('Simulation Scale')
                ax1.set_xlabel('Count')
                ax1.grid(axis='x', alpha=0.3)

                # 添加数值标签
                for i, v in enumerate(values):
                    ax1.text(v, i, f' {v:,}', va='center')

            # 右图：饼图 - 网格利用率（示例）
            if summary.get("particles") and summary.get("cells"):
                particles_per_cell = summary["particles"] / summary["cells"]

                labels = ['Occupied Cells', 'Empty Cells (est.)']

                # 假设粒子均匀分布
                occupied_ratio = min(particles_per_cell / 10, 0.9)  # 简化估计
                sizes = [occupied_ratio * 100, (1 - occupied_ratio) * 100]
                colors = ['#4CAF50', '#E0E0E0']

                ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax2.set_title('Grid Utilization (est.)')

            plt.tight_layout()
            return fig

        except Exception as e:
            print(f"绘图错误: {e}")

        return None

    def _fig_to_base64(self, fig) -> str:
        """将matplotlib图表转换为base64编码"""
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()
            return img_base64
        except Exception as e:
            print(f"图表编码错误: {e}")
            return ""

    def _fig_to_file(self, fig, session_dir, idx: int) -> str:
        """将matplotlib图表保存为PNG文件，返回相对URL

        Args:
            fig: matplotlib图表对象
            session_dir: 会话目录路径
            idx: 图片索引号

        Returns:
            相对URL路径 (如 'images/plot_0.png')
        """
        try:
            images_dir = Path(session_dir) / 'images'
            images_dir.mkdir(parents=True, exist_ok=True)

            filename = f'plot_{idx}.png'
            file_path = images_dir / filename
            fig.savefig(str(file_path), format='png', dpi=100, bbox_inches='tight')

            return f'images/{filename}'
        except Exception as e:
            print(f"图表保存错误: {e}")
            return ""

    def _generate_interpretation(self, summary: Dict, run_result: Dict) -> str:
        """生成LLM结果解释"""
        from utils import call_llm

        # 构建分析提示词
        status = run_result.get("status", "unknown")
        exec_time = run_result.get("execution_time", 0)

        prompt = f"""作为DSMC仿真专家，分析以下SPARTA仿真结果：

状态: {status}
执行时间: {exec_time:.2f} 秒

仿真统计:
- 粒子数: {summary.get('particles', 'N/A')}
- 网格数: {summary.get('cells', 'N/A')}
- 时间步数: {summary.get('timesteps', 'N/A')}

请提供：
1. 关键发现（仿真是否正常完成）
2. 结果合理性分析（粒子数、网格划分是否合适）
3. 性能评估（执行时间是否合理）
4. 改进建议（如果有）

用中文回答，使用Markdown格式。"""

        try:
            interpretation = call_llm(prompt, temperature=0.5, max_tokens=8192)
            return interpretation
        except Exception as e:
            return f"## 仿真结果\n\n状态: {status}\n执行时间: {exec_time:.2f}秒\n\n粒子数: {summary.get('particles', 'N/A')}"


# 测试代码
if __name__ == "__main__":
    # 模拟运行结果
    test_result = {
        "status": "success",
        "execution_time": 15.3,
        "session_dir": "/tmp/test_session",
        "summary": {
            "particles": 100000,
            "cells": 5000,
            "timesteps": 1000,
            "final_time": 15.3
        }
    }

    visualizer = DSMCVisualizer()

    print("测试可视化器...")
    result = visualizer.process_output(test_result)

    print(f"生成图表数: {len(result['plots'])}")
    print(f"解释长度: {len(result['interpretation'])} 字符")

    if result['plots']:
        print("✅ 图表生成成功")
    else:
        print("⚠️ 未生成图表（可能缺少matplotlib）")
