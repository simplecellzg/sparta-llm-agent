# DSMC控制面板参数同步实现

## 实施日期
2026-01-20

## 需求描述
自动修复次数默认为10，当点击仿真运行的时候，要检查控制面板上的参数设定，然后与后端的运行参数要同步。

## 实施方案

### 统一配置管理
实现了前端控制面板与后端配置的完全同步，确保所有运行参数统一从后端配置管理。

## 修改文件列表

### 1. `.env` 配置文件
**文件路径**: `llm-chat-app/.env`

**修改内容**:
- 添加了完整的默认运行参数配置段：
```env
# Default Runtime Parameters
MAX_TOKENS=4096
DEFAULT_TEMPERATURE=0.7
DEFAULT_MAX_STEPS=1000
DEFAULT_NUM_CORES=4
DEFAULT_MAX_FIX_ATTEMPTS=10

# RAG Configuration
RAG_ENABLED=true
RAG_TOP_K=5
```

**关键变化**:
- 新增 `DEFAULT_MAX_FIX_ATTEMPTS=10` 配置项（原来是硬编码的3）

---

### 2. 设置面板HTML
**文件路径**: `llm-chat-app/templates/index.html`

**修改位置**: 运行参数设置区域（约509-519行）

**修改内容**:
```html
<div class="setting-item">
    <label for="settingMaxFixAttempts">默认自动修复次数</label>
    <input type="number" id="settingMaxFixAttempts" value="10" min="0" max="20">
</div>
```

**关键变化**:
- 在设置面板中添加了"默认自动修复次数"配置项
- 用户可以在设置中修改这个默认值

**控制面板默认值修改**（约223-224行）:
```html
<input type="number" id="panelMaxFixAttempts" value="10" min="0" max="10" step="1" />
```

**关键变化**:
- 将控制面板中最大修复次数的默认值从3改为10

---

### 3. 设置面板JavaScript
**文件路径**: `llm-chat-app/static/components/settings-panel.js`

#### 修改1: `populateForm()` 方法（约82行）
**修改内容**:
```javascript
// Runtime Parameters
document.getElementById('settingMaxTokens').value = settings.MAX_TOKENS || '4096';
document.getElementById('settingTemperature').value = settings.DEFAULT_TEMPERATURE || '0.7';
document.getElementById('settingMaxSteps').value = settings.DEFAULT_MAX_STEPS || '1000';
document.getElementById('settingNumCores').value = settings.DEFAULT_NUM_CORES || '4';
document.getElementById('settingMaxFixAttempts').value = settings.DEFAULT_MAX_FIX_ATTEMPTS || '10';
```

**关键变化**:
- 从后端加载 `DEFAULT_MAX_FIX_ATTEMPTS` 配置并填充到表单

#### 修改2: `collectFormData()` 方法（约99行）
**修改内容**:
```javascript
const formData = {
    API_TYPE: document.querySelector('input[name="apiType"]:checked').value,
    API_URL: document.getElementById('settingApiUrl').value.trim(),
    LLM_MODEL: document.getElementById('settingLlmModel').value,
    MAX_TOKENS: document.getElementById('settingMaxTokens').value,
    DEFAULT_TEMPERATURE: document.getElementById('settingTemperature').value,
    DEFAULT_MAX_STEPS: document.getElementById('settingMaxSteps').value,
    DEFAULT_NUM_CORES: document.getElementById('settingNumCores').value,
    DEFAULT_MAX_FIX_ATTEMPTS: document.getElementById('settingMaxFixAttempts').value,
    RAG_ENABLED: document.getElementById('settingRagEnabled').checked ? 'true' : 'false',
    RAG_TOP_K: document.getElementById('settingRagTopK').value
};
```

**关键变化**:
- 收集 `DEFAULT_MAX_FIX_ATTEMPTS` 字段并发送到后端

---

### 4. 主应用JavaScript
**文件路径**: `llm-chat-app/static/app.js`

#### 修改1: 新增 `loadControlPanelDefaults()` 函数（约2169-2197行）
**功能说明**: 从后端加载控制面板的默认参数

**实现代码**:
```javascript
// 从后端加载控制面板默认参数
async function loadControlPanelDefaults() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) {
            console.error('加载设置失败');
            return;
        }

        const data = await response.json();
        const settings = data.settings;

        // 更新控制面板的默认值
        const numCoresInput = document.getElementById('panelNumCores');
        const maxStepsInput = document.getElementById('panelMaxSteps');
        const maxFixAttemptsInput = document.getElementById('panelMaxFixAttempts');

        if (numCoresInput && settings.DEFAULT_NUM_CORES) {
            numCoresInput.value = settings.DEFAULT_NUM_CORES;
        }
        if (maxStepsInput && settings.DEFAULT_MAX_STEPS) {
            maxStepsInput.value = settings.DEFAULT_MAX_STEPS;
        }
        if (maxFixAttemptsInput && settings.DEFAULT_MAX_FIX_ATTEMPTS) {
            maxFixAttemptsInput.value = settings.DEFAULT_MAX_FIX_ATTEMPTS;
        }
    } catch (error) {
        console.error('加载控制面板默认参数失败:', error);
    }
}
```

**关键功能**:
- 调用 `/api/settings` 获取后端配置
- 更新控制面板中的CPU核数、最大步数、最大修复次数

#### 修改2: 更新 `showDSMCControlPanel()` 函数（约2213-2214行）
**修改内容**:
```javascript
// 从后端加载默认参数
loadControlPanelDefaults();
```

**关键变化**:
- 每次显示控制面板时，自动加载最新的默认参数

#### 修改3: 更新 `DOMContentLoaded` 事件处理器（约1018-1019行）
**修改内容**:
```javascript
// 加载控制面板默认参数
loadControlPanelDefaults();
```

**关键变化**:
- 页面加载时立即加载控制面板的默认参数

---

## 实现效果

### 1. 参数同步流程
```
用户在设置面板修改参数
       ↓
保存到后端配置（.env或settings.json）
       ↓
前端加载配置 (/api/settings)
       ↓
更新控制面板默认值
       ↓
用户点击"运行仿真"
       ↓
使用控制面板当前值（已同步的默认值或用户手动修改值）
```

### 2. 关键时机
控制面板参数在以下时机自动同步：
- **页面初始加载时**: `DOMContentLoaded` 事件中调用 `loadControlPanelDefaults()`
- **显示控制面板时**: `showDSMCControlPanel()` 函数调用 `loadControlPanelDefaults()`
- **用户保存设置后**: 设置面板保存成功后，下次打开控制面板会自动加载新值

### 3. 用户体验
- ✅ 用户可以在设置面板统一管理所有默认参数
- ✅ 控制面板自动显示最新的默认值
- ✅ 用户仍可在控制面板临时调整参数（单次运行）
- ✅ 所有参数保持一致性，避免混淆

---

## 验证清单

- [x] `.env` 文件包含 `DEFAULT_MAX_FIX_ATTEMPTS=10`
- [x] 设置面板HTML显示"默认自动修复次数"配置项
- [x] 设置面板JS能正确加载和保存 `DEFAULT_MAX_FIX_ATTEMPTS`
- [x] 控制面板HTML默认值改为10
- [x] 控制面板在显示时自动加载后端配置
- [x] 页面加载时自动初始化控制面板参数
- [ ] 运行时验证：修改设置后，控制面板参数正确更新
- [ ] 运行时验证：点击运行仿真使用正确的参数值

---

## 技术细节

### API端点
- **GET /api/settings**: 获取当前配置
  - 返回格式: `{ "settings": { "DEFAULT_MAX_FIX_ATTEMPTS": "10", ... } }`

### 配置优先级
1. **settings.json** (运行时覆盖) - 最高优先级
2. **.env** (永久配置) - 默认值
3. **硬编码** (fallback) - 最低优先级

### 配置流程
```
.env (永久配置)
    ↓
ConfigManager 加载
    ↓
settings.json 覆盖 (如果存在)
    ↓
/api/settings 提供给前端
    ↓
前端控制面板使用
```

---

## 后续改进建议

1. **实时同步**: 当其他用户修改设置时，通过WebSocket推送更新
2. **参数验证**: 在前端和后端都添加参数范围验证
3. **参数历史**: 记录参数修改历史，方便回溯
4. **批量导入**: 支持从文件导入预设配置
5. **参数模板**: 提供不同场景的参数预设（快速测试、生产运行等）

---

## 相关文档
- 配置管理: `llm-chat-app/config_manager.py`
- API路由: `llm-chat-app/app.py` `/api/settings`
- 设置面板: `llm-chat-app/static/components/settings-panel.js`
修复完成时间: 2026-01-20 12:10:12
