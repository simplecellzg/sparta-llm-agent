class SettingsPanel {
    constructor() {
        this.modal = document.getElementById('settingsPanel');
        this.overlay = document.getElementById('customModalOverlay');
        this.currentSettings = {};
    }

    async show() {
        await this.loadSettings();
        this.populateForm();
        this.overlay.classList.remove('hidden');
        this.modal.classList.remove('hidden');
    }

    hide() {
        this.modal.classList.add('hidden');
        this.overlay.classList.add('hidden');
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            this.currentSettings = data.settings;
        } catch (error) {
            console.error('Error loading settings:', error);
            alert('加载设置失败');
        }
    }

    populateForm() {
        const settings = this.currentSettings;

        // 获取模型列表并设置默认值
        const modelsList = settings.MODELS ? settings.MODELS.split(',') : [];
        const defaultModel = modelsList.length > 0 ? modelsList[0].trim() : 'claude-opus-4-5-20251101';

        // API Configuration
        // API Type
        const apiType = settings.API_TYPE || 'openai';
        const apiTypeRadios = document.querySelectorAll('input[name="apiType"]');
        apiTypeRadios.forEach(radio => {
            radio.checked = radio.value === apiType;
        });

        document.getElementById('settingApiUrl').value = settings.API_URL || '';

        // Handle API Key - don't populate if it's masked
        const apiKeyInput = document.getElementById('settingApiKey');
        const apiKey = settings.API_KEY || '';
        if (apiKey && apiKey.includes('*')) {
            // API key is masked, don't populate, just show placeholder
            apiKeyInput.value = '';
            apiKeyInput.placeholder = '已设置（如需修改请重新输入完整密钥）';
        } else {
            // API key is not masked (first load or empty)
            apiKeyInput.value = apiKey;
            apiKeyInput.placeholder = 'sk-...';
        }

        // 动态填充模型选择器
        const modelSelect = document.getElementById('settingLlmModel');
        if (modelSelect && modelsList.length > 0) {
            modelSelect.innerHTML = '';
            modelsList.forEach(model => {
                const option = document.createElement('option');
                const modelTrimmed = model.trim();
                option.value = modelTrimmed;
                option.textContent = modelTrimmed;
                modelSelect.appendChild(option);
            });

            // 设置当前选中的模型（优先使用配置值，否则使用第一个）
            modelSelect.value = settings.LLM_MODEL || defaultModel;
        }

        // Runtime Parameters
        document.getElementById('settingMaxTokens').value = settings.MAX_TOKENS || '4096';
        document.getElementById('settingTemperature').value = settings.DEFAULT_TEMPERATURE || '0.7';
        document.getElementById('settingMaxSteps').value = settings.DEFAULT_MAX_STEPS || '1000';
        document.getElementById('settingNumCores').value = settings.DEFAULT_NUM_CORES || '4';
        document.getElementById('settingMaxFixAttempts').value = settings.DEFAULT_MAX_FIX_ATTEMPTS || '10';

        // RAG Configuration
        document.getElementById('settingRagEnabled').checked = settings.RAG_ENABLED === 'true';
        document.getElementById('settingRagTopK').value = settings.RAG_TOP_K || '5';
    }

    collectFormData() {
        const apiKeyInput = document.getElementById('settingApiKey').value.trim();
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

        // Only include API_KEY if user has entered a new one (non-empty and not masked)
        if (apiKeyInput && !apiKeyInput.includes('*')) {
            formData.API_KEY = apiKeyInput;
        }

        return formData;
    }

    async save() {
        const updates = this.collectFormData();
        const persistMode = document.querySelector('input[name="persistMode"]:checked').value;
        const persist = persistMode === 'permanent';

        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates, persist })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                alert(data.message);
                this.hide();

                // Optionally reload page if persistent changes made
                if (persist) {
                    if (confirm('设置已永久保存。是否重新加载页面以应用更改？')) {
                        window.location.reload();
                    }
                }
            } else {
                alert(`保存失败: ${data.error || '未知错误'}`);
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('保存设置失败');
        }
    }

    async testConnection() {
        const apiType = document.querySelector('input[name="apiType"]:checked').value;
        const apiUrl = document.getElementById('settingApiUrl').value.trim();
        const apiKeyInput = document.getElementById('settingApiKey').value.trim();
        const model = document.getElementById('settingLlmModel').value;

        if (!apiUrl) {
            alert('请填写API地址');
            return;
        }

        const statusEl = document.getElementById('connectionStatus');
        statusEl.textContent = '测试中...';
        statusEl.className = 'connection-status';
        statusEl.classList.remove('hidden');

        try {
            // Build request body
            const requestBody = {
                API_TYPE: apiType,
                API_URL: apiUrl,
                LLM_MODEL: model
            };

            // Only send API_KEY if user has entered a new one (non-empty and not masked)
            // If empty or masked, backend will use the stored key from config
            if (apiKeyInput && !apiKeyInput.includes('*')) {
                requestBody.API_KEY = apiKeyInput;
            }

            const response = await fetch('/api/settings/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const data = await response.json();

            if (data.success) {
                statusEl.textContent = '✓ 连接成功';
                statusEl.classList.add('success');
            } else {
                statusEl.textContent = `✗ ${data.error}`;
                statusEl.classList.add('error');
            }

            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, 5000);

        } catch (error) {
            statusEl.textContent = `✗ 连接失败: ${error.message}`;
            statusEl.classList.add('error');

            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, 5000);
        }
    }

    resetToDefault() {
        if (!confirm('确定要重置所有设置为默认值吗？这将清除runtime overrides。')) {
            return;
        }

        // Reload from server (will get .env defaults)
        this.loadSettings().then(() => {
            this.populateForm();
            alert('已重置为默认值（尚未保存）');
        });
    }

    toggleApiKeyVisibility() {
        const input = document.getElementById('settingApiKey');
        const btn = event.target;

        if (input.type === 'password') {
            input.type = 'text';
            btn.textContent = '🙈';
        } else {
            input.type = 'password';
            btn.textContent = '👁️';
        }

        // If input is empty (showing placeholder), inform user
        if (!input.value && input.placeholder.includes('已设置')) {
            // Show a temporary tooltip or message
            const originalPlaceholder = input.placeholder;
            input.placeholder = '密钥已保存，如需修改请输入新密钥';
            setTimeout(() => {
                input.placeholder = originalPlaceholder;
            }, 3000);
        }
    }
}

// Global instance
const settingsPanel = new SettingsPanel();

// Global functions for onclick handlers
function openSettingsPanel() {
    settingsPanel.show();
}

function closeSettingsPanel() {
    settingsPanel.hide();
}

function saveSettings() {
    settingsPanel.save();
}

function testApiConnection() {
    settingsPanel.testConnection();
}

function resetSettingsToDefault() {
    settingsPanel.resetToDefault();
}

function toggleApiKeyVisibility() {
    settingsPanel.toggleApiKeyVisibility();
}
