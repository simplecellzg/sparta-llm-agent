"""
DSMC关键词检测器
================

检测用户消息是否与DSMC仿真相关。
"""

import re
from typing import Dict, List


class DSMCKeywordDetector:
    """DSMC关键词检测器"""

    # 主要关键词（高权重）
    PRIMARY_KEYWORDS = [
        "DSMC", "dsmc",
        "SPARTA", "sparta",
        "Direct Simulation Monte Carlo",
        "直接模拟蒙特卡洛"
    ]

    # 上下文关键词（中权重）
    CONTEXT_KEYWORDS = [
        "simulation", "simulate", "模拟", "仿真",
        "rarefied", "稀薄",
        "molecular", "分子",
        "kinetic theory", "动理学",
        "collision", "碰撞",
        "particle", "粒子",
        "gas dynamics", "气体动力学",
        "hypersonic", "高超声速",
        "low density", "低密度",
        "free molecular", "自由分子",
        "Knudsen", "克努森"
    ]

    # 意图动词（低权重）
    INTENT_VERBS = [
        "run", "execute", "perform", "运行", "执行",
        "generate", "create", "make", "生成", "创建",
        "analyze", "analysis", "分析",
        "compute", "calculate", "计算",
        "simulate", "模拟"
    ]

    def __init__(self, confidence_threshold: float = 0.6):
        """
        初始化检测器

        Args:
            confidence_threshold: 置信度阈值
        """
        self.confidence_threshold = confidence_threshold

    def detect(self, message: str) -> Dict:
        """
        检测消息是否为DSMC相关

        Args:
            message: 用户消息

        Returns:
            {
                "is_dsmc": bool,
                "confidence": float (0-1),
                "matched_keywords": list,
                "intent": "generate|run|analyze|learn|unknown"
            }
        """
        message_lower = message.lower()

        # 匹配的关键词
        matched_primary = []
        matched_context = []
        matched_intent = []

        # 检查主要关键词
        for kw in self.PRIMARY_KEYWORDS:
            if kw.lower() in message_lower:
                matched_primary.append(kw)

        # 检查上下文关键词
        for kw in self.CONTEXT_KEYWORDS:
            if kw.lower() in message_lower:
                matched_context.append(kw)

        # 检查意图动词
        for verb in self.INTENT_VERBS:
            if verb.lower() in message_lower:
                matched_intent.append(verb)

        # 计算置信度得分
        score = 0.0

        # 主要关键词权重：0.6
        if matched_primary:
            score += 0.6

        # 上下文关键词权重：最多0.3
        context_score = min(len(matched_context) * 0.1, 0.3)
        score += context_score

        # 意图动词权重：最多0.1
        intent_score = min(len(matched_intent) * 0.05, 0.1)
        score += intent_score

        # 确定意图
        intent = self._determine_intent(message_lower, matched_intent)

        # 判断是否为DSMC
        is_dsmc = score >= self.confidence_threshold

        # 汇总匹配的关键词
        all_matched = matched_primary + matched_context + matched_intent

        return {
            "is_dsmc": is_dsmc,
            "confidence": min(score, 1.0),  # 确保不超过1.0
            "matched_keywords": all_matched,
            "intent": intent
        }

    def _determine_intent(self, message: str, matched_verbs: List[str]) -> str:
        """
        确定用户意图

        Args:
            message: 消息文本（小写）
            matched_verbs: 匹配的动词列表

        Returns:
            意图类型字符串
        """
        # 意图模式
        generate_patterns = [
            r"生成.*输入文件", r"create.*input",
            r"generate.*file", r"make.*input"
        ]
        run_patterns = [
            r"运行", r"执行", r"run", r"execute", r"perform"
        ]
        analyze_patterns = [
            r"分析", r"analyze", r"analysis"
        ]
        learn_patterns = [
            r"是什么", r"怎么", r"如何", r"what is", r"how to", r"explain"
        ]

        # 检查模式
        for pattern in generate_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return "generate"

        for pattern in run_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return "run"

        for pattern in analyze_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return "analyze"

        for pattern in learn_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return "learn"

        # 默认为未知
        return "unknown"

    def is_dsmc_message(self, message: str) -> bool:
        """
        简单判断消息是否为DSMC相关

        Args:
            message: 用户消息

        Returns:
            是否为DSMC相关
        """
        result = self.detect(message)
        return result["is_dsmc"]


# 测试代码
if __name__ == "__main__":
    detector = DSMCKeywordDetector()

    test_messages = [
        "我想运行DSMC模拟",
        "帮我生成SPARTA输入文件",
        "今天天气怎么样",
        "DSMC是什么",
        "模拟稀薄气体流动",
        "能帮我计算高超声速流动吗",
        "分析粒子碰撞过程"
    ]

    print("=" * 60)
    print("DSMC关键词检测测试")
    print("=" * 60)

    for msg in test_messages:
        result = detector.detect(msg)
        print(f"\n消息: {msg}")
        print(f"  是否DSMC: {result['is_dsmc']}")
        print(f"  置信度: {result['confidence']:.2f}")
        print(f"  意图: {result['intent']}")
        print(f"  匹配关键词: {result['matched_keywords']}")
