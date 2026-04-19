"""
DSMC Agent - 主协调器（简化版）
================================

协调DSMC仿真的整个工作流程，支持自动错误修复和版本管理。
此版本为MVP（最小可行产品），提供核心功能。
支持迭代功能：自然语言修改和手动编辑。
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional
from keyword_detector import DSMCKeywordDetector
from utils import call_llm, call_llm_stream, generate_session_id, get_iso_timestamp, ensure_dir
from manual_searcher import SPARTAManualSearcher
from template_system import (
    get_template,
    get_template_by_geometry,
    get_template_for_geometry,
    list_templates,
    GEOMETRY_MAPPING,
    TEMPLATES
)


# ============== 迭代数据结构定义 ==============

def create_iteration_record(
    iteration_number: int,
    input_file: str,
    input_source: str,  # "generated" | "manual_edit" | "natural_language"
    modification_description: str = "",
    parent_iteration_id: str = None,
    parameter_reasoning: str = "",      # 参数选择依据
    initial_input_file: str = None      # 初始输入文件（修复前）
) -> Dict:
    """创建新的迭代记录"""
    return {
        "iteration_id": generate_session_id(),
        "iteration_number": iteration_number,
        "parent_iteration_id": parent_iteration_id,
        "timestamp": get_iso_timestamp(),
        "created_at": get_iso_timestamp(),
        "input_file": input_file,
        "initial_input_file": initial_input_file or input_file,  # 初始输入文件
        "input_source": input_source,
        "modification_description": modification_description,
        "parameter_reasoning": parameter_reasoning,  # 参数说明
        "run_params": {},
        "status": "pending",  # pending | running | completed | failed
        "run_result": {},
        "visualization": {},
        "fix_history": [],  # 修复历史记录
        "timing": {
            "generation_time": 0.0,
            "run_time": 0.0,
            "analysis_time": 0.0,
            "total_time": 0.0
        }
    }


def create_session_statistics() -> Dict:
    """创建会话统计信息"""
    return {
        "total_iterations": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "total_time": 0.0,
        "average_iteration_time": 0.0
    }


# 几何文件映射表 - 用于生成输入文件时指定正确的示例文件
# 路径相对于 SPARTA 可执行文件目录
# 重要：必须包含测试用例中使用的所有几何类型！
GEOMETRY_FILE_MAPPING = {
    # 3D 几何
    "sphere": "examples/sphere/data.sphere",
    "球体": "examples/sphere/data.sphere",
    "spiky": "examples/spiky/data.spiky",
    "尖刺": "examples/spiky/data.spiky",
    "cube": "examples/custom/data.cube",
    "立方体": "examples/custom/data.cube",
    # 2D 几何
    "cylinder": "examples/circle/data.circle",  # 2D 圆柱
    "圆柱": "examples/circle/data.circle",
    "circle": "examples/circle/data.circle",
    "圆": "examples/circle/data.circle",
    "plane": "examples/circle/data.plane1",
    "平面": "examples/circle/data.plane1",
    "step": "examples/step/data.step",
    "阶梯": "examples/step/data.step",
    # 特殊用途
    "beam": "examples/surf_collide/data.beam",
    "束流": "examples/surf_collide/data.beam",
    "etch": "examples/ablation/data.etch2d",
    "刻蚀": "examples/ablation/data.etch2d",
    "adsorb": "examples/surf_react_adsorb/data.beam",
    "吸附": "examples/surf_react_adsorb/data.beam",

    # ===== 新增：测试用例中使用的几何类型 =====
    # flat_plate 使用 circle 的数据文件（平板可以用圆的变体）
    "flat_plate": "examples/circle/data.circle",
    "平板": "examples/circle/data.circle",
    "plate": "examples/circle/data.circle",
    # box 使用 free 目录的几何（真空腔室）
    "box": "examples/free/data.free",
    "立方体": "examples/free/data.free",
    "vacuum": "examples/free/data.free",
    "真空": "examples/free/data.free",
}

# 禁止使用的几何文件名（用于提示词负面约束）
FORBIDDEN_GEOMETRY_FILES = [
    "data.plate",
    "data.plate.txt",
    "data.flat_plate",
    "data.flat_plate.txt",
    "data.box",
    "data.box.txt",
    "data.custom",
    "data.user_defined",
]

# 物种文件映射表 - 用于验证物种是否存在
# key: 物种文件名, value: 有效物种列表
SPECIES_FILE_MAPPING = {
    "air.species": ["O2", "N2", "O", "N", "NO", "O2+", "N2+", "O+", "N+", "NO+", "e"],
    "ar.species": ["Ar"],
    "6SpeciesAir.species": ["N2", "O2", "NO", "N", "O", "N2+", "O2+", "NO+"],
    "n2.species": ["N2"],
    "co2.species": ["CO2"],
    "he.species": ["He"],  # 氦气（如果存在）
}


class DSMCAgent:
    """DSMC代理 - 主协调器"""

    def __init__(self, max_fix_attempts: int = 10):
        """初始化DSMC代理

        Args:
            max_fix_attempts: 最大自动修复尝试次数
        """
        self.keyword_detector = DSMCKeywordDetector()
        self.max_fix_attempts = max_fix_attempts

        # 设置sessions目录
        self.sessions_dir = Path(__file__).parent.parent / "llm-chat-app" / "data" / "dsmc_sessions"
        ensure_dir(self.sessions_dir)

        # 初始化手册搜索器（使用优化的topk参数）
        self.manual_searcher = SPARTAManualSearcher(topk=25, chunk_topk=12)

    def detect_dsmc(self, message: str) -> Dict:
        """
        检测消息是否为DSMC相关

        Args:
            message: 用户消息

        Returns:
            检测结果
        """
        return self.keyword_detector.detect(message)

    def handle_dsmc_query(self, message: str, conversation_context: list = None) -> Generator:
        """
        处理DSMC查询（流式响应）

        Args:
            message: 用户消息
            conversation_context: 对话上下文

        Yields:
            响应事件
        """
        # 步骤1: 检测意图
        detection_result = self.detect_dsmc(message)

        yield {
            "type": "status",
            "message": f"🔍 检测到DSMC相关查询（置信度: {detection_result['confidence']:.0%}）"
        }

        # 步骤2: 根据意图处理
        intent = detection_result['intent']

        if intent == "learn":
            # 学习/查询意图 - 直接用LLM回答
            yield {"type": "status", "message": "🤖 正在查询DSMC相关信息..."}

            prompt = self._build_learning_prompt(message)

            full_response = ""
            for chunk in call_llm_stream(prompt):
                full_response += chunk
                yield {"type": "content", "content": chunk}

            yield {"type": "done", "done": True}

        elif intent == "generate":
            # 生成输入文件意图 - 显示参数表单
            yield {
                "type": "parameter_form",
                "message": "请配置DSMC仿真参数",
                "form": {
                    "temperature": {"label": "温度 (K)", "default": 300, "type": "number"},
                    "pressure": {"label": "压力 (Pa)", "default": 101325, "type": "number"},
                    "velocity": {"label": "速度 (m/s)", "default": 1000, "type": "number"},
                    "geometry": {
                        "label": "几何形状",
                        "default": "cylinder",
                        "type": "select",
                        "options": ["cylinder", "sphere", "flat_plate"]
                    },
                    "gas": {
                        "label": "气体类型",
                        "default": "N2",
                        "type": "select",
                        "options": ["N2", "O2", "Ar", "Air"]
                    }
                }
            }

        elif intent == "run":
            # 运行模拟意图
            yield {"type": "status", "message": "⚠️ 请先生成输入文件"}
            yield {
                "type": "content",
                "content": "要运行SPARTA模拟，请先说\"生成DSMC输入文件\"来配置参数。"
            }
            yield {"type": "done", "done": True}

        else:
            # 未知意图 - 提供帮助
            help_text = self._get_help_text()
            yield {"type": "content", "content": help_text}
            yield {"type": "done", "done": True}

    def generate_input_file(self, parameters: Dict, llm_files: list = None, workspace_files: list = None) -> Generator:
        """
        生成SPARTA输入文件（流式）

        Args:
            parameters: 仿真参数
            llm_files: LLM参考文件列表 [{filename, type, content}, ...]
            workspace_files: 工作目录文件列表 [{filename, type, temp_path}, ...]

        Yields:
            生成事件
        """
        start_time = time.time()
        step_times = {}

        step_start = time.time()
        yield {"type": "status", "message": "🔧 正在生成SPARTA输入文件...", "start_time": start_time}

        # NEW: Perform manual searches before generation (PARALLEL - async version)
        yield {"type": "status", "message": "📖 正在搜索SPARTA手册获取语法参考（并行检索中...）...", "elapsed": time.time() - start_time}
        step_start = time.time()

        # Use async version for parallel search (faster: ~3-5s vs ~15-20s)
        import asyncio
        manual_search_results = asyncio.run(
            self.manual_searcher.comprehensive_search_async(parameters)
        )
        step_times['手册搜索'] = time.time() - step_start

        yield {
            "type": "status",
            "message": f"✅ 手册搜索完成 (耗时: {step_times['手册搜索']:.2f}秒)",
            "elapsed": time.time() - start_time
        }

        # Build generation prompt with manual search results
        step_start = time.time()
        prompt = self._build_input_generation_prompt_with_manual_search(
            parameters,
            manual_search_results,
            llm_files
        )
        step_times['构建提示词'] = time.time() - step_start

        # 调用LLM生成输入文件
        generated_input = ""
        for chunk in call_llm_stream(prompt, temperature=0.3):
            generated_input += chunk

        # 提取代码块
        from utils import extract_code_block
        input_file = extract_code_block(generated_input)

        if not input_file:
            input_file = generated_input

        step_times['生成输入文件'] = time.time() - step_start

        # NEW: Fix geometry file references (后处理修复几何文件名)
        step_start = time.time()
        input_file = self._fix_geometry_file_references(input_file, parameters)
        step_times['几何文件修复'] = time.time() - step_start

        # NEW: Fix species references (后处理修复物种引用)
        step_start = time.time()
        input_file = self._fix_species_references(input_file, parameters, None)
        step_times['物种文件修复'] = time.time() - step_start

        # NEW: Validate and fix syntax after generation
        step_start = time.time()
        yield {"type": "status", "message": "🔍 正在验证语法并修复错误...", "elapsed": time.time() - start_time}

        errors = self.manual_searcher.detect_syntax_errors(input_file)
        if errors:
            yield {
                "type": "status",
                "message": f"⚠️ 发现 {len(errors)} 个语法问题，正在修复...",
                "elapsed": time.time() - start_time
            }

            input_file, fix_log = self.manual_searcher.fix_all_errors(input_file)

            yield {
                "type": "status",
                "message": f"✅ 语法修复完成 (修复了 {len(fix_log)} 个问题)",
                "elapsed": time.time() - start_time
            }

        step_times['语法验证修复'] = time.time() - step_start

        # 注释功能已禁用，保持输入文件清爽
        step_start = time.time()
        annotations = {}
        step_times['生成注释'] = time.time() - step_start

        # 生成参数依据说明
        step_start = time.time()
        yield {"type": "status", "message": "💡 正在生成参数说明...", "elapsed": time.time() - start_time}
        reasoning = self._generate_reasoning(parameters)
        step_times['生成参数说明'] = time.time() - step_start

        # 返回结果
        session_id = generate_session_id()
        total_time = time.time() - start_time

        # 创建首个迭代记录
        first_iteration = create_iteration_record(
            iteration_number=1,
            input_file=input_file,
            input_source="generated",
            modification_description="初始生成",
            parameter_reasoning=reasoning,      # 保存参数说明
            initial_input_file=input_file       # 初始版本就是自己
        )
        first_iteration["timing"] = {
            "generation_time": round(total_time, 2),
            "run_time": 0.0,
            "analysis_time": 0.0,
            "total_time": round(total_time, 2)
        }

        # 复制工作目录文件到会话目录
        if workspace_files:
            session_dir = self.sessions_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            for wf in workspace_files:
                temp_path = Path(wf.get('temp_path', ''))
                if temp_path.exists():
                    import shutil
                    dest_path = session_dir / wf.get('filename', temp_path.name)
                    shutil.copy2(temp_path, dest_path)
                    logger.info(f"复制工作目录文件: {temp_path} -> {dest_path}")

        # 先保存会话数据，确保前端获取迭代列表时数据已就绪
        self._save_session(session_id, {
            "session_id": session_id,
            "input_file": input_file,
            "annotations": annotations,
            "parameters": parameters,
            "timestamp": get_iso_timestamp(),
            "status": "generated",
            # 新增迭代相关字段
            "iterations": [first_iteration],
            "current_iteration_id": first_iteration["iteration_id"],
            "statistics": {
                "total_iterations": 1,
                "successful_runs": 0,
                "failed_runs": 0,
                "total_time": round(total_time, 2),
                "average_iteration_time": round(total_time, 2)
            },
            # 保存上传的文件信息
            "uploaded_files": {
                "llm_files": [{"filename": f.get("filename"), "type": f.get("type")} for f in (llm_files or [])],
                "workspace_files": [{"filename": f.get("filename"), "type": f.get("type")} for f in (workspace_files or [])]
            }
        })

        # 然后再yield done事件通知前端
        yield {
            "type": "done",
            "result": {
                "session_id": session_id,
                "input_file": input_file,
                "annotations": annotations,
                "parameter_reasoning": reasoning,
                "warnings": [],
                "timestamp": get_iso_timestamp(),
                "timing": {
                    "total_time": round(total_time, 2),
                    "steps": {k: round(v, 2) for k, v in step_times.items()}
                },
                # 新增迭代信息
                "iteration": first_iteration,
                "iteration_id": first_iteration["iteration_id"],
                "iteration_number": 1
            }
        }

    def stop_simulation(self, session_id: str) -> Dict:
        """
        停止正在运行的SPARTA仿真

        Args:
            session_id: 会话ID

        Returns:
            {"success": bool, "message": str}
        """
        from sparta_runner import SPARTARunner
        return SPARTARunner.stop_simulation(session_id)

    def is_simulation_running(self, session_id: str) -> bool:
        """
        检查仿真是否正在运行

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否正在运行
        """
        from sparta_runner import SPARTARunner
        return SPARTARunner.is_running(session_id)

    def run_simulation(self, session_id: str, num_cores: int = 4,
                        max_steps: int = None, auto_fix: bool = True,
                        max_memory_gb: float = None) -> Generator:
        """
        运行SPARTA仿真（流式），支持自动错误修复

        Args:
            session_id: 会话ID
            num_cores: CPU核数
            max_steps: 最大步数
            auto_fix: 是否启用自动错误修复
            max_memory_gb: 最大内存限制（GB），如果指定，将限制SPARTA进程的内存使用

        Yields:
            运行事件
        """
        memory_info = f", 内存限制: {max_memory_gb}GB" if max_memory_gb else ""
        yield {"type": "status", "message": f"🚀 正在准备SPARTA执行环境... (核数: {num_cores}{memory_info})"}

        # 加载会话数据
        session_data = self._load_session(session_id)
        if not session_data:
            yield {"type": "error", "error": "会话不存在"}
            return

        input_file = session_data.get("input_file")
        if not input_file:
            yield {"type": "error", "error": "输入文件不存在"}
            return

        # 创建临时文件
        session_dir = self.sessions_dir / session_id
        ensure_dir(session_dir)

        input_file_path = session_dir / "input.sparta"
        with open(input_file_path, 'w', encoding='utf-8') as f:
            f.write(input_file)

        # 运行SPARTA
        try:
            from sparta_runner import SPARTARunner
            runner = SPARTARunner()

            if auto_fix:
                # 使用自动修复模式
                yield {"type": "status", "message": "▶️ 正在运行SPARTA仿真（启用自动修复）..."}

                for event in runner.run_with_auto_fix(
                    str(input_file_path),
                    session_id,
                    num_cores=num_cores,
                    max_steps=max_steps,
                    max_fix_attempts=self.max_fix_attempts,
                    max_memory_gb=max_memory_gb
                ):
                    event_type = event.get("type")

                    if event_type == "status":
                        yield event
                    elif event_type == "error_detected":
                        yield {
                            "type": "status",
                            "message": f"🔧 {event.get('message')}"
                        }
                        yield {
                            "type": "error_info",
                            "error_info": event.get("error_info")
                        }
                    elif event_type == "fix_applied":
                        # 记录最新的输入文件内容
                        if event.get("input_file"):
                            session_data["input_file"] = event.get("input_file")

                            # 保存修复历史到当前迭代
                            iterations = session_data.get("iterations", [])
                            if iterations:
                                current_iter = iterations[-1]
                                if "fix_history" not in current_iter:
                                    current_iter["fix_history"] = []
                                current_iter["fix_history"].append({
                                    "attempt": event.get("version", 1),
                                    "error_type": event.get("error_type", ""),
                                    "fix_description": event.get("message", ""),
                                    "timestamp": get_iso_timestamp()
                                })
                                # 更新最终 input_file，保持 initial_input_file 不变
                                current_iter["input_file"] = event.get("input_file")
                                session_data["iterations"] = iterations

                            # 立即保存更新后的session数据
                            self._save_session(session_id, session_data)
                        yield {
                            "type": "fix_applied",
                            "message": event.get("message"),
                            "version": event.get("version"),
                            "changes": event.get("changes", []),
                            "error_type": event.get("error_type", ""),
                            "input_file": event.get("input_file", "")  # 转发给前端
                        }
                    elif event_type == "success":
                        run_result = event.get("result", {})
                        yield {"type": "status", "message": "📊 正在生成可视化结果..."}

                        # 可视化结果
                        visualization_result = self._visualize_results(run_result, session_data)

                        # 更新会话数据
                        session_data["status"] = "completed"
                        # 同时更新当前迭代的状态和结果
                        iterations = session_data.get("iterations", [])
                        if iterations:
                            iterations[-1]["status"] = "completed"
                            iterations[-1]["run_result"] = visualization_result  # 保存完整结果含plots
                            iterations[-1]["run_timestamp"] = get_iso_timestamp()
                            session_data["iterations"] = iterations
                        session_data["run_result"] = run_result
                        session_data["visualization"] = visualization_result
                        self._save_session(session_id, session_data)

                        yield {
                            "type": "done",
                            "result": visualization_result
                        }
                        return
                    elif event_type == "error":
                        # 自动修复失败
                        error_msg = event.get("message", "未知错误")
                        run_result = event.get("result", {})

                        session_data["status"] = "failed"
                        session_data["error"] = error_msg
                        self._save_session(session_id, session_data)

                        yield {
                            "type": "error",
                            "error": f"SPARTA执行失败: {error_msg}"
                        }
                        return

            else:
                # 普通模式（不自动修复）
                yield {"type": "status", "message": "▶️ 正在运行SPARTA仿真..."}

                run_result = runner.run(str(input_file_path), session_id,
                                        num_cores=num_cores, max_steps=max_steps,
                                        max_memory_gb=max_memory_gb)

                if run_result.get("status") == "failed":
                    error_msg = run_result.get("stderr", "未知错误")
                    yield {"type": "error", "error": f"SPARTA执行失败: {error_msg}"}

                    # 更新会话状态
                    session_data["status"] = "failed"
                    session_data["error"] = error_msg
                    self._save_session(session_id, session_data)
                    return

                yield {"type": "status", "message": "📊 正在生成可视化结果..."}

                # 可视化结果
                visualization_result = self._visualize_results(run_result, session_data)

                # 更新会话数据
                session_data["status"] = "completed"
                # 同时更新当前迭代的状态
                iterations = session_data.get("iterations", [])
                if iterations:
                    iterations[-1]["status"] = "completed"
                    session_data["iterations"] = iterations
                session_data["run_result"] = run_result
                session_data["visualization"] = visualization_result
                self._save_session(session_id, session_data)

                yield {
                    "type": "done",
                    "result": visualization_result
                }

        except FileNotFoundError:
            yield {
                "type": "error",
                "error": "SPARTA未安装。请先运行 python agent-dsmc/sparta_installer.py 安装SPARTA。"
            }
        except Exception as e:
            yield {"type": "error", "error": f"执行失败: {str(e)}"}

    def _visualize_results(self, run_result: Dict, session_data: Dict) -> Dict:
        """
        可视化仿真结果

        Args:
            run_result: SPARTA运行结果
            session_data: 会话数据

        Returns:
            可视化结果
        """
        try:
            from visualization import DSMCVisualizer
            visualizer = DSMCVisualizer()

            # 处理输出并生成可视化
            viz_result = visualizer.process_output(run_result)

            # 生成优化建议
            suggestions = self._generate_suggestions(run_result, session_data.get("parameters", {}))
            viz_result["suggestions"] = suggestions

            return viz_result

        except Exception as e:
            # 如果可视化失败，返回基本结果
            return {
                "summary": run_result.get("summary", {}),
                "plots": [],
                "interpretation": f"仿真已完成，但可视化失败: {str(e)}",
                "suggestions": []
            }

    def _generate_suggestions(self, run_result: Dict, parameters: Dict) -> list:
        """
        生成参数优化建议

        Args:
            run_result: 运行结果
            parameters: 当前参数

        Returns:
            建议列表
        """
        # 简化版：基于规则的建议
        suggestions = []

        summary = run_result.get("summary", {})

        # 示例建议规则
        execution_time = summary.get("execution_time", 0)
        if execution_time > 60:
            suggestions.append({
                "parameter": "网格密度",
                "current": "当前设置",
                "suggested": "减少网格数",
                "reason": f"执行时间较长 ({execution_time:.1f}秒)，建议减少网格以加快计算"
            })

        particles = summary.get("particles", 0)
        if particles < 1000:
            suggestions.append({
                "parameter": "粒子数",
                "current": f"{particles}",
                "suggested": "> 10000",
                "reason": "粒子数较少，可能影响统计精度，建议增加fnum"
            })

        return suggestions

    def _save_session(self, session_id: str, data: Dict):
        """保存会话数据"""
        session_dir = self.sessions_dir / session_id
        ensure_dir(session_dir)

        metadata_file = session_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_session(self, session_id: str) -> Dict:
        """加载会话数据"""
        metadata_file = self.sessions_dir / session_id / "metadata.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ============== 迭代管理方法 ==============

    def get_iterations(self, session_id: str) -> List[Dict]:
        """
        获取会话的所有迭代记录

        Args:
            session_id: 会话ID

        Returns:
            迭代记录列表
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return []
        return session_data.get("iterations", [])

    def get_iteration(self, session_id: str, iteration_id: str) -> Optional[Dict]:
        """
        获取单个迭代记录

        Args:
            session_id: 会话ID
            iteration_id: 迭代ID

        Returns:
            迭代记录或None
        """
        iterations = self.get_iterations(session_id)
        for iteration in iterations:
            if iteration.get("iteration_id") == iteration_id:
                return iteration
        return None

    def get_current_iteration(self, session_id: str) -> Optional[Dict]:
        """
        获取当前活跃的迭代

        Args:
            session_id: 会话ID

        Returns:
            当前迭代记录或None
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return None

        current_iteration_id = session_data.get("current_iteration_id")
        if not current_iteration_id:
            iterations = session_data.get("iterations", [])
            if iterations:
                return iterations[-1]  # 返回最后一个迭代
            return None

        return self.get_iteration(session_id, current_iteration_id)

    def create_iteration(
        self,
        session_id: str,
        input_file: str,
        source: str,
        description: str = ""
    ) -> Dict:
        """
        创建新迭代

        Args:
            session_id: 会话ID
            input_file: 输入文件内容
            source: 来源类型 ("generated" | "manual_edit" | "natural_language")
            description: 修改描述

        Returns:
            新创建的迭代记录
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return {"error": "Session not found"}

        iterations = session_data.get("iterations", [])
        current_iteration_id = session_data.get("current_iteration_id")

        iteration_number = len(iterations) + 1

        iteration = create_iteration_record(
            iteration_number=iteration_number,
            input_file=input_file,
            input_source=source,
            modification_description=description,
            parent_iteration_id=current_iteration_id
        )

        iterations.append(iteration)
        session_data["iterations"] = iterations
        session_data["current_iteration_id"] = iteration["iteration_id"]
        session_data["input_file"] = input_file  # 同步更新当前输入文件

        # 更新统计
        if "statistics" not in session_data:
            session_data["statistics"] = create_session_statistics()
        session_data["statistics"]["total_iterations"] = len(iterations)

        self._save_session(session_id, session_data)
        return iteration

    def update_iteration(
        self,
        session_id: str,
        iteration_id: str,
        updates: Dict
    ) -> bool:
        """
        更新迭代记录

        Args:
            session_id: 会话ID
            iteration_id: 迭代ID
            updates: 要更新的字段

        Returns:
            是否更新成功
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return False

        iterations = session_data.get("iterations", [])
        for i, iteration in enumerate(iterations):
            if iteration.get("iteration_id") == iteration_id:
                iterations[i].update(updates)
                session_data["iterations"] = iterations
                self._save_session(session_id, session_data)
                return True
        return False

    def update_current_iteration(
        self,
        session_id: str,
        input_file: str,
        description: str = ""
    ) -> Dict:
        """
        更新当前迭代的输入文件（不创建新迭代）

        Args:
            session_id: 会话ID
            input_file: 新的输入文件内容
            description: 修改描述

        Returns:
            更新后的迭代记录
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return {"error": "Session not found"}

        iterations = session_data.get("iterations", [])
        if not iterations:
            return {"error": "No iterations to update"}

        # 更新最后一个迭代
        current_iteration = iterations[-1]
        current_iteration["input_file"] = input_file
        current_iteration["modification_description"] = description
        current_iteration["timestamp"] = get_iso_timestamp()

        # 同步更新session的input_file
        session_data["input_file"] = input_file

        self._save_session(session_id, session_data)

        return current_iteration

    def delete_iteration(
        self,
        session_id: str,
        iteration_id: str,
        delete_files: bool = False
    ) -> Dict:
        """
        删除指定迭代

        Args:
            session_id: 会话ID
            iteration_id: 迭代ID
            delete_files: 是否同时删除磁盘文件

        Returns:
            操作结果
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return {"error": "Session not found"}

        iterations = session_data.get("iterations", [])

        # 查找并移除迭代
        iteration_to_delete = None
        new_iterations = []
        for iter in iterations:
            if iter.get("iteration_id") == iteration_id:
                iteration_to_delete = iter
            else:
                new_iterations.append(iter)

        if not iteration_to_delete:
            return {"error": "Iteration not found"}

        # 不允许删除最后一个迭代
        if len(new_iterations) == 0:
            return {"error": "Cannot delete the last iteration"}

        # 更新会话数据
        session_data["iterations"] = new_iterations

        # 重新编号迭代
        for i, iter in enumerate(new_iterations):
            iter["iteration_number"] = i + 1

        # 更新当前迭代ID为最后一个
        if new_iterations:
            session_data["current_iteration_id"] = new_iterations[-1]["iteration_id"]
            session_data["input_file"] = new_iterations[-1]["input_file"]

        # 更新统计
        if "statistics" in session_data:
            session_data["statistics"]["total_iterations"] = len(new_iterations)

        self._save_session(session_id, session_data)

        return {
            "success": True,
            "deleted_iteration_id": iteration_id,
            "remaining_iterations": len(new_iterations)
        }

    def get_session_statistics(self, session_id: str) -> Dict:
        """
        获取会话统计信息

        Args:
            session_id: 会话ID

        Returns:
            统计信息
        """
        session_data = self._load_session(session_id)
        if not session_data:
            return create_session_statistics()

        statistics = session_data.get("statistics", create_session_statistics())
        iterations = session_data.get("iterations", [])

        # 计算累计时间
        total_time = sum(
            iter.get("timing", {}).get("total_time", 0)
            for iter in iterations
        )
        statistics["total_time"] = round(total_time, 2)

        # 计算平均迭代时间
        if iterations:
            statistics["average_iteration_time"] = round(
                total_time / len(iterations), 2
            )

        return statistics

    def iterate_with_natural_language(
        self,
        session_id: str,
        modification_request: str
    ) -> Generator:
        """
        通过自然语言修改输入文件

        Args:
            session_id: 会话ID
            modification_request: 用户的修改需求描述

        Yields:
            修改事件
        """
        start_time = time.time()

        yield {"type": "status", "message": "🔄 正在加载当前输入文件..."}

        session_data = self._load_session(session_id)
        if not session_data:
            yield {"type": "error", "error": "会话不存在"}
            return

        current_input = session_data.get("input_file", "")
        if not current_input:
            yield {"type": "error", "error": "当前没有输入文件"}
            return

        yield {"type": "status", "message": "🤖 正在根据需求修改输入文件..."}

        prompt = f"""你是SPARTA DSMC仿真专家。请根据用户的修改需求，修改以下输入文件。

当前输入文件：
```sparta
{current_input}
```

用户修改需求：
{modification_request}

要求：
1. 只修改需要修改的部分
2. 保持其他内容不变
3. 确保语法正确
4. 用```sparta代码块返回完整的修改后的文件

请返回修改后的完整输入文件："""

        modified_input = ""
        for chunk in call_llm_stream(prompt, temperature=0.3):
            modified_input += chunk

        # 提取代码块
        from utils import extract_code_block
        new_input_file = extract_code_block(modified_input)
        if not new_input_file:
            new_input_file = modified_input

        generation_time = time.time() - start_time

        # 创建新迭代
        iteration = self.create_iteration(
            session_id,
            new_input_file,
            "natural_language",
            modification_request[:100]  # 截断过长的描述
        )

        # 更新迭代时间
        self.update_iteration(session_id, iteration["iteration_id"], {
            "timing": {
                "generation_time": round(generation_time, 2),
                "run_time": 0.0,
                "analysis_time": 0.0,
                "total_time": round(generation_time, 2)
            }
        })

        yield {
            "type": "done",
            "result": {
                "iteration": iteration,
                "input_file": new_input_file,
                "timing": {
                    "generation_time": round(generation_time, 2),
                    "total_time": round(generation_time, 2)
                }
            }
        }

    def create_manual_iteration(
        self,
        session_id: str,
        input_file: str,
        description: str = "手动编辑"
    ) -> Dict:
        """
        创建手动编辑的迭代

        Args:
            session_id: 会话ID
            input_file: 手动编辑后的输入文件内容
            description: 修改描述

        Returns:
            新创建的迭代记录
        """
        return self.create_iteration(
            session_id,
            input_file,
            "manual_edit",
            description
        )

    def validate_input_file(self, content: str) -> Dict:
        """
        验证SPARTA输入文件

        Args:
            content: 输入文件内容

        Returns:
            {
                'valid': bool,
                'syntax_errors': [{line, message}],
                'missing_dependencies': [filename],
                'dependencies': {'found': [], 'missing': []},
                'warnings': []
            }
        """
        import re

        result = {
            'valid': True,
            'syntax_errors': [],
            'missing_dependencies': [],
            'dependencies': {'found': [], 'missing': []},
            'warnings': []
        }

        lines = content.split('\n')

        # 1. 基本语法检查
        required_commands = ['dimension', 'create_box', 'create_grid', 'run']
        found_commands = set()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # 提取命令名
            parts = stripped.split()
            if parts:
                cmd = parts[0]
                found_commands.add(cmd)

                # 检查常见语法错误
                if cmd in ['species', 'collide', 'read_surf'] and len(parts) < 2:
                    result['syntax_errors'].append({
                        'line': i,
                        'message': f'命令 {cmd} 缺少必要参数'
                    })

        # 检查必需命令
        for cmd in required_commands:
            if cmd not in found_commands:
                result['warnings'].append(f'缺少建议命令: {cmd}')

        # 2. 依赖文件检查
        data_files = set()

        # species 文件
        species_matches = re.findall(r'^\s*species\s+(\S+)', content, re.MULTILINE)
        data_files.update(species_matches)

        # VSS 文件
        vss_matches = re.findall(r'^\s*collide\s+vss\s+\S+\s+(\S+)', content, re.MULTILINE)
        data_files.update(vss_matches)

        # surf 文件
        surf_matches = re.findall(r'^\s*read_surf\s+(\S+)', content, re.MULTILINE)
        data_files.update(surf_matches)

        # 检查依赖文件是否存在
        sparta_data_dir = Path(__file__).parent.parent / "sparta" / "data"
        sparta_examples_dir = Path(__file__).parent.parent / "sparta" / "examples"

        for filename in data_files:
            found = False

            # 在标准位置查找
            if (sparta_data_dir / filename).exists():
                found = True
            else:
                # 在examples中搜索
                for example_file in sparta_examples_dir.rglob(filename):
                    found = True
                    break

            if found:
                result['dependencies']['found'].append(filename)
            else:
                result['dependencies']['missing'].append(filename)
                result['missing_dependencies'].append(filename)

        # 设置最终验证状态
        if result['syntax_errors'] or result['missing_dependencies']:
            result['valid'] = False

        return result

    def create_session_from_uploaded_file(
        self,
        conversation_id: str,
        input_content: str,
        source: str = 'uploaded'
    ) -> Dict:
        """
        从上传的输入文件创建新DSMC会话

        Args:
            conversation_id: 对话ID
            input_content: 输入文件内容
            source: 来源标识

        Returns:
            新会话信息
        """
        session_id = generate_session_id()

        # 创建会话目录
        session_dir = self.sessions_dir / session_id
        ensure_dir(session_dir)

        # 保存输入文件
        input_file_path = session_dir / "input.sparta"
        with open(input_file_path, 'w', encoding='utf-8') as f:
            f.write(input_content)

        # 创建初始迭代记录
        iteration = create_iteration_record(
            iteration_number=1,
            input_file=input_content,
            input_source=source,
            modification_description="从上传文件创建",
            parameter_reasoning="用户直接上传的输入文件"
        )

        # 创建会话元数据
        session_data = {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "created_at": get_iso_timestamp(),
            "input_file": input_content,
            "source": source,
            "iterations": [iteration],
            "current_iteration_id": iteration["iteration_id"],
            "statistics": create_session_statistics()
        }
        session_data["statistics"]["total_iterations"] = 1

        self._save_session(session_id, session_data)

        return {
            "session_id": session_id,
            "iteration": iteration
        }

    def _build_learning_prompt(self, question: str) -> str:
        """构建学习型提示词"""
        return f"""你是SPARTA DSMC（Direct Simulation Monte Carlo）仿真专家。请回答以下问题：

问题: {question}

要求：
- 用中文回答
- 清晰准确，适合初学者理解
- 如涉及技术细节，提供简要示例
- 使用Markdown格式

请回答："""

    def _build_input_generation_prompt(self, parameters: Dict, llm_files: list = None) -> str:
        """构建输入文件生成提示词（增强版）"""

        # 获取几何文件提示
        geometry = parameters.get('geometry', '')
        dimension = parameters.get('dimension', 2)
        geometry_hint = self._get_geometry_file_hint(geometry)
        template_hint = self._get_template_hint(geometry, dimension)

        # 基础参数
        prompt_parts = [f"""你是专门从事SPARTA的DSMC仿真专家助手。
你的任务是根据用户需求生成语法正确且物理有意义的SPARTA输入文件。

关键指南:
- 确保所有命令使用正确的SPARTA语法
- 选择物理上合理的参数(时间步长、单元尺寸等)
- 包含用于分析的全面输出命令
- 添加解释参数选择的注释

=== 用户需求 ===

基础参数:
- 温度: {parameters.get('temperature', 300)} K
- 压力: {parameters.get('pressure', 101325)} Pa
- 速度: {parameters.get('velocity', 1000)} m/s
- 几何: {parameters.get('geometry', 'cylinder')}
- 气体: {parameters.get('gas', 'N2')}"""]

        # 添加几何文件提示（关键改进）
        if geometry_hint:
            prompt_parts.append(geometry_hint)
            # 添加负面约束：禁止使用的文件名
            prompt_parts.append("""
=== ⚠️ 重要：禁止使用的几何文件名 ===
绝对不要使用以下文件名，这些文件不存在:
- data.plate / data.plate.txt
- data.flat_plate / data.flat_plate.txt
- data.box / data.box.txt
- data.custom / data.user_defined
只允许使用上面指定的正确几何文件！
""")

        # 添加模板提示（关键改进）
        if template_hint:
            prompt_parts.append(template_hint)

        # 添加高级参数（如果有）
        if 'boundary' in parameters:
            boundary = parameters['boundary']
            prompt_parts.append(f"""
边界条件:
- 入口类型: {boundary.get('inletType', 'freestream')}
- 出口类型: {boundary.get('outletType', 'outflow')}
- 壁面条件: {boundary.get('wallCondition', 'diffuse')}
- 壁面温度: {boundary.get('wallTemp', 300)} K""")

        if 'timeGrid' in parameters:
            tg = parameters['timeGrid']
            prompt_parts.append(f"""
时间与网格:
- 时间步长: {tg.get('timestep', '1e-7')} s
- 模拟时间: {tg.get('simTime', '1e-4')} s
- 网格分辨率: {tg.get('gridResolution', 'medium')}""")
            if tg.get('gridResolution') == 'custom':
                prompt_parts.append(f"- 网格尺寸: {tg.get('gridSize', '0.01')} m")

        if 'collision' in parameters:
            col = parameters['collision']
            prompt_parts.append(f"""
碰撞与粒子:
- 碰撞模型: {col.get('collisionModel', 'vhs')}
- 粒子权重因子: {col.get('fnum', '1e10')}
- 初始粒子数: {col.get('nparticles', 10000)}""")

        if 'output' in parameters:
            out = parameters['output']
            prompt_parts.append(f"""
输出控制:
- 输出频率: {out.get('dumpFreq', 100)} 步
- 统计采样开始: {out.get('statsStart', 500)} 步
- 输出变量: {', '.join(out.get('outputVars', ['density', 'velocity', 'temperature', 'pressure']))}""")

        # 添加自定义设定
        custom_input = parameters.get('customInput', '')
        if custom_input:
            prompt_parts.append(f"""
用户自定义要求:
{custom_input}""")

        # 添加LLM参考文件
        if llm_files:
            for f in llm_files:
                file_type = f.get('type', 'other')
                filename = f.get('filename', 'unknown')
                content = f.get('content', '')

                if file_type == 'input':
                    prompt_parts.append(f"""
参考SPARTA输入文件 ({filename}):
```
{content[:8000]}
```
请基于此文件进行修改或参考其格式和结构。""")
                elif file_type == 'reference':
                    prompt_parts.append(f"""
参考资料 ({filename}):
{content[:5000]}

请参考上述资料中的相关信息。""")

        # 增强的输出格式规范（关键改进）
        prompt_parts.append("""
=== 要求的输出格式 ===
生成完整的SPARTA输入文件,包含以下9个部分:

1. 头部注释
   - 仿真描述、日期、主要参数列表

2. 维度和单位规范
   - dimension 命令

3. 物种定义
   - species 命令（气体种类、分子参数）

4. 几何和网格设置
   - create_box 命令
   - create_grid 命令
   - read_surf 命令（如使用表面几何）

5. 初始化
   - create_particles 命令

6. 碰撞模型配置
   - collide 命令（VHS/VSS/HS）

7. 边界条件
   - boundary 命令

8. 统计采样和输出命令
   - compute 命令
   - stats_style 命令
   - dump 命令

9. 时间步长和运行命令
   - timestep 命令
   - run 命令

=== 后续说明（必须包含） ===

在输入文件后,提供以下信息:

1. 参数说明
   - 时间步长选择理由（应满足稳定性条件 Δt < 0.1×λ/v）
   - 网格尺寸选择（应满足网格收敛性 Δx < 0.1~0.5×λ）
   - 每单元粒子数（应 > 10 保证统计可靠性）

2. 预期运行时间
   - 基于问题规模的粗略估计

3. 建议检查项
   - 监控什么变量以确保物理正确性

请生成SPARTA输入文件（用```sparta代码块包裹）：""")

        return "\n".join(prompt_parts)

    def _build_input_generation_prompt_with_manual_search(
        self,
        parameters: Dict,
        manual_search_results: Dict,
        llm_files: list = None
    ) -> str:
        """
        构建包含手册搜索结果的输入文件生成提示词（增强版）

        Args:
            parameters: 用户参数
            manual_search_results: 手册搜索结果
            llm_files: LLM参考文件

        Returns:
            完整提示词
        """
        # 获取几何文件提示
        geometry = parameters.get('geometry', '')
        dimension = parameters.get('dimension', 2)
        geometry_hint = self._get_geometry_file_hint(geometry)
        template_hint = self._get_template_hint(geometry, dimension)

        # Format manual search results for LLM
        manual_context = self.manual_searcher.format_for_llm(manual_search_results)

        # Build prompt with manual context first
        prompt_parts = [f"""你是专门从事SPARTA的DSMC仿真专家助手。
你的任务是根据用户需求和检索到的知识生成语法正确且物理有意义的SPARTA输入文件。

关键指南:
- 优先考虑SPARTA手册信息
- 确保所有命令使用正确的SPARTA语法
- 选择物理上合理的参数(时间步长、单元尺寸等)
- 包含用于分析的全面输出命令
- 添加解释参数选择的注释

=== SPARTA手册参考 ===

{manual_context}

=== ⚠️ 重要：物种文件知识库（必须遵守）===

## 可用的物种文件（位于 sparta/data/ 目录）

| 气体类型 | 物种文件 | VSS文件 | 包含的物种 |
|---------|---------|---------|-----------|
| 空气(Air) | air.species | air.vss | O2, N2, O, N, NO |
| 氩气(Ar) | ar.species | ar.vss | Ar |
| 氦气(He) | he.species | he.vss | He |
| CO2 | co2.species | co2.vss | CO2 |
| 火星大气 | mars.species | mars.vss | CO2, N2, Ar |

## species命令格式（严格遵守）
```
species <species_file> <vss_file> <species1> <species2> ...
```

## 正确示例
```
# 单一气体（氩气）
species ar.species ar.vss Ar

# 空气（N2+O2混合）
species air.species air.vss N2 O2

# 氦气
species he.species he.vss He
```

## ⛔ 禁止使用以下文件名（不存在！）
- species.data, data.species
- ../data/species.data, data/species.data
- argon.species, helium.species
- 任何带路径的物种文件

=== ⚠️ 重要：命令顺序（严格遵守）===

SPARTA命令必须按以下顺序执行：

```
1. dimension 2 或 dimension 3          # 必须第一行
2. boundary <type> <type> ...          # 必须在create_box之前
3. create_box <xlo> <xhi> <ylo> <yhi> [zlo] [zhi]  # 定义计算域
4. create_grid <Nx> <Ny> [Nz]          # 创建网格
5. species <file> <vss_file> <species> # 定义物种（在collide之前！）
6. collide <ID> <style> <species_file> <params>  # 碰撞模型
7. read_surf <file>                    # 读取几何表面（如有）
8. group <ID> region <region>          # 定义组（在compute grid之前！）
9. seed <seed_value>                   # 随机种子（在create_particles之前！）
10. create_particles <params>          # 创建粒子
11. compute <ID> grid <group-ID> <values>  # 统计计算
12. timestep <dt>                      # 时间步长
13. run <steps>                        # 运行
```

=== ⚠️ 重要：常见错误预防 ===

## 错误1：compute grid group ID 不存在
❌ 错误代码:
```
compute 1 grid all n rho temp
```
原因：group "all" 未定义
✅ 正确代码:
```
group all region all
compute 1 grid all n rho temp
```

## 错误2：species file 找不到
❌ 错误代码:
```
species species.data Ar
species ../data/air.species N2 O2
```
✅ 正确代码:
```
species ar.species ar.vss Ar
species air.species air.vss N2 O2
```

## 错误3：seed command 缺失
❌ 错误：直接使用 create_particles
✅ 正确：先 seed 再 create_particles
```
seed 12345
create_particles ...
```

## 错误4：Unknown command
SPARTA没有以下命令，绝对不要使用：
- reset_stats（不存在！）
- clear_stats（不存在！）
- 其他非标准命令

=== 用户需求 ===

基础参数:
- 温度: {parameters.get('temperature', 300)} K
- 压力: {parameters.get('pressure', 101325)} Pa
- 速度: {parameters.get('velocity', 1000)} m/s
- 几何: {parameters.get('geometry', 'cylinder')}
- 气体: {parameters.get('gas', 'N2')}
- 碰撞模型: {parameters.get('collision_model', 'VSS')}"""]

        # 添加几何文件提示（关键改进）
        if geometry_hint:
            prompt_parts.append(geometry_hint)
            # 添加负面约束：禁止使用的文件名
            prompt_parts.append("""
=== ⚠️ 重要：禁止使用的几何文件名 ===
绝对不要使用以下文件名，这些文件不存在:
- data.plate / data.plate.txt
- data.flat_plate / data.flat_plate.txt
- data.box / data.box.txt
- data.custom / data.user_defined
只允许使用上面指定的正确几何文件！
""")

        # 添加模板提示（关键改进）
        if template_hint:
            prompt_parts.append(template_hint)

        # Add existing advanced parameters handling
        if 'boundary' in parameters:
            boundary = parameters['boundary']
            prompt_parts.append(f"""
边界条件:
- 入口类型: {boundary.get('inletType', 'freestream')}
- 出口类型: {boundary.get('outletType', 'outflow')}
- 壁面条件: {boundary.get('wallCondition', 'diffuse')}
- 壁面温度: {boundary.get('wallTemp', 300)} K""")

        if 'timeGrid' in parameters:
            tg = parameters['timeGrid']
            prompt_parts.append(f"""
时间与网格:
- 时间步长: {tg.get('timestep', '1e-7')} s
- 模拟时间: {tg.get('simTime', '1e-4')} s
- 网格分辨率: {tg.get('gridResolution', 'medium')}""")
            if tg.get('gridResolution') == 'custom':
                prompt_parts.append(f"- 网格尺寸: {tg.get('gridSize', '0.01')} m")

        if 'collision' in parameters:
            col = parameters['collision']
            prompt_parts.append(f"""
碰撞与粒子:
- 碰撞模型: {col.get('collisionModel', 'vhs')}
- 粒子权重因子: {col.get('fnum', '1e10')}
- 初始粒子数: {col.get('nparticles', 10000)}""")

        if 'output' in parameters:
            out = parameters['output']
            prompt_parts.append(f"""
输出控制:
- 输出频率: {out.get('dumpFreq', 100)} 步
- 统计采样开始: {out.get('statsStart', 500)} 步
- 输出变量: {', '.join(out.get('outputVars', ['density', 'velocity', 'temperature', 'pressure']))}""")

        # Add custom input
        custom_input = parameters.get('customInput', '')
        if custom_input:
            prompt_parts.append(f"""
用户自定义要求:
{custom_input}""")

        # Add LLM files if provided
        if llm_files:
            for f in llm_files:
                file_type = f.get('type', 'other')
                filename = f.get('filename', 'unknown')
                content = f.get('content', '')

                if file_type == 'input':
                    prompt_parts.append(f"""
参考SPARTA输入文件 ({filename}):
```
{content[:8000]}
```
请基于此文件进行修改或参考其格式和结构。""")
                elif file_type == 'reference':
                    prompt_parts.append(f"""
参考资料 ({filename}):
{content[:5000]}

请参考上述资料中的相关信息。""")

        # 增强的输出格式规范（关键改进）
        prompt_parts.append("""
=== 要求的输出格式 ===
生成完整的SPARTA输入文件,包含以下9个部分:

1. 头部注释
   - 仿真描述、日期、主要参数列表

2. 维度和单位规范
   - dimension 命令

3. 物种定义
   - species 命令（气体种类、分子参数）

4. 几何和网格设置
   - create_box 命令
   - create_grid 命令
   - read_surf 命令（如使用表面几何，必须使用上面指定的几何文件！）

5. 初始化
   - create_particles 命令

6. 碰撞模型配置
   - collide 命令（VHS/VSS/HS）

7. 边界条件
   - boundary 命令

8. 统计采样和输出命令
   - compute 命令
   - stats_style 命令
   - dump 命令

9. 时间步长和运行命令
   - timestep 命令
   - run 命令

=== 后续说明（必须包含） ===

在输入文件后,提供以下信息:

1. 参数说明
   - 时间步长选择理由（应满足稳定性条件 Δt < 0.1×λ/v）
   - 网格尺寸选择（应满足网格收敛性 Δx < 0.1~0.5×λ）
   - 每单元粒子数（应 > 10 保证统计可靠性）

2. 预期运行时间
   - 基于问题规模的粗略估计

3. 建议检查项
   - 监控什么变量以确保物理正确性

请生成SPARTA输入文件（用```sparta代码块包裹）：""")

        return "\n".join(prompt_parts)

    def _get_geometry_file_hint(self, geometry: str) -> str:
        """获取几何文件提示 - 告诉LLM使用哪个示例几何文件"""
        if not geometry:
            return ""

        geometry_lower = geometry.lower().strip()
        if geometry_lower in GEOMETRY_FILE_MAPPING:
            file_path = GEOMETRY_FILE_MAPPING[geometry_lower]
            filename = Path(file_path).name
            return f"""
=== 重要: 几何文件 ===
请使用以下 SPARTA 示例中的几何文件，不要自行创建或使用不存在的文件名:
- 几何类型: {geometry}
- 使用文件: {filename}
- 完整路径: {file_path}
- 使用方法: 在输入文件中使用 "read_surf {filename}"
- 注意: 确保文件在运行目录中，或使用相对于SPARTA的路径
"""
        return ""

    def _get_template_hint(self, geometry: str, dimension: int = 2) -> str:
        """获取模板提示 - 提供参考示例"""
        template = get_template_for_geometry(geometry, dimension)
        if not template:
            return ""

        # 尝试读取模板输入文件内容作为参考
        template_content = ""
        if template.input_file_path.exists():
            try:
                with open(template.input_file_path, 'r') as f:
                    content = f.read()
                    # 只取前100行作为参考
                    lines = content.split('\n')[:100]
                    template_content = '\n'.join(lines)
            except:
                pass

        hint = f"""
=== 参考模板 ===
推荐使用以下经过验证的模板作为参考:
- 模板名称: {template.name} ({template.name_zh})
- 描述: {template.description}
- 示例目录: examples/{template.example_dir}
- 输入文件: {template.input_file}
- 维度: {template.dimension}D
- 几何类型: {template.geometry_type}
"""
        if template_content:
            hint += f"""
=== {template.input_file} 参考内容 ===
```
{template_content}
```
"""

        return hint

    def _fix_geometry_file_references(self, input_file: str, parameters: Dict) -> str:
        """修复生成输入文件中的几何文件名引用

        后处理：自动检测并修复错误的几何文件名
        核心功能：解决LLM不遵循几何文件提示的问题
        """
        import re

        # 获取正确的几何文件名
        geometry = parameters.get('geometry', '').lower().strip()

        # 解析 dimension - 可能是字符串 "2d"/"3d" 或整数 2/3
        dim_value = parameters.get('dimension', 2)
        if isinstance(dim_value, str):
            dimension = 3 if '3' in dim_value else 2
        else:
            dimension = int(dim_value) if dim_value else 2

        # special handling for box geometry (vacuum chamber)
        # box doesn't need read_surf - it's a pure box simulation
        if geometry == 'box':
            # Remove any read_surf commands for box geometry
            fixed_input = re.sub(r'^\s*read_surf\s+.*\n?', '', input_file, flags=re.MULTILINE | re.IGNORECASE)
            # Ensure create_box is large enough
            if dimension == 3:
                fixed_input = re.sub(
                    r'create_box\s+[-\d.eE]+\s+[-\d.eE]+.*',
                    'create_box -10 10 -10 10 -10 10',
                    fixed_input,
                    flags=re.IGNORECASE
                )
            else:
                fixed_input = re.sub(
                    r'create_box\s+[-\d.eE]+\s+[-\d.eE]+.*',
                    'create_box -10 10 -10 10',
                    fixed_input,
                    flags=re.IGNORECASE
                )
            return fixed_input

        correct_file = GEOMETRY_FILE_MAPPING.get(geometry, "")

        # 如果没有映射，使用默认处理
        if not correct_file:
            # 尝试根据dimension推断
            if dimension == 3:
                correct_file = "examples/sphere/data.sphere"
            else:
                correct_file = "examples/circle/data.circle"

        # 提取文件名（不含路径）
        correct_filename = Path(correct_file).name

        # 检测并替换错误的几何文件名
        # 匹配模式：read_surf 后的各种错误文件名
        patterns_to_fix = [
            (r'read_surf\s+data\.plate(?:\.txt)?', f'read_surf {correct_filename}'),
            (r'read_surf\s+data\.flat_plate(?:\.txt)?', f'read_surf {correct_filename}'),
            (r'read_surf\s+data\.box(?:\.txt)?', f'read_surf {correct_filename}'),
            (r'read_surf\s+data\.custom(?:\.txt)?', f'read_surf {correct_filename}'),
            (r'read_surf\s+data\.\w+(?:\.txt)?', f'read_surf {correct_filename}'),  # 替换其他未知文件
        ]

        fixed_input = input_file
        for pattern, replacement in patterns_to_fix:
            fixed_input = re.sub(pattern, replacement, fixed_input, flags=re.IGNORECASE)

        # 确保 create_box 范围足够大（覆盖几何）
        if dimension == 3:
            # 3D 需要更大的范围
            if 'create_box' in fixed_input:
                fixed_input = re.sub(
                    r'create_box\s+[-\d.eE]+\s+[-\d.eE]+.*',
                    'create_box -10 10 -10 10 -10 10',
                    fixed_input,
                    flags=re.IGNORECASE
                )
        else:
            # 2D - 统一使用足够大的范围
            if 'create_box' in fixed_input:
                fixed_input = re.sub(
                    r'create_box\s+[-\d.eE]+\s+[-\d.eE]+.*',
                    'create_box -10 10 -10 10',
                    fixed_input,
                    flags=re.IGNORECASE
                )

        return fixed_input

    def _fix_species_references(self, input_file: str, parameters: Dict, session_dir: Path = None) -> str:
        """修复生成输入文件中的物种引用

        后处理：自动检测并修复错误的物种引用
        核心功能：根据用户指定的gas参数，验证并修复species引用
        """
        import re

        # 1. 根据用户指定的gas参数确定正确的species文件
        gas = parameters.get('gas', 'air').lower().strip()

        # 气体到species文件的映射
        if 'ar' in gas and 'air' not in gas:
            # 用户明确指定氩气
            species_filename = "ar.species"
        elif 'he' in gas:
            # 氦气
            species_filename = "he.species"
        elif 'n2' in gas and 'air' not in gas:
            # 纯氮气
            species_filename = "n2.species"
        else:
            # 默认使用空气(air.species)或6SpeciesAir
            species_filename = "air.species"

        valid_species = SPECIES_FILE_MAPPING.get(species_filename, None)

        # 如果在映射表中没找到，尝试从实际文件读取
        if valid_species is None and session_dir:
            species_path = session_dir / species_filename
            if species_path.exists():
                valid_species = self._parse_species_file(species_path)

        # 如果仍然没找到，使用默认空气物种
        if valid_species is None:
            valid_species = ["O2", "N2"]

        # 2. 找到所有mixture定义中的物种
        # 匹配: mixture air split O2 N2 或 mixture air full O2 N2
        mixture_pattern = r'mixture\s+\w+\s+(?:split|full)\s+([\w\s]+?)(?:\n|$)'
        mixtures = re.findall(mixture_pattern, input_file, re.IGNORECASE)

        # 3. 找到所有species命令中引用的物种
        # 匹配: species air.species O2
        species_ref_pattern = r'species\s+\S+\s+(\w+)'
        species_refs = re.findall(species_ref_pattern, input_file, re.IGNORECASE)

        # 4. 验证并修复
        all_referenced_species = set()
        for m in mixtures:
            all_referenced_species.update(m.split())

        fixed_input = input_file

        # 检查每个引用的物种是否有效
        for species in list(all_referenced_species) + species_refs:
            if species and species not in valid_species:
                # 物种无效，替换为第一个有效物种
                print(f"    ⚠️ 发现无效物种 '{species}'，替换为 '{valid_species[0]}'")
                fixed_input = re.sub(
                    rf'(\bmixture\s+\w+\s+(?:split|full)\s+){species}(\b)',
                    rf'\1{valid_species[0]}\2',
                    fixed_input,
                    flags=re.IGNORECASE
                )
                fixed_input = re.sub(
                    rf'(\bspecies\s+\S+\s+){species}(\b)',
                    rf'\1{valid_species[0]}\2',
                    fixed_input,
                    flags=re.IGNORECASE
                )

        # 5. 强制修正关键参数（确保遵守用户指定值）
        # 修正运行步数
        if 'num_steps' in parameters:
            target_steps = parameters['num_steps']
            fixed_input = re.sub(
                r'(\brun\s+)\d+',
                rf'\g<1>{target_steps}',
                fixed_input,
                flags=re.IGNORECASE
            )

        # 修正粒子权重fnum（控制粒子数量）
        if 'fnum' in parameters:
            target_fnum = parameters['fnum']
            # 修正 global nrho ... fnum ...
            fixed_input = re.sub(
                r'(global\s+nrho\s+[\d.e+-]+\s+fnum\s+)[\d.e+-]+',
                rf'\g<1>{target_fnum:.0e}',
                fixed_input,
                flags=re.IGNORECASE
            )
            # 如果没有fnum定义，添加到global命令后
            if 'fnum' not in fixed_input.lower():
                # 尝试在第一个global命令后添加
                fixed_input = re.sub(
                    r'(global\s+[^#\n]+)',
                    rf'\g<1> fnum {target_fnum:.0e}',
                    fixed_input,
                    count=1,
                    flags=re.IGNORECASE
                )

        # 修正网格尺寸
        if 'grid_size' in parameters:
            grid = parameters['grid_size']
            if len(grid) >= 2:
                # 2D网格
                if len(grid) == 2:
                    new_grid = f"{grid[0]} {grid[1]} 1"
                else:
                    new_grid = ' '.join(map(str, grid))
                fixed_input = re.sub(
                    r'(create_grid\s+)\d+\s+\d+(?:\s+\d+)?',
                    rf'\g<1>{new_grid}',
                    fixed_input,
                    flags=re.IGNORECASE
                )

        return fixed_input

    def _parse_species_file(self, species_path: Path) -> List[str]:
        """解析species文件，提取有效物种列表"""
        try:
            content = species_path.read_text(encoding='utf-8', errors='ignore')
            species_list = []
            for line in content.split('\n'):
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                # 物种名是第一个字段
                parts = line.split()
                if parts:
                    species_list.append(parts[0])
            return species_list
        except Exception as e:
            print(f"    ⚠️ 解析species文件失败: {e}")
            return ["O2", "N2"]  # 默认

    def _generate_annotations(self, input_file: str, parameters: Dict) -> Dict:
        """生成逐行注释（使用LLM，较慢）"""
        lines = input_file.split('\n')
        annotations = {}

        prompt = f"""为以下SPARTA输入文件生成逐行中文注释。

参数: {json.dumps(parameters, ensure_ascii=False)}

输入文件:
{input_file}

要求：
- 每行一个简短注释（1-2句话）
- 说明参数的物理意义
- 解释命令作用

请返回JSON格式：{{"行号": "注释", ...}}"""

        try:
            response = call_llm(prompt, temperature=0.3, max_tokens=8192)
            # 尝试解析JSON
            from utils import extract_code_block
            json_text = extract_code_block(response, "json")
            if not json_text:
                json_text = response

            annotations = json.loads(json_text)
        except:
            # 如果解析失败，生成基础注释
            annotations = self._generate_simple_annotations(input_file)

        return annotations

    def _generate_simple_annotations(self, input_file: str) -> Dict:
        """生成简单的基于规则的注释（快速）"""
        lines = input_file.split('\n')
        annotations = {}

        # SPARTA命令说明字典
        command_desc = {
            "dimension": "设置模拟维度",
            "boundary": "设置边界条件",
            "create_box": "创建模拟区域",
            "create_grid": "创建计算网格",
            "balance_grid": "负载均衡网格",
            "species": "定义气体种类",
            "mixture": "定义气体混合物",
            "global": "设置全局参数",
            "collide": "设置碰撞模型",
            "fix": "设置固定约束",
            "compute": "定义计算量",
            "stats": "设置统计输出",
            "stats_style": "设置统计格式",
            "dump": "输出数据到文件",
            "run": "运行模拟",
            "surf_collide": "表面碰撞模型",
            "surf_react": "表面反应模型",
            "read_surf": "读取表面几何",
            "timestep": "设置时间步长"
        }

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('#'):
                parts = line_stripped.split()
                if parts:
                    cmd = parts[0]
                    desc = command_desc.get(cmd, f"SPARTA命令: {cmd}")
                    annotations[str(i)] = desc

        return annotations

    def _generate_reasoning(self, parameters: Dict) -> str:
        """生成参数选择依据"""
        try:
            prompt = f"""解释以下DSMC仿真参数的选择依据：

参数:
{json.dumps(parameters, indent=2, ensure_ascii=False)}

要求：
- 用中文说明每个参数的物理意义
- 解释参数数值的合理性
- 指出可能的调整方向
- 使用Markdown格式

请说明："""

            reasoning = call_llm(prompt, temperature=0.5, max_tokens=8192)

            # 如果LLM调用失败（返回空字符串），使用基于规则的说明
            if not reasoning or not reasoning.strip():
                reasoning = self._generate_fallback_reasoning(parameters)

            return reasoning
        except Exception as e:
            print(f"生成参数说明失败: {e}")
            # 返回基于规则的说明作为后备
            return self._generate_fallback_reasoning(parameters)

    def _generate_fallback_reasoning(self, parameters: Dict) -> str:
        """生成基于规则的参数说明（作为后备方案）"""
        temp = parameters.get('temperature', 300)
        pressure = parameters.get('pressure', 101325)
        velocity = parameters.get('velocity', 1000)
        geometry = parameters.get('geometry', 'cylinder')
        gas = parameters.get('gas', 'N2')

        reasoning = f"""## 参数说明

### 温度: {temp} K
- 物理意义：气体分子的平均动能
- 合理性：{'室温条件' if 250 <= temp <= 350 else '特殊温度条件'}

### 压力: {pressure} Pa
- 物理意义：单位面积上的气体分子碰撞力
- 合理性：{'标准大气压' if pressure == 101325 else f'约{pressure/101325:.2f}个大气压'}

### 速度: {velocity} m/s
- 物理意义：来流速度或物体运动速度
- 马赫数：约{velocity / 340:.2f} (假设声速340m/s)
- {'亚音速流动' if velocity < 340 else ('跨音速流动' if velocity < 1200 else '超音速流动')}

### 几何形状: {geometry}
- 选择的几何：{geometry}
- 适用场景：{'钝体绕流，适合研究激波和分离' if geometry == 'cylinder' else ('球形绕流，轴对称问题' if geometry == 'sphere' else '平板流动，适合边界层研究')}

### 气体类型: {gas}
- 选择的气体：{gas}
- 特性：{'主要成分占空气78%，双原子分子' if gas == 'N2' else ('占空气21%，双原子分子，支持燃烧' if gas == 'O2' else ('惰性气体，单原子分子' if gas == 'Ar' else '空气混合物'))}

### 调整建议
- 提高温度会增加分子速度，影响碰撞频率
- 降低压力会减少粒子数，可能需要调整统计采样
- 速度变化会改变流动状态（亚/超音速）
"""
        return reasoning

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """## DSMC仿真助手

我可以帮您进行SPARTA DSMC（Direct Simulation Monte Carlo）仿真。

### 功能：
- 🔍 **学习DSMC知识**: 问我关于DSMC、SPARTA的问题
- 📝 **生成输入文件**: 说"生成DSMC输入文件"来配置参数
- ▶️ **运行模拟**: 生成输入文件后可运行仿真
- 📊 **结果分析**: 自动分析并可视化仿真结果

### 示例：
- "DSMC是什么？"
- "帮我生成一个圆柱绕流的SPARTA输入文件"
- "如何设置VSS碰撞模型？"

请告诉我您想做什么！"""

    def get_version_history(self, session_id: str) -> Dict:
        """
        获取会话的版本历史

        Args:
            session_id: 会话ID

        Returns:
            {
                "success": bool,
                "versions": [...],
                "current_version": int,
                "changelog": str
            }
        """
        try:
            from version_manager import VersionManager
            vm = VersionManager()

            history = vm.get_version_history(session_id)
            current = vm.get_current_version(session_id)
            changelog = vm.get_changelog(session_id)

            return {
                "success": True,
                "versions": history,
                "current_version": current,
                "changelog": changelog
            }
        except Exception as e:
            return {
                "success": False,
                "versions": [],
                "current_version": 1,
                "changelog": "",
                "error": str(e)
            }

    def restore_version(self, session_id: str, version: int) -> Dict:
        """
        恢复到指定版本

        Args:
            session_id: 会话ID
            version: 版本号

        Returns:
            恢复结果
        """
        try:
            from version_manager import VersionManager
            vm = VersionManager()

            result = vm.restore_version(session_id, version)

            if result["success"]:
                # 更新会话数据
                session_data = self._load_session(session_id)
                if session_data:
                    session_data["input_file"] = result["input_file"]
                    session_data["status"] = "restored"
                    self._save_session(session_id, session_data)

            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"恢复失败: {str(e)}"
            }

    def manual_fix(self, session_id: str) -> Generator:
        """
        手动触发错误修复（用于已失败的会话）

        Args:
            session_id: 会话ID

        Yields:
            修复事件
        """
        from error_fixer import SPARTAErrorFixer
        from sparta_runner import SPARTARunner

        fixer = SPARTAErrorFixer()
        runner = SPARTARunner()

        # 加载会话数据
        session_data = self._load_session(session_id)
        if not session_data:
            yield {"type": "error", "error": "会话不存在"}
            return

        # 读取日志
        yield {"type": "status", "message": "📖 读取错误日志..."}
        log_content = runner.get_log_content(session_id)

        if not log_content:
            yield {"type": "error", "error": "无法读取日志文件"}
            return

        # 解析错误
        yield {"type": "status", "message": "🔍 分析错误原因..."}
        error_info = fixer.parse_error(log_content, session_data.get("error", ""))

        if not error_info.get("has_error"):
            yield {"type": "error", "error": "无法识别错误类型"}
            return

        yield {
            "type": "error_info",
            "error_info": error_info
        }

        # 搜索解决方案
        yield {"type": "status", "message": "📖 搜索解决方案..."}
        search_results = fixer.search_solution(error_info)

        # 读取当前输入文件
        session_dir = self.sessions_dir / session_id
        input_file = session_dir / "input.sparta"
        with open(input_file, 'r', encoding='utf-8') as f:
            current_input = f.read()

        # 生成修复
        yield {"type": "status", "message": "🤖 生成修复方案..."}

        for event in fixer.generate_fix(current_input, error_info, search_results):
            if event.get("type") == "fix_generated":
                fix_result = event

                # 应用修复
                yield {"type": "status", "message": "📝 应用修复..."}
                apply_result = fixer.apply_fix(
                    session_id,
                    fix_result["fixed_content"],
                    error_info,
                    fix_result.get("explanation", "")
                )

                if apply_result.get("success"):
                    # 更新会话数据
                    session_data["input_file"] = fix_result["fixed_content"]
                    session_data["status"] = "fixed"
                    self._save_session(session_id, session_data)

                    yield {
                        "type": "done",
                        "result": {
                            "success": True,
                            "version": apply_result.get("version"),
                            "changes": fix_result.get("changes", []),
                            "explanation": fix_result.get("explanation", "")
                        }
                    }
                else:
                    yield {
                        "type": "error",
                        "error": f"应用修复失败: {apply_result.get('message')}"
                    }
                return
            elif event.get("type") == "status":
                yield event

        yield {"type": "error", "error": "生成修复方案失败"}


# 测试代码
if __name__ == "__main__":
    agent = DSMCAgent()

    # 测试检测
    messages = [
        "我想运行DSMC模拟",
        "DSMC是什么",
        "生成SPARTA输入文件"
    ]

    for msg in messages:
        print(f"\n消息: {msg}")
        result = agent.detect_dsmc(msg)
        print(f"结果: {result}")
