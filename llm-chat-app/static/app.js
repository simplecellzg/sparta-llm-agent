// 全局变量
let currentConversationId = null;
let conversations = [];
let images = [];
let fileTexts = [];
let isStreaming = false;
let lastUserMessage = null; // 保存最后一条用户消息，用于重新生成

// 迭代相关全局变量
let currentIterations = [];      // 当前会话的所有迭代
let activeIterationId = null;    // 当前活跃的迭代ID
let isEditMode = false;          // 是否处于编辑模式
let iterationMessages = {};      // 每个迭代的消息缓存 { iteration_id: [messages] }
let versionManager = null;       // 版本管理器实例
let currentSessionId = null;     // 当前DSMC会话ID
let sseConnection = null;        // SSE连接实例


// 过程跟踪状态
const PROCESS_STEPS = {
    IDLE: '就绪',
    GENERATING: '生成输入文件',
    RUNNING: '运行仿真',
    PROCESSING: '结果处理',
    VISUALIZING: '可视化',
    COMPLETED: '完成'
};
let currentProcessStep = PROCESS_STEPS.IDLE;

// ==================== 大气模型计算模块 ====================

// 物理常数
const ATMOSPHERE_CONSTANTS = {
    R: 287.05,           // 气体常数 J/(kg·K)
    g0: 9.80665,         // 标准重力加速度 m/s²
    M: 0.0289644,        // 空气摩尔质量 kg/mol
    R_universal: 8.31447,// 通用气体常数 J/(mol·K)
    k_B: 1.380649e-23,   // 玻尔兹曼常数 J/K
    N_A: 6.02214076e23   // 阿伏加德罗常数
};

// ISA标准大气模型层（0-86km）
const ISA_LAYERS = [
    { h: 0,     T0: 288.15, L: -0.0065, P0: 101325 },      // 对流层
    { h: 11000, T0: 216.65, L: 0,       P0: 22632.1 },     // 平流层下部
    { h: 20000, T0: 216.65, L: 0.001,   P0: 5474.89 },     // 平流层中部
    { h: 32000, T0: 228.65, L: 0.0028,  P0: 868.019 },     // 平流层上部
    { h: 47000, T0: 270.65, L: 0,       P0: 110.906 },     // 中间层下部
    { h: 51000, T0: 270.65, L: -0.0028, P0: 66.9389 },     // 中间层中部
    { h: 71000, T0: 214.65, L: -0.002,  P0: 3.95642 },     // 中间层上部
    { h: 86000, T0: 186.87, L: 0,       P0: 0.3734 }       // 热层边界
];

// NRLMSISE-00简化查表数据
const NRLMSISE00_TABLE = [
    { h: 100, T: 195,  P: 3.2e-2,  n: 1.2e19 },
    { h: 120, T: 360,  P: 2.5e-3,  n: 5.3e17 },
    { h: 150, T: 634,  P: 4.5e-4,  n: 5.0e16 },
    { h: 200, T: 854,  P: 8.5e-5,  n: 7.0e15 },
    { h: 250, T: 941,  P: 2.5e-5,  n: 2.0e15 },
    { h: 300, T: 976,  P: 8.8e-6,  n: 6.5e14 },
    { h: 400, T: 995,  P: 1.4e-6,  n: 1.0e14 },
    { h: 500, T: 999,  P: 3.0e-7,  n: 2.0e13 }
];

// 计算ISA标准大气参数
function calculateISA(altitudeKm) {
    const h = altitudeKm * 1000; // 转换为米

    // 查找所在层
    let layer = ISA_LAYERS[0];
    for (let i = ISA_LAYERS.length - 1; i >= 0; i--) {
        if (h >= ISA_LAYERS[i].h) {
            layer = ISA_LAYERS[i];
            break;
        }
    }

    const { h: h0, T0, L, P0 } = layer;
    const dh = h - h0;

    let T, P;

    if (L === 0) {
        // 等温层
        T = T0;
        P = P0 * Math.exp(-ATMOSPHERE_CONSTANTS.g0 * dh / (ATMOSPHERE_CONSTANTS.R * T0));
    } else {
        // 非等温层
        T = T0 + L * dh;
        P = P0 * Math.pow(T / T0, -ATMOSPHERE_CONSTANTS.g0 / (ATMOSPHERE_CONSTANTS.R * L));
    }

    // 计算密度和数密度
    const rho = P / (ATMOSPHERE_CONSTANTS.R * T);
    const n = P / (ATMOSPHERE_CONSTANTS.k_B * T);

    return {
        temperature: T,
        pressure: P,
        density: rho,
        numberDensity: n,
        modelUsed: 'ISA',
        valid: altitudeKm <= 86
    };
}

// 计算US76标准大气参数（扩展到高层）
function calculateUS76(altitudeKm) {
    if (altitudeKm <= 86) {
        const result = calculateISA(altitudeKm);
        result.modelUsed = 'US76';
        return result;
    }

    // 86km以上使用指数模型
    const h = altitudeKm;
    const h0 = 86;

    // 温度模型：渐近到1000K
    const T0 = 186.87;
    const T_inf = 1000;
    const xi = (h - h0) / 50;
    const T = T_inf - (T_inf - T0) * Math.exp(-xi);

    // 压力指数衰减
    const P0 = 0.3734;
    const H = ATMOSPHERE_CONSTANTS.R * T / ATMOSPHERE_CONSTANTS.g0;
    const P = P0 * Math.exp(-(h - h0) * 1000 / H);

    const rho = P / (ATMOSPHERE_CONSTANTS.R * T);
    const n = P / (ATMOSPHERE_CONSTANTS.k_B * T);

    return {
        temperature: T,
        pressure: P,
        density: rho,
        numberDensity: n,
        modelUsed: 'US76',
        valid: true
    };
}

// 计算NRLMSISE-00参数（简化版，使用插值）
function calculateNRLMSISE00(altitudeKm) {
    if (altitudeKm < 100) {
        const result = calculateUS76(altitudeKm);
        result.modelUsed = 'NRLMSISE-00 (US76 <100km)';
        return result;
    }

    // 在查表数据中进行插值
    let lower = NRLMSISE00_TABLE[0];
    let upper = NRLMSISE00_TABLE[NRLMSISE00_TABLE.length - 1];

    for (let i = 0; i < NRLMSISE00_TABLE.length - 1; i++) {
        if (altitudeKm >= NRLMSISE00_TABLE[i].h && altitudeKm < NRLMSISE00_TABLE[i + 1].h) {
            lower = NRLMSISE00_TABLE[i];
            upper = NRLMSISE00_TABLE[i + 1];
            break;
        }
    }

    // 插值
    const t = (altitudeKm - lower.h) / (upper.h - lower.h);
    const T = lower.T + t * (upper.T - lower.T);
    const P = lower.P * Math.pow(upper.P / lower.P, t);
    const n = lower.n * Math.pow(upper.n / lower.n, t);
    const rho = P / (ATMOSPHERE_CONSTANTS.R * T);

    return {
        temperature: T,
        pressure: P,
        density: rho,
        numberDensity: n,
        modelUsed: 'NRLMSISE-00',
        valid: true
    };
}

// 主计算函数
function calculateAtmosphereParams(altitudeKm, model) {
    switch (model) {
        case 'ISA':
            return calculateISA(altitudeKm);
        case 'US76':
            return calculateUS76(altitudeKm);
        case 'NRLMSISE00':
            return calculateNRLMSISE00(altitudeKm);
        case 'custom':
            return null;
        default:
            return calculateISA(altitudeKm);
    }
}

// 高度参数联动逻辑
let lastAppliedAtmParams = null;

function onAltitudeChange() {
    const altitudeInput = document.getElementById('altitude');
    const altitudeSlider = document.getElementById('altitudeSlider');

    if (altitudeSlider) {
        altitudeSlider.value = altitudeInput.value;
    }

    updateAtmospherePreview();
}

function onAltitudeSliderChange() {
    const altitudeInput = document.getElementById('altitude');
    const altitudeSlider = document.getElementById('altitudeSlider');

    if (altitudeInput) {
        altitudeInput.value = altitudeSlider.value;
    }

    updateAtmospherePreview();
}

function onAtmosphereModelChange() {
    const model = document.getElementById('atmosphereModel')?.value;

    if (model === 'custom') {
        document.getElementById('atmospherePreview')?.classList.add('custom-mode');
    } else {
        document.getElementById('atmospherePreview')?.classList.remove('custom-mode');
        updateAtmospherePreview();
    }
}

function updateAtmospherePreview() {
    const altitudeInput = document.getElementById('altitude');
    const modelSelect = document.getElementById('atmosphereModel');
    const valuesContainer = document.getElementById('atmosphereValues');

    if (!altitudeInput || !modelSelect || !valuesContainer) return;

    const altitude = parseFloat(altitudeInput.value) || 0;
    const model = modelSelect.value;

    if (model === 'custom') return;

    const params = calculateAtmosphereParams(altitude, model);
    if (!params) return;

    // 格式化显示
    const formatValue = (val, unit) => {
        if (val >= 1e6 || val < 0.001) {
            return val.toExponential(3) + ' ' + unit;
        }
        return val.toFixed(3) + ' ' + unit;
    };

    valuesContainer.innerHTML = `
        <div class="atm-param">
            <span class="param-label">温度</span>
            <span class="param-value">${params.temperature.toFixed(2)} K</span>
        </div>
        <div class="atm-param">
            <span class="param-label">压力</span>
            <span class="param-value">${formatValue(params.pressure, 'Pa')}</span>
        </div>
        <div class="atm-param">
            <span class="param-label">数密度</span>
            <span class="param-value">${params.numberDensity.toExponential(3)} m<sup>-3</sup></span>
        </div>
        <div class="atm-param">
            <span class="param-label">密度</span>
            <span class="param-value">${formatValue(params.density, 'kg/m³')}</span>
        </div>
        ${!params.valid ? '<div class="atm-warning">超出模型有效范围，结果为外推值</div>' : ''}
    `;
}

function applyAtmosphereParams() {
    const altitudeInput = document.getElementById('altitude');
    const modelSelect = document.getElementById('atmosphereModel');

    if (!altitudeInput || !modelSelect) return;

    const altitude = parseFloat(altitudeInput.value) || 0;
    const model = modelSelect.value;

    if (model === 'custom') {
        alert('自定义模式下请手动设置参数');
        return;
    }

    const params = calculateAtmosphereParams(altitude, model);
    if (!params) return;

    // 填充基础参数
    const tempInput = document.getElementById('temperature');
    const pressureInput = document.getElementById('pressure');

    if (tempInput) {
        tempInput.value = params.temperature.toFixed(2);
        document.getElementById('temperatureLinked')?.classList.remove('hidden');
    }

    if (pressureInput) {
        pressureInput.value = params.pressure.toExponential(4);
        document.getElementById('pressureLinked')?.classList.remove('hidden');
    }

    // 保存应用的参数
    lastAppliedAtmParams = {
        temperature: params.temperature,
        pressure: params.pressure,
        altitude: altitude,
        model: model
    };

    // 添加变化监听
    setupParamChangeListeners();
}

function setupParamChangeListeners() {
    ['temperature', 'pressure'].forEach(paramId => {
        const input = document.getElementById(paramId);
        if (input && !input._hasLinkedListener) {
            input.addEventListener('input', function() {
                document.getElementById(paramId + 'Linked')?.classList.add('hidden');
            });
            input._hasLinkedListener = true;
        }
    });
}

// DOM元素
const conversationList = document.getElementById('conversationList');
// ==================== DSMC模板管理 ====================

// DSMC Template Management
let dsmcTemplates = [];

// Load templates on page load
async function loadDSMCTemplates() {
    try {
        const response = await fetch('/static/data/dsmc-templates.json');
        const data = await response.json();
        dsmcTemplates = data.templates;

        // Populate template selector
        const select = document.getElementById('templateSelect');
        if (select) {
            select.innerHTML = '<option value="">-- Select Template --</option>';
            dsmcTemplates.forEach(template => {
                const option = document.createElement('option');
                option.value = template.id;
                option.textContent = template.name;
                select.appendChild(option);
            });
        }

        console.log('DSMC templates loaded:', dsmcTemplates.length);
    } catch (error) {
        console.error('Failed to load DSMC templates:', error);
    }
}

// Load template into form
function loadTemplate() {
    const select = document.getElementById('templateSelect');
    const templateId = select.value;

    if (!templateId) {
        // Clear description
        document.getElementById('templateDescription').textContent = '';
        return;
    }

    const template = dsmcTemplates.find(t => t.id === templateId);
    if (!template) {
        console.error('Template not found:', templateId);
        return;
    }

    // Show description
    document.getElementById('templateDescription').textContent = template.description;

    // Populate form fields
    const params = template.parameters;

    // Dimension
    const dimensionRadios = document.querySelectorAll('input[name="dimension"]');
    dimensionRadios.forEach(radio => {
        radio.checked = radio.value === params.dimension;
    });

    // Geometry
    const geometrySelect = document.getElementById('geometry');
    if (geometrySelect) geometrySelect.value = params.geometry;

    // Grid size
    document.getElementById('gridX').value = params.grid_size[0];
    document.getElementById('gridY').value = params.grid_size[1];
    document.getElementById('gridZ').value = params.grid_size[2];

    // Gas properties
    const gasSelect = document.getElementById('gas');
    if (gasSelect) gasSelect.value = params.gas;

    document.getElementById('temperature').value = params.temperature;
    document.getElementById('pressure').value = params.pressure;
    document.getElementById('velocity').value = params.velocity;

    // Atmospheric model
    const atmModelRadios = document.querySelectorAll('input[name="atmospheric_model"]');
    atmModelRadios.forEach(radio => {
        radio.checked = radio.value === params.atmospheric_model;
    });

    if (params.altitude_km !== null) {
        document.getElementById('altitude').value = params.altitude_km;
        // Trigger atmospheric calculation
        onAltitudeChange();
    }

    // Simulation parameters
    document.getElementById('timestep').value = params.timestep;
    document.getElementById('numSteps').value = params.num_steps;

    const collisionSelect = document.getElementById('collisionModel');
    if (collisionSelect) collisionSelect.value = params.collision_model;

    console.log('Template loaded:', template.name);
}

// ==================== DSMC表单验证 ====================

const validationRules = {
    temperature: {
        min: 50,
        max: 5000,
        unit: 'K',
        validate: (value) => {
            if (value <= 0) return { valid: false, message: 'Temperature must be > 0K' };
            if (value < 50) return { valid: false, message: 'Temperature too low (min 50K)' };
            if (value > 5000) return { valid: 'warning', message: 'Very high temperature (max recommended 5000K)' };
            return { valid: true, message: 'Valid temperature range' };
        },
        tooltip: 'Gas temperature in Kelvin. SPARTA requires T > 0K. Typical range: 50-5000K.'
    },
    pressure: {
        min: 0,
        max: 1e7,
        unit: 'Pa',
        validate: (value) => {
            if (value <= 0) return { valid: false, message: 'Pressure must be > 0 Pa' };
            if (value < 0.01) return { valid: 'warning', message: 'Very low pressure (near vacuum)' };
            if (value > 1e7) return { valid: 'warning', message: 'Very high pressure' };
            return { valid: true, message: 'Valid pressure range' };
        },
        tooltip: 'Gas pressure in Pascals. Must be > 0. Vacuum: <1 Pa, Atmospheric: ~101325 Pa.'
    },
    velocity: {
        min: 0,
        max: 10000,
        unit: 'm/s',
        validate: (value) => {
            if (value < 0) return { valid: false, message: 'Velocity cannot be negative' };
            if (value > 10000) return { valid: 'warning', message: 'Very high velocity (>Mach 30)' };
            return { valid: true, message: 'Valid velocity' };
        },
        tooltip: 'Flow velocity in m/s. 0 for stationary gas. Typical: 100-7500 m/s.'
    },
    gridX: {
        min: 10,
        max: 1000,
        validate: (value) => {
            if (value < 10) return { valid: false, message: 'Grid too coarse (min 10 cells)' };
            if (value > 1000) return { valid: 'warning', message: 'Very fine grid (may be slow)' };
            return { valid: true, message: 'Good grid resolution' };
        },
        tooltip: 'Number of grid cells in X direction. Min 10, recommended 50-200.'
    },
    gridY: {
        min: 10,
        max: 1000,
        validate: (value) => {
            if (value < 10) return { valid: false, message: 'Grid too coarse (min 10 cells)' };
            if (value > 1000) return { valid: 'warning', message: 'Very fine grid (may be slow)' };
            return { valid: true, message: 'Good grid resolution' };
        },
        tooltip: 'Number of grid cells in Y direction. Min 10, recommended 50-200.'
    },
    gridZ: {
        min: 1,
        max: 1000,
        validate: (value, dimension) => {
            if (dimension === '2d' && value !== 1) {
                return { valid: false, message: '2D simulation must have Z=1' };
            }
            if (dimension === '3d' && value < 10) {
                return { valid: false, message: 'Grid too coarse (min 10 cells for 3D)' };
            }
            if (value > 1000) return { valid: 'warning', message: 'Very fine grid (may be slow)' };
            return { valid: true, message: 'Good grid resolution' };
        },
        tooltip: 'Number of grid cells in Z direction. For 2D: must be 1. For 3D: min 10.'
    },
    timestep: {
        min: 1e-9,
        max: 1e-4,
        unit: 's',
        validate: (value) => {
            if (value <= 0) return { valid: false, message: 'Timestep must be > 0' };
            if (value < 1e-9) return { valid: false, message: 'Timestep too small' };
            if (value > 1e-4) return { valid: 'warning', message: 'Timestep may be too large' };
            return { valid: true, message: 'Valid timestep' };
        },
        tooltip: 'Simulation timestep in seconds. Must be smaller than mean collision time. Typical: 1e-7 to 1e-6 s.'
    },
    numSteps: {
        min: 100,
        max: 100000,
        validate: (value) => {
            if (value < 100) return { valid: false, message: 'Too few steps (min 100)' };
            if (value > 100000) return { valid: 'warning', message: 'Many steps (may take long time)' };
            return { valid: true, message: 'Good number of steps' };
        },
        tooltip: 'Number of simulation timesteps. More steps = more accurate but slower. Typical: 1000-10000.'
    }
};

function validateField(fieldId, value, extraContext = {}) {
    const rule = validationRules[fieldId];
    if (!rule) return { valid: true };

    let numValue = parseFloat(value);
    if (isNaN(numValue)) {
        return { valid: false, message: 'Invalid number' };
    }

    return rule.validate(numValue, extraContext.dimension);
}

function updateFieldValidation(fieldId) {
    const input = document.getElementById(fieldId);
    if (!input) return;

    const value = input.value;

    // Get extra context if needed
    const extraContext = {};
    if (fieldId === 'gridZ') {
        const dimensionRadio = document.querySelector('input[name="dimension"]:checked');
        extraContext.dimension = dimensionRadio ? dimensionRadio.value : '3d';
    }

    const result = validateField(fieldId, value, extraContext);

    // Remove existing validation classes
    input.classList.remove('valid', 'warning', 'invalid');

    // Add new validation class
    if (result.valid === true) {
        input.classList.add('valid');
    } else if (result.valid === 'warning') {
        input.classList.add('warning');
    } else {
        input.classList.add('invalid');
    }

    // Update validation message
    const messageId = fieldId + 'ValidationMessage';
    let messageEl = document.getElementById(messageId);

    if (!messageEl) {
        // Create message element if it doesn't exist
        messageEl = document.createElement('div');
        messageEl.id = messageId;
        messageEl.className = 'validation-message';
        input.parentNode.appendChild(messageEl);
    }

    messageEl.textContent = result.message || '';
    messageEl.classList.remove('success', 'warning', 'error');

    if (result.valid === true) {
        messageEl.classList.add('success');
    } else if (result.valid === 'warning') {
        messageEl.classList.add('warning');
    } else {
        messageEl.classList.add('error');
    }

    messageEl.classList.toggle('show', !!result.message);

    return result;
}

function validateAllFields() {
    const fieldsToValidate = [
        'temperature', 'pressure', 'velocity',
        'gridX', 'gridY', 'gridZ',
        'timestep', 'numSteps'
    ];

    let allValid = true;
    const errors = [];

    fieldsToValidate.forEach(fieldId => {
        const result = updateFieldValidation(fieldId);
        if (result.valid !== true) {
            allValid = false;
            if (result.valid === false) {
                errors.push(`${fieldId}: ${result.message}`);
            }
        }
    });

    return { valid: allValid, errors };
}

// Attach validation to input events
function attachValidationListeners() {
    const fieldsToValidate = [
        'temperature', 'pressure', 'velocity',
        'gridX', 'gridY', 'gridZ',
        'timestep', 'numSteps'
    ];

    fieldsToValidate.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (input) {
            input.addEventListener('blur', () => updateFieldValidation(fieldId));
            input.addEventListener('input', () => {
                // Debounce validation on input
                clearTimeout(input.validationTimeout);
                input.validationTimeout = setTimeout(() => {
                    updateFieldValidation(fieldId);
                }, 500);
            });
        }
    });

    // Validate gridZ when dimension changes
    const dimensionRadios = document.querySelectorAll('input[name="dimension"]');
    dimensionRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            updateFieldValidation('gridZ');
        });
    });
}

// ==================== 文件上传处理 ====================

let uploadedFileData = null;

async function handleSpartaFileUpload(file) {
    try {
        showStatus('Uploading and validating file...');

        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/dsmc/upload-input', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.valid) {
            // Store upload data
            uploadedFileData = result;

            // Show modal
            showUploadModal(result);

            hideStatus();
        } else {
            // Show validation errors
            showUploadErrors(result);
        }
    } catch (error) {
        console.error('Upload failed:', error);
        showStatus('Upload failed: ' + error.message, 'error');
    }
}

function showUploadModal(result) {
    // Populate file info
    document.getElementById('uploadedFileName').textContent = result.stats.filename;
    document.getElementById('uploadedFileStats').textContent =
        `${result.stats.lines} 行 | ${result.stats.commands} 个命令`;

    // Show preview
    document.getElementById('uploadedInputFilePreview').textContent = result.preview;

    // Show warnings if any
    if (result.warnings && result.warnings.length > 0) {
        const validationDiv = document.getElementById('inputFileValidationResult');
        validationDiv.innerHTML = `
            <h5>⚠️ 警告:</h5>
            <ul>
                ${result.warnings.map(w => `<li>${w}</li>`).join('')}
            </ul>
        `;
        validationDiv.classList.remove('hidden');
    } else {
        document.getElementById('inputFileValidationResult').classList.add('hidden');
    }

    // Set default mode to direct_run
    const directRunRadio = document.querySelector('input[name="uploadMode"][value="direct_run"]');
    if (directRunRadio) {
        directRunRadio.checked = true;
        showRunConfigSection();
    }

    // Sync run params from control panel defaults
    syncRunParamsFromPanel();

    // Show modal
    const modal = document.getElementById('inputFileUploadModal');
    if (modal) modal.classList.remove('hidden');
    const overlay = document.getElementById('customModalOverlay');
    if (overlay) overlay.classList.remove('hidden');
}

function showUploadErrors(result) {
    const modal = document.getElementById('inputFileUploadModal');
    const statusDiv = document.getElementById('fileStatus');
    const validationDiv = document.getElementById('inputFileValidationResult');

    // Update status to error
    if (statusDiv) {
        statusDiv.innerHTML = `
            <span class="status-icon">❌</span>
            <span class="status-text">验证失败</span>
        `;
        statusDiv.classList.add('error');
    }

    // Show errors
    if (validationDiv) {
        validationDiv.innerHTML = `
            <h5>❌ 错误:</h5>
            <ul>
                ${result.errors.map(e => `<li>${e}</li>`).join('')}
            </ul>
        `;

        if (result.suggestions && result.suggestions.length > 0) {
            validationDiv.innerHTML += `
                <h5>💡 建议:</h5>
                <ul>
                    ${result.suggestions.map(s => `<li>${s}</li>`).join('')}
                </ul>
            `;
        }

        validationDiv.classList.remove('hidden');
    }

    // Hide mode selection (can't run invalid file)
    const modeSection = document.querySelector('.upload-mode-section');
    if (modeSection) modeSection.style.display = 'none';

    // Change action button to close
    const actionBtn = document.getElementById('uploadActionBtn');
    if (actionBtn) {
        actionBtn.textContent = '关闭';
        actionBtn.onclick = closeInputFileUploadModal;
    }

    // Show modal
    if (modal) modal.classList.remove('hidden');
    const overlay = document.getElementById('customModalOverlay');
    if (overlay) overlay.classList.remove('hidden');
}

function togglePreview() {
    const preview = document.getElementById('uploadedInputFilePreview');
    const btn = document.querySelector('.btn-toggle-preview');

    if (preview) preview.classList.toggle('collapsed');
    if (btn) btn.classList.toggle('expanded');
}

function syncRunParamsFromPanel() {
    // Sync from control panel if values exist
    const panelCores = document.getElementById('panelNumCores');
    const panelSteps = document.getElementById('panelMaxSteps');
    const panelMemory = document.getElementById('panelMaxMemory');
    const panelFix = document.getElementById('panelMaxFixAttempts');

    if (panelCores) {
        const uploadCores = document.getElementById('uploadRunCores');
        if (uploadCores) uploadCores.value = panelCores.value;
    }
    if (panelSteps) {
        const uploadSteps = document.getElementById('uploadRunSteps');
        if (uploadSteps) uploadSteps.value = panelSteps.value;
    }
    if (panelMemory) {
        const uploadMemory = document.getElementById('uploadRunMemory');
        if (uploadMemory) uploadMemory.value = panelMemory.value;
    }
    if (panelFix) {
        const uploadFix = document.getElementById('uploadRunMaxFix');
        if (uploadFix) uploadFix.value = panelFix.value;
    }
}

function showRunConfigSection() {
    const modeRadio = document.querySelector('input[name="uploadMode"]:checked');
    if (!modeRadio) return;

    const mode = modeRadio.value;
    const configSection = document.getElementById('runConfigSection');
    const actionBtn = document.getElementById('uploadActionBtn');

    if (mode === 'direct_run') {
        if (configSection) configSection.style.display = 'block';
        if (actionBtn) {
            actionBtn.innerHTML = '🚀 开始运行';
            actionBtn.onclick = runUploadedFile;
        }
    } else {
        if (configSection) configSection.style.display = 'none';
        if (actionBtn) {
            actionBtn.innerHTML = '📚 用作参考';
            actionBtn.onclick = useUploadedFileAsReference;
        }
    }
}

async function runUploadedFile() {
    if (!uploadedFileData) {
        alert('No file data available');
        return;
    }

    const uploadCores = document.getElementById('uploadRunCores');
    const uploadSteps = document.getElementById('uploadRunSteps');
    const uploadMemory = document.getElementById('uploadRunMemory');
    const uploadFix = document.getElementById('uploadRunMaxFix');

    const runParams = {
        temp_id: uploadedFileData.temp_id,
        num_cores: uploadCores ? parseInt(uploadCores.value) : 4,
        max_steps: uploadSteps ? parseInt(uploadSteps.value) : 1000,
        max_memory_gb: uploadMemory ? parseInt(uploadMemory.value) : 100,
        max_fix_attempts: uploadFix ? parseInt(uploadFix.value) : 3
    };

    // Validate params
    if (runParams.num_cores < 1 || runParams.num_cores > 128) {
        alert('CPU核数必须在1-128之间');
        return;
    }

    if (runParams.max_steps < 100) {
        alert('步数不能少于100');
        return;
    }

    try {
        showStatus(`准备运行: ${runParams.num_cores}核心, ${runParams.max_steps}步...`);

        // Close modal
        closeInputFileUploadModal();

        // Call backend to create session and run
        const response = await fetch('/api/dsmc/run-uploaded', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(runParams)
        });

        const result = await response.json();

        if (result.success) {
            // Open control panel
            showDSMCControlPanel(result.session_id);

            // Start monitoring
            if (typeof monitorSimulation === 'function') {
                monitorSimulation(result.session_id);
            }

            showStatus('仿真已启动', 'success');
        } else {
            showStatus('运行失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Run failed:', error);
        showStatus('运行失败: ' + error.message, 'error');
    }
}

function useUploadedFileAsReference() {
    if (!uploadedFileData || !uploadedFileData.params) {
        alert('No parameters to extract');
        return;
    }

    // Close modal
    closeInputFileUploadModal();

    // Open DSMC parameter form (if function exists)
    if (typeof openDSMCParameterModal === 'function') {
        openDSMCParameterModal();
    }

    // Populate form with extracted parameters
    setTimeout(() => {
        populateFormFromParams(uploadedFileData.params);
        showStatus('参数已提取到表单', 'success');
    }, 300);
}

function populateFormFromParams(params) {
    // Dimension
    if (params.dimension) {
        const dimensionRadio = document.querySelector(`input[name="dimension"][value="${params.dimension}"]`);
        if (dimensionRadio) dimensionRadio.checked = true;
    }

    // Grid
    if (params.grid_size) {
        const gridX = document.getElementById('gridX');
        const gridY = document.getElementById('gridY');
        const gridZ = document.getElementById('gridZ');
        if (gridX) gridX.value = params.grid_size[0];
        if (gridY) gridY.value = params.grid_size[1];
        if (gridZ) gridZ.value = params.grid_size[2];
    }

    // Temperature
    if (params.temperature) {
        const temp = document.getElementById('temperature');
        if (temp) temp.value = params.temperature;
    }

    // Velocity
    if (params.velocity !== undefined) {
        const vel = document.getElementById('velocity');
        if (vel) vel.value = params.velocity;
    }

    // Gas
    if (params.gas) {
        const gasSelect = document.getElementById('gas');
        if (gasSelect) gasSelect.value = params.gas;
    }

    // Timestep
    if (params.timestep) {
        const timestep = document.getElementById('timestep');
        if (timestep) timestep.value = params.timestep;
    }

    // Steps
    if (params.num_steps) {
        const steps = document.getElementById('numSteps');
        if (steps) steps.value = params.num_steps;
    }

    // Collision model
    if (params.collision_model) {
        const collisionSelect = document.getElementById('collisionModel');
        if (collisionSelect) collisionSelect.value = params.collision_model;
    }

    console.log('Form populated with uploaded file parameters:', params);
}

function closeInputFileUploadModal() {
    const modal = document.getElementById('inputFileUploadModal');
    const overlay = document.getElementById('customModalOverlay');
    const fileStatus = document.getElementById('fileStatus');
    const modeSection = document.querySelector('.upload-mode-section');

    if (modal) modal.classList.add('hidden');
    if (overlay) overlay.classList.add('hidden');

    // Reset
    uploadedFileData = null;
    if (fileStatus) fileStatus.classList.remove('error');
    if (modeSection) modeSection.style.display = 'block';
}

// ==================== DOM元素引用 ====================

const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const modelSelect = document.getElementById('modelSelect');
const ragToggle = document.getElementById('ragToggle');
const downloadMDBtn = document.getElementById('downloadMDBtn');
const downloadAllMDBtn = document.getElementById('downloadAllMDBtn');
const uploadImageBtn = document.getElementById('uploadImageBtn');
const uploadFileBtn = document.getElementById('uploadFileBtn');
const imageInput = document.getElementById('imageInput');
const fileInput = document.getElementById('fileInput');
const inputAttachments = document.getElementById('inputAttachments');
const welcomeMessage = document.getElementById('welcomeMessage');
const statusBar = document.getElementById('statusBar');
const statusText = document.getElementById('statusText');
const statusStats = document.getElementById('statusStats');

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 检查后端连接
    const connected = await checkBackendConnection();
    if (connected) {
        loadConversations();
        setupEventListeners();
        setupMarkdown();
        loadDSMCTemplates(); // Load DSMC template presets

        // Attach validation listeners after a short delay to ensure DOM is ready
        setTimeout(() => {
            attachValidationListeners();
        }, 500);
    }
});

// 检查后端连接
async function checkBackendConnection() {
    try {
        const response = await fetch('/api/models', {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        if (response.ok) {
            console.log('Backend connected successfully');
            hideConnectionError();
            return true;
        } else {
            showConnectionError('后端响应异常，状态码: ' + response.status);
            return false;
        }
    } catch (error) {
        console.error('Backend connection failed:', error);
        showConnectionError('无法连接到后端服务，请确保服务已启动');
        return false;
    }
}

// 显示连接错误
function showConnectionError(message) {
    let errorDiv = document.getElementById('connectionError');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'connectionError';
        errorDiv.className = 'connection-error';
        document.body.insertBefore(errorDiv, document.body.firstChild);
    }
    errorDiv.innerHTML = `
        <div class="error-content">
            <span class="error-icon">⚠️</span>
            <span class="error-message">${message}</span>
            <button onclick="retryConnection()" class="retry-btn">重试连接</button>
        </div>
    `;
    errorDiv.style.display = 'flex';
}

// 隐藏连接错误
function hideConnectionError() {
    const errorDiv = document.getElementById('connectionError');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// 重试连接
async function retryConnection() {
    const retryBtn = document.querySelector('.retry-btn');
    if (retryBtn) {
        retryBtn.textContent = '连接中...';
        retryBtn.disabled = true;
    }
    const connected = await checkBackendConnection();
    if (connected) {
        loadConversations();
        setupEventListeners();
        setupMarkdown();
    }
    if (retryBtn) {
        retryBtn.textContent = '重试连接';
        retryBtn.disabled = false;
    }
}

// 配置Markdown解析器
function setupMarkdown() {
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) {}
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true
    });
}

// 设置事件监听
function setupEventListeners() {
    // 发送消息
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 输入框自动调整高度
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
        updateSendButton();
    });

    // 新建对话
    newChatBtn.addEventListener('click', createNewConversation);

    // 下载当前版本MD
    downloadMDBtn.addEventListener('click', downloadCurrentVersionMD);

    // 下载所有版本MD
    downloadAllMDBtn.addEventListener('click', downloadAllVersionsMD);

    // 上传图片
    uploadImageBtn.addEventListener('click', () => imageInput.click());
    imageInput.addEventListener('change', handleImageUpload);

    // 上传文件
    uploadFileBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);

    // RAG开关变化
    ragToggle.addEventListener('change', () => {
        const label = document.querySelector('.rag-label');
        if (ragToggle.checked) {
            label.style.color = 'var(--rag-color)';
        } else {
            label.style.color = 'var(--text-secondary)';
        }
    });

    // 生成DSMC按钮
    const generateDSMCBtn = document.getElementById('generateDSMCBtn');
    if (generateDSMCBtn) {
        generateDSMCBtn.addEventListener('click', () => {
            messageInput.value = '生成dsmc输入文件';
            messageInput.style.height = 'auto';
            updateSendButton();
            sendMessage();
        });
    }

    // 初始化日志区域拖拽
    setupLogResize();
}

// 日志区域拖拽调整高度
function setupLogResize() {
    const handle = document.getElementById('logResizeHandle');
    const logSection = document.getElementById('logSection');

    if (!handle || !logSection) return;

    let startY, startHeight;
    let isDragging = false;

    // 从localStorage恢复高度
    const savedHeight = localStorage.getItem('logSectionHeight');
    if (savedHeight) {
        logSection.style.height = savedHeight + 'px';
    }

    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startY = e.clientY;
        startHeight = logSection.offsetHeight;
        isDragging = true;
        handle.classList.add('dragging');
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';

        document.addEventListener('mousemove', resize);
        document.addEventListener('mouseup', stopResize);
    });

    function resize(e) {
        if (!isDragging) return;
        const deltaY = startY - e.clientY;
        const newHeight = Math.max(100, Math.min(600, startHeight + deltaY));
        logSection.style.height = newHeight + 'px';
    }

    function stopResize() {
        if (!isDragging) return;
        isDragging = false;
        handle.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        // 保存到localStorage
        localStorage.setItem('logSectionHeight', logSection.offsetHeight);

        document.removeEventListener('mousemove', resize);
        document.removeEventListener('mouseup', stopResize);
    }

    // 触摸支持
    handle.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        startY = touch.clientY;
        startHeight = logSection.offsetHeight;
        isDragging = true;
        handle.classList.add('dragging');
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!isDragging) return;
        const touch = e.touches[0];
        const deltaY = startY - touch.clientY;
        const newHeight = Math.max(100, Math.min(600, startHeight + deltaY));
        logSection.style.height = newHeight + 'px';
    }, { passive: true });

    document.addEventListener('touchend', () => {
        if (!isDragging) return;
        isDragging = false;
        handle.classList.remove('dragging');
        localStorage.setItem('logSectionHeight', logSection.offsetHeight);
    });
}

// 更新发送按钮状态
function updateSendButton() {
    const hasContent = messageInput.value.trim() || images.length > 0 || fileTexts.length > 0;
    sendBtn.disabled = !hasContent || isStreaming;
}

// 加载对话列表
async function loadConversations() {
    try {
        console.log('正在加载对话列表...');
        const response = await fetch('/api/conversations');
        conversations = await response.json();
        console.log('加载到的对话数量:', conversations.length);
        renderConversationList();
    } catch (error) {
        console.error('加载对话列表失败:', error);
    }
}

// 渲染对话列表
function renderConversationList() {
    conversationList.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
             data-id="${conv.id}" onclick="selectConversation('${conv.id}')">
            <span class="conv-title">${escapeHtml(conv.title)}</span>
            ${conv.rag_enabled ? '<span class="rag-badge">RAG</span>' : ''}
            <span class="conv-delete" onclick="event.stopPropagation(); deleteConversation('${conv.id}')">🗑️</span>
        </div>
    `).join('');
}

// 选择对话
async function selectConversation(convId) {
    currentConversationId = convId;
    renderConversationList();

    // 重置DSMC状态（不立即隐藏面板，让renderMessages决定）
    dsmcSession = null;
    hideDSMCControlPanel();

    // 清理迭代消息缓存（不立即渲染标签，避免闪动）
    iterationMessages = {};
    currentIterations = [];
    activeIterationId = null;

    try {
        const response = await fetch(`/api/conversations/${convId}`);
        const conv = await response.json();

        modelSelect.value = conv.model || modelSelect.options[0].value;
        ragToggle.checked = conv.rag_enabled || false;

        renderMessages(conv.messages || []);

        // 如果渲染后没有迭代，确保隐藏迭代标签栏
        if (currentIterations.length === 0) {
            const iterationTabs = document.getElementById('iterationTabs');
            if (iterationTabs) {
                iterationTabs.classList.add('hidden');
            }
        }

        // 如果渲染后有DSMC session，显示控制面板
        if (dsmcSession) {
            showDSMCControlPanel();
            showDSMCIndicator();
        }
    } catch (error) {
        console.error('加载对话失败:', error);
    }
}

// 创建新对话
async function createNewConversation() {
    try {
        const response = await fetch('/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: modelSelect.value,
                rag_enabled: ragToggle.checked
            })
        });
        const data = await response.json();
        currentConversationId = data.id;
        await loadConversations();
        chatMessages.innerHTML = '';
        welcomeMessage.style.display = 'block';
        clearAttachments();
        // 隐藏DSMC面板
        hideDSMCRunPanel();
        dsmcSession = null;
        // 清空迭代相关状态并隐藏标签栏（新对话没有迭代，直接隐藏）
        iterationMessages = {};
        currentIterations = [];
        activeIterationId = null;
        const iterationTabs = document.getElementById('iterationTabs');
        if (iterationTabs) {
            iterationTabs.classList.add('hidden');
        }
    } catch (error) {
        console.error('创建对话失败:', error);
    }
}

// 删除对话
async function deleteConversation(convId) {
    try {
        await fetch(`/api/conversations/${convId}`, { method: 'DELETE' });
        if (currentConversationId === convId) {
            currentConversationId = null;
            chatMessages.innerHTML = '';
            welcomeMessage.style.display = 'block';
        }
        await loadConversations();
    } catch (error) {
        console.error('删除对话失败:', error);
    }
}

// 渲染消息列表
function renderMessages(messages) {
    if (messages.length === 0) {
        welcomeMessage.style.display = 'block';
        chatMessages.innerHTML = '';
        chatMessages.appendChild(welcomeMessage);
        return;
    }

    welcomeMessage.style.display = 'none';
    chatMessages.innerHTML = messages.map(msg => createMessageHTML(msg)).join('');
    
    // 渲染LaTeX和代码高亮
    renderMathAndCode();
    scrollToBottom();
}

// 创建消息HTML
function createMessageHTML(msg) {
    const isUser = msg.role === 'user';
    const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : '';

    let contentHTML = '';
    if (isUser) {
        contentHTML = `<div class="message-text">${escapeHtml(msg.content)}</div>`;
        if (msg.images && msg.images.length > 0) {
            contentHTML += `<div class="message-images">
                ${msg.images.map(img => `<img src="${img}" onclick="showImageModal(this.src)">`).join('')}
            </div>`;
        }
    } else {
        // 检查是否有DSMC仿真结果
        if (msg.dsmc_simulation_results) {
            contentHTML = createDSMCSimulationResultsHTML(msg.dsmc_simulation_results);
        }
        // 检查是否有DSMC输入文件数据
        else if (msg.dsmc_input_file) {
            contentHTML = createDSMCInputFileHTML(msg.dsmc_input_file);
        } else {
            contentHTML = `<div class="message-text">${renderMarkdown(msg.content)}</div>`;
        }
    }

    // 时间显示在文本上方
    // 用户消息：时间在右方
    // 助手消息：时间在左方
    let ragInfoHTML = '';
    if (msg.rag_data) {
        ragInfoHTML = `<span class="rag-info">📊 ${msg.rag_data.entities}实体 | ${msg.rag_data.relationships}关系 | ${msg.rag_data.documents}文档</span>`;
    }

    return `
        <div class="message ${isUser ? 'user' : 'assistant'}">
            <div class="message-time ${isUser ? 'time-right' : 'time-left'}">
                <span>${time}</span>
                ${ragInfoHTML}
            </div>
            <div class="message-content">
                ${contentHTML}
            </div>
        </div>
    `;
}

// 创建DSMC仿真结果HTML（用于历史记录显示）
function createDSMCSimulationResultsHTML(data) {
    const { session_id, summary, plots, interpretation, suggestions } = data;

    // 保存session ID以便后续操作
    if (session_id) {
        dsmcSession = session_id;
    }

    let summaryHTML = '';
    if (summary) {
        summaryHTML = `
            <div class="result-summary">
                <h4>📈 仿真摘要</h4>
                ${Object.entries(summary).map(([key, value]) =>
                    `<p><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</p>`
                ).join('')}
            </div>
        `;
    }

    let plotsHTML = '';
    if (plots && plots.length > 0) {
        plotsHTML = `
            <div class="result-plots">
                <h4>📊 可视化图表</h4>
                ${plots.map(plot => {
                    const imageSrc = `/api/dsmc/sessions/${dsmcSession}/files/${plot.image_url}`;
                    return `
                    <div class="result-plot">
                        <h5>${escapeHtml(plot.title)}</h5>
                        <img src="${imageSrc}" alt="${escapeHtml(plot.title)}">
                    </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    let interpretationHTML = '';
    if (interpretation) {
        interpretationHTML = `
            <div class="result-interpretation">
                <h4>🤖 LLM分析</h4>
                ${renderMarkdown(interpretation)}
            </div>
        `;
    }

    let suggestionsHTML = '';
    if (suggestions && suggestions.length > 0) {
        suggestionsHTML = `
            <div class="iteration-panel">
                <h4>💡 优化建议</h4>
                ${suggestions.map(s => `
                    <div class="suggestion-item">
                        <strong>${escapeHtml(s.parameter)}</strong>:
                        ${escapeHtml(s.current)} → ${escapeHtml(s.suggested)}
                        <div class="reason">${escapeHtml(s.reason)}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    const resultsHTML = `
        <div class="dsmc-results">
            <h3>✅ DSMC仿真完成</h3>
            ${summaryHTML}
            ${plotsHTML}
            ${interpretationHTML}
            ${suggestionsHTML}
        </div>
    `;

    return `<div class="message-text">${resultsHTML}</div>`;
}

// 创建DSMC输入文件HTML（用于历史记录显示）
function createDSMCInputFileHTML(data) {
    const { input_file, annotations, parameter_reasoning, warnings, session_id, parameters, iteration } = data;

    // 保存session ID以便后续操作
    if (session_id) {
        dsmcSession = session_id;
        // 加载迭代列表
        loadIterations(session_id);
    }

    // 使用新的语法高亮函数生成代码HTML
    const codeHTML = generateHighlightedCodeLines(input_file || '', annotations || {});

    let warningsHTML = '';
    if (warnings && warnings.length > 0) {
        warningsHTML = `
            <div class="warnings">
                <h4>⚠️ 警告</h4>
                ${warnings.map(w => `<p>• ${escapeHtml(w)}</p>`).join('')}
            </div>
        `;
    }

    let paramsHTML = '';
    if (parameters) {
        paramsHTML = `
            <div class="timing-info">
                <h4>🔧 仿真参数</h4>
                <p><strong>温度:</strong> ${parameters.temperature} K</p>
                <p><strong>压力:</strong> ${parameters.pressure} Pa</p>
                <p><strong>速度:</strong> ${parameters.velocity} m/s</p>
                <p><strong>几何形状:</strong> ${parameters.geometry}</p>
                <p><strong>气体:</strong> ${parameters.gas}</p>
            </div>
        `;
    }

    // 迭代信息
    const iterationInfo = iteration ? `v${iteration.iteration_number}` : 'v1';

    const previewHTML = `
        <div class="dsmc-input-preview">
            <div class="input-header">
                <h3>📄 SPARTA输入文件预览 (${iterationInfo})</h3>
            </div>
            <div class="input-content">
                ${codeHTML}
            </div>
            ${paramsHTML}
            ${parameter_reasoning ? `
                <div class="parameter-reasoning">
                    <h4>📊 参数选择依据</h4>
                    <div class="reasoning-content">${renderMarkdown(parameter_reasoning)}</div>
                </div>
            ` : ''}
            ${warningsHTML}
        </div>
    `;

    // 显示运行面板（如果有session_id）
    if (session_id) {
        setTimeout(() => showDSMCRunPanel(), 100);
    }

    return `<div class="message-text">${previewHTML}</div>`;
}

// 渲染Markdown
function renderMarkdown(text) {
    if (!text) return '';
    
    // 预处理LaTeX公式，防止被Markdown解析器破坏
    const latexBlocks = [];
    const latexInlines = [];
    
    // 保护块级公式 $$...$$
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
        latexBlocks.push(formula);
        return `%%LATEXBLOCK${latexBlocks.length - 1}%%`;
    });
    
    // 保护行内公式 $...$
    text = text.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
        latexInlines.push(formula);
        return `%%LATEXINLINE${latexInlines.length - 1}%%`;
    });
    
    // 渲染Markdown
    let html = marked.parse(text);
    
    // 恢复块级公式
    html = html.replace(/%%LATEXBLOCK(\d+)%%/g, (match, index) => {
        return `<div class="katex-block" data-latex="${escapeHtml(latexBlocks[index])}"></div>`;
    });
    
    // 恢复行内公式
    html = html.replace(/%%LATEXINLINE(\d+)%%/g, (match, index) => {
        return `<span class="katex-inline" data-latex="${escapeHtml(latexInlines[index])}"></span>`;
    });
    
    return html;
}

// 渲染数学公式和代码高亮
function renderMathAndCode() {
    // 渲染块级公式
    document.querySelectorAll('.katex-block').forEach(el => {
        try {
            katex.render(el.dataset.latex, el, { displayMode: true, throwOnError: false });
        } catch (e) {
            el.textContent = el.dataset.latex;
        }
    });
    
    // 渲染行内公式
    document.querySelectorAll('.katex-inline').forEach(el => {
        try {
            katex.render(el.dataset.latex, el, { displayMode: false, throwOnError: false });
        } catch (e) {
            el.textContent = el.dataset.latex;
        }
    });
    
    // 代码高亮已在marked中处理
}

// 发送消息
async function sendMessage() {
    if (isStreaming) return;

    const message = messageInput.value.trim();
    let fullMessage = message;

    // 添加文件内容到消息
    if (fileTexts.length > 0) {
        const fileContent = fileTexts.map(f => `\n\n【文件: ${f.filename}】\n${f.text}`).join('');
        fullMessage += fileContent;
    }

    if (!fullMessage && images.length === 0) return;

    // 保存当前状态
    const currentImages = [...images];
    const currentModel = modelSelect.value;
    const currentRagEnabled = ragToggle.checked;

    // 保存最后一条用户消息用于重新生成
    lastUserMessage = {
        message: fullMessage,
        images: currentImages,
        model: currentModel,
        ragEnabled: currentRagEnabled
    };

    // 清空输入
    messageInput.value = '';
    messageInput.style.height = 'auto';
    clearAttachments();
    updateSendButton();

    // 发送消息
    await sendMessageWithData(fullMessage, currentImages, currentModel, currentRagEnabled);
}

// 使用指定数据发送消息
async function sendMessageWithData(fullMessage, currentImages, currentModel, currentRagEnabled) {
    if (isStreaming) return;

    // 如果没有当前对话，创建一个
    if (!currentConversationId) {
        await createNewConversation();
    }

    // 隐藏欢迎消息
    welcomeMessage.style.display = 'none';

    // 显示用户消息
    const userMsg = {
        role: 'user',
        content: fullMessage,
        images: [...currentImages],
        timestamp: new Date().toISOString()
    };
    chatMessages.innerHTML += createMessageHTML(userMsg);
    scrollToBottom();
    
    // 开始流式响应
    isStreaming = true;
    updateSendButton();
    
    // 创建助手消息容器
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'message assistant';
    assistantDiv.innerHTML = `
        <div class="message-time time-left">
            <span id="assistantTime"></span>
            <span id="assistantRagInfo"></span>
        </div>
        <div class="message-content">
            <div class="message-text"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
        </div>
    `;
    chatMessages.appendChild(assistantDiv);
    scrollToBottom();

    const messageTextDiv = assistantDiv.querySelector('.message-text');
    const messageTimeSpan = assistantDiv.querySelector('#assistantTime');
    const ragInfoSpan = assistantDiv.querySelector('#assistantRagInfo');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                message: fullMessage,
                model: currentModel,
                images: currentImages,
                rag_enabled: currentRagEnabled
            })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let ragStats = null;
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'status') {
                            // 显示状态
                            showStatus(data.message);
                            if (data.stats) {
                                showStats(data.stats);
                                ragStats = data.stats;
                            }
                        } else if (data.type === 'parameter_form') {
                            // DSMC参数表单
                            hideStatus();
                            showDSMCIndicator();
                            displayParameterForm();
                            messageTextDiv.innerHTML = '<span style="color: var(--rag-color);">请在下方填写DSMC仿真参数</span>';
                            messageTimeSpan.textContent = new Date().toLocaleTimeString();
                        } else if (data.type === 'content') {
                            // 隐藏状态栏（首次收到内容时）
                            if (fullResponse === '') {
                                hideStatus();
                            }
                            fullResponse += data.content;
                            messageTextDiv.innerHTML = renderMarkdown(fullResponse);
                            renderMathAndCode();
                            scrollToBottom();
                        } else if (data.type === 'done') {
                            hideStatus();
                            // 添加时间戳
                            messageTimeSpan.textContent = new Date().toLocaleTimeString();
                            // 添加RAG信息
                            if (ragStats) {
                                ragInfoSpan.innerHTML = `<span class="rag-info">📊 ${ragStats.entities}实体 | ${ragStats.relationships}关系 | ${ragStats.documents}文档</span>`;
                            }
                        } else if (data.type === 'error') {
                            hideStatus();
                            messageTextDiv.innerHTML = `<span style="color: var(--error-color);">❌ ${escapeHtml(data.error || data.message)}</span>`;
                            messageTimeSpan.textContent = new Date().toLocaleTimeString();
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }
            }
        }
        
    } catch (error) {
        hideStatus();
        messageTextDiv.innerHTML = `<span style="color: var(--error-color);">❌ 发送失败: ${escapeHtml(error.message)}</span>`;
    }

    isStreaming = false;
    updateSendButton();
    await loadConversations();
}

// 显示状态
function showStatus(message) {
    statusBar.classList.remove('hidden');
    statusText.textContent = message;
}

// 显示统计信息
function showStats(stats) {
    statusStats.classList.remove('hidden');
    statusStats.innerHTML = `
        <span>📦 ${stats.entities} 实体</span>
        <span>🔗 ${stats.relationships} 关系</span>
        <span>📄 ${stats.documents} 文档</span>
    `;
}

// 隐藏状态
function hideStatus() {
    statusBar.classList.add('hidden');
    statusStats.classList.add('hidden');
}

// 处理图片上传
function handleImageUpload(e) {
    const files = e.target.files;
    for (const file of files) {
        const reader = new FileReader();
        reader.onload = (event) => {
            images.push(event.target.result);
            renderAttachments();
            updateSendButton();
        };
        reader.readAsDataURL(file);
    }
    imageInput.value = '';
}

// 处理文件上传
async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.error) {
            alert('文件上传失败: ' + data.error);
            return;
        }

        // 检测文件类型
        const fileTypeInfo = detectUploadedFileType(file.name);

        fileTexts.push({
            filename: data.filename,
            text: data.text,
            size: file.size,
            fileType: fileTypeInfo.type,
            fileIcon: fileTypeInfo.icon,
            fileLabel: fileTypeInfo.label
        });
        renderAttachments();
        updateSendButton();
    } catch (error) {
        alert('文件上传失败: ' + error.message);
    }

    fileInput.value = '';
}

// 检测上传文件类型
function detectUploadedFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const typeMap = {
        'sparta': { type: 'sparta', label: 'SPARTA输入', icon: '📝' },
        'in': { type: 'sparta', label: 'SPARTA输入', icon: '📝' },
        'pdf': { type: 'reference', label: '参考资料', icon: '📄' },
        'doc': { type: 'reference', label: '参考资料', icon: '📄' },
        'docx': { type: 'reference', label: '参考资料', icon: '📄' },
        'md': { type: 'document', label: '文档', icon: '📝' },
        'txt': { type: 'text', label: '文本', icon: '📄' },
        'json': { type: 'config', label: '配置', icon: '⚙️' },
        'yaml': { type: 'config', label: '配置', icon: '⚙️' },
        'yml': { type: 'config', label: '配置', icon: '⚙️' },
        'xml': { type: 'config', label: '配置', icon: '⚙️' },
        'dat': { type: 'data', label: '数据', icon: '📊' },
        'csv': { type: 'data', label: '数据', icon: '📊' },
        'xls': { type: 'data', label: '数据', icon: '📊' },
        'xlsx': { type: 'data', label: '数据', icon: '📊' },
        'stl': { type: 'geometry', label: '几何', icon: '📐' },
        'obj': { type: 'geometry', label: '几何', icon: '📐' },
        'surf': { type: 'geometry', label: '几何', icon: '📐' },
        'grid': { type: 'grid', label: '网格', icon: '🔲' },
        'py': { type: 'code', label: '代码', icon: '💻' },
        'js': { type: 'code', label: '代码', icon: '💻' },
        'html': { type: 'code', label: '代码', icon: '💻' },
        'css': { type: 'code', label: '代码', icon: '💻' }
    };
    return typeMap[ext] || { type: 'other', label: '其他', icon: '📎' };
}

// 格式化文件大小（用于附件显示）
function formatAttachmentSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// 渲染附件预览
function renderAttachments() {
    let html = '';

    images.forEach((img, index) => {
        html += `
            <div class="attachment-preview">
                <img src="${img}">
                <button class="remove-btn" onclick="removeImage(${index})">×</button>
            </div>
        `;
    });

    fileTexts.forEach((file, index) => {
        const icon = file.fileIcon || '📄';
        const size = file.size ? formatAttachmentSize(file.size) : '';
        const filename = file.filename || '未知文件';
        const currentType = file.fileType || 'other';

        html += `
            <div class="attachment-preview file-attachment">
                <div class="file-preview-detailed">
                    <span class="file-icon-large">${icon}</span>
                    <div class="file-info-detailed">
                        <span class="file-name-full" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
                        <span class="file-size-info">${size}</span>
                    </div>
                    <select class="file-type-selector" onchange="updateFileType(${index}, this.value)">
                        <option value="reference" ${currentType === 'reference' ? 'selected' : ''}>参考资料</option>
                        <option value="sparta" ${currentType === 'sparta' ? 'selected' : ''}>SPARTA输入</option>
                        <option value="document" ${currentType === 'document' ? 'selected' : ''}>文档</option>
                        <option value="data" ${currentType === 'data' ? 'selected' : ''}>数据</option>
                        <option value="geometry" ${currentType === 'geometry' ? 'selected' : ''}>几何</option>
                        <option value="grid" ${currentType === 'grid' ? 'selected' : ''}>网格</option>
                        <option value="config" ${currentType === 'config' ? 'selected' : ''}>配置</option>
                        <option value="code" ${currentType === 'code' ? 'selected' : ''}>代码</option>
                        <option value="other" ${currentType === 'other' ? 'selected' : ''}>其他</option>
                    </select>
                </div>
                <button class="remove-btn" onclick="removeFile(${index})">×</button>
            </div>
        `;
    });

    inputAttachments.innerHTML = html;
}

// 更新文件类型
function updateFileType(index, newType) {
    if (fileTexts[index]) {
        fileTexts[index].fileType = newType;
        // 更新对应的图标和标签
        const typeIconMap = {
            'reference': { icon: '📄', label: '参考资料' },
            'sparta': { icon: '📝', label: 'SPARTA输入' },
            'document': { icon: '📝', label: '文档' },
            'data': { icon: '📊', label: '数据' },
            'geometry': { icon: '📐', label: '几何' },
            'grid': { icon: '🔲', label: '网格' },
            'config': { icon: '⚙️', label: '配置' },
            'code': { icon: '💻', label: '代码' },
            'other': { icon: '📎', label: '其他' }
        };
        const typeInfo = typeIconMap[newType] || typeIconMap['other'];
        fileTexts[index].fileIcon = typeInfo.icon;
        fileTexts[index].fileLabel = typeInfo.label;
    }
}

// 移除图片
function removeImage(index) {
    images.splice(index, 1);
    renderAttachments();
    updateSendButton();
}

// 移除文件
function removeFile(index) {
    fileTexts.splice(index, 1);
    renderAttachments();
    updateSendButton();
}

// 清空附件
function clearAttachments() {
    images = [];
    fileTexts = [];
    inputAttachments.innerHTML = '';
}

// 显示图片模态框
function showImageModal(src) {
    const modal = document.createElement('div');
    modal.className = 'image-modal';
    modal.innerHTML = `<img src="${src}">`;
    modal.onclick = () => modal.remove();
    document.body.appendChild(modal);
}

// 滚动到底部
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== DSMC相关功能 ====================

// DSMC全局变量
let dsmcSession = null;
let currentDSMCParameters = null;
let isSimulationRunning = false;  // 追踪仿真是否正在运行

// DSMC DOM元素
const dsmcIndicator = document.getElementById('dsmcIndicator');

// 显示/隐藏运行和停止按钮
function showRunButton() {
    const runBtn = document.getElementById('runSimulationBtn');
    const stopBtn = document.getElementById('stopSimulationBtn');
    if (runBtn) runBtn.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
    isSimulationRunning = false;
}

function showStopButton() {
    const runBtn = document.getElementById('runSimulationBtn');
    const stopBtn = document.getElementById('stopSimulationBtn');
    if (runBtn) runBtn.classList.add('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    isSimulationRunning = true;
}

// 停止仿真
async function stopSimulation() {
    if (!dsmcSession) {
        alert('没有可停止的仿真会话');
        return;
    }

    if (!isSimulationRunning) {
        alert('当前没有正在运行的仿真');
        return;
    }

    if (!confirm('确定要停止当前运行的仿真吗？')) {
        return;
    }

    try {
        showStatus('正在停止仿真...');

        const response = await fetch(`/api/dsmc/stop/${dsmcSession}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            hideStatus();
            showRunButton();

            // 在对话中显示停止消息
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="message-text">
                        <div class="dsmc-results">
                            <h3>⏹️ 仿真已停止</h3>
                            <p>用户手动停止了SPARTA仿真。</p>
                        </div>
                    </div>
                    <div class="message-meta"><span>${new Date().toLocaleTimeString()}</span></div>
                </div>
            `;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
        } else {
            hideStatus();
            alert('停止仿真失败: ' + result.message);
        }
    } catch (error) {
        hideStatus();
        showRunButton();
        alert('停止仿真失败: ' + error.message);
    }
}

// 显示DSMC模式指示器
function showDSMCIndicator() {
    if (dsmcIndicator) {
        dsmcIndicator.classList.remove('hidden');
    }
}

// 隐藏DSMC模式指示器
function hideDSMCIndicator() {
    if (dsmcIndicator) {
        dsmcIndicator.classList.add('hidden');
    }
}

// 显示DSMC控制面板（合并后的）
function showDSMCControlPanel() {
    const panel = document.getElementById('dsmcControlPanel');
    if (panel) {
        panel.classList.remove('disabled');
    }
    // 刷新监控数据
    if (dsmcSession) {
        refreshMonitor();
        refreshLog();
    }
}

// 隐藏DSMC控制面板（变暗但不隐藏）
function hideDSMCControlPanel() {
    const panel = document.getElementById('dsmcControlPanel');
    if (panel) {
        panel.classList.add('disabled');
    }
    stopMonitoring();
}

// 兼容旧函数名
function showDSMCRunPanel() {
    showDSMCControlPanel();
}

function hideDSMCRunPanel() {
    hideDSMCControlPanel();
}

// 更新控制面板中的耗时信息
function updateTimingInfo(timing) {
    const container = document.getElementById('timingInfoContainer');
    const content = document.getElementById('timingInfoContent');

    if (!container || !content) return;

    const steps = timing.steps || {};
    const stepsList = Object.entries(steps).map(([name, time]) =>
        `<div class="timing-step"><span class="step-name">${name}</span><span class="step-time">${time}s</span></div>`
    ).join('');

    content.innerHTML = `
        <div class="timing-total"><strong>总时间:</strong> ${timing.total_time}秒</div>
        ${stepsList ? `<div class="timing-steps">${stepsList}</div>` : ''}
    `;

    container.classList.remove('hidden');
}

// ==================== 文件类型识别映射 ====================
const FILE_TYPE_MAP = {
    // 几何形状
    'stl': { type: 'geometry', label: '几何形状', zone: 'workspace', icon: '📐' },
    'obj': { type: 'geometry', label: '几何形状', zone: 'workspace', icon: '📐' },
    'surf': { type: 'geometry', label: '几何形状', zone: 'workspace', icon: '📐' },
    // SPARTA输入文件
    'sparta': { type: 'input', label: 'SPARTA输入文件', zone: 'llm', icon: '📝' },
    'in': { type: 'input', label: 'SPARTA输入文件', zone: 'llm', icon: '📝' },
    // 气体数据
    'dat': { type: 'gas_data', label: '气体种类数据', zone: 'workspace', icon: '🔬' },
    'species': { type: 'gas_data', label: '气体种类数据', zone: 'workspace', icon: '🔬' },
    // 网格文件
    'grid': { type: 'grid', label: '网格文件', zone: 'workspace', icon: '🔲' },
    // 论文/资料 (zone: llm - 传给AI理解)
    'pdf': { type: 'reference', label: '论文/资料', zone: 'llm', icon: '📄' },
    'doc': { type: 'reference', label: '论文/资料', zone: 'llm', icon: '📄' },
    'docx': { type: 'reference', label: '论文/资料', zone: 'llm', icon: '📄' },
    'md': { type: 'reference', label: '论文/资料', zone: 'llm', icon: '📄' },
    'txt': { type: 'reference', label: '论文/资料', zone: 'llm', icon: '📄' },
    // 其他
    'default': { type: 'other', label: '其他配置', zone: 'workspace', icon: '📎' }
};

// 文件类型到zone的映射
const TYPE_ZONE_MAP = {
    'geometry': 'workspace',
    'input': 'llm',
    'gas_data': 'workspace',
    'grid': 'workspace',
    'grid_data': 'workspace',
    'reference': 'llm',
    'other': 'workspace'
};

// 存储上传的DSMC文件
let uploadedDSMCFiles = [];

// 检测文件类型
function detectFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    // 检查 data.* 模式
    if (filename.toLowerCase().startsWith('data.')) {
        return { type: 'grid_data', label: '网格数据', zone: 'workspace', icon: '🗂️' };
    }
    return FILE_TYPE_MAP[ext] || FILE_TYPE_MAP['default'];
}

// 格式化文件大小
function formatFileSizeSmall(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// 显示参数配置表单（科学计算风格+分组折叠+文件上传）
function displayParameterForm() {
    // 生成唯一的表单ID，避免多个表单ID冲突
    const formId = 'parameterForm_' + Date.now();

    const formHTML = `
        <div class="dsmc-parameter-form scientific-style" id="dsmcParameterForm">
            <div class="form-header">
                <span class="form-header-icon">⚛️</span>
                <h3>DSMC仿真参数配置</h3>
            </div>
            <form id="${formId}" novalidate>
                <!-- 高度与大气模型组 - 默认展开 -->
                <div class="param-group expanded" id="altitudeParams">
                    <div class="group-header" onclick="toggleParamGroup('altitudeParams')">
                        <span class="group-title"><span class="group-icon">🌍</span> 高度与大气模型</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row altitude-input-row">
                            <label>飞行高度 <span class="unit">(km)</span></label>
                            <div class="altitude-input-container">
                                <input type="number" id="altitude" name="altitude" value="100" min="0" max="500" step="1" oninput="onAltitudeChange()">
                                <input type="range" id="altitudeSlider" min="0" max="500" value="100" step="1" oninput="onAltitudeSliderChange()">
                            </div>
                            <span class="tooltip-icon" title="大气层高度范围：0-500km">?</span>
                        </div>
                        <div class="param-row">
                            <label>大气模型</label>
                            <select id="atmosphereModel" name="atmosphereModel" onchange="onAtmosphereModelChange()">
                                <option value="ISA" selected>ISA 标准大气</option>
                                <option value="US76">US76 标准大气</option>
                                <option value="NRLMSISE00">NRLMSISE-00</option>
                                <option value="custom">自定义</option>
                            </select>
                            <span class="tooltip-icon" title="ISA适用于0-86km，NRLMSISE-00适用于高层大气">?</span>
                        </div>
                        <div class="atmosphere-preview" id="atmospherePreview">
                            <div class="preview-header">
                                <span>大气参数预览</span>
                                <button type="button" class="btn-apply-atm" onclick="applyAtmosphereParams()">应用到基础参数</button>
                            </div>
                            <div class="preview-values" id="atmosphereValues">
                                <!-- 动态填充 -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 基础参数组 - 默认展开 -->
                <div class="param-group expanded" id="basicParams">
                    <div class="group-header" onclick="toggleParamGroup('basicParams')">
                        <span class="group-title"><span class="group-icon">🎯</span> 基础参数</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row">
                            <label>温度 <span class="unit">(K)</span></label>
                            <div class="linked-input">
                                <input type="number" id="temperature" name="temperature" value="300" min="1" max="10000" required>
                                <span class="linked-indicator hidden" id="temperatureLinked" title="从高度计算得出">🔗</span>
                            </div>
                            <span class="tooltip-icon" title="流场静态温度">?</span>
                        </div>
                        <div class="param-row">
                            <label>压力 <span class="unit">(Pa)</span></label>
                            <div class="linked-input">
                                <input type="text" id="pressure" name="pressure" value="101325" pattern="[0-9.eE+-]+" required>
                                <span class="linked-indicator hidden" id="pressureLinked" title="从高度计算得出">🔗</span>
                            </div>
                            <span class="tooltip-icon" title="环境静压">?</span>
                        </div>
                        <div class="param-row">
                            <label>速度 <span class="unit">(m/s)</span></label>
                            <input type="number" id="velocity" name="velocity" value="1000" min="0" max="10000" required>
                            <span class="tooltip-icon" title="来流速度">?</span>
                        </div>
                        <div class="param-row">
                            <label>几何形状</label>
                            <select id="geometry" name="geometry" required>
                                <option value="cylinder">圆柱体</option>
                                <option value="sphere">球体</option>
                                <option value="plate">平板</option>
                                <option value="cone">锥体</option>
                                <option value="custom">自定义(需上传)</option>
                            </select>
                        </div>
                        <div class="param-row">
                            <label>气体类型</label>
                            <select id="gas" name="gas" required>
                                <option value="N2">氮气 (N2)</option>
                                <option value="O2">氧气 (O2)</option>
                                <option value="Ar">氩气 (Ar)</option>
                                <option value="Air">空气 (Air)</option>
                                <option value="He">氦气 (He)</option>
                                <option value="custom">自定义(需上传)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- 边界条件组 - 默认折叠 -->
                <div class="param-group collapsed" id="boundaryParams">
                    <div class="group-header" onclick="toggleParamGroup('boundaryParams')">
                        <span class="group-title"><span class="group-icon">🔲</span> 边界条件</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row">
                            <label>入口类型</label>
                            <select id="inletType" name="inletType">
                                <option value="freestream">自由来流</option>
                                <option value="pressure">压力入口</option>
                                <option value="velocity">速度入口</option>
                            </select>
                        </div>
                        <div class="param-row">
                            <label>出口类型</label>
                            <select id="outletType" name="outletType">
                                <option value="outflow">自由出流</option>
                                <option value="vacuum">真空</option>
                            </select>
                        </div>
                        <div class="param-row">
                            <label>壁面条件</label>
                            <select id="wallCondition" name="wallCondition">
                                <option value="diffuse">漫反射</option>
                                <option value="specular">镜面反射</option>
                                <option value="thermal">热适应</option>
                            </select>
                        </div>
                        <div class="param-row">
                            <label>壁面温度 <span class="unit">(K)</span></label>
                            <input type="number" id="wallTemp" name="wallTemp" value="300" min="1">
                        </div>
                    </div>
                </div>

                <!-- 时间与网格组 - 默认折叠 -->
                <div class="param-group collapsed" id="timeGridParams">
                    <div class="group-header" onclick="toggleParamGroup('timeGridParams')">
                        <span class="group-title"><span class="group-icon">⏱️</span> 时间与网格</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row">
                            <label>时间步长 <span class="unit">(s)</span></label>
                            <input type="text" id="timestep" name="timestep" value="1e-7">
                        </div>
                        <div class="param-row">
                            <label>模拟时间 <span class="unit">(s)</span></label>
                            <input type="text" id="simTime" name="simTime" value="1e-4">
                        </div>
                        <div class="param-row">
                            <label>网格分辨率</label>
                            <select id="gridResolution" name="gridResolution" onchange="toggleCustomGrid()">
                                <option value="coarse">粗网格</option>
                                <option value="medium" selected>中等网格</option>
                                <option value="fine">细网格</option>
                                <option value="custom">自定义</option>
                            </select>
                        </div>
                        <div class="param-row" id="customGridRow" style="display:none">
                            <label>网格尺寸 <span class="unit">(m)</span></label>
                            <input type="text" id="gridSize" name="gridSize" value="0.01">
                        </div>
                    </div>
                </div>

                <!-- 碰撞与粒子组 - 默认折叠 -->
                <div class="param-group collapsed" id="collisionParams">
                    <div class="group-header" onclick="toggleParamGroup('collisionParams')">
                        <span class="group-title"><span class="group-icon">💥</span> 碰撞与粒子</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row">
                            <label>碰撞模型</label>
                            <select id="collisionModel" name="collisionModel">
                                <option value="vhs" selected>VHS</option>
                                <option value="vss">VSS</option>
                                <option value="hs">硬球</option>
                            </select>
                        </div>
                        <div class="param-row">
                            <label>粒子权重因子</label>
                            <input type="text" id="fnum" name="fnum" value="1e10">
                            <span class="tooltip-icon" title="每个模拟粒子代表的真实分子数">?</span>
                        </div>
                        <div class="param-row">
                            <label>初始粒子数</label>
                            <input type="number" id="nparticles" name="nparticles" value="10000" min="1000">
                        </div>
                    </div>
                </div>

                <!-- 输出控制组 - 默认折叠 -->
                <div class="param-group collapsed" id="outputParams">
                    <div class="group-header" onclick="toggleParamGroup('outputParams')">
                        <span class="group-title"><span class="group-icon">📊</span> 输出控制</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <div class="param-row">
                            <label>输出频率 <span class="unit">(步)</span></label>
                            <input type="number" id="dumpFreq" name="dumpFreq" value="100" min="1">
                        </div>
                        <div class="param-row">
                            <label>统计采样开始 <span class="unit">(步)</span></label>
                            <input type="number" id="statsStart" name="statsStart" value="500" min="0">
                        </div>
                        <div class="param-row">
                            <label>输出变量</label>
                            <div class="checkbox-group">
                                <label><input type="checkbox" name="outputVars" value="density" checked> 密度</label>
                                <label><input type="checkbox" name="outputVars" value="velocity" checked> 速度</label>
                                <label><input type="checkbox" name="outputVars" value="temperature" checked> 温度</label>
                                <label><input type="checkbox" name="outputVars" value="pressure" checked> 压力</label>
                                <label><input type="checkbox" name="outputVars" value="mach"> 马赫数</label>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 文件上传区域 -->
                <div class="file-upload-section">
                    <div class="upload-header">
                        <span class="upload-icon">📁</span>
                        <h4>文件上传</h4>
                    </div>
                    <div class="upload-dropzone" id="uploadDropzone">
                        <div class="dropzone-content">
                            <span class="cloud-icon">☁️</span>
                            <p>拖拽文件到此处，或 <label for="dsmcFileInput" class="upload-link">点击选择</label></p>
                            <p class="supported-types">支持: .stl, .obj, .sparta, .in, .dat, .grid, .pdf, .doc 等</p>
                        </div>
                        <input type="file" id="dsmcFileInput" multiple hidden>
                    </div>

                    <!-- 已上传文件列表 - 分区显示 -->
                    <div class="uploaded-files" id="uploadedFiles" style="display:none">
                        <!-- LLM参考文件区 -->
                        <div class="file-zone llm-zone">
                            <div class="zone-header">
                                <span class="zone-title">📚 LLM参考资料</span>
                                <span class="zone-hint">内容将传给AI理解</span>
                            </div>
                            <div class="zone-files" id="llmFiles">
                                <div class="zone-empty">暂无文件</div>
                            </div>
                        </div>

                        <!-- 工作目录文件区 -->
                        <div class="file-zone workspace-zone">
                            <div class="zone-header">
                                <span class="zone-title">📁 仿真工作目录</span>
                                <span class="zone-hint">将复制到运行目录</span>
                            </div>
                            <div class="zone-files" id="workspaceFiles">
                                <div class="zone-empty">暂无文件</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 自定义设定（自然语言补充） -->
                <div class="param-group expanded" id="customParams">
                    <div class="group-header" onclick="toggleParamGroup('customParams')">
                        <span class="group-title"><span class="group-icon">✏️</span> 自定义设定</span>
                        <span class="group-toggle">▼</span>
                    </div>
                    <div class="group-content">
                        <textarea id="customInput" name="customInput" placeholder="使用自然语言描述额外的仿真需求，例如：&#10;- 添加一个正弦波形的入口边界&#10;- 设置更高的网格精度&#10;- 使用特定的碰撞模型" rows="3" style="width:100%; padding:10px; background:var(--bg-primary); border:1px solid var(--border-color); border-radius:8px; color:var(--text-primary); font-size:0.85rem; resize:vertical;"></textarea>
                    </div>
                </div>

                <button type="submit" class="form-submit-btn">
                    <span>🚀</span>
                    <span>生成SPARTA输入文件</span>
                </button>
            </form>
        </div>
    `;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">${formHTML}</div>
            <div class="message-meta"><span>${new Date().toLocaleTimeString()}</span></div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    // 清空已上传文件列表
    uploadedDSMCFiles = [];

    // 绑定表单提交事件 - 使用唯一的formId
    const formElement = document.getElementById(formId);
    if (formElement) {
        formElement.addEventListener('submit', handleParameterSubmit);
    } else {
        console.error('无法找到表单元素:', formId);
    }

    // 绑定文件上传事件
    setupDSMCFileUpload();

    // 初始化大气参数预览
    updateAtmospherePreview();
}

// 参数组折叠/展开
function toggleParamGroup(groupId) {
    const group = document.getElementById(groupId);
    if (!group) return;

    if (group.classList.contains('collapsed')) {
        group.classList.remove('collapsed');
        group.classList.add('expanded');
    } else {
        group.classList.remove('expanded');
        group.classList.add('collapsed');
    }
}

// 切换自定义网格输入显示
function toggleCustomGrid() {
    const select = document.getElementById('gridResolution');
    const customRow = document.getElementById('customGridRow');
    if (select && customRow) {
        customRow.style.display = select.value === 'custom' ? 'flex' : 'none';
    }
}

// 设置DSMC文件上传
function setupDSMCFileUpload() {
    console.log('setupDSMCFileUpload called');
    const dropzone = document.getElementById('uploadDropzone');
    const fileInput = document.getElementById('dsmcFileInput');

    console.log('dropzone:', !!dropzone, 'fileInput:', !!fileInput);

    if (!dropzone || !fileInput) {
        console.error('setupDSMCFileUpload: DOM elements not found!');
        return;
    }

    // 检查是否已经绑定过事件（防止重复绑定）
    if (dropzone.dataset.uploadInitialized === 'true') {
        console.log('setupDSMCFileUpload: already initialized, skipping');
        return;
    }
    dropzone.dataset.uploadInitialized = 'true';

    // 点击上传
    dropzone.addEventListener('click', (e) => {
        console.log('Dropzone clicked, target:', e.target.tagName);
        // 如果点击的是 INPUT 或 LABEL，让浏览器默认行为处理，不要重复触发
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'LABEL') {
            return;
        }
        fileInput.click();
    });

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        console.log('File input changed, files:', e.target.files.length);
        if (e.target.files.length > 0) {
            // 复制文件列表，避免 async 函数执行时被清空
            const files = Array.from(e.target.files);
            handleDSMCFileUpload(files);
        }
        // 重置input，允许重复选择同一文件
        fileInput.value = '';
    });

    // 拖拽上传
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        console.log('File dropped, files:', e.dataTransfer.files.length);
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleDSMCFileUpload(e.dataTransfer.files);
        }
    });

    console.log('setupDSMCFileUpload completed successfully');
}

// 处理DSMC文件上传
async function handleDSMCFileUpload(files) {
    console.log('handleDSMCFileUpload called, files count:', files.length);

    for (const file of files) {
        console.log('Processing file:', file.name, 'size:', file.size);
        const typeInfo = detectFileType(file.name);
        console.log('Detected type:', typeInfo);

        // 读取文件内容（对于LLM参考文件）
        let content = null;
        if (typeInfo.zone === 'llm') {
            content = await readDSMCFileContent(file);
            console.log('File content loaded, length:', content ? content.length : 0);
        }

        const fileData = {
            id: 'file_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
            file: file,
            filename: file.name,
            size: file.size,
            type: typeInfo.type,
            zone: typeInfo.zone,
            icon: typeInfo.icon,
            label: typeInfo.label,
            content: content
        };

        // 检测是否为SPARTA输入文件，弹出选择对话框
        if (typeInfo.type === 'input' && content) {
            showInputFileUploadModal(fileData);
        } else {
            uploadedDSMCFiles.push(fileData);
            console.log('File added to uploadedDSMCFiles, total:', uploadedDSMCFiles.length);
        }
    }

    updateFileZonesDisplay();
}

// ==================== SPARTA输入文件上传弹窗 ====================

// 存储待处理的上传输入文件
let pendingInputFile = null;

// 显示输入文件上传选项弹窗
function showInputFileUploadModal(fileData) {
    pendingInputFile = fileData;

    // 显示文件预览
    const previewContainer = document.getElementById('uploadedInputFilePreview');
    if (previewContainer) {
        const contentPreview = fileData.content ? fileData.content.substring(0, 500) : '';
        previewContainer.innerHTML = `
            <div class="file-preview-item">
                <span class="file-icon">📄</span>
                <span class="file-name">${escapeHtml(fileData.filename)}</span>
                <span class="file-size">${formatFileSizeSmall(fileData.size)}</span>
            </div>
            <div class="file-content-preview">
                <pre>${escapeHtml(contentPreview)}${fileData.content && fileData.content.length > 500 ? '...' : ''}</pre>
            </div>
        `;
    }

    // 隐藏验证结果
    const validationResult = document.getElementById('inputFileValidationResult');
    if (validationResult) {
        validationResult.classList.add('hidden');
        validationResult.innerHTML = '';
    }

    // 重置运行按钮
    const runBtn = document.getElementById('runDirectlyBtn');
    if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '🚀 直接运行';
        runBtn.onclick = validateAndRunDirectly;
    }

    showModalOverlay();
    document.getElementById('inputFileUploadModal').classList.remove('hidden');
}

// 关闭输入文件上传弹窗
function closeInputFileUploadModal() {
    pendingInputFile = null;
    document.getElementById('inputFileUploadModal').classList.add('hidden');
    hideModalOverlay();
}

// 作为参考处理
function useAsReference() {
    if (pendingInputFile) {
        // 保持原有逻辑：添加到uploadedDSMCFiles作为LLM参考
        uploadedDSMCFiles.push(pendingInputFile);
        updateFileZonesDisplay();
        console.log('文件已添加为LLM参考:', pendingInputFile.filename);
    }
    closeInputFileUploadModal();
}

// 验证并直接运行
async function validateAndRunDirectly() {
    if (!pendingInputFile) return;

    const runBtn = document.getElementById('runDirectlyBtn');
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner-small"></span> 验证中...';

    const validationResult = document.getElementById('inputFileValidationResult');
    validationResult.classList.remove('hidden');
    validationResult.innerHTML = '<div class="validating">🔍 正在进行语法检查和依赖验证...</div>';

    try {
        // 调用后端验证API
        const response = await fetch('/api/dsmc/validate-input', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: pendingInputFile.content,
                filename: pendingInputFile.filename
            })
        });

        const result = await response.json();

        if (result.valid) {
            validationResult.innerHTML = `
                <div class="validation-success">
                    <h4>✅ 验证通过</h4>
                    <ul>
                        <li>语法检查: 通过</li>
                        <li>依赖文件: ${result.dependencies?.found?.length || 0} 个已找到</li>
                    </ul>
                    ${result.warnings?.length > 0 ? `
                        <div class="validation-warnings">
                            <h5>⚠️ 警告</h5>
                            <ul>${result.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                </div>
            `;

            // 启用直接运行按钮，改为"确认运行"
            runBtn.disabled = false;
            runBtn.innerHTML = '✅ 确认运行';
            runBtn.onclick = executeDirectRun;
        } else {
            validationResult.innerHTML = `
                <div class="validation-error">
                    <h4>❌ 验证失败</h4>
                    <div class="error-details">
                        ${result.syntax_errors?.length > 0 ? `
                            <div class="syntax-errors">
                                <h5>语法错误</h5>
                                <ul>${result.syntax_errors.map(e => `<li>行 ${e.line}: ${escapeHtml(e.message)}</li>`).join('')}</ul>
                            </div>
                        ` : ''}
                        ${result.missing_dependencies?.length > 0 ? `
                            <div class="missing-deps">
                                <h5>缺失依赖文件</h5>
                                <ul>${result.missing_dependencies.map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>
                            </div>
                        ` : ''}
                    </div>
                    <p class="validation-hint">您可以选择"作为参考"让AI根据此文件生成修正版本。</p>
                </div>
            `;
            runBtn.disabled = false;
            runBtn.innerHTML = '🚀 直接运行';
            runBtn.onclick = validateAndRunDirectly;
        }
    } catch (error) {
        validationResult.innerHTML = `<div class="validation-error">验证请求失败: ${escapeHtml(error.message)}</div>`;
        runBtn.disabled = false;
        runBtn.innerHTML = '🚀 直接运行';
        runBtn.onclick = validateAndRunDirectly;
    }
}

// 执行直接运行
async function executeDirectRun() {
    if (!pendingInputFile) return;

    // 先保存文件数据，因为closeInputFileUploadModal会将pendingInputFile设为null
    const inputContent = pendingInputFile.content;
    const inputFilename = pendingInputFile.filename;

    closeInputFileUploadModal();
    showStatus('🚀 正在创建会话并运行仿真...');
    updateProcessTracker(PROCESS_STEPS.RUNNING);

    try {
        // 如果没有活跃的对话，创建新对话
        if (!currentConversationId) {
            await createNewConversation();
        }

        // 调用后端API创建DSMC会话并运行
        const response = await fetch('/api/dsmc/run-uploaded-input', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                input_content: inputContent,
                filename: inputFilename
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.substring(6));

                        if (event.type === 'status') {
                            showStatus(event.message);
                        } else if (event.type === 'session_created') {
                            dsmcSession = event.session_id;
                            console.log('DSMC会话已创建:', dsmcSession);
                        } else if (event.type === 'iteration_created') {
                            await loadIterations(dsmcSession, true);
                        } else if (event.type === 'done' || event.type === 'run_complete') {
                            hideStatus();
                            await loadIterations(dsmcSession, true);
                            if (activeIterationId) {
                                await switchIteration(activeIterationId);
                            }
                            completeProcessTracker();
                        } else if (event.type === 'error') {
                            hideStatus();
                            resetProcessTracker();
                            alert('运行失败: ' + event.error);
                        }
                    } catch (e) {
                        console.error('解析事件失败:', e, line);
                    }
                }
            }
        }
    } catch (error) {
        hideStatus();
        resetProcessTracker();
        alert('运行失败: ' + error.message);
    }
}

// 格式化文件大小（小版本）
function formatFileSizeSmall(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// 读取文件内容
function readDSMCFileContent(file) {
    return new Promise((resolve) => {
        // 对于文本文件，直接读取
        if (file.type.startsWith('text/') ||
            file.name.endsWith('.sparta') ||
            file.name.endsWith('.in') ||
            file.name.endsWith('.dat')) {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => resolve(null);
            reader.readAsText(file);
        } else {
            // 其他文件标记为需要后端处理
            resolve('[需要后端提取内容]');
        }
    });
}

// 更新文件分区显示
function updateFileZonesDisplay() {
    const uploadedFilesContainer = document.getElementById('uploadedFiles');
    const llmFilesContainer = document.getElementById('llmFiles');
    const workspaceFilesContainer = document.getElementById('workspaceFiles');

    console.log('updateFileZonesDisplay called, files:', uploadedDSMCFiles.length);
    console.log('uploadedDSMCFiles:', uploadedDSMCFiles);

    if (!uploadedFilesContainer || !llmFilesContainer || !workspaceFilesContainer) {
        console.error('File zone containers not found!', {
            uploadedFiles: !!uploadedFilesContainer,
            llmFiles: !!llmFilesContainer,
            workspaceFiles: !!workspaceFilesContainer
        });
        return;
    }

    const llmFiles = uploadedDSMCFiles.filter(f => f.zone === 'llm');
    const workspaceFiles = uploadedDSMCFiles.filter(f => f.zone === 'workspace');

    console.log('llmFiles count:', llmFiles.length, 'workspaceFiles count:', workspaceFiles.length);

    // 渲染LLM文件区
    if (llmFiles.length > 0) {
        const html = llmFiles.map(f => createDSMCFileItemHTML(f)).join('');
        console.log('LLM files HTML length:', html.length);
        llmFilesContainer.innerHTML = html;
    } else {
        llmFilesContainer.innerHTML = '<div class="zone-empty">暂无文件</div>';
    }

    // 渲染工作目录文件区
    if (workspaceFiles.length > 0) {
        const html = workspaceFiles.map(f => createDSMCFileItemHTML(f)).join('');
        console.log('Workspace files HTML length:', html.length);
        workspaceFilesContainer.innerHTML = html;
    } else {
        workspaceFilesContainer.innerHTML = '<div class="zone-empty">暂无文件</div>';
    }

    // 显示/隐藏文件区域
    uploadedFilesContainer.style.display = uploadedDSMCFiles.length > 0 ? 'block' : 'none';
    console.log('uploadedFilesContainer display:', uploadedFilesContainer.style.display);
}

// 创建文件条目HTML
function createDSMCFileItemHTML(fileData) {
    return `
        <div class="uploaded-file-item" data-file-id="${fileData.id}">
            <span class="file-type-icon">${fileData.icon}</span>
            <div class="file-name" title="${fileData.filename}">${fileData.filename}</div>
            <span class="file-size">${formatFileSizeSmall(fileData.size)}</span>
            <select class="file-type-select" onchange="updateDSMCFileType('${fileData.id}', this.value)">
                <option value="geometry" ${fileData.type === 'geometry' ? 'selected' : ''}>几何形状</option>
                <option value="input" ${fileData.type === 'input' ? 'selected' : ''}>SPARTA输入</option>
                <option value="gas_data" ${fileData.type === 'gas_data' ? 'selected' : ''}>气体数据</option>
                <option value="grid" ${fileData.type === 'grid' ? 'selected' : ''}>网格文件</option>
                <option value="grid_data" ${fileData.type === 'grid_data' ? 'selected' : ''}>网格数据</option>
                <option value="reference" ${fileData.type === 'reference' ? 'selected' : ''}>参考资料</option>
                <option value="other" ${fileData.type === 'other' ? 'selected' : ''}>其他</option>
            </select>
            <button type="button" class="file-remove-btn" onclick="removeDSMCFile('${fileData.id}')" title="删除">✕</button>
        </div>
    `;
}

// 更新文件类型
function updateDSMCFileType(fileId, newType) {
    const fileData = uploadedDSMCFiles.find(f => f.id === fileId);
    if (fileData) {
        fileData.type = newType;
        fileData.zone = TYPE_ZONE_MAP[newType] || 'workspace';

        // 如果新zone是llm但还没有内容，需要读取
        if (fileData.zone === 'llm' && !fileData.content) {
            readDSMCFileContent(fileData.file).then(content => {
                fileData.content = content;
            });
        }

        updateFileZonesDisplay();
    }
}

// 删除文件
function removeDSMCFile(fileId) {
    uploadedDSMCFiles = uploadedDSMCFiles.filter(f => f.id !== fileId);
    updateFileZonesDisplay();
}

// 处理参数表单提交
async function handleParameterSubmit(e) {
    e.preventDefault();
    console.log('handleParameterSubmit 被调用');

    // 检查是否有活跃的对话
    if (!currentConversationId) {
        console.log('没有活跃对话，创建新对话...');
        await createNewConversation();
    }

    const formData = new FormData(e.target);

    // 收集基础参数
    currentDSMCParameters = {
        temperature: parseFloat(formData.get('temperature')),
        pressure: parseFloat(formData.get('pressure')),
        velocity: parseFloat(formData.get('velocity')),
        geometry: formData.get('geometry'),
        gas: formData.get('gas'),
        customInput: formData.get('customInput') || ''
    };

    // 收集高级参数（边界条件）
    currentDSMCParameters.boundary = {
        inletType: formData.get('inletType') || 'freestream',
        outletType: formData.get('outletType') || 'outflow',
        wallCondition: formData.get('wallCondition') || 'diffuse',
        wallTemp: parseFloat(formData.get('wallTemp')) || 300
    };

    // 收集高级参数（时间与网格）
    currentDSMCParameters.timeGrid = {
        timestep: formData.get('timestep') || '1e-7',
        simTime: formData.get('simTime') || '1e-4',
        gridResolution: formData.get('gridResolution') || 'medium',
        gridSize: formData.get('gridSize') || '0.01'
    };

    // 收集高级参数（碰撞与粒子）
    currentDSMCParameters.collision = {
        collisionModel: formData.get('collisionModel') || 'vhs',
        fnum: formData.get('fnum') || '1e10',
        nparticles: parseInt(formData.get('nparticles')) || 10000
    };

    // 收集高级参数（输出控制）
    const outputVars = formData.getAll('outputVars');
    currentDSMCParameters.output = {
        dumpFreq: parseInt(formData.get('dumpFreq')) || 100,
        statsStart: parseInt(formData.get('statsStart')) || 500,
        outputVars: outputVars.length > 0 ? outputVars : ['density', 'velocity', 'temperature', 'pressure']
    };

    // 收集LLM参考文件
    const llmFiles = uploadedDSMCFiles
        .filter(f => f.zone === 'llm')
        .map(f => ({
            filename: f.filename,
            type: f.type,
            content: f.content
        }));

    // 收集工作目录文件（需要单独上传到后端）
    const workspaceFiles = uploadedDSMCFiles
        .filter(f => f.zone === 'workspace')
        .map(f => ({
            filename: f.filename,
            type: f.type,
            file: f.file
        }));

    // 禁用表单
    e.target.querySelectorAll('input, select, button, textarea').forEach(el => el.disabled = true);

    // 立即创建 pending 状态的 v1 标签页
    const pendingIterationId = 'pending_' + Date.now();
    const pendingIteration = {
        iteration_id: pendingIterationId,
        iteration_number: 1,
        modification_description: '初始版本',
        status: 'pending',
        timestamp: null
    };
    currentIterations = [pendingIteration];
    activeIterationId = pendingIterationId;
    renderIterationTabs(currentIterations);

    // 更新过程追踪（状态条已取消，使用菜单栏追踪）
    updateProcessTracker(PROCESS_STEPS.GENERATING);

    try {
        // 如果有工作目录文件，先上传它们
        let uploadedWorkspaceFiles = [];
        if (workspaceFiles.length > 0) {
            showStatus('正在上传仿真文件...');
            for (const wf of workspaceFiles) {
                const uploadFormData = new FormData();
                uploadFormData.append('file', wf.file);
                uploadFormData.append('type', wf.type);
                uploadFormData.append('zone', 'workspace');

                try {
                    const uploadRes = await fetch('/api/dsmc/upload', {
                        method: 'POST',
                        body: uploadFormData
                    });
                    if (uploadRes.ok) {
                        const uploadResult = await uploadRes.json();
                        uploadedWorkspaceFiles.push(uploadResult);
                    }
                } catch (uploadErr) {
                    console.error('文件上传失败:', wf.filename, uploadErr);
                }
            }
        }

        const response = await fetch('/api/dsmc/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                parameters: currentDSMCParameters,
                llm_files: llmFiles,
                workspace_files: uploadedWorkspaceFiles
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let inputFileData = null;
        let buffer = ''; // 缓冲区用于处理跨chunk的行

        console.log('开始接收流式响应...');

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                console.log('流式响应结束');
                break;
            }

            // 将新数据追加到缓冲区
            buffer += decoder.decode(value, { stream: true });

            // 按行分割（保留未完成的行在缓冲区）
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // 保留最后一个未完成的行

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6).trim();
                        if (!jsonStr) continue;

                        const data = JSON.parse(jsonStr);
                        console.log('收到事件:', data.type);

                        if (data.type === 'status') {
                            showStatus(data.message);
                        } else if (data.type === 'done') {
                            console.log('收到done事件，结果大小:', JSON.stringify(data.result).length);
                            hideStatus();
                            inputFileData = data.result;
                        } else if (data.type === 'error') {
                            console.error('收到错误:', data.error);
                            hideStatus();
                            alert('生成失败: ' + data.error);
                            return;
                        }
                    } catch (e) {
                        console.error('JSON解析错误:', e, '行内容:', line.slice(0, 100));
                    }
                }
            }
        }

        // 处理缓冲区中剩余的数据
        if (buffer.startsWith('data: ')) {
            try {
                const jsonStr = buffer.slice(6).trim();
                if (jsonStr) {
                    const data = JSON.parse(jsonStr);
                    console.log('处理缓冲区事件:', data.type);
                    if (data.type === 'done') {
                        inputFileData = data.result;
                    }
                }
            } catch (e) {
                console.error('缓冲区JSON解析错误:', e);
            }
        }

        if (inputFileData) {
            console.log('显示输入文件，session_id:', inputFileData.session_id);
            displayInputFile(inputFileData);
            completeProcessTracker();
        } else {
            console.error('未收到输入文件数据');
            hideStatus();
            resetProcessTracker();
            alert('生成失败: 未收到完整数据');
        }

    } catch (error) {
        console.error('生成失败:', error);
        hideStatus();
        resetProcessTracker();
        alert('生成失败: ' + error.message);
    }
}

// 显示输入文件预览
function displayInputFile(data) {
    const { input_file, annotations, parameter_reasoning, warnings, session_id, timing } = data;

    // 保存session ID
    dsmcSession = session_id;

    // 使用带语法高亮的代码生成
    const codeHTML = generateHighlightedCodeLines(input_file || '', annotations || {});

    let warningsHTML = '';
    if (warnings && warnings.length > 0) {
        warningsHTML = `
            <div class="warnings">
                <h4>⚠️ 警告</h4>
                ${warnings.map(w => `<p>• ${escapeHtml(w)}</p>`).join('')}
            </div>
        `;
    }

    // 生成时间信息 - 显示到控制面板
    if (timing) {
        updateTimingInfo(timing);
    }

    const previewHTML = `
        <div class="dsmc-input-preview">
            <div class="input-header">
                <h3>📄 SPARTA输入文件预览</h3>
            </div>
            <div class="input-content">
                ${codeHTML}
            </div>
            ${parameter_reasoning ? `
                <div class="parameter-reasoning">
                    <h4>📊 参数选择依据</h4>
                    <div class="reasoning-content">${renderMarkdown(parameter_reasoning)}</div>
                </div>
            ` : ''}
            ${warningsHTML}
        </div>
    `;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">${previewHTML}</div>
            <div class="message-meta"><span>${new Date().toLocaleTimeString()}</span></div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);

    // 渲染Markdown中的数学公式和代码高亮
    renderMathAndCode();

    // 显示固定的运行控制面板
    showDSMCRunPanel();

    scrollToBottom();

    // 强制样式重计算，确保首次显示时代码高亮生效
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            forceStyleRecalculation();
        });
    });

    // 加载真实的迭代列表，替换临时的 pending 标签页
    if (session_id) {
        loadIterations(session_id, true);
    }
}

// 生成统一的文件名前缀: {session}_{版本号}_{时间（精确到分钟）}
function generateFileNamePrefix() {
    const versionNum = getCurrentIterationNumber();
    const now = new Date();
    // 格式: YYYYMMDDHHMM
    const timeStr = now.getFullYear().toString() +
        String(now.getMonth() + 1).padStart(2, '0') +
        String(now.getDate()).padStart(2, '0') +
        String(now.getHours()).padStart(2, '0') +
        String(now.getMinutes()).padStart(2, '0');
    return `${dsmcSession}_v${versionNum}_${timeStr}`;
}

// 下载输入文件
function downloadInputFile() {
    if (!dsmcSession) {
        alert('没有可下载的输入文件');
        return;
    }

    fetch(`/api/dsmc/sessions/${dsmcSession}`)
        .then(res => res.json())
        .then(data => {
            const blob = new Blob([data.input_file], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${generateFileNamePrefix()}_input.sparta`;
            a.click();
            URL.revokeObjectURL(url);
        })
        .catch(error => {
            alert('下载失败: ' + error.message);
        });
}

// 运行SPARTA模拟
async function runSimulation() {
    if (!dsmcSession) {
        alert('没有可运行的会话');
        return;
    }

    // 从固定面板获取运行参数
    const numCores = parseInt(document.getElementById('panelNumCores')?.value) || 4;
    const maxSteps = parseInt(document.getElementById('panelMaxSteps')?.value) || 1000;
    const maxMemoryGB = parseFloat(document.getElementById('panelMaxMemory')?.value) || null;
    const maxFixAttempts = parseInt(document.getElementById('panelMaxFixAttempts')?.value) || 3;

    let confirmMsg = `确定要运行SPARTA仿真吗？\n\nCPU核数: ${numCores}\n最大步数: ${maxSteps}\n最大修复次数: ${maxFixAttempts}`;
    if (maxMemoryGB) {
        confirmMsg += `\n内存限制: ${maxMemoryGB} GB`;
    }
    confirmMsg += '\n\n这可能需要几分钟时间。';

    if (!confirm(confirmMsg)) {
        return;
    }

    // 隐藏运行面板
    hideDSMCRunPanel();
    showStatus('正在运行SPARTA仿真...');
    updateProcessTracker(PROCESS_STEPS.RUNNING);

    try {
        const requestBody = {
            session_id: dsmcSession,
            num_cores: numCores,
            max_steps: maxSteps,
            max_fix_attempts: maxFixAttempts
        };
        if (maxMemoryGB) {
            requestBody.max_memory_gb = maxMemoryGB;
        }

        const response = await fetch('/api/dsmc/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let resultData = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'status') {
                            showStatus(data.message);
                            // 解析进度信息（如果消息包含步数）
                            const stepMatch = data.message.match(/Step[:\s]*(\d+)/i);
                            if (stepMatch) {
                                const currentStep = parseInt(stepMatch[1]);
                                const totalSteps = parseInt(document.getElementById('panelMaxSteps')?.value) || 1000;
                                updateHeaderProgress(currentStep, totalSteps, true);
                            } else if (data.message.includes('运行') || data.message.includes('仿真')) {
                                // 开始运行时显示初始进度
                                const totalSteps = parseInt(document.getElementById('panelMaxSteps')?.value) || 1000;
                                updateHeaderProgress(0, totalSteps, true);
                            }
                        } else if (data.type === 'done') {
                            hideStatus();
                            hideHeaderProgress();
                            resultData = data.result;
                            console.log('Received done event, resultData:', resultData);
                        } else if (data.type === 'error') {
                            hideStatus();
                            hideHeaderProgress();
                            alert('运行失败: ' + data.error);
                            return;
                        }
                    } catch (e) {
                        console.error('解析错误:', e);
                    }
                }
            }
        }

        console.log('Stream finished, resultData exists:', !!resultData);
        if (resultData) {
            updateProcessTracker(PROCESS_STEPS.PROCESSING);
            displaySimulationResults(resultData);
            // 刷新迭代列表以更新标签页状态（从 pending 变为 completed）
            if (dsmcSession) {
                await loadIterations(dsmcSession, false);  // false = 不自动切换迭代
            }
            completeProcessTracker();
        } else {
            console.error('No resultData received from stream');
            resetProcessTracker();
        }

    } catch (error) {
        hideStatus();
        resetProcessTracker();
        alert('运行失败: ' + error.message);
    }
}

// 显示仿真结果
function displaySimulationResults(result) {
    console.log('displaySimulationResults called with:', result);
    updateProcessTracker(PROCESS_STEPS.VISUALIZING);
    const { summary, plots, interpretation, suggestions } = result;

    let summaryHTML = '';
    if (summary) {
        console.log('Summary:', summary);
        summaryHTML = `
            <div class="result-summary">
                <h4>📈 仿真摘要</h4>
                ${Object.entries(summary).map(([key, value]) =>
                    `<p><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</p>`
                ).join('')}
            </div>
        `;
    }

    let plotsHTML = '';
    if (plots && plots.length > 0) {
        console.log('Plots count:', plots.length);
        console.log('First plot image_url:', plots[0]?.image_url || 'N/A');
        plotsHTML = `
            <div class="result-plots">
                <h4>📊 可视化图表</h4>
                ${plots.map(plot => {
                    const imageSrc = `/api/dsmc/sessions/${dsmcSession}/files/${plot.image_url}`;
                    return `
                    <div class="result-plot">
                        <h5>${escapeHtml(plot.title)}</h5>
                        <img src="${imageSrc}" alt="${escapeHtml(plot.title)}" onerror="console.error('Image load error:', this.src)">
                    </div>
                    `;
                }).join('')}
            </div>
        `;
    } else {
        console.log('No plots available');
    }

    let interpretationHTML = '';
    if (interpretation) {
        interpretationHTML = `
            <div class="result-interpretation">
                <h4>🤖 LLM分析</h4>
                ${renderMarkdown(interpretation)}
            </div>
        `;
    }

    let suggestionsHTML = '';
    if (suggestions && suggestions.length > 0) {
        suggestionsHTML = `
            <div class="iteration-panel">
                <h4>💡 优化建议</h4>
                ${suggestions.map(s => `
                    <div class="suggestion-item">
                        <strong>${escapeHtml(s.parameter)}</strong>:
                        ${escapeHtml(s.current)} → ${escapeHtml(s.suggested)}
                        <div class="reason">${escapeHtml(s.reason)}</div>
                    </div>
                `).join('')}
                <button onclick="iterateParameters()" style="margin-top: 15px;">🔄 重新配置参数</button>
            </div>
        `;
    }

    const resultsHTML = `
        <div class="dsmc-results">
            <h3>✅ DSMC仿真完成</h3>
            ${summaryHTML}
            ${plotsHTML}
            ${interpretationHTML}
            ${suggestionsHTML}
        </div>
    `;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">${resultsHTML}</div>
            <div class="message-meta"><span>${new Date().toLocaleTimeString()}</span></div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    renderMathAndCode();
}

// 迭代参数（显示新的参数表单）
function iterateParameters() {
    hideDSMCIndicator();
    hideDSMCRunPanel();
    dsmcSession = null;
    displayParameterForm();
}

// ==================== 文件监控功能 ====================

// 监控相关变量
let monitorInterval = null;
let logMonitorInterval = null;
let isMonitoring = false;

// 显示监控面板（使用合并后的控制面板）
function showMonitorPanel() {
    showDSMCControlPanel();
}

// 隐藏监控面板
function hideMonitorPanel() {
    // 监控功能已整合到控制面板，不再单独隐藏
    stopMonitoring();
}

// 开始监控
function startMonitoring(sessionId) {
    if (!sessionId) return;

    isMonitoring = true;
    showDSMCControlPanel();

    // 立即执行一次
    refreshMonitor();
    refreshLog();

    // 设置定时刷新（文件列表每30秒，日志每10秒）
    monitorInterval = setInterval(refreshMonitor, 30000);
    logMonitorInterval = setInterval(refreshLog, 10000);
}

// 停止监控
function stopMonitoring() {
    isMonitoring = false;
    if (monitorInterval) {
        clearInterval(monitorInterval);
        monitorInterval = null;
    }
    if (logMonitorInterval) {
        clearInterval(logMonitorInterval);
        logMonitorInterval = null;
    }
}

// ==================== 版本管理器集成 ====================

// 初始化版本管理器
function initializeVersionManager(sessionId) {
    if (!sessionId) return;

    currentSessionId = sessionId;

    if (!versionManager) {
        // 首次创建
        if (typeof VersionManager !== 'undefined') {
            versionManager = new VersionManager(sessionId);
            const initialized = versionManager.init('versionHistoryList');
            if (initialized) {
                console.log('✅ VersionManager initialized for session:', sessionId);
            }
        } else {
            console.warn('VersionManager not loaded');
        }
    } else {
        // 更新现有实例
        versionManager.sessionId = sessionId;
        versionManager.loadIterations();
    }

    // 更新版本计数
    updateVersionCount();
}

// 更新版本计数徽章
async function updateVersionCount() {
    const versionCountEl = document.getElementById('versionCount');
    if (!versionCountEl) return;

    if (!versionManager || !versionManager.iterations) {
        versionCountEl.textContent = '0';
        return;
    }

    versionCountEl.textContent = versionManager.iterations.length;
}

// 当新迭代开始时更新
function onNewIterationStarted(sessionId, iterationId) {
    console.log('New iteration started:', iterationId);
    if (versionManager && versionManager.sessionId === sessionId) {
        versionManager.loadIterations();
    }
}

// 当迭代完成时更新
function onIterationComplete(sessionId, iterationId, status) {
    console.log('Iteration completed:', iterationId, status);
    if (versionManager && versionManager.sessionId === sessionId) {
        versionManager.loadIterations();
    }
}

// ==================== Server-Sent Events (SSE) 实时更新 ====================

// 连接SSE
function connectSSE(sessionId) {
    // 关闭现有连接
    if (sseConnection) {
        sseConnection.close();
    }

    // 创建新的EventSource连接
    sseConnection = new EventSource(`/api/dsmc/sessions/${sessionId}/events`);

    sseConnection.onopen = () => {
        console.log('SSE connection opened');
        updateProcessTracker('已连接', 'connected');
    };

    sseConnection.onmessage = (e) => {
        const message = JSON.parse(e.data);
        handleSSEMessage(message);
    };

    sseConnection.onerror = (error) => {
        console.error('SSE error:', error);
        updateProcessTracker('连接错误', 'error');

        // 尝试在5秒后重新连接
        setTimeout(() => {
            if (currentSessionId) {
                console.log('Attempting SSE reconnect...');
                connectSSE(currentSessionId);
            }
        }, 5000);
    };
}

// 断开SSE连接
function disconnectSSE() {
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
        console.log('SSE connection closed');
    }
}

// 处理SSE消息
function handleSSEMessage(message) {
    const { type, data } = message;

    console.log('SSE message received:', type, data);

    switch (type) {
        case 'connected':
            console.log('SSE connected:', data);
            break;

        case 'heartbeat':
            // 心跳 - 保持连接活跃
            break;

        case 'simulation_started':
            console.log('Simulation started:', data);
            updateProcessTracker('仿真运行中', 'running');
            if (data.max_steps) {
                updateHeaderProgress(0, data.max_steps);
            }
            break;

        case 'progress_update':
            console.log('Progress update:', data);
            const { current_step, total_steps, percentage } = data;
            if (current_step && total_steps) {
                updateHeaderProgress(current_step, total_steps);
            }
            if (percentage !== undefined) {
                updateProcessTracker(`运行中 ${percentage.toFixed(1)}%`, 'running');
            }
            break;

        case 'simulation_completed':
            console.log('Simulation completed:', data);
            updateProcessTracker('已完成', 'completed');
            if (data.total_time) {
                updateHeaderProgress(data.total_steps || 1000, data.total_steps || 1000);
            }

            // 重新加载版本管理器以显示新迭代
            if (versionManager) {
                versionManager.loadIterations();
            }

            // 显示完成通知
            if (data.total_time) {
                showNotification('仿真完成', `总时间: ${data.total_time.toFixed(2)}s`, 'success');
            } else {
                showNotification('仿真完成', '仿真已成功完成', 'success');
            }
            break;

        case 'simulation_failed':
            console.log('Simulation failed:', data);
            updateProcessTracker('失败', 'failed');

            // 重新加载版本管理器
            if (versionManager) {
                versionManager.loadIterations();
            }

            // 显示错误通知
            showNotification('仿真失败', data.error || '未知错误', 'error');
            break;

        case 'iteration_updated':
            console.log('Iteration updated:', data);

            // 重新加载版本管理器
            if (versionManager) {
                versionManager.loadIterations();
            }
            break;

        default:
            console.warn('Unknown SSE message type:', type);
    }
}

// 更新头部进度指示器
function updateHeaderProgress(current, total) {
    const progressEl = document.getElementById('headerSimProgress');
    const progressText = document.getElementById('progressText');
    const progressIcon = document.getElementById('progressIcon');

    if (!progressEl || !progressText || !progressIcon) return;

    if (current >= total) {
        progressEl.classList.add('hidden');
    } else {
        progressEl.classList.remove('hidden');
        progressText.textContent = `${current}/${total}`;

        // 动画图标
        progressIcon.textContent = current % 200 === 0 ? '⌛' : '⏳';
    }
}

// 显示通知
function showNotification(title, message, type = 'info') {
    // 简单的toast通知
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<strong>${title}</strong><p>${message}</p>`;
    toast.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 16px 20px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        min-width: 300px;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// 当DSMC生成完成时调用
function onDSMCGenerationComplete(sessionId) {
    currentSessionId = sessionId;

    // 初始化版本管理器
    initializeVersionManager(sessionId);

    // 连接SSE进行实时更新
    connectSSE(sessionId);

    // 显示控制面板
    showDSMCControlPanel();

    // 开始监控
    startMonitoring(sessionId);
}


// 刷新监控数据
async function refreshMonitor() {
    if (!dsmcSession) return;

    try {
        const response = await fetch(`/api/dsmc/monitor/${dsmcSession}`);
        const data = await response.json();

        if (data.error) {
            console.log('监控数据获取失败:', data.error);
            return;
        }

        // 更新工作目录
        const workdirInput = document.getElementById('workdirInput');
        if (workdirInput) {
            workdirInput.value = data.session_dir || '';
        }

        // 更新文件总数
        const totalFilesCount = document.getElementById('totalFilesCount');
        if (totalFilesCount) {
            totalFilesCount.textContent = data.total_files || 0;
        }

        // 更新文件列表
        updateFileList(data.files || []);

    } catch (error) {
        console.error('刷新监控数据失败:', error);
    }
}

// 更新文件列表
function updateFileList(files) {
    const container = document.getElementById('fileListContainer');
    if (!container) return;

    if (files.length === 0) {
        container.innerHTML = '<div class="empty-message">暂无文件</div>';
        return;
    }

    container.innerHTML = files.map(file => `
        <div class="file-item" onclick="viewFile('${escapeHtml(file.name)}')" title="${escapeHtml(file.name)}">
            <span class="file-icon">${getFileIcon(file.type)}</span>
            <span class="file-name">${escapeHtml(file.name)}</span>
            <span class="file-size">${formatFileSize(file.size)}</span>
        </div>
    `).join('');
}

// 刷新日志
async function refreshLog() {
    if (!dsmcSession) return;

    try {
        const response = await fetch(`/api/dsmc/monitor/${dsmcSession}/log?lines=100`);
        const data = await response.json();

        const logContent = document.getElementById('logContent');
        const logLineCount = document.getElementById('logLineCount');
        const logFileSize = document.getElementById('logFileSize');
        const logLastUpdate = document.getElementById('logLastUpdate');
        const autoScrollToggle = document.getElementById('autoScrollToggle');
        const logContainer = document.getElementById('logContainer');

        if (data.error && !data.content) {
            if (logContent) logContent.textContent = data.error || '等待仿真运行...';
            return;
        }

        // 更新日志内容
        if (logContent) {
            logContent.textContent = data.content || '(空日志)';
        }

        // 更新统计信息
        if (logLineCount) {
            logLineCount.textContent = `${data.line_count || 0} 行`;
        }
        if (logFileSize) {
            logFileSize.textContent = formatFileSize(data.file_size || 0);
        }
        if (logLastUpdate) {
            const modified = data.modified ? new Date(data.modified).toLocaleTimeString() : '-';
            logLastUpdate.textContent = `更新: ${modified}`;
        }

        // 自动滚动到底部
        if (autoScrollToggle && autoScrollToggle.checked && logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }

    } catch (error) {
        console.error('刷新日志失败:', error);
    }
}

// 复制工作目录
function copyWorkdir() {
    const workdirInput = document.getElementById('workdirInput');
    if (workdirInput && workdirInput.value) {
        navigator.clipboard.writeText(workdirInput.value).then(() => {
            // 显示复制成功提示
            const btn = document.querySelector('.workdir-container .btn-icon-small:last-child');
            if (btn) {
                const originalText = btn.textContent;
                btn.textContent = '✓';
                setTimeout(() => { btn.textContent = originalText; }, 1000);
            }
        }).catch(err => {
            console.error('复制失败:', err);
        });
    }
}

// 查看文件内容
async function viewFile(filename) {
    if (!dsmcSession) return;

    try {
        const response = await fetch(`/api/dsmc/sessions/${dsmcSession}/files/${encodeURIComponent(filename)}`);
        const data = await response.json();

        if (data.error) {
            alert('无法读取文件: ' + data.error);
            return;
        }

        // 创建模态框显示文件内容
        const modal = document.createElement('div');
        modal.className = 'file-modal';
        modal.innerHTML = `
            <div class="file-modal-content">
                <div class="file-modal-header">
                    <h3>${escapeHtml(filename)}</h3>
                    <span class="file-modal-size">${formatFileSize(data.file_size)}</span>
                    <button class="modal-close-btn" onclick="this.closest('.file-modal').remove()">×</button>
                </div>
                <pre class="file-modal-body">${escapeHtml(data.content)}</pre>
            </div>
        `;
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
        document.body.appendChild(modal);

    } catch (error) {
        alert('读取文件失败: ' + error.message);
    }
}

// 获取文件图标
function getFileIcon(type) {
    const icons = {
        '.sparta': '📝',
        '.dat': '📊',
        '.dump': '📦',
        '.log': '📜',
        '.grid': '🔲',
        '.json': '📋',
        '.txt': '📄',
        '.png': '🖼️',
        '.jpg': '🖼️',
        '.jpeg': '🖼️'
    };
    return icons[type] || '📄';
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// 覆盖原有的runSimulation函数以启动监控
const originalRunSimulation = runSimulation;
runSimulation = async function() {
    // 开始监控
    if (dsmcSession) {
        startMonitoring(dsmcSession);
    }

    if (!dsmcSession) {
        alert('没有可运行的会话');
        return;
    }

    // 从固定面板获取运行参数
    const numCores = parseInt(document.getElementById('panelNumCores')?.value) || 4;
    const maxSteps = parseInt(document.getElementById('panelMaxSteps')?.value) || 1000;
    const maxMemoryGB = parseFloat(document.getElementById('panelMaxMemory')?.value) || null;

    let confirmMsg = `确定要运行SPARTA仿真吗？\n\nCPU核数: ${numCores}\n最大步数: ${maxSteps}`;
    if (maxMemoryGB) {
        confirmMsg += `\n内存限制: ${maxMemoryGB} GB`;
    }
    confirmMsg += '\n\n这可能需要几分钟时间。';

    if (!confirm(confirmMsg)) {
        return;
    }

    // 显示停止按钮，隐藏运行按钮
    showStopButton();

    // 不隐藏运行面板，保持可见
    showStatus('正在运行SPARTA仿真...');
    updateProcessTracker(PROCESS_STEPS.RUNNING);

    try {
        const requestBody = {
            session_id: dsmcSession,
            conversation_id: currentConversationId,  // 添加对话ID以保存结果到历史
            num_cores: numCores,
            max_steps: maxSteps
        };
        if (maxMemoryGB) {
            requestBody.max_memory_gb = maxMemoryGB;
        }

        const response = await fetch('/api/dsmc/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let resultData = null;
        let buffer = ''; // 缓冲区用于处理跨chunk的行
        let updatedInputFile = null; // 保存更新后的输入文件

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                console.log('流式响应结束');
                break;
            }

            // 将新数据追加到缓冲区
            buffer += decoder.decode(value, { stream: true });

            // 按行分割（保留未完成的行在缓冲区）
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // 保留最后一个未完成的行

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6).trim();
                        if (!jsonStr) continue;

                        const data = JSON.parse(jsonStr);
                        console.log('收到事件:', data.type);

                        if (data.type === 'status') {
                            showStatus(data.message);
                        } else if (data.type === 'fix_applied') {
                            // 输入文件已修复，保存更新后的内容
                            showStatus(data.message || '已应用修复');
                            if (data.input_file) {
                                updatedInputFile = data.input_file;
                                console.log('收到更新后的输入文件，版本:', data.version);
                            }
                        } else if (data.type === 'done') {
                            hideStatus();
                            resultData = data.result;
                            console.log('Received done event, resultData:', resultData);
                        } else if (data.type === 'error') {
                            hideStatus();
                            showRunButton();
                            alert('运行失败: ' + data.error);
                            return;
                        }
                    } catch (e) {
                        console.error('JSON解析错误:', e, '行内容:', line.slice(0, 100));
                    }
                }
            }
        }

        // 处理缓冲区中剩余的数据
        if (buffer.startsWith('data: ')) {
            try {
                const jsonStr = buffer.slice(6).trim();
                if (jsonStr) {
                    const data = JSON.parse(jsonStr);
                    console.log('处理缓冲区事件:', data.type);
                    if (data.type === 'done') {
                        resultData = data.result;
                    }
                }
            } catch (e) {
                console.error('缓冲区JSON解析错误:', e);
            }
        }

        console.log('Stream finished, resultData exists:', !!resultData);
        if (resultData) {
            updateProcessTracker(PROCESS_STEPS.PROCESSING);
            // 如果有更新的输入文件，先显示它
            if (updatedInputFile) {
                displayUpdatedInputFile(updatedInputFile);
            }
            displaySimulationResults(resultData);
            showRunButton();
            completeProcessTracker();
        } else {
            console.error('No resultData received from stream');
            showRunButton();
            resetProcessTracker();
        }

    } catch (error) {
        hideStatus();
        showRunButton();
        resetProcessTracker();
        alert('运行失败: ' + error.message);
    }
};

// 显示更新后的输入文件
function displayUpdatedInputFile(inputFile) {
    // 创建一个消息显示更新后的输入文件
    const lines = inputFile.split('\n');
    let codeHTML = '';
    lines.forEach((line, index) => {
        const lineNum = index + 1;
        codeHTML += `
            <div class="code-line">
                <span class="line-number">${lineNum}</span>
                <span class="sparta-code">${escapeHtml(line)}</span>
            </div>
        `;
    });

    const previewHTML = `
        <div class="dsmc-input-preview updated-input">
            <div class="input-header">
                <h3>🔄 更新后的SPARTA输入文件</h3>
                <span class="update-badge">已自动修复</span>
            </div>
            <div class="input-content">
                ${codeHTML}
            </div>
        </div>
    `;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">${previewHTML}</div>
            <div class="message-meta"><span>${new Date().toLocaleTimeString()}</span></div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ==================== SPARTA语法高亮 ====================

function highlightSpartaCode(code) {
    const lines = code.split('\n');
    return lines.map((line, index) => {
        const lineNum = index + 1;
        let highlightedLine = escapeHtml(line);

        // 注释高亮 (# 开头)
        if (line.trim().startsWith('#')) {
            highlightedLine = `<span class="sparta-comment">${highlightedLine}</span>`;
        } else {
            // 命令关键字高亮
            const commands = [
                'dimension', 'boundary', 'create_box', 'create_grid',
                'balance_grid', 'species', 'mixture', 'global',
                'collide', 'fix', 'compute', 'stats', 'stats_style',
                'dump', 'run', 'surf_collide', 'surf_react', 'read_surf',
                'timestep', 'variable', 'units', 'seed', 'region',
                'surf_modify', 'react', 'bound_modify', 'adapt_grid'
            ];

            commands.forEach(cmd => {
                const regex = new RegExp(`\\b(${cmd})\\b`, 'g');
                highlightedLine = highlightedLine.replace(
                    regex,
                    '<span class="sparta-keyword">$1</span>'
                );
            });

            // 数值高亮
            highlightedLine = highlightedLine.replace(
                /\b(\d+\.?\d*(?:[eE][+-]?\d+)?)\b/g,
                '<span class="sparta-number">$1</span>'
            );
        }

        return highlightedLine;
    }).join('\n');
}

// 生成带语法高亮的代码行HTML
function generateHighlightedCodeLines(code, annotations = {}) {
    const lines = code.split('\n');
    return lines.map((line, index) => {
        const lineNum = index + 1;
        let highlightedLine = escapeHtml(line);

        // 注释高亮
        if (line.trim().startsWith('#')) {
            highlightedLine = `<span class="sparta-comment">${highlightedLine}</span>`;
        } else {
            // 关键字高亮
            const commands = [
                'dimension', 'boundary', 'create_box', 'create_grid',
                'balance_grid', 'species', 'mixture', 'global',
                'collide', 'fix', 'compute', 'stats', 'stats_style',
                'dump', 'run', 'surf_collide', 'surf_react', 'read_surf',
                'timestep', 'variable', 'units', 'seed', 'region'
            ];
            commands.forEach(cmd => {
                const regex = new RegExp(`\\b(${cmd})\\b`, 'g');
                highlightedLine = highlightedLine.replace(regex, '<span class="sparta-keyword">$1</span>');
            });
            // 数值高亮
            highlightedLine = highlightedLine.replace(/\b(\d+\.?\d*(?:[eE][+-]?\d+)?)\b/g, '<span class="sparta-number">$1</span>');
        }

        const annotation = annotations[lineNum] || annotations[String(lineNum)] || '';

        return `
            <div class="code-line">
                <span class="line-number">${lineNum}</span>
                <span class="sparta-code">${highlightedLine}</span>
                ${annotation ? `<span class="annotation">${escapeHtml(annotation)}</span>` : ''}
            </div>
        `;
    }).join('');
}

// 强制浏览器重新计算样式，解决首次渲染时代码高亮不显示的问题
function forceStyleRecalculation() {
    const codeElements = document.querySelectorAll('.sparta-code, .sparta-keyword, .sparta-comment, .sparta-number');
    codeElements.forEach(el => {
        // 读取元素的offsetHeight会触发浏览器重排
        void el.offsetHeight;
    });
}

// ==================== 迭代标签管理 ====================

async function loadIterations(sessionId, autoSwitchToLatest = true) {
    try {
        const response = await fetch(`/api/dsmc/sessions/${sessionId}/iterations`);
        if (response.ok) {
            const data = await response.json();
            const newIterations = data.iterations || [];
            const statistics = data.statistics || {};

            // 【Bug修复】检测新增的迭代，清除其缓存确保重新加载
            const existingIds = new Set(currentIterations.map(i => i.iteration_id));
            newIterations.forEach(iter => {
                if (!existingIds.has(iter.iteration_id)) {
                    // 新增的迭代，清除其缓存（如果有）
                    delete iterationMessages[iter.iteration_id];
                    console.log('清除新迭代缓存:', iter.iteration_id);
                }
            });

            // 【Bug修复】对于已存在的迭代，如果input_file发生变化也要清除缓存
            newIterations.forEach(newIter => {
                const oldIter = currentIterations.find(i => i.iteration_id === newIter.iteration_id);
                if (oldIter && oldIter.input_file !== newIter.input_file) {
                    delete iterationMessages[newIter.iteration_id];
                    console.log('清除已更新迭代缓存:', newIter.iteration_id);
                }
            });

            currentIterations = newIterations;

            // 如果需要自动切换且有迭代记录
            if (autoSwitchToLatest && currentIterations.length > 0) {
                activeIterationId = currentIterations[currentIterations.length - 1].iteration_id;
            }

            renderIterationTabs(currentIterations);
            updateTimingStats(statistics);

            // 返回最新的迭代ID
            return currentIterations.length > 0
                ? currentIterations[currentIterations.length - 1].iteration_id
                : null;
        }
    } catch (error) {
        console.error('加载迭代列表失败:', error);
    }
    return null;
}

function renderIterationTabs(iterations) {
    const container = document.getElementById('iterationTabs');
    if (!container) return;

    if (iterations.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    container.innerHTML = iterations.map(iter => {
        const fullDesc = iter.modification_description || '初始版本';
        // 截断到8个字符，超过则添加省略号
        const shortDesc = fullDesc.length > 8 ? fullDesc.substring(0, 8) + '...' : fullDesc;
        // 移除pending状态判断，标签栏始终正常显示
        const tabClass = `iteration-tab ${iter.iteration_id === activeIterationId ? 'active' : ''}`;

        return `
        <div class="${tabClass}"
             data-iteration-id="${iter.iteration_id}"
             title="${escapeHtml(fullDesc)}">
            <div class="tab-content" onclick="switchIteration('${iter.iteration_id}')">
                <span class="tab-desc">${escapeHtml(shortDesc)}</span>
                <span class="tab-version">v${iter.iteration_number} · ${formatIterationTime(iter.timestamp)}</span>
            </div>
            <button class="tab-delete-btn" onclick="event.stopPropagation(); showDeleteIterationConfirm('${iter.iteration_id}', 'v${iter.iteration_number}')" title="删除此迭代">×</button>
        </div>
    `}).join('');
}

function formatIterationTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

async function switchIteration(iterationId) {
    activeIterationId = iterationId;
    renderIterationTabs(currentIterations);

    // 查找对应迭代
    const iteration = currentIterations.find(i => i.iteration_id === iterationId);
    if (iteration) {
        updateControlPanelForIteration(iteration);
        // 渲染该迭代的内容
        await renderIterationContent(iteration);
    }
}

// 渲染迭代内容到聊天区域
async function renderIterationContent(iteration) {
    const iterationId = iteration.iteration_id;

    // 隐藏欢迎消息
    welcomeMessage.style.display = 'none';

    // 【Bug修复】改进缓存有效性检查：确保缓存对应的input_file与当前一致
    const cachedMessages = iterationMessages[iterationId];
    const cachedInputFile = cachedMessages?._sourceInputFile;

    if (cachedMessages &&
        cachedMessages.length > 0 &&
        cachedInputFile === iteration.input_file) {
        renderIterationMessagesHTML(cachedMessages, iteration.iteration_number);
        return;
    }

    // 【Bug修复】如果iteration.input_file为空，尝试从后端重新获取完整数据
    if (!iteration.input_file && dsmcSession) {
        console.warn(`迭代 ${iterationId} 的input_file为空，尝试重新获取...`);
        try {
            const response = await fetch(`/api/dsmc/sessions/${dsmcSession}/iterations/${iterationId}`);
            if (response.ok) {
                const freshIteration = await response.json();
                if (freshIteration.input_file) {
                    iteration = freshIteration;
                    // 更新currentIterations中的记录
                    const idx = currentIterations.findIndex(i => i.iteration_id === iterationId);
                    if (idx !== -1) {
                        currentIterations[idx] = freshIteration;
                    }
                    console.log('成功获取完整迭代数据:', iterationId);
                }
            }
        } catch (e) {
            console.error('重新获取迭代数据失败:', e);
        }
    }

    // 构建该迭代的消息内容
    const messages = [];

    // 判断是否有修复历史
    const hasFixHistory = iteration.fix_history && iteration.fix_history.length > 0;
    const hasDifferentFinal = hasFixHistory &&
        iteration.initial_input_file &&
        iteration.initial_input_file !== iteration.input_file;

    // 1. 添加初始输入文件消息
    if (iteration.initial_input_file || iteration.input_file) {
        messages.push({
            type: 'input_file',
            content: iteration.initial_input_file || iteration.input_file,
            annotations: iteration.annotations || {},
            parameter_reasoning: iteration.parameter_reasoning,
            warnings: iteration.warnings,
            timestamp: iteration.timestamp,
            isInitial: true,
            isFinal: !hasDifferentFinal  // 如果没有修复，初始就是最终
        });
    }

    // 2. 如果有修复历史，显示修复摘要
    if (hasFixHistory) {
        messages.push({
            type: 'fix_summary',
            fixes: iteration.fix_history,
            timestamp: iteration.fix_history[iteration.fix_history.length - 1]?.timestamp
        });
    }

    // 3. 如果有修复后的最终版本（且与初始不同），显示成功版本
    if (hasDifferentFinal) {
        messages.push({
            type: 'input_file',
            content: iteration.input_file,
            annotations: {},
            timestamp: iteration.timestamp,
            isInitial: false,
            isFinal: true
        });
    }

    // 4. 添加仿真结果消息
    if (iteration.run_result && Object.keys(iteration.run_result).length > 0) {
        messages.push({
            type: 'simulation_result',
            content: iteration.run_result,
            timestamp: iteration.run_timestamp
        });
    }

    // 【Bug修复】记录缓存对应的源input_file，用于缓存失效判断
    messages._sourceInputFile = iteration.input_file;

    // 缓存并渲染
    iterationMessages[iterationId] = messages;
    renderIterationMessagesHTML(messages, iteration.iteration_number);
}

// 渲染迭代消息列表
function renderIterationMessagesHTML(messages, iterationNumber) {
    if (messages.length === 0) {
        // 新版本，显示空状态提示
        chatMessages.innerHTML = `
            <div class="empty-iteration-message">
                <h3>📄 版本 v${iterationNumber}</h3>
                <p>此版本尚无内容，请生成输入文件或运行仿真</p>
            </div>
        `;
        return;
    }

    chatMessages.innerHTML = messages.map(msg => {
        if (msg.type === 'input_file') {
            return createIterationInputFileHTML(msg, iterationNumber);
        } else if (msg.type === 'simulation_result') {
            return createIterationSimulationResultHTML(msg);
        } else if (msg.type === 'fix_summary') {
            return createFixSummaryHTML(msg);
        }
        return '';
    }).join('');

    // 渲染代码高亮和数学公式
    renderMathAndCode();
    scrollToBottom();
}

// 创建修复摘要HTML
function createFixSummaryHTML(msg) {
    const fixes = msg.fixes || [];
    const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN') : '';

    return `
        <div class="message assistant">
            <div class="message-time time-left"><span>${time}</span></div>
            <div class="message-content">
                <div class="message-text">
                    <div class="fix-summary">
                        <div class="fix-header">
                            <h4>🔧 自动修复记录 (共${fixes.length}次修复)</h4>
                        </div>
                        <div class="fix-list">
                            ${fixes.map((fix, idx) => `
                                <div class="fix-item">
                                    <span class="fix-number">修复 ${idx + 1}</span>
                                    <span class="fix-type">${escapeHtml(fix.error_type || '未知错误')}</span>
                                    <span class="fix-desc">${escapeHtml(fix.fix_description || '')}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 创建迭代输入文件HTML
function createIterationInputFileHTML(msg, iterationNumber) {
    const codeHTML = generateHighlightedCodeLines(msg.content, msg.annotations || {});
    const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN') : '';

    // 根据状态确定标题和样式
    let titleIcon = '📄';
    let titleText = 'SPARTA输入文件预览';
    let titleClass = '';

    if (msg.isInitial && !msg.isFinal) {
        // 初始版本（有修复历史时）
        titleIcon = '📄';
        titleText = '初始输入文件';
        titleClass = 'input-initial';
    } else if (msg.isFinal && !msg.isInitial) {
        // 成功运行版本（修复后）
        titleIcon = '✅';
        titleText = '成功运行版本';
        titleClass = 'input-success';
    } else if (msg.isInitial && msg.isFinal) {
        // 既是初始也是最终版本（无需修复）
        titleIcon = '📄';
        titleText = 'SPARTA输入文件';
        titleClass = '';
    }

    let warningsHTML = '';
    if (msg.warnings && msg.warnings.length > 0) {
        warningsHTML = `
            <div class="warnings">
                <h4>⚠️ 警告</h4>
                ${msg.warnings.map(w => `<p>• ${escapeHtml(w)}</p>`).join('')}
            </div>
        `;
    }

    return `
        <div class="message assistant">
            <div class="message-time time-left"><span>${time}</span></div>
            <div class="message-content">
                <div class="message-text">
                    <div class="dsmc-input-preview ${titleClass}">
                        <div class="input-header">
                            <h3>${titleIcon} ${titleText} (v${iterationNumber})</h3>
                        </div>
                        <div class="input-content">
                            ${codeHTML}
                        </div>
                        ${msg.parameter_reasoning ? `
                            <div class="parameter-reasoning">
                                <h4>📊 参数选择依据</h4>
                                <div class="reasoning-content">${renderMarkdown(msg.parameter_reasoning)}</div>
                            </div>
                        ` : ''}
                        ${warningsHTML}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 创建迭代仿真结果HTML
function createIterationSimulationResultHTML(msg) {
    const result = msg.content;
    const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN') : '';

    let summaryHTML = '';
    if (result.summary) {
        const entries = Object.entries(result.summary);
        summaryHTML = `
            <div class="result-summary">
                <h4>📊 仿真摘要</h4>
                <div class="summary-grid">
                    ${entries.map(([key, value]) => `
                        <div class="summary-item">
                            <span class="summary-label">${key}</span>
                            <span class="summary-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // 新增：渲染 plots
    let plotsHTML = '';
    if (result.plots && result.plots.length > 0) {
        plotsHTML = `
            <div class="result-plots">
                <h4>📈 可视化结果</h4>
                <div class="plots-grid">
                    ${result.plots.map(plot => {
                        const imageSrc = `/api/dsmc/sessions/${dsmcSession}/files/${plot.image_url}`;
                        return `
                        <div class="result-plot">
                            <h5>${escapeHtml(plot.title || '图表')}</h5>
                            <img src="${imageSrc}"
                                 alt="${escapeHtml(plot.title || '图表')}"
                                 class="plot-image"
                                 onclick="openPlotModal(this.src, '${escapeHtml(plot.title || '图表')}')">
                        </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    let interpretationHTML = '';
    if (result.interpretation) {
        interpretationHTML = `
            <div class="result-interpretation">
                <h4>🤖 LLM 分析</h4>
                <div class="interpretation-content">${renderMarkdown(result.interpretation)}</div>
            </div>
        `;
    }

    // 新增：渲染 suggestions
    let suggestionsHTML = '';
    if (result.suggestions && result.suggestions.length > 0) {
        suggestionsHTML = `
            <div class="result-suggestions">
                <h4>💡 优化建议</h4>
                <ul class="suggestions-list">
                    ${result.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    return `
        <div class="message assistant">
            <div class="message-time time-left"><span>${time}</span></div>
            <div class="message-content">
                <div class="message-text">
                    <div class="dsmc-simulation-results">
                        <div class="results-header">
                            <h3>🚀 SPARTA仿真结果</h3>
                        </div>
                        ${summaryHTML}
                        ${plotsHTML}
                        ${interpretationHTML}
                        ${suggestionsHTML}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function updateControlPanelForIteration(iteration) {
    // 更新运行参数
    const runParams = iteration.run_params || {};
    if (runParams.num_cores) {
        document.getElementById('panelNumCores').value = runParams.num_cores;
    }
    if (runParams.max_steps) {
        document.getElementById('panelMaxSteps').value = runParams.max_steps;
    }

    // 更新时间统计
    const timing = iteration.timing || {};
    document.getElementById('currentIterationTime').textContent = (timing.total_time || 0) + 's';
}

function updateTimingStats(statistics) {
    document.getElementById('totalTime').textContent = (statistics.total_time || 0) + 's';
    document.getElementById('iterationCount').textContent = statistics.total_iterations || 0;

    // 如果有当前迭代，更新当前迭代时间
    if (activeIterationId) {
        const currentIter = currentIterations.find(i => i.iteration_id === activeIterationId);
        if (currentIter && currentIter.timing) {
            document.getElementById('currentIterationTime').textContent = (currentIter.timing.total_time || 0) + 's';
        }
    }
}

// ==================== 编辑器功能 ====================

function toggleEditMode() {
    isEditMode = !isEditMode;
    const previewDivs = document.querySelectorAll('.input-content');
    const editorDivs = document.querySelectorAll('.input-editor');

    if (isEditMode) {
        // 进入编辑模式
        previewDivs.forEach(div => div.classList.add('hidden'));
        editorDivs.forEach(div => {
            div.classList.remove('hidden');
            const textarea = div.querySelector('.code-editor');
            if (textarea) {
                textarea.value = getCurrentInputFile();
            }
        });
    } else {
        // 退出编辑模式
        previewDivs.forEach(div => div.classList.remove('hidden'));
        editorDivs.forEach(div => div.classList.add('hidden'));
    }
}

function cancelEdit() {
    isEditMode = false;
    const previewDivs = document.querySelectorAll('.input-content');
    const editorDivs = document.querySelectorAll('.input-editor');

    previewDivs.forEach(div => div.classList.remove('hidden'));
    editorDivs.forEach(div => div.classList.add('hidden'));
}

async function saveAndRun() {
    const textarea = document.querySelector('.code-editor');
    if (!textarea) return;

    const newContent = textarea.value;
    if (!dsmcSession) {
        alert('没有活跃的DSMC会话');
        return;
    }

    try {
        showStatus('📝 保存修改并创建新迭代...');

        // 创建新迭代
        const response = await fetch(`/api/dsmc/sessions/${dsmcSession}/iterations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: 'manual_edit',
                description: '手动编辑',
                input_file: newContent
            })
        });

        if (response.ok) {
            const iteration = await response.json();
            console.log('创建新迭代:', iteration);

            // 刷新迭代列表
            await loadIterations(dsmcSession);

            // 退出编辑模式
            cancelEdit();

            // 运行仿真
            runSimulation();
        } else {
            const error = await response.json();
            alert('保存失败: ' + (error.error || '未知错误'));
        }
    } catch (error) {
        hideStatus();
        alert('保存失败: ' + error.message);
    }
}

function getCurrentInputFile() {
    // 优先从当前迭代获取输入文件
    if (activeIterationId && currentIterations.length > 0) {
        const iter = currentIterations.find(i => i.iteration_id === activeIterationId);
        if (iter && iter.input_file) {
            return iter.input_file;
        }
    }

    // 回退：从最后一个输入预览的DOM中提取文本
    const inputPreviews = document.querySelectorAll('.dsmc-input-preview');
    if (inputPreviews.length > 0) {
        const lastPreview = inputPreviews[inputPreviews.length - 1];
        const codeLines = lastPreview.querySelectorAll('.sparta-code');
        if (codeLines.length > 0) {
            return Array.from(codeLines).map(el => el.textContent).join('\n');
        }
    }

    return '';
}

// 获取当前活跃迭代的版本号
function getCurrentIterationNumber() {
    if (activeIterationId && currentIterations.length > 0) {
        const iter = currentIterations.find(i => i.iteration_id === activeIterationId);
        if (iter) {
            return iter.iteration_number;
        }
    }
    // 回退到最新迭代
    if (currentIterations.length > 0) {
        return currentIterations[currentIterations.length - 1].iteration_number;
    }
    return 1;
}

// ==================== 下载功能 ====================

async function downloadAllFiles() {
    if (!dsmcSession) {
        alert('没有可下载的文件');
        return;
    }

    try {
        const link = document.createElement('a');
        link.href = `/api/dsmc/sessions/${dsmcSession}/download/all`;
        link.download = `${generateFileNamePrefix()}_files.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        alert('下载失败: ' + error.message);
    }
}

async function downloadSingleFile(filename) {
    if (!dsmcSession) {
        alert('没有可下载的文件');
        return;
    }

    try {
        const link = document.createElement('a');
        link.href = `/api/dsmc/sessions/${dsmcSession}/files/${encodeURIComponent(filename)}/download`;
        link.download = `${generateFileNamePrefix()}_${filename}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        alert('下载失败: ' + error.message);
    }
}

// ==================== MD对话记录下载 ====================

// 辅助函数：格式化时间字符串
function formatTimeString(date) {
    return date.getFullYear().toString() +
        String(date.getMonth() + 1).padStart(2, '0') +
        String(date.getDate()).padStart(2, '0') +
        String(date.getHours()).padStart(2, '0') +
        String(date.getMinutes()).padStart(2, '0');
}

// 辅助函数：下载MD文件
function downloadMDFile(content, filename) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// 辅助函数：Base64转Blob
function base64ToBlob(base64, mimeType) {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
}

// 生成完整版本的MD内容
function generateVersionMD(iteration, versionNum, includeImageRefs = false) {
    const now = new Date();
    let mdContent = `# SPARTA DSMC - 版本 v${versionNum}\n\n`;
    mdContent += `**会话ID**: ${dsmcSession || currentConversationId || 'N/A'}\n`;
    mdContent += `**版本**: v${versionNum}\n`;
    mdContent += `**描述**: ${iteration.modification_description || '初始版本'}\n`;
    mdContent += `**生成时间**: ${now.toLocaleString('zh-CN')}\n\n`;
    mdContent += `---\n\n`;

    // 判断是否有修复历史
    const hasFixHistory = iteration.fix_history && iteration.fix_history.length > 0;
    const hasDifferentFinal = hasFixHistory &&
        iteration.initial_input_file &&
        iteration.initial_input_file !== iteration.input_file;

    // 1. 初始输入文件
    if (iteration.initial_input_file || iteration.input_file) {
        if (hasDifferentFinal) {
            mdContent += `## 📄 初始输入文件\n\n`;
            mdContent += `> 此为初始生成的输入文件，经过自动修复后得到最终版本\n\n`;
        } else {
            mdContent += `## 📄 输入文件\n\n`;
        }
        mdContent += '```sparta\n';
        mdContent += iteration.initial_input_file || iteration.input_file;
        mdContent += '\n```\n\n';
    }

    // 2. 参数选择依据
    if (iteration.parameter_reasoning) {
        mdContent += `## 📊 参数选择依据\n\n`;
        mdContent += iteration.parameter_reasoning + '\n\n';
    }

    // 3. 修复历史记录
    if (hasFixHistory) {
        mdContent += `## 🔧 自动修复记录\n\n`;
        mdContent += `共进行了 ${iteration.fix_history.length} 次修复：\n\n`;
        iteration.fix_history.forEach((fix, idx) => {
            mdContent += `### 修复 ${idx + 1}\n\n`;
            mdContent += `- **错误类型**: ${fix.error_type || '未知'}\n`;
            mdContent += `- **修复说明**: ${fix.fix_description || ''}\n`;
            if (fix.timestamp) {
                mdContent += `- **时间**: ${new Date(fix.timestamp).toLocaleString('zh-CN')}\n`;
            }
            mdContent += '\n';
        });
    }

    // 4. 成功运行版本（如果与初始版本不同）
    if (hasDifferentFinal) {
        mdContent += `## ✅ 成功运行版本\n\n`;
        mdContent += `> 经过自动修复后能够成功运行的最终版本\n\n`;
        mdContent += '```sparta\n';
        mdContent += iteration.input_file;
        mdContent += '\n```\n\n';
    }

    // 5. 仿真结果
    if (iteration.run_result && Object.keys(iteration.run_result).length > 0) {
        mdContent += `## 🚀 仿真结果\n\n`;

        // 摘要
        if (iteration.run_result.summary) {
            mdContent += `### 📈 摘要\n\n`;
            Object.entries(iteration.run_result.summary).forEach(([key, value]) => {
                mdContent += `- **${key}**: ${value}\n`;
            });
            mdContent += '\n';
        }

        // LLM分析
        if (iteration.run_result.interpretation) {
            mdContent += `### 🤖 LLM 分析\n\n${iteration.run_result.interpretation}\n\n`;
        }

        // 可视化结果（图片引用）
        if (includeImageRefs && iteration.run_result.plots && iteration.run_result.plots.length > 0) {
            mdContent += `### 📊 可视化结果\n\n`;
            iteration.run_result.plots.forEach((plot, idx) => {
                const filename = `plot_${idx + 1}.png`;
                mdContent += `#### ${plot.title || `图表 ${idx + 1}`}\n\n`;
                mdContent += `![${plot.title || `图表 ${idx + 1}`}](images/${filename})\n\n`;
            });
        }

        // 优化建议
        if (iteration.run_result.suggestions && iteration.run_result.suggestions.length > 0) {
            mdContent += `### 💡 优化建议\n\n`;
            iteration.run_result.suggestions.forEach(s => {
                if (typeof s === 'string') {
                    mdContent += `- ${s}\n`;
                } else if (s.parameter) {
                    mdContent += `- **${s.parameter}**: ${s.current} → ${s.suggested}\n`;
                    if (s.reason) {
                        mdContent += `  - 原因: ${s.reason}\n`;
                    }
                }
            });
            mdContent += '\n';
        }
    }

    // 6. 运行参数
    mdContent += `## ⚙️ 运行参数\n\n`;
    mdContent += `- **CPU核数**: ${document.getElementById('panelNumCores')?.value || 4}\n`;
    mdContent += `- **最大步数**: ${document.getElementById('panelMaxSteps')?.value || 1000}\n`;
    mdContent += `- **内存限制**: ${document.getElementById('panelMaxMemory')?.value || 100} GB\n`;
    mdContent += `- **最大修复次数**: ${document.getElementById('panelMaxFixAttempts')?.value || 3}\n\n`;

    return mdContent;
}

// 下载带图片的ZIP包
async function downloadVersionWithZIP(iteration, versionNum) {
    const sessionId = dsmcSession || currentConversationId || 'conversation';
    const now = new Date();
    const timeStr = formatTimeString(now);

    try {
        showStatus('📦 正在打包文件...');

        const zip = new JSZip();

        // 1. 添加 README.md（完整内容，带图片引用）
        const mdContent = generateVersionMD(iteration, versionNum, true);
        zip.file('README.md', mdContent);

        // 2. 添加输入文件
        if (iteration.input_file) {
            zip.file('input.sparta', iteration.input_file);
        }

        // 3. 如果有不同的初始版本，也添加
        const hasDifferentInitial = iteration.initial_input_file &&
            iteration.initial_input_file !== iteration.input_file;
        if (hasDifferentInitial) {
            zip.file('input_initial.sparta', iteration.initial_input_file);
        }

        // 4. 添加可视化图片
        if (iteration.run_result && iteration.run_result.plots && iteration.run_result.plots.length > 0) {
            const imagesFolder = zip.folder('images');
            for (let idx = 0; idx < iteration.run_result.plots.length; idx++) {
                const plot = iteration.run_result.plots[idx];
                const filename = `plot_${idx + 1}.png`;
                if (plot.image_url) {
                    // 从URL获取图片文件
                    try {
                        const response = await fetch(`/api/dsmc/sessions/${dsmcSession}/files/${plot.image_url}`);
                        if (response.ok) {
                            const blob = await response.blob();
                            imagesFolder.file(filename, blob);
                        }
                    } catch (e) {
                        console.error('Failed to fetch image:', e);
                    }
                }
            }
        }

        // 生成并下载ZIP
        const zipBlob = await zip.generateAsync({ type: 'blob' });
        const url = URL.createObjectURL(zipBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${sessionId}_v${versionNum}_${timeStr}.zip`;
        a.click();
        URL.revokeObjectURL(url);

        hideStatus();
    } catch (error) {
        hideStatus();
        console.error('ZIP打包失败:', error);
        alert('ZIP打包失败: ' + error.message);
    }
}

// 下载当前版本MD（自动判断是否需要ZIP）
async function downloadCurrentVersionMD() {
    if (!currentConversationId) {
        alert('没有可下载的对话');
        return;
    }

    // 如果没有迭代数据，回退到下载所有版本
    if (!activeIterationId || currentIterations.length === 0) {
        await downloadAllVersionsMD();
        return;
    }

    try {
        const iteration = currentIterations.find(i => i.iteration_id === activeIterationId);
        if (!iteration) {
            alert('未找到当前版本');
            return;
        }

        const versionNum = iteration.iteration_number;

        // 检查是否有图片需要打包
        const hasPlots = iteration.run_result &&
            iteration.run_result.plots &&
            iteration.run_result.plots.length > 0;

        if (hasPlots) {
            // 有图片，使用ZIP打包
            await downloadVersionWithZIP(iteration, versionNum);
        } else {
            // 无图片，直接下载MD
            const now = new Date();
            const timeStr = formatTimeString(now);
            const mdContent = generateVersionMD(iteration, versionNum, false);
            const sessionId = dsmcSession || currentConversationId || 'conversation';
            downloadMDFile(mdContent, `${sessionId}_v${versionNum}_${timeStr}.md`);
        }

    } catch (error) {
        console.error('下载失败:', error);
        alert('下载失败: ' + error.message);
    }
}

// 下载所有版本（ZIP打包）
async function downloadAllVersionsMD() {
    if (!currentConversationId) {
        alert('没有可下载的对话');
        return;
    }

    try {
        const now = new Date();
        const timeStr = formatTimeString(now);
        const sessionId = dsmcSession || currentConversationId || 'conversation';

        // 检查是否有任何图片
        let hasAnyPlots = false;
        if (currentIterations.length > 0) {
            hasAnyPlots = currentIterations.some(iter =>
                iter.run_result && iter.run_result.plots && iter.run_result.plots.length > 0
            );
        }

        if (hasAnyPlots && currentIterations.length > 0) {
            // 有图片，使用ZIP打包所有版本
            showStatus('📦 正在打包所有版本...');

            const zip = new JSZip();
            let combinedMD = `# SPARTA DSMC 完整对话记录\n\n`;
            combinedMD += `**会话ID**: ${sessionId}\n`;
            combinedMD += `**版本数量**: ${currentIterations.length}\n`;
            combinedMD += `**生成时间**: ${now.toLocaleString('zh-CN')}\n\n`;
            combinedMD += `---\n\n`;

            let imageIndex = 0;
            const imagesFolder = zip.folder('images');

            for (const iteration of currentIterations) {
                const versionNum = iteration.iteration_number;

                // 为每个版本创建子文件夹
                const versionFolder = zip.folder(`v${versionNum}`);

                // 添加输入文件
                if (iteration.input_file) {
                    versionFolder.file('input.sparta', iteration.input_file);
                }

                // 添加初始版本（如果不同）
                const hasDifferentInitial = iteration.initial_input_file &&
                    iteration.initial_input_file !== iteration.input_file;
                if (hasDifferentInitial) {
                    versionFolder.file('input_initial.sparta', iteration.initial_input_file);
                }

                // 添加版本MD内容到总MD
                combinedMD += `# 版本 v${versionNum}\n\n`;
                combinedMD += `**描述**: ${iteration.modification_description || '初始版本'}\n`;
                combinedMD += `**时间**: ${iteration.timestamp ? new Date(iteration.timestamp).toLocaleString('zh-CN') : 'N/A'}\n\n`;

                // 输入文件
                if (iteration.input_file) {
                    if (hasDifferentInitial) {
                        combinedMD += `## 初始输入文件\n\n`;
                        combinedMD += '```sparta\n';
                        combinedMD += iteration.initial_input_file;
                        combinedMD += '\n```\n\n';
                        combinedMD += `## 成功运行版本\n\n`;
                    } else {
                        combinedMD += `## 输入文件\n\n`;
                    }
                    combinedMD += '```sparta\n';
                    combinedMD += iteration.input_file;
                    combinedMD += '\n```\n\n';
                }

                // 参数说明
                if (iteration.parameter_reasoning) {
                    combinedMD += `## 参数选择依据\n\n${iteration.parameter_reasoning}\n\n`;
                }

                // 修复历史
                if (iteration.fix_history && iteration.fix_history.length > 0) {
                    combinedMD += `## 修复记录\n\n`;
                    iteration.fix_history.forEach((fix, idx) => {
                        combinedMD += `${idx + 1}. **${fix.error_type || '错误'}**: ${fix.fix_description || ''}\n`;
                    });
                    combinedMD += '\n';
                }

                // 仿真结果
                if (iteration.run_result) {
                    if (iteration.run_result.interpretation) {
                        combinedMD += `## 仿真结果分析\n\n${iteration.run_result.interpretation}\n\n`;
                    }

                    // 处理图片
                    if (iteration.run_result.plots && iteration.run_result.plots.length > 0) {
                        combinedMD += `## 可视化结果\n\n`;
                        for (let idx = 0; idx < iteration.run_result.plots.length; idx++) {
                            const plot = iteration.run_result.plots[idx];
                            const filename = `v${versionNum}_plot_${idx + 1}.png`;
                            if (plot.image_url) {
                                try {
                                    const response = await fetch(`/api/dsmc/sessions/${dsmcSession}/files/${plot.image_url}`);
                                    if (response.ok) {
                                        const blob = await response.blob();
                                        imagesFolder.file(filename, blob);
                                    }
                                } catch (e) {
                                    console.error('Failed to fetch image:', e);
                                }
                            }
                            combinedMD += `### ${plot.title || `图表 ${idx + 1}`}\n\n`;
                            combinedMD += `![${plot.title || `图表 ${idx + 1}`}](images/${filename})\n\n`;
                            imageIndex++;
                        }
                    }
                }

                combinedMD += `---\n\n`;
            }

            // 运行参数
            combinedMD += `## 运行参数\n\n`;
            combinedMD += `- CPU核数: ${document.getElementById('panelNumCores')?.value || 4}\n`;
            combinedMD += `- 最大步数: ${document.getElementById('panelMaxSteps')?.value || 1000}\n`;
            combinedMD += `- 内存限制: ${document.getElementById('panelMaxMemory')?.value || 100} GB\n`;
            combinedMD += `- 最大修复次数: ${document.getElementById('panelMaxFixAttempts')?.value || 3}\n\n`;

            zip.file('README.md', combinedMD);

            // 生成并下载ZIP
            const zipBlob = await zip.generateAsync({ type: 'blob' });
            const url = URL.createObjectURL(zipBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${sessionId}_all_versions_${timeStr}.zip`;
            a.click();
            URL.revokeObjectURL(url);

            hideStatus();
        } else {
            // 无图片或无迭代数据，直接下载MD
            const response = await fetch(`/api/conversations/${currentConversationId}`);
            const conversation = await response.json();

            let mdContent = `# SPARTA DSMC 完整对话记录\n\n`;
            mdContent += `**会话ID**: ${sessionId}\n`;
            mdContent += `**版本数量**: ${currentIterations.length || 1}\n`;
            mdContent += `**生成时间**: ${now.toLocaleString('zh-CN')}\n\n`;
            mdContent += `---\n\n`;

            if (currentIterations.length > 0) {
                for (const iteration of currentIterations) {
                    mdContent += generateVersionMD(iteration, iteration.iteration_number, false);
                    mdContent += `---\n\n`;
                }
            } else {
                mdContent += `## 对话记录\n\n`;
                if (conversation.messages) {
                    conversation.messages.forEach((msg) => {
                        const role = msg.role === 'user' ? '用户' : '助手';
                        const timestamp = msg.timestamp ? new Date(msg.timestamp).toLocaleString('zh-CN') : '';
                        mdContent += `### ${role} ${timestamp ? `(${timestamp})` : ''}\n\n`;
                        mdContent += `${msg.content || ''}\n\n`;

                        if (msg.dsmc_input_file && msg.dsmc_input_file.input_file) {
                            mdContent += `#### 生成的输入文件\n\n`;
                            mdContent += '```sparta\n';
                            mdContent += msg.dsmc_input_file.input_file;
                            mdContent += '\n```\n\n';
                        }

                        if (msg.dsmc_simulation_results && msg.dsmc_simulation_results.interpretation) {
                            mdContent += `#### 仿真结果分析\n\n${msg.dsmc_simulation_results.interpretation}\n\n`;
                        }
                    });
                }
            }

            downloadMDFile(mdContent, `${sessionId}_all_versions_${timeStr}.md`);
        }

    } catch (error) {
        hideStatus();
        console.error('下载失败:', error);
        alert('下载失败: ' + error.message);
    }
}

// ==================== 顶部进度指示器 ====================

function updateHeaderProgress(currentStep, totalSteps, isRunning) {
    const container = document.getElementById('headerSimProgress');
    const icon = document.getElementById('progressIcon');
    const text = document.getElementById('progressText');

    if (!container) return;

    if (isRunning) {
        container.classList.remove('hidden');
        icon.textContent = '🔄';
        text.textContent = `${currentStep}/${totalSteps}`;
    } else {
        container.classList.add('hidden');
    }
}

function hideHeaderProgress() {
    const container = document.getElementById('headerSimProgress');
    if (container) {
        container.classList.add('hidden');
    }
}

// ==================== 过程跟踪管理 ====================

function updateProcessTracker(step) {
    const tracker = document.getElementById('processTracker');
    const statusEl = document.getElementById('trackerStatus');

    if (!tracker || !statusEl) return;

    currentProcessStep = step;
    statusEl.textContent = step;

    // 更新样式
    tracker.classList.remove('active', 'completed');

    if (step === PROCESS_STEPS.COMPLETED) {
        tracker.classList.add('completed');
    } else if (step !== PROCESS_STEPS.IDLE) {
        tracker.classList.add('active');
    }
}

function resetProcessTracker() {
    updateProcessTracker(PROCESS_STEPS.IDLE);
}

function completeProcessTracker() {
    updateProcessTracker(PROCESS_STEPS.COMPLETED);
    // 5秒后恢复为就绪状态
    setTimeout(() => {
        updateProcessTracker(PROCESS_STEPS.IDLE);
    }, 5000);
}

// ==================== 自然语言迭代 ====================

// 临时pending迭代的ID前缀
const PENDING_ITERATION_PREFIX = 'pending_';

async function iterateWithNaturalLanguage(modificationRequest) {
    if (!dsmcSession) {
        alert('没有活跃的DSMC会话');
        return;
    }

    // 立即创建一个pending状态的临时标签页
    const nextIterationNum = currentIterations.length > 0
        ? Math.max(...currentIterations.map(i => i.iteration_number)) + 1
        : 1;
    const pendingIterationId = PENDING_ITERATION_PREFIX + Date.now();
    const pendingIteration = {
        iteration_id: pendingIterationId,
        iteration_number: nextIterationNum,
        modification_description: modificationRequest.substring(0, 20) + (modificationRequest.length > 20 ? '...' : ''),
        status: 'pending',
        timestamp: null
    };

    // 添加临时标签页并渲染
    currentIterations.push(pendingIteration);
    renderIterationTabs(currentIterations);

    showStatus('🤖 正在根据需求修改输入文件...');
    updateProcessTracker(PROCESS_STEPS.GENERATING);

    try {
        const response = await fetch('/api/dsmc/iterate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: dsmcSession,
                modification_request: modificationRequest
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = ''; // 缓冲不完整的行

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            // 保留最后一个可能不完整的行
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.substring(6));

                        if (event.type === 'status') {
                            showStatus(event.message);
                        } else if (event.type === 'done') {
                            hideStatus();
                            const result = event.result;

                            // 【Bug修复】获取新创建的迭代信息并强制清除其缓存
                            const newIteration = result?.iteration;
                            if (newIteration?.iteration_id) {
                                delete iterationMessages[newIteration.iteration_id];
                                console.log('强制清除新迭代缓存:', newIteration.iteration_id);
                            }

                            // 刷新迭代列表（会替换掉临时标签）
                            const newIterationId = await loadIterations(dsmcSession, true);

                            // 【Bug修复】确保使用完整的迭代数据进行渲染
                            if (newIterationId) {
                                const fullIteration = currentIterations.find(i => i.iteration_id === newIterationId);
                                // 如果后端返回的input_file更完整，使用它
                                if (fullIteration && result?.input_file && !fullIteration.input_file) {
                                    fullIteration.input_file = result.input_file;
                                }
                                await switchIteration(newIterationId);
                            }
                            completeProcessTracker();
                        } else if (event.type === 'error') {
                            hideStatus();
                            // 移除临时标签页
                            removePendingIteration(pendingIterationId);
                            resetProcessTracker();
                            alert('修改失败: ' + event.error);
                        }
                    } catch (e) {
                        console.error('解析事件失败:', e, line);
                    }
                }
            }
        }

        // 处理缓冲区中剩余的数据
        if (buffer.startsWith('data: ')) {
            try {
                const event = JSON.parse(buffer.substring(6));
                if (event.type === 'done') {
                    hideStatus();
                    const result = event.result;

                    // 【Bug修复】获取新创建的迭代信息并强制清除其缓存
                    const newIteration = result?.iteration;
                    if (newIteration?.iteration_id) {
                        delete iterationMessages[newIteration.iteration_id];
                    }

                    const newIterationId = await loadIterations(dsmcSession, true);
                    if (newIterationId) {
                        const fullIteration = currentIterations.find(i => i.iteration_id === newIterationId);
                        if (fullIteration && result?.input_file && !fullIteration.input_file) {
                            fullIteration.input_file = result.input_file;
                        }
                        await switchIteration(newIterationId);
                    }
                    completeProcessTracker();
                }
            } catch (e) {
                console.error('解析最终事件失败:', e);
            }
        }
    } catch (error) {
        hideStatus();
        // 移除临时标签页
        removePendingIteration(pendingIterationId);
        resetProcessTracker();
        alert('修改失败: ' + error.message);
    }
}

// 移除临时pending迭代
function removePendingIteration(pendingId) {
    const index = currentIterations.findIndex(i => i.iteration_id === pendingId);
    if (index !== -1) {
        currentIterations.splice(index, 1);
        renderIterationTabs(currentIterations);
    }
}

function displayIterationResult(result) {
    const iteration = result.iteration || {};
    const inputFile = result.input_file || '';

    const codeHTML = generateHighlightedCodeLines(inputFile);

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">
                <div class="dsmc-input-preview">
                    <div class="input-header">
                        <h3>🔄 迭代 #${iteration.iteration_number}: ${escapeHtml(iteration.modification_description || '修改')}</h3>
                    </div>
                    <div class="input-content">
                        ${codeHTML}
                    </div>
                </div>
            </div>
            <div class="message-meta">
                <span>${new Date().toLocaleTimeString()}</span>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ==================== 自然语言迭代对话框 ====================

// 显示自然语言迭代对话框 (保留旧版本作为备用)
function showIterateDialog() {
    if (!dsmcSession) {
        alert('没有活跃的DSMC会话');
        return;
    }

    const request = prompt('请输入修改需求（例如："增加网格密度" 或 "将温度改为500K"）：');
    if (request && request.trim()) {
        iterateWithNaturalLanguage(request.trim());
    }
}

// ==================== 自定义弹窗功能 ====================

// 弹窗相关全局变量
let pendingDeleteIterationId = null;

// 显示/隐藏弹窗覆盖层
function showModalOverlay() {
    // 先隐藏所有现有弹窗，确保不会同时显示多个
    document.querySelectorAll('.custom-modal').forEach(modal => {
        modal.classList.add('hidden');
    });
    document.getElementById('customModalOverlay').classList.remove('hidden');
}

function hideModalOverlay() {
    document.getElementById('customModalOverlay').classList.add('hidden');
    // 隐藏所有子弹窗
    document.querySelectorAll('.custom-modal').forEach(modal => {
        modal.classList.add('hidden');
    });
    // 重置删除确认的迭代ID
    pendingDeleteIterationId = null;
}

// AI编辑弹窗
function showAIEditModal() {
    if (!dsmcSession) {
        alert('没有活跃的DSMC会话');
        return;
    }
    // 确保关闭所有其他弹窗，避免状态残留
    document.querySelectorAll('.custom-modal').forEach(modal => {
        modal.classList.add('hidden');
    });
    showModalOverlay();
    document.getElementById('aiEditModal').classList.remove('hidden');
    document.getElementById('aiEditInput').value = '';
    document.getElementById('aiEditInput').focus();
}

function closeAIEditModal() {
    hideModalOverlay();
}

// 图片弹窗查看功能
function openPlotModal(imageSrc, title) {
    // 创建弹窗元素（如果不存在）
    let modal = document.getElementById('plotViewModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'plotViewModal';
        modal.className = 'plot-view-modal';
        modal.innerHTML = `
            <div class="plot-view-content">
                <div class="plot-view-header">
                    <h3 id="plotViewTitle"></h3>
                    <button class="plot-view-close" onclick="closePlotModal()">×</button>
                </div>
                <div class="plot-view-body">
                    <img id="plotViewImage" src="" alt="">
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById('plotViewTitle').textContent = title;
    document.getElementById('plotViewImage').src = imageSrc;
    document.getElementById('plotViewImage').alt = title;
    modal.classList.add('active');

    // 点击背景关闭
    modal.onclick = function(e) {
        if (e.target === modal) {
            closePlotModal();
        }
    };
}

function closePlotModal() {
    const modal = document.getElementById('plotViewModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function setAIEditExample(text) {
    document.getElementById('aiEditInput').value = text;
    document.getElementById('aiEditInput').focus();
}

function submitAIEdit() {
    const request = document.getElementById('aiEditInput').value.trim();
    if (!request) {
        alert('请输入修改需求');
        return;
    }
    closeAIEditModal();
    iterateWithNaturalLanguage(request);
}

// 直接编辑功能已移除

// 在聊天中显示更新后的输入文件
function displayUpdatedInputFileInChat(inputFile, description) {
    const codeHTML = generateHighlightedCodeLines(inputFile);

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">
                <div class="dsmc-input-preview updated-input">
                    <div class="input-header">
                        <h3>💾 ${escapeHtml(description)}</h3>
                        <span class="update-badge">已保存</span>
                    </div>
                    <div class="input-content">
                        ${codeHTML}
                    </div>
                </div>
            </div>
            <div class="message-meta">
                <span>${new Date().toLocaleTimeString()}</span>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    // 强制重新计算样式
    requestAnimationFrame(() => {
        forceStyleRecalculation();
    });
}

// ==================== 迭代删除功能 ====================

function showDeleteIterationConfirm(iterationId, versionLabel) {
    pendingDeleteIterationId = iterationId;

    const message = document.getElementById('deleteConfirmMessage');
    message.textContent = `确定要删除迭代 ${versionLabel} 吗？`;

    showModalOverlay();
    document.getElementById('deleteConfirmModal').classList.remove('hidden');
}

function closeDeleteConfirmModal() {
    pendingDeleteIterationId = null;
    hideModalOverlay();
}

// 仅删除标签（不删除文件）
async function deleteIterationTabOnly() {
    if (!pendingDeleteIterationId || !dsmcSession) {
        closeDeleteConfirmModal();
        return;
    }

    const iterationId = pendingDeleteIterationId;
    closeDeleteConfirmModal();

    // 确保退出编辑模式
    cancelEdit();

    showStatus('🗑️ 正在删除标签...');

    try {
        const response = await fetch(
            `/api/dsmc/sessions/${dsmcSession}/iterations/${iterationId}?delete_files=false`,
            { method: 'DELETE' }
        );

        if (response.ok) {
            hideStatus();
            await loadIterations(dsmcSession);

            // 如果删除的是当前活跃的标签，切换到最后一个
            if (iterationId === activeIterationId && currentIterations.length > 0) {
                switchIteration(currentIterations[currentIterations.length - 1].iteration_id);
            }
        } else {
            hideStatus();
            const error = await response.json();
            alert('删除失败: ' + (error.error || '未知错误'));
        }
    } catch (error) {
        hideStatus();
        alert('删除失败: ' + error.message);
    }
}

// 完全删除（包括文件）
async function deleteIterationCompletely() {
    if (!pendingDeleteIterationId || !dsmcSession) {
        closeDeleteConfirmModal();
        return;
    }

    const iterationId = pendingDeleteIterationId;
    closeDeleteConfirmModal();

    // 确保退出编辑模式
    cancelEdit();

    showStatus('🗑️ 正在完全删除迭代...');

    try {
        const response = await fetch(
            `/api/dsmc/sessions/${dsmcSession}/iterations/${iterationId}?delete_files=true`,
            { method: 'DELETE' }
        );

        if (response.ok) {
            hideStatus();
            await loadIterations(dsmcSession);

            // 如果删除的是当前活跃的标签，切换到最后一个
            if (iterationId === activeIterationId && currentIterations.length > 0) {
                switchIteration(currentIterations[currentIterations.length - 1].iteration_id);
            }
        } else {
            hideStatus();
            const error = await response.json();
            alert('删除失败: ' + (error.error || '未知错误'));
        }
    } catch (error) {
        hideStatus();
        alert('删除失败: ' + error.message);
    }
}

// 键盘事件：Escape关闭弹窗
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('customModalOverlay');
        if (overlay && !overlay.classList.contains('hidden')) {
            hideModalOverlay();
        }
    }
});

// 点击覆盖层关闭弹窗
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('customModalOverlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target.id === 'customModalOverlay') {
                hideModalOverlay();
            }
        });
    }
});
// Settings Modal Management (Phase 1 - UI only, no backend yet)

function openSettingsModal() {
    document.getElementById('settingsModalOverlay').classList.remove('hidden');
    // TODO: Load current settings in Phase 5
}

function closeSettingsModal() {
    document.getElementById('settingsModalOverlay').classList.add('hidden');
}

function saveSettings() {
    alert('Settings save will be implemented in Phase 5');
    closeSettingsModal();
}

function testConnection() {
    const btn = document.getElementById('testConnectionBtn');
    btn.disabled = true;
    btn.textContent = 'Testing...';

    // Placeholder - will be implemented in Phase 5
    setTimeout(() => {
        const status = document.getElementById('connectionStatus');
        status.classList.remove('hidden');
        status.className = 'connection-status success';
        status.textContent = '✅ Connection successful (mock)';

        btn.disabled = false;
        btn.textContent = 'Test';
    }, 1000);
}

// Settings button event listener
document.getElementById('settingsBtn')?.addEventListener('click', openSettingsModal);

// API key show/hide toggle
document.getElementById('toggleApiKeyBtn')?.addEventListener('click', function() {
    const input = document.getElementById('apiKey');
    if (input.type === 'password') {
        input.type = 'text';
        this.textContent = '🙈';
    } else {
        input.type = 'password';
        this.textContent = '👁️';
    }
});

// Close settings modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('settingsModalOverlay');
        if (overlay && !overlay.classList.contains('hidden')) {
            closeSettingsModal();
        }
    }
});

// Close settings modal by clicking overlay
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('settingsModalOverlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target.id === 'settingsModalOverlay') {
                closeSettingsModal();
            }
        });
    }
});

// Disconnect SSE when leaving page
window.addEventListener('beforeunload', () => {
    disconnectSSE();
});

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Debounce function to limit API call frequency
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function to limit execution frequency
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between executions in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============================================================================
// Global Error Handling
// ============================================================================

// Global error handler for uncaught exceptions
window.addEventListener('error', (event) => {
    console.error('Global error caught:', event.error);

    // Show user-friendly error message
    showNotification(
        '应用程序错误',
        '发生了一个错误。如果问题持续存在，请刷新页面。',
        'error'
    );

    // Log error to backend for debugging
    fetch('/api/log-client-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: event.error?.message || 'Unknown error',
            stack: event.error?.stack || '',
            url: window.location.href,
            timestamp: new Date().toISOString(),
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno
        })
    }).catch(() => {
        // Silently fail if error logging fails (to avoid infinite loop)
        console.warn('Failed to log error to backend');
    });
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);

    // Show user-friendly error message
    showNotification(
        '操作失败',
        event.reason?.message || '请检查网络连接后重试',
        'error'
    );

    // Log to backend
    fetch('/api/log-client-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: `Unhandled promise rejection: ${event.reason?.message || event.reason}`,
            stack: event.reason?.stack || '',
            url: window.location.href,
            timestamp: new Date().toISOString()
        })
    }).catch(() => {
        console.warn('Failed to log promise rejection to backend');
    });
});

// ============================================================================
// Log Rendering Performance Optimization
// ============================================================================

// Maximum number of lines to display in log viewer
const MAX_LOG_LINES = 1000;
let logBuffer = [];

/**
 * Append log lines with automatic truncation for performance
 * @param {string[]} newLines - Array of new log lines to append
 */
function appendLogLinesOptimized(newLines) {
    if (!Array.isArray(newLines)) {
        newLines = [newLines];
    }

    // Add new lines to buffer
    logBuffer = logBuffer.concat(newLines);

    // Truncate to keep only last MAX_LOG_LINES
    if (logBuffer.length > MAX_LOG_LINES) {
        const removed = logBuffer.length - MAX_LOG_LINES;
        logBuffer = logBuffer.slice(-MAX_LOG_LINES);

        // Add truncation notice at the top
        console.info(`Log truncated: ${removed} oldest lines removed (keeping last ${MAX_LOG_LINES})`);
    }

    // Render to DOM
    const logContent = document.getElementById('logContent');
    if (logContent) {
        logContent.textContent = logBuffer.join('\n');

        // Auto-scroll if enabled
        const autoScrollToggle = document.getElementById('autoScrollToggle');
        if (autoScrollToggle && autoScrollToggle.checked) {
            logContent.scrollTop = logContent.scrollHeight;
        }
    }
}

// Export for use in other parts of the app
window.appendLogLinesOptimized = appendLogLinesOptimized;
