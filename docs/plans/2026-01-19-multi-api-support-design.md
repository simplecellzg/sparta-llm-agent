# 多API格式支持和配置增强设计文档

**日期：** 2026-01-19
**状态：** 已批准
**作者：** Claude + User

## 概述

本设计文档描述了如何为LLM应用添加Anthropic和OpenAI兼容API的支持，修复预设模板bug，改进API key显示，以及实现API连接测试功能。

## 目标

1. 支持单套API配置，可选择Anthropic或OpenAI兼容格式
2. 正确掩码API key（显示前5位+后4位）
3. 修复预设模板加载时的DOM元素错误
4. 实现针对不同API格式的连接测试功能

## 架构设计

### 1. 环境变量配置

**.env文件新增/修改：**

```env
# Single API Configuration
API_URL=https://api.mjdjourney.cn/v1
API_KEY=sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d
API_TYPE=openai  # 新增：指定API格式 (anthropic 或 openai)

PORT=21000
MODELS=claude-opus-4-5-20251101,gemini-3-pro-preview,deepseek-v3-250324
LLM_MODEL=claude-opus-4-5-20251101
```

**说明：**
- `API_TYPE`: 新增配置项，值为 `anthropic` 或 `openai`
- 所有LLM和Agent应用使用同一套API配置

### 2. API Key掩码算法

**实现位置：** `app.py`

```python
def mask_api_key(value: str) -> str:
    """掩码API key，显示前5位和后4位"""
    if len(value) <= 9:
        return '***'
    return value[:5] + '*' * (len(value) - 9) + value[-4:]
```

**示例：**
- 输入：`sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d`
- 输出：`sk-LG****************************E12d`

### 3. 设置面板UI

**位置：** `templates/index.html`, `static/components/settings-panel.js`

**UI结构：**
```
┌─────────────────────────────────────┐
│ API类型: ◉ OpenAI兼容  ○ Anthropic │
├─────────────────────────────────────┤
│ API地址: [https://api.mjdjourney...]│
│ API密钥: [sk-LG***************E12d] │
│          [👁️ 显示/隐藏]              │
│ 当前模型: [claude-opus-4-5...]      │
├─────────────────────────────────────┤
│ [测试连接]  [保存]                  │
└─────────────────────────────────────┘
```

**HTML新增元素：**
```html
<div class="form-group">
    <label>API类型</label>
    <div>
        <label><input type="radio" name="apiType" value="openai" checked> OpenAI兼容</label>
        <label><input type="radio" name="apiType" value="anthropic"> Anthropic</label>
    </div>
</div>
```

### 4. API连接测试实现

#### 4.1 Anthropic API格式

**参考文档：**
- [Messages - Claude API Reference](https://docs.anthropic.com/en/api/messages)
- [API Overview - Claude Docs](https://platform.claude.com/docs/en/api/overview)

**端点：** `{API_URL}/messages`

**请求头：**
```python
headers = {
    'x-api-key': api_key,
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json'
}
```

**请求体：**
```python
payload = {
    'model': model,
    'max_tokens': 10,
    'messages': [{'role': 'user', 'content': 'test'}]
}
```

#### 4.2 OpenAI兼容API格式

**端点：** `{API_URL}/chat/completions`

**请求头：**
```python
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}
```

**请求体：**
```python
payload = {
    'model': model,
    'max_tokens': 10,
    'messages': [{'role': 'user', 'content': 'test'}]
}
```

#### 4.3 后端实现

**位置：** `app.py` - `/api/settings/test-connection`

```python
@app.route('/api/settings/test-connection', methods=['POST'])
def test_api_connection():
    """测试API连接"""
    data = request.get_json() or {}
    api_type = data.get('API_TYPE', 'openai')
    api_url = data.get('API_URL')
    api_key = data.get('API_KEY')
    model = data.get('LLM_MODEL')

    if api_type == 'anthropic':
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        test_url = f"{api_url.rstrip('/')}/messages"
        payload = {
            'model': model,
            'max_tokens': 10,
            'messages': [{'role': 'user', 'content': 'test'}]
        }
    else:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        test_url = f"{api_url.rstrip('/')}/chat/completions"
        payload = {
            'model': model,
            'max_tokens': 10,
            'messages': [{'role': 'user', 'content': 'test'}]
        }

    response = requests.post(test_url, headers=headers, json=payload, timeout=10)

    if response.status_code == 200:
        return jsonify({'success': True, 'message': '连接成功'})
    else:
        return jsonify({
            'success': False,
            'error': f'连接失败: {response.status_code} - {response.text[:100]}'
        }), 400
```

### 5. LLM调用统一处理

**位置：** `app.py` - 新增辅助函数

```python
def call_llm_api(messages, model=None, stream=False, max_tokens=4096):
    """统一的LLM API调用函数"""
    config = get_config_manager()
    api_type = config.get('API_TYPE', 'openai')
    api_url = config.get('API_URL')
    api_key = config.get('API_KEY')
    model = model or config.get('LLM_MODEL')

    if api_type == 'anthropic':
        return call_anthropic_api(api_url, api_key, model, messages, stream, max_tokens)
    else:
        return call_openai_api(api_url, api_key, model, messages, stream, max_tokens)

def call_anthropic_api(api_url, api_key, model, messages, stream, max_tokens):
    """Anthropic格式的API调用"""
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    url = f"{api_url.rstrip('/')}/messages"
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': messages,
        'stream': stream
    }
    return requests.post(url, headers=headers, json=payload, stream=stream, timeout=90)

def call_openai_api(api_url, api_key, model, messages, stream, max_tokens):
    """OpenAI兼容格式的API调用"""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    url = f"{api_url.rstrip('/')}/chat/completions"
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': messages,
        'stream': stream
    }
    return requests.post(url, headers=headers, json=payload, stream=stream, timeout=90)
```

**需要重构的调用点：**
- `/api/chat` 端点
- DSMC agent中的LLM调用
- lightrag agent中的LLM调用

### 6. 预设模板Bug修复

**位置：** `static/app.js` - `loadTemplate()` 函数

**问题：** 第398-400行尝试设置不存在的DOM元素：
```javascript
document.getElementById('gridX').value = params.grid_size[0];
document.getElementById('gridY').value = params.grid_size[1];
document.getElementById('gridZ').value = params.grid_size[2];
```

**解决方案：** 移除这3行代码（网格大小由系统自动计算）

## 文件修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `.env` | 新增 | 添加API_TYPE配置 |
| `config_manager.py` | 无需修改 | 现有功能已满足需求 |
| `app.py` | 修改/新增 | 1. 修改API key掩码逻辑<br>2. 新增统一LLM调用函数<br>3. 修改test-connection端点<br>4. 重构所有LLM调用点 |
| `settings-panel.js` | 修改 | 1. 添加API类型字段处理<br>2. 修改testConnection函数 |
| `templates/index.html` | 新增 | 添加API类型单选按钮UI |
| `static/app.js` | 修改 | 移除loadTemplate中398-400行 |

## 测试计划

### 单元测试
1. **API key掩码函数**
   - 测试正常长度key
   - 测试短key（<9字符）
   - 测试边界情况

### 集成测试
2. **API连接测试**
   - 测试Anthropic API格式
   - 测试OpenAI兼容格式
   - 测试错误处理（无效key、网络错误）

### 功能测试
3. **设置面板**
   - 切换API类型
   - 保存配置（runtime和persistent）
   - 验证API key正确掩码显示

4. **预设模板**
   - 加载各个模板不报错
   - 参数正确填充到表单

5. **LLM调用**
   - 聊天对话使用正确API格式
   - DSMC生成使用正确API格式
   - 流式响应正常工作

## 实施步骤

1. 修改`.env`添加API_TYPE配置
2. 实现API key掩码函数
3. 修复预设模板bug（快速修复）
4. 添加设置面板UI（API类型选择器）
5. 实现API连接测试（两种格式）
6. 重构LLM调用为统一接口
7. 更新所有LLM调用点
8. 测试验证

## 风险和注意事项

1. **向后兼容性：** 需要确保没有API_TYPE配置时默认使用openai格式
2. **错误处理：** 两种API的错误响应格式可能不同，需要统一处理
3. **流式响应：** Anthropic和OpenAI的SSE格式可能略有差异，需要仔细测试
4. **配置迁移：** 现有用户需要手动添加API_TYPE到.env

## 参考资料

- [Messages - Claude API Reference](https://docs.anthropic.com/en/api/messages)
- [Using the Messages API - Claude Docs](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)
- [API Overview - Claude Docs](https://platform.claude.com/docs/en/api/overview)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
