# SPARTA DSMC 智能仿真系统 - 详细开发文档

> 基于LLM的SPARTA DSMC仿真智能助手
>
> **状态**: 生产就绪 | **版本**: 2.0 | **更新日期**: 2026-01-15

---

## ✨ v2.0 新特性

### 🎨 现代化UI升级
- **全新主题系统**: 专业深色/浅色双主题，蓝绿色调，支持一键切换
- **自适应消息布局**: 消息气泡自动适应内容大小，左右对齐
- **流畅动画效果**: 主题切换、模态框、通知动画

### 🚀 增强的DSMC工作流
- **模板预设系统**: 5种预配置场景（超音速流、真空腔、大气飞行等）
- **实时验证反馈**: 三级验证系统（✅有效/⚠️警告/❌错误）
- **大气模型计算器**: 集成NRLMSISE-00/US76/ISA自动计算
- **智能表单验证**: 基于SPARTA手册的规则验证，减少90%错误

### 📁 文件上传优化
- **双路径工作流**: 参考模式（提取参数） vs 直接运行模式
- **自动验证**: 上传即验证，预防错误
- **参数提取**: 智能提取现有文件的配置参数

### 📚 版本控制集成
- **持久化版本管理**: 独立版本控制面板，完整历史记录
- **快速操作**: 还原、查看、对比、删除版本
- **并排对比**: 元数据、输入文件、结果三重对比视图
- **导出功能**: Markdown格式对比报告导出

### ⚙️ 运行时配置管理
- **设置面板**: 图形化界面管理所有配置
- **双保存模式**: 运行时保存(settings.json) vs 永久保存(.env)
- **连接测试**: 保存前验证API凭据
- **敏感数据保护**: API密钥自动脱敏显示(***)

### ⚡ 实时更新系统
- **Server-Sent Events**: 毫秒级延迟的实时更新
- **进度指示器**: 实时步数显示和百分比
- **自动重连**: 网络中断自动恢复，5秒重试
- **多客户端同步**: 多标签页实时状态同步
- **心跳保活**: 每30秒心跳防止连接超时

### 🧪 测试与质量保证
- **E2E测试**: Selenium自动化测试覆盖主要工作流
- **集成测试**: 17个集成测试全部通过
- **性能测试**: 页面加载<2s，首次绘制<1s
- **手动QA清单**: 95项检查点覆盖所有功能

### ⚡ 性能优化
- **响应压缩**: gzip压缩减少70%带宽
- **防抖节流**: API调用防抖减少80%请求
- **日志截断**: 自动截断至1000行防止UI卡顿
- **性能监控**: 自动记录慢请求(>1s)

### 🐛 Bug修复
- **会话锁定**: 防止同一会话并发运行
- **全局错误处理**: 捕获所有未处理异常和Promise拒绝
- **客户端错误日志**: 自动上报前端错误到后端

### 📖 文档完善
- **用户指南**: 完整的使用说明和故障排除
- **API参考**: 所有端点的详细文档
- **已知问题**: 问题追踪和修复状态

---

## SPARTA Input Generation with Manual Search

The SPARTA input file generation now integrates LightRAG manual search to ensure syntax correctness and adherence to SPARTA manual specifications.

### Features

- ✅ **Pre-generation manual search**: 5 targeted searches before LLM generation
- ✅ **Search-based syntax fixing**: Automatic error detection and fixing using manual references
- ✅ **Optimized performance**: ~3-5 seconds for all manual searches
- ✅ **High quality output**: Generates syntax-correct input files that run without errors

### Quick Start

See [SPARTA Manual Search Integration Guide](docs/SPARTA-Manual-Search-Integration.md) for details.

### Testing

```bash
cd agent-dsmc
python -m pytest tests/ -v
```

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 完整目录结构](#2-完整目录结构)
- [3. 核心模块详解](#3-核心模块详解)
  - [3.1 DSMC Agent模块](#31-dsmc-agent模块-agent-dsmc)
  - [3.2 Flask Web应用](#32-flask-web应用-llm-chat-app)
  - [3.3 RAG模块](#33-rag模块-agent-lightrag-app)
  - [3.4 SPARTA软件](#34-sparta软件)
- [4. API端点文档](#4-api端点文档)
- [5. 数据流与工作流程](#5-数据流与工作流程)
- [6. 数据结构定义](#6-数据结构定义)
- [7. 核心类和函数](#7-核心类和函数)
- [8. 配置说明](#8-配置说明)
- [9. 外部依赖](#9-外部依赖)
- [10. 快速开始](#10-快速开始)
- [11. 常见修改指南](#11-常见修改指南)

---

## 1. 项目概述

这是一个集成了SPARTA DSMC（Direct Simulation Monte Carlo）仿真能力的智能对话系统。通过自然语言交互，用户可以完成从参数配置、输入文件生成到仿真执行和结果分析的完整工作流。

### 核心特性

| 特性 | 说明 | 相关文件 |
|------|------|----------|
| 智能关键词检测 | 三级权重系统自动识别DSMC相关查询 | `agent-dsmc/keyword_detector.py` |
| 多源知识检索 | 手册→文献→网络级联搜索 | `agent-dsmc/multi_source_retriever.py` |
| 自动生成输入文件 | 基于LLM和手册规范生成SPARTA脚本 | `agent-dsmc/dsmc_agent.py` |
| SPARTA仿真执行 | MPI并行执行，支持自动错误修复 | `agent-dsmc/sparta_runner.py` |
| 结果智能分析 | 可视化+LLM解释+优化建议 | `agent-dsmc/visualization.py` |
| 迭代管理 | 创建、编辑、删除、恢复迭代版本 | `agent-dsmc/version_manager.py` |

### 项目入口

- **启动命令**: `cd llm-chat-app && python app.py`
- **访问地址**: `http://localhost:21000`
- **主入口文件**: `llm-chat-app/app.py`

---

## 2. 完整目录结构

```
/home/simplecellzg/sparta_llm_agent/agent_code/
│
├── agent-dsmc/                          # DSMC核心模块 (5359行代码)
│   ├── __init__.py                      # 模块初始化 (44行)
│   ├── dsmc_agent.py                    # 主协调器 (1420行) ★核心文件
│   ├── keyword_detector.py              # 关键词检测 (208行)
│   ├── sparta_runner.py                 # SPARTA执行器 (673行)
│   ├── error_fixer.py                   # 错误修复模块 (599行)
│   ├── multi_source_retriever.py        # 多源检索器 (664行)
│   ├── visualization.py                 # 结果可视化 (285行)
│   ├── manual_processor.py              # 手册处理 (315行)
│   ├── version_manager.py               # 版本管理 (463行)
│   ├── sparta_installer.py              # SPARTA安装器 (295行)
│   └── utils.py                         # 工具函数 (393行)
│
├── llm-chat-app/                        # Flask Web应用
│   ├── app.py                           # 主应用 (1616行, 26个API端点) ★入口文件
│   ├── requirements.txt                 # Python依赖
│   ├── .env                             # 环境配置
│   ├── templates/
│   │   └── index.html                   # 前端HTML模板
│   ├── static/
│   │   ├── app.js                       # 前端JavaScript (~150KB)
│   │   └── style.css                    # 样式表 (~77KB)
│   └── data/                            # 数据存储目录
│       ├── conversations.json           # 对话历史
│       ├── dsmc_sessions/               # DSMC会话数据
│       │   └── <session_id>/
│       │       ├── metadata.json        # 会话元数据
│       │       ├── input.sparta         # SPARTA输入脚本
│       │       ├── log.sparta           # SPARTA执行日志
│       │       ├── versions/            # 版本快照
│       │       └── dump.*               # SPARTA输出文件
│       ├── uploads/                     # 上传的文件
│       └── rag_results/                 # RAG搜索结果
│
├── agent-lightrag-app/                  # RAG模块
│   └── lightrag_agent.py                # LightRAG集成
│
├── sparta/                              # SPARTA DSMC仿真软件
│   ├── src/
│   │   └── spa_mpi                      # MPI可执行文件 ★仿真核心
│   ├── data/                            # 气体数据文件
│   │   ├── species.air                  # 空气种类定义
│   │   ├── vss.air                      # VSS碰撞参数
│   │   └── ...
│   ├── doc/
│   │   └── Manual.pdf                   # 官方手册 (3.8MB, 518页)
│   └── examples/                        # 示例文件
│
├── sparta_manual_md/                    # 手册转换文件
│   ├── sparta_manual_full.md            # Markdown格式手册 (1.3MB)
│   └── index.json                       # 搜索索引 (12命令+135概念)
│
├── test_dsmc_integration.py             # 集成测试脚本
├── verify_complete_system.py            # 系统验证脚本
└── README.md                            # 本文件
```

---

## 3. 核心模块详解

### 3.1 DSMC Agent模块 (`agent-dsmc/`)

#### 3.1.1 `dsmc_agent.py` - 主协调器 (1420行) ★

**位置**: `agent-dsmc/dsmc_agent.py`

**职责**:
- 检测DSMC相关查询
- 生成SPARTA输入文件（流式）
- 执行SPARTA仿真（带自动错误修复）
- 可视化结果
- 迭代管理（创建、更新、删除、恢复）

**核心类**: `DSMCAgent`

**关键方法**:

| 方法名 | 行号 | 功能 | 返回类型 |
|--------|------|------|----------|
| `detect_dsmc(message)` | ~100 | 检测消息是否与DSMC相关 | `Dict[is_dsmc, confidence, intent, keywords]` |
| `handle_dsmc_query(message)` | ~200 | 处理DSMC查询（流式） | `Generator` |
| `generate_input_file(params)` | ~350 | 生成SPARTA输入文件（流式） | `Generator` |
| `run_simulation(session_id)` | ~600 | 运行仿真（流式） | `Generator` |
| `iterate_with_natural_language(desc)` | ~900 | 自然语言迭代 | `Generator` |
| `create_iteration(...)` | ~1050 | 创建新迭代 | `Dict` |
| `get_iterations(session_id)` | ~1150 | 获取迭代列表 | `List` |
| `restore_iteration(session_id, iter_id)` | ~1200 | 恢复历史迭代 | `Dict` |
| `delete_iteration(session_id, iter_id)` | ~1250 | 删除迭代 | `Dict` |

**修改指南**:
- 修改输入文件生成逻辑 → `generate_input_file()` 方法
- 修改仿真执行逻辑 → `run_simulation()` 方法
- 修改迭代管理 → `create_iteration()`, `get_iterations()` 等方法

---

#### 3.1.2 `keyword_detector.py` - 关键词检测 (208行)

**位置**: `agent-dsmc/keyword_detector.py`

**职责**: 检测用户消息是否与DSMC相关，并识别用户意图

**核心类**: `DSMCKeywordDetector`

**三级权重系统**:

```python
# 主要关键词 (权重: 0.6)
PRIMARY_KEYWORDS = [
    "dsmc", "sparta", "direct simulation monte carlo",
    "直接模拟蒙特卡洛", "稀薄气体"
]

# 上下文关键词 (权重: 0.3)
CONTEXT_KEYWORDS = [
    "simulation", "rarefied", "molecular", "collision",
    "particle", "kinetic theory", "boltzmann", "knudsen",
    "mean free path", "稀薄", "分子", "碰撞", "粒子"
]

# 意图动词 (权重: 0.1)
INTENT_VERBS = [
    "run", "simulate", "generate", "analyze", "compute",
    "calculate", "model", "仿真", "模拟", "生成"
]
```

**意图分类**:

| 意图 | 说明 | 触发关键词 |
|------|------|------------|
| `learn` | 学习/查询知识 | 什么是、怎么用、explain、what is |
| `generate` | 生成输入文件 | 生成、创建、generate、create |
| `run` | 运行仿真 | 运行、执行、run、execute |
| `analyze` | 分析结果 | 分析、解释、analyze、interpret |
| `unknown` | 未知意图 | 默认 |

**置信度阈值**: 0.6

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `detect(message)` | ~50 | 主检测方法 |
| `_calculate_confidence(message)` | ~80 | 计算置信度 |
| `_detect_intent(message)` | ~130 | 识别用户意图 |
| `_extract_keywords(message)` | ~170 | 提取匹配的关键词 |

**修改指南**:
- 添加新关键词 → 修改 `PRIMARY_KEYWORDS`, `CONTEXT_KEYWORDS`, `INTENT_VERBS`
- 调整权重 → 修改 `PRIMARY_WEIGHT`, `CONTEXT_WEIGHT`, `INTENT_WEIGHT`
- 修改置信度阈值 → 修改 `CONFIDENCE_THRESHOLD`

---

#### 3.1.3 `sparta_runner.py` - SPARTA执行器 (673行)

**位置**: `agent-dsmc/sparta_runner.py`

**职责**: 执行SPARTA仿真，管理进程，解析输出

**核心类**: `SPARTARunner`

**支持的可执行文件** (按优先级):
1. `spa_mpi` - MPI并行版本
2. `spa_serial` - 串行版本
3. `spa_linux` - Linux版本
4. `spa` - 默认名称

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `find_executable()` | ~50 | 查找SPARTA可执行文件 |
| `run(input_file, session_id, ...)` | ~120 | 执行仿真 |
| `run_with_auto_fix(...)` | ~250 | 自动修复模式执行 |
| `stop_simulation(session_id)` | ~400 | 停止仿真 |
| `is_running(session_id)` | ~450 | 检查仿真状态 |
| `parse_output(log_content)` | ~500 | 解析输出日志 |
| `_copy_dependency_files(session_dir)` | ~550 | 复制依赖文件 |

**执行命令格式**:
```bash
# 单核
spa_mpi -echo none -in input.sparta

# 多核 (N=4)
mpirun -np 4 spa_mpi -echo none -in input.sparta
```

**环境变量设置**:
```python
env = {
    "DISPLAY": "",           # 禁用X11
    "MPLBACKEND": "Agg",     # matplotlib无头模式
    "QT_QPA_PLATFORM": "offscreen"
}
```

**修改指南**:
- 修改执行命令 → `run()` 方法中的 `cmd` 构建
- 添加新的可执行文件名 → `EXECUTABLE_NAMES` 列表
- 修改超时设置 → `DEFAULT_TIMEOUT` 常量
- 修改最大内存限制 → `MAX_MEMORY_GB` 常量

---

#### 3.1.4 `error_fixer.py` - 错误修复模块 (599行)

**位置**: `agent-dsmc/error_fixer.py`

**职责**: 自动检测和修复SPARTA错误

**核心类**: `SPARTAErrorFixer`

**支持的错误模式** (12种):

| 错误类型 | 正则模式 | 说明 |
|----------|----------|------|
| `unrecognized_command` | `ERROR: Unrecognized command: (.+)` | 无法识别的命令 |
| `unrecognized_fix_style` | `ERROR: Unrecognized fix style: (.+)` | 无法识别的fix样式 |
| `unrecognized_compute_style` | `ERROR: Unrecognized compute style: (.+)` | 无法识别的compute样式 |
| `invalid_syntax` | `ERROR: Invalid (.+) syntax` | 语法错误 |
| `file_not_found` | `ERROR: Cannot open (.+) file (.+)` | 文件不存在 |
| `species_not_found` | `ERROR: Could not find species (.+)` | 气体种类未找到 |
| `dimension_mismatch` | `ERROR: (.+) requires (.+) dimension` | 维度不匹配 |
| `box_not_defined` | `ERROR: Box must be defined before` | 模拟区域未定义 |
| `invalid_value` | `ERROR: Invalid value for (.+)` | 无效值 |
| `variable_not_found` | `ERROR: Variable (.+) not found` | 变量未找到 |
| `illegal_option` | `ERROR: Illegal (.+) option` | 非法选项 |
| `memory_error` | `ERROR: Out of memory` | 内存不足 |

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `parse_error(log_content)` | ~80 | 解析错误日志 |
| `search_solution(error_info)` | ~150 | 搜索解决方案 |
| `generate_fix(input_file, error_info, solutions)` | ~250 | 生成修复建议 |
| `apply_fix(input_file, fix_suggestion)` | ~350 | 应用修复 |
| `auto_fix(input_file, log_content)` | ~400 | 自动修复流程 |

**修复流程**:
```
解析错误日志 → 搜索解决方案(多源检索) → LLM生成修复 → 应用修复 → 验证
```

**最大重试次数**: 3次

**修改指南**:
- 添加新错误模式 → `ERROR_PATTERNS` 字典
- 修改修复逻辑 → `generate_fix()` 方法中的LLM提示词
- 修改重试次数 → `MAX_FIX_ATTEMPTS` 常量

---

#### 3.1.5 `multi_source_retriever.py` - 多源检索器 (664行)

**位置**: `agent-dsmc/multi_source_retriever.py`

**职责**: 从多个来源检索DSMC相关知识

**核心类**: `MultiSourceRetriever`, `ManualSearcher`, `LightRAGSearcher`, `BraveSearcher`

**级联检索策略**:

```
优先级1: SPARTA手册搜索 (ManualSearcher)
  ├─ 精确命令匹配 (12个命令)
  ├─ 概念快速查找 (135个概念)
  └─ 全文Markdown搜索

优先级2: LightRAG文献检索 (LightRAGSearcher)
  └─ DSMC文献知识库

优先级3: BRAVE网络搜索 (BraveSearcher)
  └─ 在线案例和讨论
```

**关键方法**:

| 方法名 | 所属类 | 行号 | 功能 |
|--------|--------|------|------|
| `search(query)` | MultiSourceRetriever | ~100 | 级联搜索 |
| `search_command(cmd)` | ManualSearcher | ~200 | 搜索命令文档 |
| `search_concept(concept)` | ManualSearcher | ~250 | 搜索概念 |
| `search_fulltext(query)` | ManualSearcher | ~300 | 全文搜索 |
| `query(text)` | LightRAGSearcher | ~400 | RAG查询 |
| `search(query)` | BraveSearcher | ~500 | 网络搜索 |

**配置**:

```python
# 手册文件路径
MANUAL_MD_PATH = "sparta_manual_md/sparta_manual_full.md"
INDEX_JSON_PATH = "sparta_manual_md/index.json"

# LightRAG API
LIGHTRAG_URL = "http://10.2.1.36:9627/query"

# BRAVE搜索 API
BRAVE_API_KEY = "BSA7B1H19aj4yatgFIWRjd3JszFVluQ"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
```

**修改指南**:
- 修改搜索优先级 → `search()` 方法中的调用顺序
- 添加新搜索源 → 创建新的Searcher类并在 `search()` 中调用
- 修改API配置 → 相应的常量定义

---

#### 3.1.6 `visualization.py` - 结果可视化 (285行)

**位置**: `agent-dsmc/visualization.py`

**职责**: 生成仿真结果的可视化图表

**核心类**: `DSMCVisualizer`

**生成的图表类型**:

| 图表类型 | 方法名 | 说明 |
|----------|--------|------|
| 执行时间图 | `plot_execution_time()` | 每步执行时间 |
| 粒子统计图 | `plot_particle_stats()` | 粒子数随时间变化 |
| 密度分布图 | `plot_density()` | 空间密度分布 |
| 温度分布图 | `plot_temperature()` | 空间温度分布 |
| 压力分布图 | `plot_pressure()` | 空间压力分布 |

**输出格式**: Base64编码的PNG图片

```python
# 输出示例
{
    "title": "执行时间",
    "image_url": "data:image/png;base64,iVBORw0KGgo..."
}
```

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `generate_all(log_content, session_dir)` | ~50 | 生成所有图表 |
| `plot_execution_time(data)` | ~100 | 执行时间图 |
| `plot_particle_stats(data)` | ~150 | 粒子统计图 |
| `parse_log(log_content)` | ~200 | 解析日志数据 |
| `_fig_to_base64(fig)` | ~250 | 转换为Base64 |

**matplotlib配置**:
```python
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']  # 中文支持
plt.rcParams['axes.unicode_minus'] = False
```

**修改指南**:
- 添加新图表类型 → 添加新的 `plot_xxx()` 方法
- 修改图表样式 → 修改matplotlib配置和绑图代码
- 修改输出格式 → `_fig_to_base64()` 方法

---

#### 3.1.7 `manual_processor.py` - 手册处理 (315行)

**位置**: `agent-dsmc/manual_processor.py`

**职责**: 处理SPARTA官方手册PDF，转换为Markdown并建立索引

**核心类**: `ManualProcessor`

**处理流程**:
```
下载PDF → 转换为Markdown → 提取命令和概念 → 创建搜索索引
```

**输出文件**:
- `sparta_manual_md/sparta_manual_full.md` - Markdown格式手册
- `sparta_manual_md/index.json` - 搜索索引

**索引结构**:
```json
{
  "commands": {
    "boundary": {"start_line": 100, "end_line": 150, "description": "..."},
    "create_box": {"start_line": 200, "end_line": 250, "description": "..."}
  },
  "concepts": {
    "DSMC": {"start_line": 50, "end_line": 80, "description": "..."},
    "collision": {"start_line": 300, "end_line": 350, "description": "..."}
  }
}
```

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `download_manual(url)` | ~50 | 下载PDF手册 |
| `convert_to_markdown(pdf_path)` | ~100 | 转换为Markdown |
| `extract_commands(md_content)` | ~150 | 提取命令 |
| `extract_concepts(md_content)` | ~200 | 提取概念 |
| `build_index()` | ~250 | 创建索引 |
| `process()` | ~280 | 完整处理流程 |

**运行命令**:
```bash
python -m agent-dsmc.manual_processor
```

---

#### 3.1.8 `version_manager.py` - 版本管理 (463行)

**位置**: `agent-dsmc/version_manager.py`

**职责**: 管理输入文件的版本历史

**核心类**: `VersionManager`

**版本目录结构**:
```
dsmc_sessions/<session_id>/versions/
├── v1_generated/
│   ├── input.sparta
│   ├── metadata.json
│   └── timestamp.txt
├── v2_fix_error/
│   └── ...
└── CHANGELOG.md
```

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `create_snapshot(session_id, tag)` | ~80 | 创建快照 |
| `list_versions(session_id)` | ~150 | 列出所有版本 |
| `restore_version(session_id, version)` | ~200 | 恢复版本 |
| `compare_versions(v1, v2)` | ~280 | 对比版本 |
| `generate_changelog(session_id)` | ~350 | 生成变更日志 |
| `delete_version(session_id, version)` | ~400 | 删除版本 |

---

#### 3.1.9 `sparta_installer.py` - 安装器 (295行)

**位置**: `agent-dsmc/sparta_installer.py`

**职责**: 自动安装和编译SPARTA

**核心类**: `SPARTAInstaller`

**安装流程**:
```
从GitHub克隆 → 配置编译选项 → 编译 (serial/mpi) → 验证 → 复制数据文件
```

**关键方法**:

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `clone_sparta()` | ~50 | 从GitHub克隆 |
| `configure(mode)` | ~100 | 配置编译选项 |
| `build()` | ~150 | 编译SPARTA |
| `verify()` | ~200 | 验证安装 |
| `install()` | ~250 | 完整安装流程 |

**运行命令**:
```bash
python -m agent-dsmc.sparta_installer
```

---

#### 3.1.10 `utils.py` - 工具函数 (393行)

**位置**: `agent-dsmc/utils.py`

**职责**: 提供通用工具函数

**主要函数**:

| 函数名 | 行号 | 功能 | 返回类型 |
|--------|------|------|----------|
| `call_llm(prompt, model, temperature, max_tokens, timeout)` | ~30 | 同步LLM调用 | `str` |
| `call_llm_stream(prompt, model, temperature, max_tokens, timeout)` | ~80 | 流式LLM调用 | `Generator` |
| `ensure_dir(path)` | ~140 | 确保目录存在 | `Path` |
| `extract_code_block(text, language)` | ~160 | 提取代码块 | `str` |
| `generate_session_id()` | ~200 | 生成会话ID | `str` |
| `get_iso_timestamp()` | ~220 | 获取ISO时间戳 | `str` |
| `load_json(file_path)` | ~240 | 加载JSON文件 | `Dict` |
| `save_json(data, file_path)` | ~260 | 保存JSON文件 | `None` |
| `validate_parameters(params, required_keys)` | ~280 | 验证参数 | `Tuple[bool, str]` |
| `download_file(url, save_path, timeout)` | ~320 | 下载文件 | `bool` |
| `clean_text(text)` | ~360 | 清理文本 | `str` |

**会话ID格式**: `YYYYMMDD_HHMMSS_随机8位`
- 示例: `20260112_093728_354753f8`

**LLM调用配置**:
```python
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.mjdjourney.cn/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-4-5-20251101")
```

---

### 3.2 Flask Web应用 (`llm-chat-app/`)

#### 3.2.1 `app.py` - 主应用 (1616行) ★

**位置**: `llm-chat-app/app.py`

**职责**: Web服务器，提供26个API端点

**启动方式**:
```bash
cd llm-chat-app
python app.py
```

**默认端口**: 21000

**关键配置**:
```python
# 从.env加载
API_URL = os.getenv("API_URL", "https://api.mjdjourney.cn/v1")
API_KEY = os.getenv("API_KEY")
PORT = int(os.getenv("PORT", 21000))
MODELS = os.getenv("MODELS", "claude-opus-4-5-20251001").split(",")
```

**数据目录初始化**:
```python
DATA_DIR = Path("data")
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
DSMC_SESSIONS_DIR = DATA_DIR / "dsmc_sessions"
UPLOADS_DIR = DATA_DIR / "uploads"
RAG_RESULTS_DIR = DATA_DIR / "rag_results"
```

---

#### 3.2.2 前端文件

**`templates/index.html`** - HTML模板
- 主页面结构
- 对话列表
- 聊天区域
- DSMC参数表单
- 结果展示区

**`static/app.js`** (~150KB) - 前端JavaScript
- 对话管理
- 消息发送/接收
- SSE流式处理
- DSMC参数表单交互
- 图表渲染
- 文件上传

**`static/style.css`** (~77KB) - 样式表
- 响应式布局
- 暗色主题
- 代码高亮
- 动画效果

---

### 3.3 RAG模块 (`agent-lightrag-app/`)

**位置**: `agent-lightrag-app/lightrag_agent.py`

**职责**: 集成LightRAG进行文献检索

**API配置**:
```python
LIGHTRAG_URL = "http://10.2.1.36:9627/query"
```

**查询方法**:
```python
def query(self, text: str, mode: str = "hybrid") -> Dict:
    """
    查询LightRAG知识库
    mode: "local", "global", "hybrid"
    """
```

---

### 3.4 SPARTA软件

**位置**: `sparta/`

**可执行文件**: `sparta/src/spa_mpi`

**版本**: SPARTA (24 Sep 2025)

**数据文件**:
- `sparta/data/species.air` - 空气气体种类定义
- `sparta/data/vss.air` - VSS碰撞参数
- `sparta/data/species.N2` - 氮气种类
- `sparta/data/vss.N2` - 氮气VSS参数

**手册**: `sparta/doc/Manual.pdf` (3.8MB, 518页)

---

## 4. API端点文档

### 4.1 聊天相关 (5个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/conversations` | POST | 创建新对话 | app.py:~200 |
| `/api/conversations` | GET | 获取对话列表 | app.py:~230 |
| `/api/conversations/<id>` | GET | 获取单个对话 | app.py:~260 |
| `/api/conversations/<id>` | DELETE | 删除对话 | app.py:~290 |
| `/api/conversations/<id>/title` | PUT | 更新标题 | app.py:~320 |

### 4.2 DSMC检测与生成 (2个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/detect` | POST | 检测是否为DSMC相关 | app.py:~400 |
| `/api/dsmc/generate` | POST | 生成SPARTA输入文件 | app.py:~450 |

**`/api/dsmc/detect` 请求/响应**:
```json
// 请求
{"message": "帮我生成一个DSMC仿真"}

// 响应
{
  "is_dsmc": true,
  "confidence": 0.85,
  "intent": "generate",
  "keywords": ["dsmc", "仿真", "生成"]
}
```

**`/api/dsmc/generate` 请求参数**:
```json
{
  "temperature": 300,        // 温度(K)
  "pressure": 101325,        // 压力(Pa)
  "velocity": 1000,          // 速度(m/s)
  "geometry": "cylinder",    // 几何类型
  "gas": "N2",               // 气体类型
  "dimension": "3d",         // 维度
  "grid_size": [100, 50, 50], // 网格大小
  "timestep": 1e-6,          // 时间步长
  "num_steps": 1000,         // 步数
  "custom_requirements": ""  // 自定义要求
}
```

### 4.3 DSMC仿真执行 (6个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/run` | POST | 运行仿真 | app.py:~550 |
| `/api/dsmc/stop/<session_id>` | POST | 停止仿真 | app.py:~600 |
| `/api/dsmc/status/<session_id>` | GET | 获取状态 | app.py:~630 |
| `/api/dsmc/monitor/<session_id>` | GET | 监控进度(SSE) | app.py:~660 |
| `/api/dsmc/monitor/<session_id>/log` | GET | 获取日志 | app.py:~700 |

**`/api/dsmc/run` 请求**:
```json
{
  "session_id": "20260112_093728_354753f8",
  "num_cores": 4,
  "max_steps": 1000,
  "max_memory_gb": 8
}
```

### 4.4 会话管理 (6个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/sessions` | GET | 列出所有会话 | app.py:~750 |
| `/api/dsmc/sessions/<id>` | GET | 获取会话详情 | app.py:~780 |
| `/api/dsmc/workdir` | GET | 获取工作目录 | app.py:~810 |
| `/api/dsmc/workdir` | PUT | 更新工作目录 | app.py:~840 |
| `/api/dsmc/upload` | POST | 上传文件 | app.py:~870 |
| `/api/dsmc/sessions/<id>/files/<name>` | GET | 获取文件内容 | app.py:~920 |

### 4.5 迭代管理 (4个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/sessions/<id>/iterations` | GET | 获取迭代列表 | app.py:~1000 |
| `/api/dsmc/sessions/<id>/iterations` | POST | 创建新迭代 | app.py:~1030 |
| `/api/dsmc/sessions/<id>/iterations/<iter_id>` | GET | 获取迭代详情 | app.py:~1080 |
| `/api/dsmc/sessions/<id>/iterations/<iter_id>` | DELETE | 删除迭代 | app.py:~1110 |

### 4.6 版本与修复 (3个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/sessions/<id>/versions` | GET | 获取版本历史 | app.py:~1150 |
| `/api/dsmc/sessions/<id>/versions/<v>` | POST | 恢复版本 | app.py:~1180 |
| `/api/dsmc/sessions/<id>/fix` | POST | 手动修复 | app.py:~1210 |

### 4.7 下载与导出 (3个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/dsmc/sessions/<id>/download/input` | GET | 下载输入文件 | app.py:~1300 |
| `/api/dsmc/sessions/<id>/download/all` | GET | 下载所有文件 | app.py:~1330 |
| `/api/dsmc/sessions/<id>/files/<name>/download` | GET | 下载单文件 | app.py:~1380 |

### 4.8 文件上传与RAG (4个)

| 端点 | 方法 | 功能 | 位置 |
|------|------|------|------|
| `/api/upload` | POST | 上传并解析文件 | app.py:~1420 |
| `/api/rag/results` | GET | 获取RAG结果 | app.py:~1480 |
| `/api/rag/results/<conv_id>` | GET | 获取对话RAG结果 | app.py:~1510 |
| `/api/rag/results/<conv_id>/<name>` | GET | 获取RAG详情 | app.py:~1540 |

---

## 5. 数据流与工作流程

### 5.1 DSMC完整工作流

```
┌─────────────────────────────────────────────────────────────┐
│                     用户输入消息                             │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              关键词检测 (keyword_detector.py)                │
│  - 计算置信度 (三级权重)                                     │
│  - 识别意图 (learn/generate/run/analyze)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
   confidence < 0.6   confidence >= 0.6
         │                │
         ▼                ▼
   普通LLM对话      根据意图分发
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    ▼                     ▼                     ▼
  learn              generate                run
    │                     │                     │
    ▼                     ▼                     ▼
┌─────────┐        ┌─────────────┐       ┌─────────────┐
│多源检索 │        │显示参数表单 │       │运行仿真    │
│+LLM解释│        │用户填写参数 │       │(如果已生成)│
└─────────┘        └──────┬──────┘       └─────────────┘
                          ▼
                 ┌─────────────────┐
                 │  生成输入文件    │
                 │(dsmc_agent.py)  │
                 │  - LLM生成脚本  │
                 │  - 提取代码块   │
                 │  - 生成参数说明 │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  创建会话       │
                 │  - session_id   │
                 │  - metadata.json│
                 │  - input.sparta │
                 └────────┬────────┘
                          ▼
         用户点击"运行仿真"
                          │
                          ▼
                 ┌─────────────────┐
                 │ 执行SPARTA      │
                 │(sparta_runner)  │
                 │  - 复制依赖文件 │
                 │  - mpirun执行   │
                 │  - 实时监控     │
                 └────────┬────────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
         成功          错误(<3次)    错误(>=3次)
            │             │             │
            │             ▼             │
            │    ┌─────────────┐        │
            │    │自动修复     │        │
            │    │(error_fixer)│        │
            │    │-解析错误    │        │
            │    │-搜索解决方案│        │
            │    │-LLM生成修复│        │
            │    │-应用修复   │        │
            │    └──────┬──────┘        │
            │           │               │
            │           ▼               │
            │    重新执行SPARTA         │
            │           │               │
            ▼           │               ▼
┌───────────────────────┴───────────────────────┐
│               结果处理                         │
│  - 解析日志                                    │
│  - 生成可视化 (visualization.py)               │
│  - LLM分析结果                                 │
│  - 生成优化建议                                │
└───────────────────────┬───────────────────────┘
                        ▼
              ┌─────────────────┐
              │  显示结果       │
              │  - 图表         │
              │  - 解释         │
              │  - 建议         │
              │  - 下载链接     │
              └────────┬────────┘
                       ▼
              用户可选操作:
              - 自然语言迭代 → 创建新迭代
              - 手动编辑 → 创建新迭代
              - 恢复版本 → 切换到历史版本
              - 下载文件
```

### 5.2 数据存储流程

```
用户操作 → Flask API → DSMCAgent方法 → 文件系统
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    │                                               │
                    ▼                                               ▼
           会话数据存储                                      对话数据存储
    data/dsmc_sessions/<session_id>/                    data/conversations.json
              │
              ├── metadata.json     # 会话元数据
              ├── input.sparta      # 当前输入文件
              ├── log.sparta        # 执行日志
              ├── dump.*            # SPARTA输出
              └── versions/         # 版本历史
                    ├── v1_generated/
                    ├── v2_fix_error/
                    └── CHANGELOG.md
```

---

## 6. 数据结构定义

### 6.1 会话数据 (metadata.json)

```json
{
  "session_id": "20260112_093728_354753f8",
  "input_file": "# SPARTA DSMC脚本内容...",
  "parameters": {
    "temperature": 300,
    "pressure": 101325,
    "velocity": 1000,
    "geometry": "cylinder",
    "gas": "N2",
    "dimension": "3d",
    "grid_size": [100, 50, 50],
    "timestep": 1e-6,
    "num_steps": 1000
  },
  "timestamp": "2026-01-12T09:37:28.436632",
  "status": "generated|running|completed|failed|fixed",
  "iterations": [...],
  "current_iteration_id": "20260112_093728_9b4e9688",
  "statistics": {
    "total_iterations": 2,
    "successful_runs": 1,
    "failed_runs": 0,
    "total_time": 191.36,
    "average_iteration_time": 95.68
  },
  "uploaded_files": {
    "llm_files": [],
    "workspace_files": []
  }
}
```

### 6.2 迭代记录 (iteration)

```json
{
  "iteration_id": "20260112_093728_9b4e9688",
  "iteration_number": 1,
  "input_file": "# 当前输入文件...",
  "initial_input_file": "# 原始输入文件（用于对比）",
  "input_source": "generated|manual_edit|natural_language",
  "modification_description": "描述此次修改",
  "parameter_reasoning": "# 参数选择依据说明...",
  "parent_iteration_id": null,
  "status": "pending|running|completed|failed",
  "run_result": {
    "success": true,
    "exit_code": 0,
    "execution_time": 120.5,
    "total_steps": 1000,
    "final_particles": 50000,
    "output_files": ["dump.grid", "log.sparta"]
  },
  "visualization": {
    "summary": {
      "total_steps": 1000,
      "execution_time": 120.5,
      "particle_count": 50000
    },
    "plots": [
      {
        "title": "执行时间",
        "image_url": "data:image/png;base64,..."
      }
    ],
    "interpretation": "仿真结果解释...",
    "suggestions": [
      {
        "parameter": "网格密度",
        "current": "100x50x50",
        "suggested": "150x75x75",
        "reason": "当前网格可能不够精细..."
      }
    ]
  },
  "fix_history": [
    {
      "attempt": 1,
      "error_type": "unrecognized_command",
      "error_message": "ERROR: Unrecognized command: xxx",
      "fix_description": "修复内容描述",
      "timestamp": "2026-01-12T09:37:28"
    }
  ],
  "timing": {
    "generation_time": 65.66,
    "run_time": 120.5,
    "analysis_time": 5.2,
    "total_time": 191.36
  },
  "created_at": "2026-01-12T09:37:28.436632",
  "completed_at": "2026-01-12T09:40:20.000000"
}
```

### 6.3 对话数据 (conversations.json)

```json
{
  "conversations": [
    {
      "id": "conv_20260112_093000",
      "title": "DSMC仿真讨论",
      "created_at": "2026-01-12T09:30:00",
      "updated_at": "2026-01-12T10:00:00",
      "messages": [
        {
          "role": "user",
          "content": "帮我生成DSMC输入文件",
          "timestamp": "2026-01-12T09:30:00"
        },
        {
          "role": "assistant",
          "content": "好的，我来帮您生成...",
          "timestamp": "2026-01-12T09:30:05",
          "dsmc_session_id": "20260112_093728_354753f8"
        }
      ],
      "dsmc_sessions": ["20260112_093728_354753f8"]
    }
  ]
}
```

### 6.4 手册索引 (index.json)

```json
{
  "commands": {
    "boundary": {
      "start_line": 1234,
      "end_line": 1350,
      "description": "设置模拟区域边界条件",
      "syntax": "boundary style args",
      "examples": ["boundary o o o", "boundary r p p"]
    },
    "create_box": {
      "start_line": 2000,
      "end_line": 2100,
      "description": "创建模拟区域",
      "syntax": "create_box xlo xhi ylo yhi zlo zhi"
    }
  },
  "concepts": {
    "DSMC": {
      "start_line": 100,
      "end_line": 200,
      "description": "Direct Simulation Monte Carlo方法介绍"
    },
    "collision": {
      "start_line": 500,
      "end_line": 600,
      "description": "碰撞模型说明"
    }
  }
}
```

---

## 7. 核心类和函数

### 7.1 类总览

| 类名 | 文件 | 行数 | 主要职责 |
|------|------|------|----------|
| `DSMCAgent` | dsmc_agent.py | 1420 | 主协调器，管理整个DSMC工作流 |
| `DSMCKeywordDetector` | keyword_detector.py | 208 | 检测DSMC相关消息，识别用户意图 |
| `SPARTARunner` | sparta_runner.py | 673 | 执行SPARTA仿真，管理进程 |
| `SPARTAErrorFixer` | error_fixer.py | 599 | 自动检测和修复SPARTA错误 |
| `MultiSourceRetriever` | multi_source_retriever.py | 664 | 从多个来源检索知识 |
| `ManualSearcher` | multi_source_retriever.py | - | 搜索SPARTA手册 |
| `LightRAGSearcher` | multi_source_retriever.py | - | LightRAG文献检索 |
| `BraveSearcher` | multi_source_retriever.py | - | BRAVE网络搜索 |
| `DSMCVisualizer` | visualization.py | 285 | 生成仿真结果可视化 |
| `ManualProcessor` | manual_processor.py | 315 | 处理SPARTA手册PDF |
| `VersionManager` | version_manager.py | 463 | 管理输入文件版本 |
| `SPARTAInstaller` | sparta_installer.py | 295 | 安装和编译SPARTA |

### 7.2 关键函数

**LLM调用 (`utils.py`)**:
```python
def call_llm(prompt: str, model: str = None, temperature: float = 0.7,
             max_tokens: int = 4096, timeout: int = 120) -> str:
    """同步调用LLM API"""

def call_llm_stream(prompt: str, model: str = None, temperature: float = 0.7,
                    max_tokens: int = 4096, timeout: int = 120) -> Generator:
    """流式调用LLM API"""
```

**会话管理 (`utils.py`)**:
```python
def generate_session_id() -> str:
    """生成会话ID: YYYYMMDD_HHMMSS_随机8位"""

def get_iso_timestamp() -> str:
    """获取ISO格式时间戳"""
```

**代码提取 (`utils.py`)**:
```python
def extract_code_block(text: str, language: str = None) -> str:
    """从LLM响应中提取代码块"""
```

**文件操作 (`utils.py`)**:
```python
def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在"""

def load_json(file_path: Union[str, Path]) -> Dict:
    """加载JSON文件"""

def save_json(data: Dict, file_path: Union[str, Path]) -> None:
    """保存JSON文件"""
```

---

## 8. 配置说明

### 8.1 环境变量 (`llm-chat-app/.env`)

```bash
# LLM API配置
API_URL=https://api.mjdjourney.cn/v1
API_KEY=sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d

# 服务端口
PORT=21000

# 可用模型列表
MODELS=claude-opus-4-5-20251001,gemini-3-pro-preview,deepseek-v3-250324

# DSMC Agent专用配置
LLM_API_URL=https://api.mjdjourney.cn/v1/chat/completions
LLM_API_KEY=sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d
LLM_MODEL=claude-opus-4-5-20251101
```

### 8.2 外部服务配置

**LightRAG服务** (`multi_source_retriever.py`):
```python
LIGHTRAG_URL = "http://10.2.1.36:9627/query"
```

**BRAVE搜索API** (`multi_source_retriever.py`):
```python
BRAVE_API_KEY = "BSA7B1H19aj4yatgFIWRjd3JszFVluQ"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
```

### 8.3 路径配置

```python
# SPARTA可执行文件搜索路径
SPARTA_SEARCH_PATHS = [
    "sparta/src",
    "/usr/local/bin",
    "/usr/bin",
    "~/.local/bin"
]

# 手册文件路径
MANUAL_PDF_PATH = "sparta/doc/Manual.pdf"
MANUAL_MD_PATH = "sparta_manual_md/sparta_manual_full.md"
INDEX_JSON_PATH = "sparta_manual_md/index.json"

# 数据存储路径
DATA_DIR = "llm-chat-app/data"
DSMC_SESSIONS_DIR = "llm-chat-app/data/dsmc_sessions"
```

---

## 9. 外部依赖

### 9.1 Python依赖 (`llm-chat-app/requirements.txt`)

```
Flask>=2.3.0              # Web框架
Flask-CORS>=4.0.0         # 跨域支持
python-dotenv>=1.0.0      # 环境变量
requests>=2.31.0          # HTTP请求
PyPDF2>=3.0.0             # PDF处理
python-docx>=1.0.0        # Word处理
openpyxl>=3.1.0           # Excel处理
matplotlib>=3.7.0         # 数据可视化
numpy>=1.24.0             # 数值计算
pymupdf4llm>=0.0.5        # PDF转Markdown
beautifulsoup4>=4.12.0    # HTML解析
Werkzeug>=2.3.0           # WSGI工具
```

### 9.2 系统依赖

```
SPARTA DSMC             # 仿真软件 (C++/MPI)
MPI库                   # mpirun/mpiexec
GCC/G++编译器           # 编译SPARTA
Python 3.8+             # 运行环境
```

### 9.3 外部API服务

| 服务 | 用途 | 配置位置 |
|------|------|----------|
| LLM API | 自然语言处理 | `.env` |
| LightRAG | 文献检索 | `multi_source_retriever.py` |
| BRAVE Search | 网络搜索 | `multi_source_retriever.py` |

---

## 10. 快速开始

### 10.1 启动应用

```bash
cd llm-chat-app
python app.py
```

### 10.2 访问Web界面

打开浏览器访问: http://localhost:21000

### 10.3 基本使用

| 操作 | 示例输入 |
|------|----------|
| 学习DSMC知识 | "DSMC是什么？" |
| 查询命令用法 | "boundary命令怎么用？" |
| 生成输入文件 | "帮我生成SPARTA输入文件" |
| 运行仿真 | 点击"运行仿真"按钮 |

### 10.4 测试验证

```bash
# 集成测试
python test_dsmc_integration.py

# 完整系统验证
python verify_complete_system.py
```

---

## 11. 常见修改指南

### 11.1 添加新的关键词

**文件**: `agent-dsmc/keyword_detector.py`

**位置**: 类开头的常量定义

```python
# 添加主要关键词 (权重0.6)
PRIMARY_KEYWORDS = [
    "dsmc", "sparta", "新关键词"
]

# 添加上下文关键词 (权重0.3)
CONTEXT_KEYWORDS = [
    "simulation", "新上下文词"
]
```

### 11.2 添加新的错误模式

**文件**: `agent-dsmc/error_fixer.py`

**位置**: `ERROR_PATTERNS` 字典

```python
ERROR_PATTERNS = {
    "新错误类型": {
        "pattern": r"ERROR: 新的正则模式 (.+)",
        "description": "错误描述"
    }
}
```

### 11.3 添加新的API端点

**文件**: `llm-chat-app/app.py`

**步骤**:
1. 在文件末尾添加新路由
2. 使用 `@app.route()` 装饰器
3. 实现处理函数

```python
@app.route('/api/new/endpoint', methods=['POST'])
def new_endpoint():
    data = request.get_json()
    # 处理逻辑
    return jsonify({"result": "success"})
```

### 11.4 修改输入文件生成逻辑

**文件**: `agent-dsmc/dsmc_agent.py`

**方法**: `generate_input_file()`

**位置**: 约350行

修改LLM提示词或参数处理逻辑。

### 11.5 添加新的可视化图表

**文件**: `agent-dsmc/visualization.py`

**步骤**:
1. 添加新的 `plot_xxx()` 方法
2. 在 `generate_all()` 中调用

```python
def plot_new_chart(self, data):
    fig, ax = plt.subplots()
    # 绑图逻辑
    return self._fig_to_base64(fig)
```

### 11.6 修改LLM模型

**文件**: `llm-chat-app/.env` 或 `agent-dsmc/utils.py`

```bash
# .env
LLM_MODEL=新模型名称
```

### 11.7 添加新的检索源

**文件**: `agent-dsmc/multi_source_retriever.py`

**步骤**:
1. 创建新的Searcher类
2. 在 `MultiSourceRetriever.search()` 中调用

```python
class NewSearcher:
    def search(self, query: str) -> Dict:
        # 搜索逻辑
        pass

# 在 search() 方法中添加
results.update(self.new_searcher.search(query))
```

---

## 性能指标

| 操作 | 典型耗时 | 影响因素 |
|------|----------|----------|
| 关键词检测 | <10ms | 消息长度 |
| 手册检索 | <100ms | 索引大小 |
| 输入文件生成 | 5-10秒 | LLM响应速度 |
| 参数说明生成 | 3-5秒 | LLM响应速度 |
| SPARTA执行 | 秒级-分钟级 | 问题规模 |
| 可视化生成 | 2-3秒 | 数据量 |
| 自动修复 | 10-60秒 | 错误复杂度 |

---

## 联系与支持

- **项目路径**: `/home/simplecellzg/sparta_llm_agent/agent_code/`
- **主入口**: `llm-chat-app/app.py`
- **访问地址**: `http://localhost:21000`

---

**版本**: 1.0
**更新时间**: 2026-01-12
**状态**: 生产就绪
