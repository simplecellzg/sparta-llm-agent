"""
DSMC Agent Module
=================

集成SPARTA DSMC仿真能力的智能代理模块。

主要组件:
- DSMCAgent: 主协调器
- DSMCKeywordDetector: DSMC关键词检测
- MultiSourceRetriever: 多源信息检索（手册>文献>网络）
- SPARTAInputGenerator: SPARTA输入文件生成器
- SPARTARunner: SPARTA执行器
- DSMCVisualizer: 结果可视化器
"""

__version__ = "1.0.0"
__author__ = "SPARTA DSMC Integration Team"

# 延迟导入避免循环依赖
def _lazy_import():
    from dsmc_agent import DSMCAgent
    from keyword_detector import DSMCKeywordDetector
    return DSMCAgent, DSMCKeywordDetector

# 提供便捷访问
DSMCAgent = None
DSMCKeywordDetector = None

def get_agent():
    global DSMCAgent, DSMCKeywordDetector
    if DSMCAgent is None:
        DSMCAgent, DSMCKeywordDetector = _lazy_import()
    return DSMCAgent()

def get_detector():
    global DSMCAgent, DSMCKeywordDetector
    if DSMCKeywordDetector is None:
        DSMCAgent, DSMCKeywordDetector = _lazy_import()
    return DSMCKeywordDetector()

__all__ = [
    "get_agent",
    "get_detector",
]
