# UI修复与功能增强 - TDD实施计划

**日期**: 2026-01-16
**项目**: SPARTA LLM Agent Chat Application
**目标**: 修复API配置、模型选择、DSMC控制面板可见性等7个关键问题

---

## 问题概览

1. ❌ API配置返回401错误 - 令牌认证失败
2. ❌ 预设的三个模型未显示在选择列表中
3. ❌ 系统设置中默认模型未设置为第一个模型
4. ❌ 运行参数中缺少"最大修复次数"参数传递
5. ❌ 预设模板选项处于灰色不可用状态
6. ❌ DSMC控制面板不保持常亮
7. ❌ 大气模型默认值应为US76而非ISA

---

## Issue 1: API认证401错误

### 当前状态
- **文件**: `llm-chat-app/app.py:979`
- **问题**: API返回401错误，提示"无效的令牌"
- **根因**: 虽然代码使用了Bearer认证格式，但可能是：
  1. API密钥本身无效或过期
  2. 令牌字符串有空格或格式问题
  3. API端点URL配置不正确

### 测试用例

#### Test 1.1: 验证API密钥格式
```python
# test_api_auth.py
def test_api_key_no_whitespace():
    """测试API密钥没有前后空格"""
    from app import API_KEY
    assert API_KEY == API_KEY.strip(), "API key contains whitespace"
    assert len(API_KEY) > 0, "API key is empty"

def test_api_key_format():
    """测试API密钥格式正确"""
    from app import API_KEY
    assert API_KEY.startswith('sk-'), "API key should start with 'sk-'"
    assert len(API_KEY) >= 20, "API key too short"
```

#### Test 1.2: 测试API请求头构造
```python
def test_authorization_header_format():
    """测试Authorization头格式正确"""
    from app import API_KEY
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    assert headers["Authorization"].startswith("Bearer sk-"), \
        "Authorization header format incorrect"
    assert " " in headers["Authorization"], \
        "Missing space between Bearer and token"
```

#### Test 1.3: 测试API端点URL
```python
def test_api_url_format():
    """测试API URL格式正确"""
    from app import API_URL
    assert API_URL.startswith('https://'), "API URL should use HTTPS"
    assert not API_URL.endswith('/'), "API URL should not end with slash"

def test_chat_completions_endpoint():
    """测试聊天API端点路径"""
    from app import API_URL
    endpoint = f"{API_URL}/chat/completions"
    assert "/v1/chat/completions" in endpoint, "Missing /chat/completions path"
```

### 实施步骤

1. **添加调试日志** (`app.py:973-991`)
   ```python
   logger.info(f"📤 调用LLM API: {API_URL}")
   logger.info(f"  API密钥前缀: {API_KEY[:15]}...")  # 只记录前缀
   logger.info(f"  完整端点: {API_URL}/chat/completions")
   ```

2. **添加API响应错误处理** (`app.py:1028-1030`)
   ```python
   except Exception as e:
       logger.error(f"❌ LLM调用失败: {str(e)}", exc_info=True)
       if hasattr(e, 'response'):
           logger.error(f"  API响应: {e.response.text}")
       yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
   ```

3. **添加.env文件验证函数**
   ```python
   def validate_env_config():
       """在启动时验证环境配置"""
       errors = []

       if not API_KEY or API_KEY != API_KEY.strip():
           errors.append("API_KEY contains whitespace or is empty")

       if not API_URL.startswith('https://'):
           errors.append("API_URL should use HTTPS")

       if len(MODELS) == 0:
           errors.append("MODELS list is empty")

       if errors:
           logger.error("❌ 配置验证失败:")
           for error in errors:
               logger.error(f"  - {error}")
           return False

       logger.info("✅ 配置验证通过")
       return True
   ```

4. **在启动时调用验证** (`app.py:2355附近`)
   ```python
   if __name__ == '__main__':
       if not validate_env_config():
           logger.error("配置验证失败，请检查.env文件")
           sys.exit(1)

       logger.info("🚀 启动LLM聊天应用服务器")
       # ...
   ```

---

## Issue 2: 模型列表未显示

### 当前状态
- **问题**: .env中配置的三个模型未出现在UI选择列表中
- **配置**: `MODELS=claude-opus-4-5-20251101,gemini-3-pro-preview,deepseek-v3-250324`
- **根因**: 前端可能使用缓存的模型列表，未动态加载

### 测试用例

#### Test 2.1: 后端模型列表加载
```python
def test_models_loaded_from_env():
    """测试从.env加载的模型列表"""
    from app import MODELS
    assert len(MODELS) == 3, f"Expected 3 models, got {len(MODELS)}"
    assert "claude-opus-4-5-20251101" in MODELS
    assert "gemini-3-pro-preview" in MODELS
    assert "deepseek-v3-250324" in MODELS

def test_models_api_endpoint():
    """测试/api/models端点返回正确的模型列表"""
    from app import app
    with app.test_client() as client:
        response = client.get('/api/models')
        assert response.status_code == 200
        models = response.get_json()
        assert isinstance(models, list)
        assert len(models) == 3
```

#### Test 2.2: 前端模型选择器填充
```javascript
// test_model_selector.js
describe('Model Selector', () => {
    test('should fetch models from API on page load', async () => {
        const response = await fetch('/api/models');
        const models = await response.json();

        expect(models).toHaveLength(3);
        expect(models).toContain('claude-opus-4-5-20251101');
    });

    test('should populate model selector dropdown', () => {
        const select = document.getElementById('modelSelect');
        expect(select.options.length).toBeGreaterThan(0);
        expect(select.options[0].value).toBe('claude-opus-4-5-20251101');
    });
});
```

### 实施步骤

1. **确认/api/models端点存在** (`app.py:270-272`)
   - 端点已存在，返回MODELS列表 ✅

2. **修改前端动态加载模型** (`static/app.js:1030附近`)
   ```javascript
   // 在页面初始化时动态加载模型列表
   async function loadAvailableModels() {
       try {
           const response = await fetch('/api/models', {
               method: 'GET',
               headers: { 'Content-Type': 'application/json' }
           });

           if (!response.ok) {
               console.error('Failed to fetch models:', response.status);
               return;
           }

           const models = await response.json();
           const modelSelect = document.getElementById('modelSelect');

           if (modelSelect && models.length > 0) {
               // 清空现有选项
               modelSelect.innerHTML = '';

               // 添加从API获取的模型
               models.forEach(model => {
                   const option = document.createElement('option');
                   option.value = model;
                   option.textContent = model;
                   modelSelect.appendChild(option);
               });

               console.log(`✅ 加载了 ${models.length} 个模型`);
           }
       } catch (error) {
           console.error('Error loading models:', error);
       }
   }
   ```

3. **在页面加载时调用** (`static/app.js:1150附近的init函数`)
   ```javascript
   async function init() {
       // ...现有初始化代码...

       // 加载可用模型列表
       await loadAvailableModels();

       // ...其他初始化...
   }
   ```

4. **修改模板以避免硬编码** (`templates/index.html:72-78`)
   ```html
   <div class="model-selector">
       <label for="modelSelect">模型</label>
       <select id="modelSelect">
           <!-- 模型列表将通过JavaScript动态加载 -->
       </select>
   </div>
   ```

---

## Issue 3: 设置面板默认模型

### 当前状态
- **文件**: `static/components/settings-panel.js:37`
- **问题**: 硬编码默认模型为`claude-sonnet-4-5-20250929`，应使用MODELS[0]

### 测试用例

#### Test 3.1: 设置面板默认值
```javascript
describe('Settings Panel', () => {
    test('should use first model from MODELS as default', async () => {
        const settingsPanel = new SettingsPanel();
        await settingsPanel.loadSettings();

        const modelInput = document.getElementById('settingLlmModel');
        expect(modelInput.value).toBe('claude-opus-4-5-20251101');
    });

    test('should load MODELS list into settings dropdown', async () => {
        const response = await fetch('/api/settings');
        const data = await response.json();

        expect(data.settings.MODELS).toBeDefined();
        const models = data.settings.MODELS.split(',');
        expect(models[0]).toBe('claude-opus-4-5-20251101');
    });
});
```

### 实施步骤

1. **修改后端/api/settings端点** (`app.py:2180-2207`)
   ```python
   @app.route('/api/settings', methods=['GET'])
   def get_settings():
       """Get current application settings"""
       try:
           config = get_config_manager()
           settings = config.get_all()

           # 添加MODELS列表
           settings['MODELS'] = ','.join(MODELS)  # 添加这一行

           # Mask sensitive keys
           masked_settings = {}
           # ...现有代码...
   ```

2. **修改前端settings-panel.js** (`static/components/settings-panel.js:30-48`)
   ```javascript
   populateForm() {
       const settings = this.currentSettings;

       // 获取模型列表并设置默认值
       const modelsList = settings.MODELS ? settings.MODELS.split(',') : [];
       const defaultModel = modelsList.length > 0 ? modelsList[0] : 'claude-opus-4-5-20251101';

       // API Configuration
       document.getElementById('settingApiUrl').value = settings.API_URL || '';
       document.getElementById('settingApiKey').value = settings.API_KEY || '';

       // 动态填充模型选择器
       const modelSelect = document.getElementById('settingLlmModel');
       if (modelSelect && modelsList.length > 0) {
           modelSelect.innerHTML = '';
           modelsList.forEach(model => {
               const option = document.createElement('option');
               option.value = model.trim();
               option.textContent = model.trim();
               modelSelect.appendChild(option);
           });
       }

       // 设置当前选中的模型
       modelSelect.value = settings.LLM_MODEL || defaultModel;

       // ...其他设置...
   }
   ```

3. **更新settings-panel.js模板** (`templates/index.html:476-483`)
   ```html
   <div class="setting-item">
       <label for="settingLlmModel">LLM模型</label>
       <select id="settingLlmModel">
           <!-- 动态从MODELS配置加载 -->
       </select>
   </div>
   ```

---

## Issue 4: 最大修复次数参数传递

### 当前状态
- **UI字段**: `templates/index.html:225` - `#panelMaxFixAttempts`
- **问题**: 参数未传递到后端API调用

### 测试用例

#### Test 4.1: 前端参数收集
```javascript
describe('Simulation Parameters', () => {
    test('should collect max_fix_attempts from panel', () => {
        document.getElementById('panelMaxFixAttempts').value = '5';

        const params = collectSimulationParams();
        expect(params.max_fix_attempts).toBe(5);
    });

    test('should include max_fix_attempts in API call', async () => {
        const fetchSpy = jest.spyOn(window, 'fetch');

        await runSimulation();

        const callArgs = fetchSpy.mock.calls[0];
        const body = JSON.parse(callArgs[1].body);
        expect(body.max_fix_attempts).toBeDefined();
    });
});
```

#### Test 4.2: 后端参数接收
```python
def test_run_simulation_with_max_fix_attempts():
    """测试运行仿真时接收max_fix_attempts参数"""
    from app import app

    with app.test_client() as client:
        response = client.post('/api/dsmc/run',
            json={
                'session_id': 'test_session',
                'num_cores': 4,
                'max_steps': 1000,
                'max_fix_attempts': 5
            })

        # 验证参数被接收（通过日志或返回值）
        # assert captured in logs: "最大修复次数: 5"
```

### 实施步骤

1. **查找runSimulation函数** (需要grep确认位置)
   ```bash
   grep -n "function runSimulation" llm-chat-app/static/app.js
   ```

2. **修改runSimulation函数参数收集**
   ```javascript
   function runSimulation() {
       if (!currentSessionId) {
           alert('没有活动的DSMC会话');
           return;
       }

       // 收集运行参数
       const numCores = parseInt(document.getElementById('panelNumCores').value);
       const maxSteps = parseInt(document.getElementById('panelMaxSteps').value);
       const maxMemory = parseInt(document.getElementById('panelMaxMemory').value);
       const maxFixAttempts = parseInt(document.getElementById('panelMaxFixAttempts').value); // 添加这一行

       // 发送到后端
       fetch(`/api/dsmc/run`, {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({
               session_id: currentSessionId,
               conversation_id: currentConversationId,
               num_cores: numCores,
               max_steps: maxSteps,
               max_memory_gb: maxMemory,
               max_fix_attempts: maxFixAttempts  // 添加这一行
           })
       });

       // ...
   }
   ```

3. **验证后端已支持该参数** (`app.py:1285-1295`)
   - ✅ 后端已经支持: `max_fix_attempts = data.get('max_fix_attempts', 3)`
   - ✅ 日志已输出: `logger.info(f"  最大修复次数: {max_fix_attempts}")`

---

## Issue 5: 预设模板选择启用

### 当前状态
- **HTML**: `templates/index.html:198` - `#templateSelect`
- **问题**: 控制面板有`.disabled`类使模板选择器灰色不可用
- **根因**: 控制面板初始状态`class="dsmc-control-panel disabled"`

### 测试用例

#### Test 5.1: 模板选择器可用性
```javascript
describe('Template Selector', () => {
    test('should be enabled on page load', () => {
        const templateSelect = document.getElementById('templateSelect');
        expect(templateSelect.disabled).toBe(false);
        expect(templateSelect.classList.contains('disabled')).toBe(false);
    });

    test('should load templates from JSON', async () => {
        await loadDSMCTemplates();

        const templateSelect = document.getElementById('templateSelect');
        expect(templateSelect.options.length).toBeGreaterThan(1);
    });

    test('should call loadTemplate on selection change', () => {
        const loadTemplateSpy = jest.spyOn(window, 'loadTemplate');
        const templateSelect = document.getElementById('templateSelect');

        templateSelect.value = 'hypersonic-flow';
        templateSelect.dispatchEvent(new Event('change'));

        expect(loadTemplateSpy).toHaveBeenCalled();
    });
});
```

### 实施步骤

1. **修改CSS移除模板选择器禁用** (`static/style.css`)
   ```css
   /* 模板选择器始终可用 */
   .dsmc-control-panel.disabled .template-selector-group {
       opacity: 1 !important;
       pointer-events: auto !important;
   }

   .dsmc-control-panel.disabled .template-selector-group select {
       opacity: 1 !important;
       cursor: pointer !important;
   }
   ```

2. **修改loadTemplate函数使其创建新会话** (`static/app.js:365附近`)
   ```javascript
   function loadTemplate() {
       const select = document.getElementById('templateSelect');
       const templateId = select.value;

       if (!templateId) {
           document.getElementById('templateDescription').textContent = '';
           return;
       }

       const template = dsmcTemplates.find(t => t.id === templateId);
       if (!template) return;

       // 显示模板描述
       document.getElementById('templateDescription').textContent = template.description;

       // 询问用户是否要开始新会话
       if (confirm(`加载模板: ${template.name}\n\n${template.description}\n\n是否要用此模板创建新的DSMC会话?`)) {
           // 填充参数到消息输入框
           messageInput.value = `使用${template.name}模板生成DSMC输入文件`;

           // 或者直接调用参数表单并预填充
           displayParameterForm();
           setTimeout(() => {
               populateFormFromTemplate(template);
           }, 100);
       }
   }

   function populateFormFromTemplate(template) {
       // 根据模板的params填充表单
       if (template.params) {
           for (const [key, value] of Object.entries(template.params)) {
               const input = document.getElementById(key);
               if (input) {
                   input.value = value;
               }
           }
       }
   }
   ```

3. **确保模板数据文件存在** (`static/data/dsmc-templates.json`)
   - 需要检查文件是否存在，如果不存在则创建示例模板

---

## Issue 6: DSMC控制面板常亮

### 当前状态
- **HTML**: `templates/index.html:186` - `.dsmc-control-panel disabled`
- **JS**: `static/app.js:2140` - `hideDSMCControlPanel()` 函数
- **问题**: 控制面板在无会话时变暗并禁用

### 测试用例

#### Test 6.1: 控制面板可见性
```javascript
describe('DSMC Control Panel', () => {
    test('should be visible on page load', () => {
        const panel = document.getElementById('dsmcControlPanel');
        expect(panel.classList.contains('hidden')).toBe(false);
    });

    test('should remain visible when switching conversations', async () => {
        await selectConversation('conv1');
        const panel = document.getElementById('dsmcControlPanel');
        expect(panel.classList.contains('hidden')).toBe(false);
    });

    test('should update session status without hiding', () => {
        const panel = document.getElementById('dsmcControlPanel');
        const initialDisplay = window.getComputedStyle(panel).display;

        // 模拟会话状态改变
        updatePanelSessionStatus(null);

        const afterDisplay = window.getComputedStyle(panel).display;
        expect(afterDisplay).toBe(initialDisplay);
    });
});
```

### 实施步骤

1. **修改CSS保持面板可见** (`static/style.css`)
   ```css
   /* DSMC控制面板始终可见，用状态指示器代替灰化 */
   .dsmc-control-panel {
       display: flex;
       flex-direction: column;
       opacity: 1 !important;  /* 强制不透明 */
       pointer-events: auto !important;  /* 强制可交互 */
   }

   /* 用顶部状态栏指示是否有活动会话 */
   .dsmc-control-panel::before {
       content: attr(data-status);
       display: block;
       padding: 8px;
       background: var(--bg-tertiary);
       border-bottom: 1px solid var(--border-color);
       font-size: 12px;
       text-align: center;
       color: var(--text-secondary);
   }

   .dsmc-control-panel[data-status="active"]::before {
       background: var(--success-bg);
       color: var(--success-color);
       content: "✓ 会话活跃";
   }

   .dsmc-control-panel[data-status="inactive"]::before {
       content: "○ 无活动会话 - 可选择模板开始";
   }
   ```

2. **修改hideDSMCControlPanel函数** (`static/app.js:2140`)
   ```javascript
   // 不再隐藏面板，只更新状态
   function hideDSMCControlPanel() {
       const panel = document.getElementById('dsmcControlPanel');
       if (panel) {
           // 移除disabled类
           panel.classList.remove('disabled');
           // 设置状态为inactive
           panel.setAttribute('data-status', 'inactive');

           // 禁用运行按钮（但保持模板选择器可用）
           const runBtn = document.getElementById('runSimulationBtn');
           if (runBtn) {
               runBtn.disabled = true;
               runBtn.title = '请先创建DSMC会话';
           }
       }
   }
   ```

3. **修改showDSMCControlPanel函数** (`static/app.js:2127`)
   ```javascript
   function showDSMCControlPanel() {
       const panel = document.getElementById('dsmcControlPanel');
       if (panel) {
           panel.classList.remove('disabled');
           panel.setAttribute('data-status', 'active');

           // 启用运行按钮
           const runBtn = document.getElementById('runSimulationBtn');
           if (runBtn) {
               runBtn.disabled = false;
               runBtn.title = '运行仿真';
           }
       }
   }
   ```

4. **移除不必要的hide调用**
   - 搜索所有`hideDSMCControlPanel()`调用
   - 评估是否需要保留（大多数情况下应该只更新状态而非隐藏）

---

## Issue 7: 大气模型默认为US76

### 当前状态
- **文件**: `static/app.js:2262`
- **当前**: `<option value="ISA" selected>ISA 标准大气</option>`
- **目标**: 将`selected`属性移到US76选项

### 测试用例

#### Test 7.1: 默认大气模型
```javascript
describe('Atmospheric Model', () => {
    test('should default to US76', () => {
        displayParameterForm();

        const modelSelect = document.getElementById('atmosphereModel');
        expect(modelSelect.value).toBe('US76');
    });

    test('should calculate atmosphere params with US76', () => {
        document.getElementById('altitude').value = '100';
        document.getElementById('atmosphereModel').value = 'US76';

        onAltitudeChange();

        const preview = document.getElementById('atmosphereValues');
        expect(preview.textContent).toContain('US76');
    });
});
```

### 实施步骤

1. **修改displayParameterForm函数** (`static/app.js:2261-2266`)
   ```javascript
   <select id="atmosphereModel" name="atmosphereModel" onchange="onAtmosphereModelChange()">
       <option value="ISA">ISA 标准大气</option>
       <option value="US76" selected>US76 标准大气</option>  <!-- 移动selected到这里 -->
       <option value="NRLMSISE00">NRLMSISE-00</option>
       <option value="custom">自定义</option>
   </select>
   ```

2. **确保初始化时使用US76计算** (`static/app.js:200附近`)
   ```javascript
   function onAltitudeChange() {
       const altitude = parseFloat(document.getElementById('altitude').value);
       const model = document.getElementById('atmosphereModel')?.value || 'US76';  // 默认US76

       if (isNaN(altitude) || altitude < 0) return;

       const params = calculateAtmosphereParams(altitude, model);
       // ...
   }
   ```

3. **更新工具提示说明** (`static/app.js:2267`)
   ```javascript
   <span class="tooltip-icon" title="US76适用于0-1000km，ISA适用于0-86km，NRLMSISE-00适用于高层大气">?</span>
   ```

---

## 测试执行计划

### 第一阶段: 单元测试
1. 运行后端Python测试
   ```bash
   cd llm-chat-app
   pytest tests/test_api_auth.py -v
   pytest tests/test_models.py -v
   pytest tests/test_settings.py -v
   ```

2. 运行前端JavaScript测试
   ```bash
   npm test -- test_model_selector.js
   npm test -- test_settings_panel.js
   npm test -- test_simulation_params.js
   ```

### 第二阶段: 集成测试
1. 测试API认证流程
   - 启动服务器
   - 发送测试消息
   - 验证不再返回401错误

2. 测试模型选择
   - 打开应用
   - 检查模型下拉列表
   - 验证三个模型都显示

3. 测试DSMC控制面板
   - 检查面板初始可见
   - 选择模板
   - 验证模板可加载

### 第三阶段: 端到端测试
```python
# test_e2e.py
def test_full_dsmc_workflow():
    """完整的DSMC工作流测试"""
    # 1. 打开应用
    driver.get('http://localhost:21000')

    # 2. 验证控制面板可见
    panel = driver.find_element(By.ID, 'dsmcControlPanel')
    assert panel.is_displayed()

    # 3. 选择模板
    template_select = driver.find_element(By.ID, 'templateSelect')
    template_select.select_by_value('hypersonic-flow')

    # 4. 验证参数表单打开且US76已选中
    wait.until(EC.presence_of_element_located((By.ID, 'atmosphereModel')))
    atm_model = driver.find_element(By.ID, 'atmosphereModel')
    assert atm_model.get_attribute('value') == 'US76'

    # 5. 设置最大修复次数
    max_fix = driver.find_element(By.ID, 'panelMaxFixAttempts')
    max_fix.clear()
    max_fix.send_keys('5')

    # 6. 提交并验证请求包含max_fix_attempts
    # (需要设置网络拦截来验证)
```

---

## 实施顺序建议

1. **Issue 1 (API认证)** - 最高优先级，影响所有功能
2. **Issue 2 (模型列表)** - 高优先级，用户可见问题
3. **Issue 3 (默认模型)** - 中优先级，设置UX优化
4. **Issue 7 (大气模型)** - 中优先级，一行代码修复
5. **Issue 6 (控制面板)** - 中优先级，UI改进
6. **Issue 5 (模板选择)** - 中优先级，依赖Issue 6
7. **Issue 4 (修复次数)** - 低优先级，功能已存在只需连接

---

## 回归测试清单

在实施所有修复后，执行以下检查：

- [ ] API调用不再返回401错误
- [ ] 模型选择器显示3个预设模型
- [ ] 设置面板默认选中第一个模型
- [ ] 新建对话时模型默认为第一个
- [ ] DSMC控制面板始终可见
- [ ] 预设模板选择器可用且能加载模板
- [ ] 参数表单中大气模型默认为US76
- [ ] 运行仿真时max_fix_attempts参数传递到后端
- [ ] 后端日志显示正确的max_fix_attempts值
- [ ] 所有现有功能仍正常工作（无回归）

---

## 性能考虑

1. **模型列表加载**: 使用缓存避免重复API调用
   ```javascript
   let cachedModels = null;
   async function loadAvailableModels() {
       if (cachedModels) return cachedModels;
       // ...fetch and cache...
   }
   ```

2. **控制面板渲染**: 避免不必要的DOM操作
   - 只在状态真正改变时更新UI
   - 使用`requestAnimationFrame`优化动画

3. **大气模型计算**: 缓存计算结果
   ```javascript
   const atmParamsCache = new Map();
   function calculateAtmosphereParams(altitude, model) {
       const key = `${altitude}_${model}`;
       if (atmParamsCache.has(key)) {
           return atmParamsCache.get(key);
       }
       const result = _calculateAtmosphereParams(altitude, model);
       atmParamsCache.set(key, result);
       return result;
   }
   ```

---

## 文档更新

完成实施后需要更新：

1. **用户文档**
   - 添加模型配置说明
   - 更新DSMC控制面板使用指南
   - 添加预设模板使用示例

2. **开发者文档**
   - API认证最佳实践
   - 环境变量配置指南
   - 测试覆盖率报告

3. **CHANGELOG**
   ```markdown
   ## [v2.1.0] - 2026-01-16

   ### Fixed
   - API authentication 401 error with improved error logging
   - Model selection dropdown now displays all configured models
   - Settings panel defaults to first model from configuration
   - DSMC simulation max_fix_attempts parameter now correctly passed
   - Preset template selector enabled for immediate use
   - DSMC control panel remains visible and accessible at all times
   - Atmospheric model defaults to US76 instead of ISA

   ### Improved
   - Added comprehensive validation for .env configuration
   - Enhanced error messages for API failures
   - Better logging for debugging authentication issues
   ```

---

## 总结

本TDD计划涵盖了7个核心问题的：
- **测试用例设计** (单元、集成、E2E)
- **详细实施步骤** (代码位置、修改内容)
- **测试执行计划** (三阶段测试策略)
- **回归测试清单** (确保无副作用)
- **性能优化建议** (缓存、DOM优化)

预计实施时间: 4-6小时
测试时间: 2-3小时
总计: 6-9小时

---

**下一步**: 是否开始实施? 建议从Issue 1开始，逐个解决并测试。
