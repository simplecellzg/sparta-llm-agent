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


class DSMCAgent:
    """DSMC代理 - 主协调器"""

    def __init__(self, max_fix_attempts: int = 3):
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

        # NEW: Perform manual searches before generation
        yield {"type": "status", "message": "📖 正在搜索SPARTA手册获取语法参考...", "elapsed": time.time() - start_time}
        step_start = time.time()

        manual_search_results = self.manual_searcher.comprehensive_search(parameters)
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
        """构建输入文件生成提示词"""
        # 基础参数
        prompt_parts = [f"""你是SPARTA DSMC仿真专家。请根据以下参数生成完整的SPARTA输入文件：

基础参数:
- 温度: {parameters.get('temperature', 300)} K
- 压力: {parameters.get('pressure', 101325)} Pa
- 速度: {parameters.get('velocity', 1000)} m/s
- 几何: {parameters.get('geometry', 'cylinder')}
- 气体: {parameters.get('gas', 'N2')}"""]

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

        # 添加生成要求
        prompt_parts.append("""
要求：
1. 生成完整的SPARTA输入脚本
2. 包含dimension、boundary、create_box、create_grid等必要命令
3. 设置合理的碰撞模型（如VSS）
4. 网格划分要适当
5. 包含输出dump命令
6. 遵循SPARTA语法规范

请生成SPARTA输入文件（用```sparta代码块包裹）：""")

        return "\n".join(prompt_parts)

    def _build_input_generation_prompt_with_manual_search(
        self,
        parameters: Dict,
        manual_search_results: Dict,
        llm_files: list = None
    ) -> str:
        """
        构建包含手册搜索结果的输入文件生成提示词

        Args:
            parameters: 用户参数
            manual_search_results: 手册搜索结果
            llm_files: LLM参考文件

        Returns:
            完整提示词
        """
        # Format manual search results for LLM
        manual_context = self.manual_searcher.format_for_llm(manual_search_results)

        # Build prompt with manual context first
        prompt_parts = [f"""你是SPARTA DSMC仿真专家。请根据以下参数和手册参考生成完整的SPARTA输入文件。

## SPARTA手册参考

{manual_context}

## 用户参数

基础参数:
- 温度: {parameters.get('temperature', 300)} K
- 压力: {parameters.get('pressure', 101325)} Pa
- 速度: {parameters.get('velocity', 1000)} m/s
- 几何: {parameters.get('geometry', 'cylinder')}
- 气体: {parameters.get('gas', 'N2')}
- 碰撞模型: {parameters.get('collision_model', 'VSS')}"""]

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

        # Add generation requirements
        prompt_parts.append("""
## 生成要求

请严格遵循上述SPARTA手册参考中的语法和示例：

1. 生成完整的SPARTA输入脚本
2. 包含所有必要命令（dimension、create_box、create_grid、species、run等）
3. 命令参数格式必须与手册示例完全一致
4. 网格划分要适当（根据几何尺寸）
5. 包含输出dump和stats命令
6. 遵循SPARTA语法规范
7. 参考手册中的示例案例结构

请生成SPARTA输入文件（用```sparta代码块包裹）：""")

        return "\n".join(prompt_parts)

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
            response = call_llm(prompt, temperature=0.3, max_tokens=2048)
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

            reasoning = call_llm(prompt, temperature=0.5, max_tokens=4096)

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
