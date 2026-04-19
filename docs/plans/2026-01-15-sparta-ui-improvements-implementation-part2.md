# SPARTA UI Improvements v2.0 - Implementation Plan (Part 2)

## Continuation from Part 1

This is Part 2 of the implementation plan, continuing from Phase 2 Task 2.2.

---

### Task 2.3: Create DSMC Form Template Presets

**Files:**
- Create: `llm-chat-app/static/data/dsmc-templates.json`
- Modify: `llm-chat-app/static/app.js` (add template loading)
- Modify: `llm-chat-app/templates/index.html` (update form to include template selector)

**Step 1: Create template data file**

Create `llm-chat-app/static/data/dsmc-templates.json`:

```json
{
  "templates": [
    {
      "id": "hypersonic_reentry",
      "name": "Hypersonic Flow (Re-entry)",
      "description": "High-altitude hypersonic flow simulation for re-entry vehicles",
      "parameters": {
        "dimension": "3d",
        "geometry": "cylinder",
        "grid_size": [150, 75, 75],
        "gas": "Air",
        "temperature": 196,
        "pressure": 1.05,
        "velocity": 7500,
        "altitude_km": 80,
        "atmospheric_model": "NRLMSISE-00",
        "timestep": 1e-7,
        "num_steps": 2000,
        "collision_model": "VSS"
      }
    },
    {
      "id": "vacuum_chamber",
      "name": "Vacuum Chamber",
      "description": "Low-pressure vacuum chamber simulation",
      "parameters": {
        "dimension": "3d",
        "geometry": "box",
        "grid_size": [50, 50, 50],
        "gas": "Ar",
        "temperature": 300,
        "pressure": 0.5,
        "velocity": 0,
        "altitude_km": null,
        "atmospheric_model": "Custom",
        "timestep": 1e-6,
        "num_steps": 1000,
        "collision_model": "VHS"
      }
    },
    {
      "id": "atmospheric_flight",
      "name": "Atmospheric Flight (0-100km)",
      "description": "Standard atmospheric flight conditions",
      "parameters": {
        "dimension": "3d",
        "geometry": "cylinder",
        "grid_size": [100, 50, 50],
        "gas": "Air",
        "temperature": 288,
        "pressure": 101325,
        "velocity": 500,
        "altitude_km": 0,
        "atmospheric_model": "NRLMSISE-00",
        "timestep": 1e-6,
        "num_steps": 1000,
        "collision_model": "VSS"
      }
    },
    {
      "id": "shock_tube",
      "name": "Shock Tube",
      "description": "1D/2D shock tube with temperature gradients",
      "parameters": {
        "dimension": "2d",
        "geometry": "box",
        "grid_size": [200, 20, 1],
        "gas": "N2",
        "temperature": 300,
        "pressure": 101325,
        "velocity": 0,
        "altitude_km": null,
        "atmospheric_model": "Custom",
        "timestep": 1e-7,
        "num_steps": 5000,
        "collision_model": "VSS"
      }
    },
    {
      "id": "custom",
      "name": "Custom (Manual Configuration)",
      "description": "Start with blank template for manual configuration",
      "parameters": {
        "dimension": "3d",
        "geometry": "box",
        "grid_size": [100, 50, 50],
        "gas": "Air",
        "temperature": 300,
        "pressure": 101325,
        "velocity": 1000,
        "altitude_km": null,
        "atmospheric_model": "Custom",
        "timestep": 1e-6,
        "num_steps": 1000,
        "collision_model": "VSS"
      }
    }
  ]
}
```

**Step 2: Add template selector to form HTML**

Modify `llm-chat-app/templates/index.html`, find the DSMC parameter form modal and add template selector at top:

```html
<!-- DSMC Parameter Configuration Modal (existing modal) -->
<div id="dsmcParameterModal" class="custom-modal hidden">
    <div class="modal-header">
        <h3>🚀 DSMC仿真参数配置</h3>
        <button class="modal-close-btn" onclick="closeDSMCParameterModal()">×</button>
    </div>

    <div class="modal-body dsmc-form-body">
        <!-- Template Selector (NEW) -->
        <div class="form-section">
            <h4>📋 预设模板</h4>
            <div class="form-group">
                <label for="templateSelect">选择模板:</label>
                <select id="templateSelect" class="form-select" onchange="loadTemplate()">
                    <option value="">-- Select Template --</option>
                    <!-- Will be populated by JavaScript -->
                </select>
                <p class="form-help-text" id="templateDescription"></p>
            </div>
        </div>

        <!-- Rest of existing form... -->
```

**Step 3: Add JavaScript template loading logic**

Add to `llm-chat-app/static/app.js`:

```javascript
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDSMCTemplates();
});
```

**Step 4: Manual verification**

Run: Refresh `http://localhost:21000`
Test:
1. Click "DSMC参数设置" button
2. Template dropdown shows 5 templates
3. Select "Hypersonic Flow (Re-entry)"
4. Form fields populate with template values
5. Description shows under dropdown
6. Select "Vacuum Chamber" → Fields update
7. Select "Custom" → Blank template loads

Expected:
- All templates load from JSON file
- Selecting template populates all form fields
- Description appears for each template
- Smooth transitions when changing templates

**Step 5: Commit**

```bash
mkdir -p llm-chat-app/static/data
git add llm-chat-app/static/data/dsmc-templates.json
git add llm-chat-app/templates/index.html
git add llm-chat-app/static/app.js
git commit -m "feat(dsmc): add template presets for common scenarios

- Create 5 preset templates (hypersonic, vacuum, atmospheric, shock tube, custom)
- Template selector dropdown in parameter form
- Auto-populate form fields from template
- Show template description on selection
- JSON-based template storage for easy extension

Templates:
- Hypersonic Flow (Re-entry): 80km altitude, Mach 15
- Vacuum Chamber: Low pressure, argon gas
- Atmospheric Flight: Standard conditions, 0-100km
- Shock Tube: 1D/2D with temperature gradients
- Custom: Blank template

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 2.4: Add Form Validation UI with Real-Time Feedback

**Files:**
- Modify: `llm-chat-app/static/app.js` (add validation functions)
- Modify: `llm-chat-app/static/style.css` (add validation styles)
- Modify: `llm-chat-app/templates/index.html` (add validation indicators)

**Step 1: Add validation styles to CSS**

Add to `llm-chat-app/static/style.css`:

```css
/* Form Validation Styles */
.form-input.valid,
.form-select.valid {
    border-color: var(--success-color);
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
}

.form-input.warning,
.form-select.warning {
    border-color: var(--warning-color);
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1);
}

.form-input.invalid,
.form-select.invalid {
    border-color: var(--error-color);
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}

.validation-icon {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 1.2rem;
    pointer-events: none;
}

.validation-message {
    margin-top: 4px;
    font-size: 0.85rem;
    display: none;
}

.validation-message.show {
    display: block;
}

.validation-message.success {
    color: var(--success-color);
}

.validation-message.warning {
    color: var(--warning-color);
}

.validation-message.error {
    color: var(--error-color);
}

.form-input-wrapper {
    position: relative;
}

.info-tooltip {
    display: inline-block;
    margin-left: 6px;
    cursor: help;
    color: var(--text-muted);
    font-size: 0.9rem;
}

.info-tooltip:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
    white-space: nowrap;
    z-index: 1000;
    margin-top: 8px;
    left: 0;
    box-shadow: var(--shadow-md);
}
```

**Step 2: Add validation logic to JavaScript**

Add to `llm-chat-app/static/app.js`:

```javascript
// DSMC Form Validation

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

// Initialize validation on modal open
function openDSMCParameterModal() {
    // ... existing code ...

    // Attach validation listeners
    setTimeout(() => {
        attachValidationListeners();
    }, 100);
}
```

**Step 3: Add tooltips to form fields in HTML**

Modify `llm-chat-app/templates/index.html`, add info icons to form labels:

```html
<div class="form-group">
    <label for="temperature">
        Temperature (K):
        <span class="info-tooltip" data-tooltip="Gas temperature in Kelvin. SPARTA requires T > 0K. Typical range: 50-5000K.">ℹ️</span>
    </label>
    <div class="form-input-wrapper">
        <input type="number" id="temperature" class="form-input" step="0.1">
        <!-- Validation message will be injected here -->
    </div>
</div>

<!-- Repeat for other fields: pressure, velocity, grid, timestep, numSteps -->
```

**Step 4: Manual verification**

Run: Refresh `http://localhost:21000`
Test:
1. Open DSMC parameter form
2. Enter temperature = -100 → Red border, error message
3. Enter temperature = 300 → Green border, success message
4. Enter temperature = 6000 → Yellow border, warning message
5. Hover over ℹ️ icon → Tooltip shows
6. Change dimension to 2D, set gridZ = 50 → Error (must be 1)
7. Tab through all fields → Validation triggers on blur

Expected:
- Real-time validation with color indicators
- Green = valid, Yellow = warning, Red = invalid
- Helpful error messages appear below fields
- Tooltips show SPARTA manual guidance
- Validation prevents invalid submissions

**Step 5: Commit**

```bash
git add llm-chat-app/static/style.css
git add llm-chat-app/static/app.js
git add llm-chat-app/templates/index.html
git commit -m "feat(dsmc): add real-time form validation with visual feedback

- Validate all parameter fields against SPARTA manual rules
- Three-level feedback: valid (green), warning (yellow), error (red)
- Real-time validation on input/blur events
- Helpful error messages below each field
- Info tooltips with SPARTA manual guidance
- Prevent submission with invalid values

Validation rules:
- Temperature: 50-5000K (error if <50 or <=0)
- Pressure: >0 Pa (warning if very low/high)
- Velocity: >=0 m/s (warning if >10000)
- Grid: >=10 cells per dimension (except Z in 2D)
- Timestep: 1e-9 to 1e-4 s
- Steps: 100-100000

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 2.5: Integrate Atmospheric Model Calculator in Form

**Files:**
- Modify: `llm-chat-app/static/app.js` (port atmospheric calculations from existing code)
- Modify: `llm-chat-app/templates/index.html` (add atmospheric model section to form)
- Modify: `llm-chat-app/static/style.css` (add atmospheric display styles)

**Step 1: Add atmospheric model section to form HTML**

Modify `llm-chat-app/templates/index.html`, add after Gas Properties section:

```html
<!-- Atmospheric Model Section (NEW) -->
<div class="form-section">
    <h4>🌍 Atmospheric Model</h4>

    <div class="form-group">
        <label>Model:</label>
        <div class="radio-group">
            <label class="radio-label">
                <input type="radio" name="atmospheric_model" value="NRLMSISE-00" checked onchange="onAtmosphericModelChange()">
                <span>NRLMSISE-00</span>
            </label>
            <label class="radio-label">
                <input type="radio" name="atmospheric_model" value="US76" onchange="onAtmosphericModelChange()">
                <span>US76</span>
            </label>
            <label class="radio-label">
                <input type="radio" name="atmospheric_model" value="ISA" onchange="onAtmosphericModelChange()">
                <span>ISA</span>
            </label>
            <label class="radio-label">
                <input type="radio" name="atmospheric_model" value="Custom" onchange="onAtmosphericModelChange()">
                <span>Custom</span>
            </label>
        </div>
        <p class="form-help-text">
            <strong>NRLMSISE-00</strong> (recommended): Most accurate, 0-500km<br>
            <strong>US76</strong>: Standard atmosphere, 0-1000km<br>
            <strong>ISA</strong>: International standard, 0-86km<br>
            <strong>Custom</strong>: Manual input
        </p>
    </div>

    <div id="altitudeSection" class="form-group">
        <label for="altitude">
            Altitude (km):
            <span class="info-tooltip" data-tooltip="Altitude above sea level. Atmospheric properties calculated automatically.">ℹ️</span>
        </label>
        <div class="form-row">
            <input type="number" id="altitude" class="form-input-sm" value="80" min="0" max="500" onchange="onAltitudeChange()" oninput="onAltitudeSliderInput()">
            <input type="range" id="altitudeSlider" min="0" max="500" value="80" step="1" onchange="onAltitudeChange()" oninput="onAltitudeSliderInput()">
        </div>
        <span class="slider-value-display" id="altitudeDisplay">80 km</span>
    </div>

    <div id="atmosphericResults" class="atmospheric-results hidden">
        <h5>Auto-calculated Values:</h5>
        <div class="result-grid">
            <div class="result-item">
                <span class="result-label">Temperature:</span>
                <span class="result-value" id="atmTemp">-</span>
            </div>
            <div class="result-item">
                <span class="result-label">Pressure:</span>
                <span class="result-value" id="atmPressure">-</span>
            </div>
            <div class="result-item">
                <span class="result-label">Density:</span>
                <span class="result-value" id="atmDensity">-</span>
            </div>
            <div class="result-item">
                <span class="result-label">Number Density:</span>
                <span class="result-value" id="atmNumberDensity">-</span>
            </div>
        </div>
        <div class="form-group">
            <label class="checkbox-label">
                <input type="checkbox" id="overrideGasProps" onchange="onOverrideGasProps()">
                <span>Override gas properties with atmospheric values</span>
            </label>
        </div>
    </div>
</div>
```

**Step 2: Add atmospheric calculation styles**

Add to `llm-chat-app/static/style.css`:

```css
/* Atmospheric Results Display */
.atmospheric-results {
    margin-top: 16px;
    padding: 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.atmospheric-results h5 {
    margin-bottom: 12px;
    color: var(--text-primary);
    font-size: 0.95rem;
}

.result-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
}

.result-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px;
    background: var(--bg-secondary);
    border-radius: 6px;
}

.result-label {
    color: var(--text-secondary);
    font-size: 0.85rem;
}

.result-value {
    color: var(--accent-primary);
    font-weight: 600;
    font-size: 0.9rem;
}

.slider-value-display {
    display: block;
    text-align: center;
    margin-top: 8px;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
    cursor: pointer;
}

input[type="range"] {
    width: 100%;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    outline: none;
    -webkit-appearance: none;
}

input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: var(--accent-primary);
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: var(--accent-primary);
    border-radius: 50%;
    cursor: pointer;
    border: none;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
```

**Step 3: Port atmospheric calculation from existing app.js**

Find the existing `calculateAtmosphereParams` function in `llm-chat-app/static/app.js` (lines ~26-192) and ensure it's wired up to the new form:

```javascript
// Atmospheric Model Event Handlers (using existing calculation functions)

function onAtmosphericModelChange() {
    const selectedModel = document.querySelector('input[name="atmospheric_model"]:checked').value;
    const altitudeSection = document.getElementById('altitudeSection');
    const resultsSection = document.getElementById('atmosphericResults');

    if (selectedModel === 'Custom') {
        // Hide altitude section for custom
        altitudeSection.classList.add('hidden');
        resultsSection.classList.add('hidden');
    } else {
        // Show altitude section
        altitudeSection.classList.remove('hidden');
        // Calculate atmospheric parameters
        onAltitudeChange();
    }
}

function onAltitudeSliderInput() {
    const slider = document.getElementById('altitudeSlider');
    const input = document.getElementById('altitude');
    const display = document.getElementById('altitudeDisplay');

    // Sync slider with input
    input.value = slider.value;
    display.textContent = `${slider.value} km`;
}

function onAltitudeChange() {
    const altitudeInput = document.getElementById('altitude');
    const slider = document.getElementById('altitudeSlider');
    const display = document.getElementById('altitudeDisplay');

    // Sync input with slider
    if (slider) slider.value = altitudeInput.value;
    if (display) display.textContent = `${altitudeInput.value} km`;

    // Get selected model
    const selectedModel = document.querySelector('input[name="atmospheric_model"]:checked').value;

    if (selectedModel === 'Custom') return;

    // Calculate atmospheric parameters using existing function
    const altitudeKm = parseFloat(altitudeInput.value);
    const result = calculateAtmosphereParams(altitudeKm, selectedModel);

    if (result) {
        // Display results
        document.getElementById('atmTemp').textContent = `${result.temperature.toFixed(1)} K`;
        document.getElementById('atmPressure').textContent = `${result.pressure.toExponential(2)} Pa`;
        document.getElementById('atmDensity').textContent = `${result.density.toExponential(2)} kg/m³`;
        document.getElementById('atmNumberDensity').textContent = `${result.numberDensity.toExponential(2)} #/m³`;

        document.getElementById('atmosphericResults').classList.remove('hidden');

        // Store for override
        window.lastAtmosphericResult = result;

        console.log(`Atmospheric params calculated at ${altitudeKm}km:`, result);
    }
}

function onOverrideGasProps() {
    const checkbox = document.getElementById('overrideGasProps');
    const result = window.lastAtmosphericResult;

    if (!checkbox.checked || !result) return;

    // Override gas properties with atmospheric values
    document.getElementById('temperature').value = result.temperature.toFixed(1);
    document.getElementById('pressure').value = result.pressure.toFixed(2);

    // Trigger validation
    updateFieldValidation('temperature');
    updateFieldValidation('pressure');

    console.log('Gas properties overridden with atmospheric values');
}
```

**Step 4: Manual verification**

Run: Refresh `http://localhost:21000`
Test:
1. Open DSMC parameter form
2. Select NRLMSISE-00 model (default)
3. Set altitude to 80km → Results calculate and display
4. Move slider → Values update in real-time
5. Check "Override gas properties" → Temperature and pressure fields update
6. Change model to ISA → Results recalculate
7. Change model to Custom → Altitude section hides

Expected:
- Atmospheric parameters calculate instantly
- Results display: Temperature, Pressure, Density, Number Density
- Slider syncs with input field
- Override checkbox applies values to form
- Different models produce different results
- Custom model hides atmospheric section

**Step 5: Commit**

```bash
git add llm-chat-app/templates/index.html
git add llm-chat-app/static/style.css
git add llm-chat-app/static/app.js
git commit -m "feat(dsmc): integrate atmospheric model calculator in parameter form

- Add atmospheric model selector (NRLMSISE-00, US76, ISA, Custom)
- Altitude input with slider (0-500km)
- Auto-calculate temperature, pressure, density, number density
- Display calculated values in result grid
- Override checkbox to apply atmospheric values to form
- Real-time updates on altitude change
- NRLMSISE-00 set as robust default

Uses existing atmospheric calculation functions from app.js.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 3: File Upload & Direct Run Workflow (3 days)

### Task 3.1: Create Backend Endpoint for File Upload and Validation

**Files:**
- Modify: `llm-chat-app/app.py` (add `/api/dsmc/upload-input` endpoint)
- Modify: `agent-dsmc/sparta_validator.py` (add parameter extraction method)

**Step 1: Add parameter extraction to validator**

Modify `agent-dsmc/sparta_validator.py`, add method:

```python
def extract_parameters(self, content: str) -> Dict:
    """
    Extract parameters from SPARTA input file

    Returns:
        {
            'dimension': str,
            'geometry': str,
            'grid_size': List[int],
            'temperature': float,
            'pressure': float,
            'velocity': float,
            'gas': str,
            'timestep': float,
            'num_steps': int,
            'collision_model': str
        }
    """
    params = {}

    # Dimension
    dim_match = re.search(r'^\s*dimension\s+(\d+)', content, re.MULTILINE)
    if dim_match:
        dim = dim_match.group(1)
        params['dimension'] = f"{dim}d"

    # Grid size
    grid_match = re.search(r'create_grid\s+(\d+)\s+(\d+)\s+(\d+)', content)
    if grid_match:
        params['grid_size'] = [int(grid_match.group(i)) for i in range(1, 4)]

    # Temperature from global command
    temp_match = re.search(r'global\s+.*temp\s+([\d.e+-]+)', content)
    if temp_match:
        params['temperature'] = float(temp_match.group(1))

    # Pressure - estimate from number density if available
    # (SPARTA uses fnum, need to reverse engineer)
    fnum_match = re.search(r'global\s+.*fnum\s+([\d.e+-]+)', content)
    if fnum_match:
        # Rough estimate: P ~ n * kB * T
        # This is simplified - real extraction would be more complex
        pass

    # Velocity from stream command
    vel_match = re.search(r'global\s+.*vstream\s+([\d.e+-]+)', content)
    if vel_match:
        params['velocity'] = abs(float(vel_match.group(1)))
    else:
        params['velocity'] = 0

    # Gas species
    species_match = re.search(r'species\s+([\w.]+)', content)
    if species_match:
        species_file = species_match.group(1)
        if 'N2' in species_file or 'n2' in species_file.lower():
            params['gas'] = 'N2'
        elif 'air' in species_file.lower():
            params['gas'] = 'Air'
        elif 'ar' in species_file.lower():
            params['gas'] = 'Ar'
        elif 'co2' in species_file.lower():
            params['gas'] = 'CO2'
        else:
            params['gas'] = 'Unknown'

    # Timestep
    timestep_match = re.search(r'timestep\s+([\d.e+-]+)', content)
    if timestep_match:
        params['timestep'] = float(timestep_match.group(1))

    # Steps from run command
    run_match = re.search(r'^\s*run\s+(\d+)', content, re.MULTILINE)
    if run_match:
        params['num_steps'] = int(run_match.group(1))

    # Collision model
    collide_match = re.search(r'collide\s+(\w+)', content)
    if collide_match:
        model = collide_match.group(1).upper()
        params['collision_model'] = model if model in ['VSS', 'VHS', 'HS'] else 'VSS'

    # Geometry - infer from create_box
    box_match = re.search(r'create_box\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)', content)
    if box_match:
        # Simple heuristic: if box is roughly cubic, it's a box, otherwise cylinder
        # This is simplified - real detection would check surf commands
        params['geometry'] = 'box'

    return params
```

**Step 2: Create upload endpoint in Flask**

Modify `llm-chat-app/app.py`, add endpoint:

```python
@app.route('/api/dsmc/upload-input', methods=['POST'])
def upload_sparta_input():
    """
    Upload and validate SPARTA input file

    Returns:
        {
            "valid": bool,
            "temp_id": str (if valid),
            "params": Dict (if valid),
            "preview": str (if valid),
            "stats": Dict (if valid),
            "errors": List[str] (if invalid),
            "warnings": List[str],
            "suggestions": List[str] (if invalid)
        }
    """
    try:
        # Check if file in request
        if 'file' not in request.files:
            return jsonify({"valid": False, "errors": ["No file uploaded"]}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"valid": False, "errors": ["Empty filename"]}), 400

        # Read file content
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return jsonify({"valid": False, "errors": ["File is not valid UTF-8 text"]}), 400

        # Validate using SpartaValidator
        validator = get_sparta_validator()
        validation_result = validator.validate(content)

        if validation_result['valid']:
            # Extract parameters
            params = validator.extract_parameters(content)

            # Generate temp ID
            temp_id = str(uuid.uuid4())

            # Save to temporary location
            temp_file = UPLOADS_DIR / f"{temp_id}.sparta"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Generate preview (first 500 chars)
            preview = content[:500]
            if len(content) > 500:
                preview += "\n..."

            # Count lines and commands
            lines = content.split('\n')
            commands = sum(1 for line in lines if line.strip() and not line.strip().startswith('#'))

            return jsonify({
                "valid": True,
                "temp_id": temp_id,
                "params": params,
                "preview": preview,
                "stats": {
                    "lines": len(lines),
                    "commands": commands,
                    "filename": file.filename
                },
                "warnings": validation_result['warnings']
            })
        else:
            # Invalid file
            return jsonify({
                "valid": False,
                "errors": validation_result['errors'],
                "warnings": validation_result['warnings'],
                "suggestions": validation_result['suggestions']
            }), 400

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        return jsonify({"valid": False, "errors": [str(e)]}), 500

# Helper to get validator instance
def get_sparta_validator():
    """Get or create SpartaValidator instance"""
    global sparta_validator_instance
    if sparta_validator_instance is None:
        from sparta_validator import SpartaValidator
        sparta_validator_instance = SpartaValidator()
    return sparta_validator_instance

sparta_validator_instance = None
```

**Step 3: Manual verification with curl**

Run: `cd llm-chat-app && python app.py`

Test with valid SPARTA file:
```bash
# Create test file
cat > /tmp/test_valid.sparta << 'EOF'
dimension 3
create_box 0 10 0 5 0 5
boundary o o o
create_grid 100 50 50
species air.species N2 O2
global temp 300 fnum 1e20
timestep 1e-6
collide vss air vss.air
run 1000
EOF

# Upload
curl -X POST http://localhost:21000/api/dsmc/upload-input \
  -F "file=@/tmp/test_valid.sparta"
```

Expected output:
```json
{
  "valid": true,
  "temp_id": "abc123-...",
  "params": {
    "dimension": "3d",
    "grid_size": [100, 50, 50],
    "temperature": 300,
    "velocity": 0,
    "gas": "Air",
    "timestep": 1e-6,
    "num_steps": 1000,
    "collision_model": "VSS",
    "geometry": "box"
  },
  "preview": "dimension 3\ncreate_box...",
  "stats": {
    "lines": 9,
    "commands": 9,
    "filename": "test_valid.sparta"
  }
}
```

Test with invalid file:
```bash
cat > /tmp/test_invalid.sparta << 'EOF'
dimension 5
create_box 0 10 0 5 0 5
EOF

curl -X POST http://localhost:21000/api/dsmc/upload-input \
  -F "file=@/tmp/test_invalid.sparta"
```

Expected output (400 error):
```json
{
  "valid": false,
  "errors": [
    "Invalid dimension: 5 (must be 2 or 3)",
    "Missing required command: create_grid",
    "Missing required command: species"
  ],
  "suggestions": [
    "Add 'create_grid nx ny nz' to define grid cells",
    "Add 'species air.species N2 O2' or similar..."
  ]
}
```

**Step 4: Commit**

```bash
git add llm-chat-app/app.py
git add agent-dsmc/sparta_validator.py
git commit -m "feat(dsmc): add file upload and validation endpoint

- POST /api/dsmc/upload-input endpoint
- Validate uploaded SPARTA files using SpartaValidator
- Extract parameters from valid files
- Return temp_id, params, preview, stats for valid files
- Return errors, warnings, suggestions for invalid files
- Save temp files for later use
- Support UTF-8 text files only

Parameter extraction:
- Dimension, grid size, temperature, velocity
- Gas species, timestep, steps, collision model
- Geometry inference from create_box

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 3.2: Create Upload Modal UI with Dual-Path Workflow

**Files:**
- Modify: `llm-chat-app/templates/index.html` (update existing upload modal)
- Modify: `llm-chat-app/static/app.js` (add upload handling logic)
- Modify: `llm-chat-app/static/style.css` (add upload modal styles)

**Step 1: Update upload modal HTML**

Modify `llm-chat-app/templates/index.html`, find `inputFileUploadModal` and update:

```html
<!-- SPARTA Input File Upload Modal -->
<div id="inputFileUploadModal" class="custom-modal hidden">
    <div class="modal-header">
        <h3>📄 SPARTA输入文件已上传</h3>
        <button class="modal-close-btn" onclick="closeInputFileUploadModal()">×</button>
    </div>

    <div class="modal-body">
        <!-- File Info (NEW) -->
        <div id="uploadFileInfo" class="upload-file-info">
            <div class="file-status" id="fileStatus">
                <span class="status-icon">✅</span>
                <span class="status-text">验证通过</span>
            </div>
            <div class="file-details">
                <span class="file-name" id="uploadedFileName">-</span>
                <span class="file-stats" id="uploadedFileStats">-</span>
            </div>
        </div>

        <!-- Preview Section -->
        <div class="upload-preview-section">
            <h4>预览 <button class="btn-toggle-preview" onclick="togglePreview()">▼</button></h4>
            <pre id="uploadedInputFilePreview" class="upload-preview collapsed">
<!-- File content will be shown here -->
            </pre>
        </div>

        <!-- Validation Results (warnings/errors) -->
        <div id="inputFileValidationResult" class="validation-result hidden">
            <!-- Validation messages will be shown here -->
        </div>

        <!-- Mode Selection -->
        <div class="upload-mode-section">
            <h4>选择处理方式:</h4>

            <!-- Reference Mode -->
            <div class="mode-option">
                <label class="mode-label">
                    <input type="radio" name="uploadMode" value="reference">
                    <span class="mode-icon">📚</span>
                    <div class="mode-details">
                        <h5>用作参考</h5>
                        <p>将参数提取到表单中，供修改后生成</p>
                    </div>
                </label>
            </div>

            <!-- Direct Run Mode -->
            <div class="mode-option">
                <label class="mode-label">
                    <input type="radio" name="uploadMode" value="direct_run" checked>
                    <span class="mode-icon">🚀</span>
                    <div class="mode-details">
                        <h5>直接运行</h5>
                        <p>配置运行参数并立即执行仿真</p>
                    </div>
                </label>
            </div>

            <!-- Run Configuration (shown only for direct_run) -->
            <div id="runConfigSection" class="run-config-section">
                <h5>⚙️ 运行参数配置</h5>
                <div class="run-config-grid">
                    <div class="config-item">
                        <label>CPU核数:</label>
                        <input type="number" id="uploadRunCores" value="4" min="1" max="128">
                    </div>
                    <div class="config-item">
                        <label>最大步数:</label>
                        <input type="number" id="uploadRunSteps" value="1000" min="100">
                        <span class="config-hint">(覆盖文件中的run命令)</span>
                    </div>
                    <div class="config-item">
                        <label>内存限制(GB):</label>
                        <input type="number" id="uploadRunMemory" value="100" min="1">
                    </div>
                    <div class="config-item">
                        <label>最大修复次数:</label>
                        <input type="number" id="uploadRunMaxFix" value="3" min="0" max="10">
                    </div>
                </div>
                <div class="config-warning">
                    ⚠️ 注意: 步数设置将覆盖输入文件中的 'run' 命令参数
                </div>
            </div>
        </div>
    </div>

    <div class="modal-footer">
        <button onclick="closeInputFileUploadModal()" class="btn-secondary">取消</button>
        <button onclick="handleUploadMode()" class="btn-primary" id="uploadActionBtn">🚀 开始运行</button>
    </div>
</div>
```

**Step 2: Add upload modal styles**

Add to `llm-chat-app/static/style.css`:

```css
/* Upload Modal Styles */
.upload-file-info {
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 16px;
}

.file-status {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.status-icon {
    font-size: 1.5rem;
}

.status-text {
    font-weight: 600;
    color: var(--success-color);
}

.file-status.error .status-text {
    color: var(--error-color);
}

.file-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.file-name {
    font-weight: 600;
    color: var(--text-primary);
}

.file-stats {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.upload-preview-section {
    margin-bottom: 16px;
}

.upload-preview-section h4 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.btn-toggle-preview {
    background: none;
    border: none;
    color: var(--accent-primary);
    cursor: pointer;
    font-size: 1rem;
    transition: transform 0.3s ease;
}

.btn-toggle-preview.expanded {
    transform: rotate(180deg);
}

.upload-preview {
    max-height: 300px;
    overflow-y: auto;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 12px;
    font-family: 'Monaco', 'Courier New', monospace;
    font-size: 0.85rem;
    line-height: 1.4;
    color: var(--text-primary);
    white-space: pre-wrap;
    transition: max-height 0.3s ease;
}

.upload-preview.collapsed {
    max-height: 0;
    padding: 0;
    border: none;
    overflow: hidden;
}

.upload-mode-section {
    margin-top: 16px;
}

.upload-mode-section h4 {
    margin-bottom: 12px;
    color: var(--text-primary);
}

.mode-option {
    margin-bottom: 12px;
}

.mode-label {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    background: var(--bg-tertiary);
    border: 2px solid transparent;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.mode-label:hover {
    background: var(--bg-card);
    border-color: var(--border-color);
}

.mode-label input[type="radio"] {
    margin-top: 4px;
}

.mode-label input[type="radio"]:checked ~ * {
    /* Highlight when selected */
}

.mode-label:has(input[type="radio"]:checked) {
    border-color: var(--accent-primary);
    background: var(--bg-card);
}

.mode-icon {
    font-size: 2rem;
    flex-shrink: 0;
}

.mode-details {
    flex: 1;
}

.mode-details h5 {
    margin: 0 0 4px 0;
    color: var(--text-primary);
}

.mode-details p {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.run-config-section {
    margin-top: 16px;
    padding: 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.run-config-section h5 {
    margin-bottom: 12px;
    color: var(--text-primary);
}

.run-config-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
}

.config-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.config-item label {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.config-item input {
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
}

.config-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-style: italic;
}

.config-warning {
    padding: 8px 12px;
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid var(--warning-color);
    border-radius: 6px;
    color: var(--warning-color);
    font-size: 0.85rem;
}
```

**Step 3: Add upload handling JavaScript**

Add to `llm-chat-app/static/app.js`:

```javascript
// File Upload Handling

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
    document.querySelector('input[name="uploadMode"][value="direct_run"]').checked = true;
    showRunConfigSection();

    // Sync run params from control panel defaults
    syncRunParamsFromPanel();

    // Show modal
    document.getElementById('inputFileUploadModal').classList.remove('hidden');
    document.getElementById('customModalOverlay').classList.remove('hidden');
}

function showUploadErrors(result) {
    const modal = document.getElementById('inputFileUploadModal');
    const statusDiv = document.getElementById('fileStatus');
    const validationDiv = document.getElementById('inputFileValidationResult');

    // Update status to error
    statusDiv.innerHTML = `
        <span class="status-icon">❌</span>
        <span class="status-text">验证失败</span>
    `;
    statusDiv.classList.add('error');

    // Show errors
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

    // Hide mode selection (can't run invalid file)
    document.querySelector('.upload-mode-section').style.display = 'none';

    // Change action button to close
    const actionBtn = document.getElementById('uploadActionBtn');
    actionBtn.textContent = '关闭';
    actionBtn.onclick = closeInputFileUploadModal;

    // Show modal
    modal.classList.remove('hidden');
    document.getElementById('customModalOverlay').classList.remove('hidden');
}

function togglePreview() {
    const preview = document.getElementById('uploadedInputFilePreview');
    const btn = document.querySelector('.btn-toggle-preview');

    preview.classList.toggle('collapsed');
    btn.classList.toggle('expanded');
}

function syncRunParamsFromPanel() {
    // Sync from control panel if values exist
    const panelCores = document.getElementById('panelNumCores');
    const panelSteps = document.getElementById('panelMaxSteps');
    const panelMemory = document.getElementById('panelMaxMemory');
    const panelFix = document.getElementById('panelMaxFixAttempts');

    if (panelCores) {
        document.getElementById('uploadRunCores').value = panelCores.value;
    }
    if (panelSteps) {
        document.getElementById('uploadRunSteps').value = panelSteps.value;
    }
    if (panelMemory) {
        document.getElementById('uploadRunMemory').value = panelMemory.value;
    }
    if (panelFix) {
        document.getElementById('uploadRunMaxFix').value = panelFix.value;
    }
}

function showRunConfigSection() {
    const mode = document.querySelector('input[name="uploadMode"]:checked').value;
    const configSection = document.getElementById('runConfigSection');
    const actionBtn = document.getElementById('uploadActionBtn');

    if (mode === 'direct_run') {
        configSection.style.display = 'block';
        actionBtn.innerHTML = '🚀 开始运行';
        actionBtn.onclick = runUploadedFile;
    } else {
        configSection.style.display = 'none';
        actionBtn.innerHTML = '📚 用作参考';
        actionBtn.onclick = useUploadedFileAsReference;
    }
}

// Attach mode change listener
document.addEventListener('DOMContentLoaded', () => {
    const modeRadios = document.querySelectorAll('input[name="uploadMode"]');
    modeRadios.forEach(radio => {
        radio.addEventListener('change', showRunConfigSection);
    });
});

async function runUploadedFile() {
    if (!uploadedFileData) {
        alert('No file data available');
        return;
    }

    const runParams = {
        temp_id: uploadedFileData.temp_id,
        num_cores: parseInt(document.getElementById('uploadRunCores').value),
        max_steps: parseInt(document.getElementById('uploadRunSteps').value),
        max_memory_gb: parseInt(document.getElementById('uploadRunMemory').value),
        max_fix_attempts: parseInt(document.getElementById('uploadRunMaxFix').value)
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
            monitorSimulation(result.session_id);

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

    // Open DSMC parameter form
    openDSMCParameterModal();

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
        document.getElementById('gridX').value = params.grid_size[0];
        document.getElementById('gridY').value = params.grid_size[1];
        document.getElementById('gridZ').value = params.grid_size[2];
    }

    // Temperature
    if (params.temperature) {
        document.getElementById('temperature').value = params.temperature;
    }

    // Velocity
    if (params.velocity !== undefined) {
        document.getElementById('velocity').value = params.velocity;
    }

    // Gas
    if (params.gas) {
        const gasSelect = document.getElementById('gas');
        if (gasSelect) gasSelect.value = params.gas;
    }

    // Timestep
    if (params.timestep) {
        document.getElementById('timestep').value = params.timestep;
    }

    // Steps
    if (params.num_steps) {
        document.getElementById('numSteps').value = params.num_steps;
    }

    // Collision model
    if (params.collision_model) {
        const collisionSelect = document.getElementById('collisionModel');
        if (collisionSelect) collisionSelect.value = params.collision_model;
    }

    console.log('Form populated with uploaded file parameters:', params);
}

function closeInputFileUploadModal() {
    document.getElementById('inputFileUploadModal').classList.add('hidden');
    document.getElementById('customModalOverlay').classList.add('hidden');

    // Reset
    uploadedFileData = null;
    document.getElementById('fileStatus').classList.remove('error');
    document.querySelector('.upload-mode-section').style.display = 'block';
}

// Attach to file input
document.getElementById('fileInput')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        // Check if it's a SPARTA file
        if (file.name.endsWith('.sparta') || file.name.endsWith('.in') || file.name.endsWith('.dat')) {
            handleSpartaFileUpload(file);
        } else {
            alert('Please upload a SPARTA input file (.sparta, .in, .dat)');
        }
        // Reset input
        e.target.value = '';
    }
});
```

**Step 4: Manual verification**

Run: Refresh `http://localhost:21000`

Test with valid file:
1. Click file upload button (📎)
2. Select a valid .sparta file
3. Modal opens with file info
4. Preview shows file content (collapsed by default)
5. Click preview toggle → Content expands
6. Select "直接运行" mode → Run config section shows
7. Adjust run parameters (cores, steps, memory, fix)
8. Click "开始运行" → Modal closes, control panel opens

Test with invalid file:
1. Upload invalid file
2. Modal shows errors and suggestions
3. Mode selection hidden
4. Action button changes to "关闭"

Test reference mode:
1. Upload valid file
2. Select "用作参考" mode
3. Click action button
4. Parameter form opens
5. Fields populated with extracted values

Expected:
- Upload validates file before showing modal
- Dual-path workflow (reference vs. direct run)
- Run parameters configurable
- Error handling with helpful messages
- Smooth transitions between screens

**Step 5: Commit**

```bash
git add llm-chat-app/templates/index.html
git add llm-chat-app/static/style.css
git add llm-chat-app/static/app.js
git commit -m "feat(dsmc): add upload modal with dual-path workflow UI

- Upload modal shows file info, preview, validation results
- Two modes: use as reference or run directly
- Run configuration section for direct execution
- Run params: CPU cores, max steps (overrides file), memory, fix attempts
- Extract parameters and populate form for reference mode
- Collapsible preview section
- Error handling with suggestions
- Sync run params from control panel defaults

Modal workflow:
1. Upload file → Validate
2. If valid → Show modal with modes
3. Direct run → Configure → Execute
4. Reference → Extract params → Open form

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 3.3: Create Backend Endpoint for Direct Run

**Files:**
- Modify: `llm-chat-app/app.py` (add `/api/dsmc/run-uploaded` endpoint)
- Modify: `agent-dsmc/dsmc_agent.py` (add `create_session_from_input` method if not exists)

**Step 1: Add run-uploaded endpoint**

Modify `llm-chat-app/app.py`, add endpoint:

```python
@app.route('/api/dsmc/run-uploaded', methods=['POST'])
def run_uploaded_input():
    """
    Run uploaded SPARTA file directly

    Request:
        {
            "temp_id": str,
            "num_cores": int,
            "max_steps": int,
            "max_memory_gb": int,
            "max_fix_attempts": int
        }

    Returns:
        {
            "success": bool,
            "session_id": str (if success),
            "message": str,
            "error": str (if failure)
        }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['temp_id', 'num_cores', 'max_steps']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing field: {field}"}), 400

        temp_id = data['temp_id']
        num_cores = int(data.get('num_cores', 4))
        max_steps = int(data.get('max_steps', 1000))
        max_memory_gb = int(data.get('max_memory_gb', 100))
        max_fix_attempts = int(data.get('max_fix_attempts', 3))

        # Read temp file
        temp_file = UPLOADS_DIR / f"{temp_id}.sparta"
        if not temp_file.exists():
            return jsonify({"success": False, "error": "Temporary file not found"}), 404

        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Override run command with max_steps
        modified_content = override_run_steps(content, max_steps)

        # Create session
        agent = get_dsmc_agent()
        session_id = generate_session_id()

        # Create session directory
        session_dir = DSMC_SESSIONS_DIR / session_id
        session_dir.mkdir(exist_ok=True, parents=True)

        # Save input file
        input_file_path = session_dir / 'input.sparta'
        with open(input_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        # Create metadata
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "source": "uploaded",
            "original_filename": temp_file.name,
            "input_file": str(input_file_path),
            "status": "pending",
            "run_params": {
                "num_cores": num_cores,
                "max_steps": max_steps,
                "max_memory_gb": max_memory_gb,
                "max_fix_attempts": max_fix_attempts
            },
            "iterations": []
        }

        metadata_path = session_dir / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        # Run simulation in background thread
        def run_async():
            try:
                logger.info(f"Starting uploaded file simulation: {session_id}")

                # Update status
                metadata['status'] = 'running'
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Run simulation
                from sparta_runner import SPARTARunner
                runner = SPARTARunner()

                result = runner.run(
                    input_file=str(input_file_path),
                    session_id=session_id,
                    num_cores=num_cores,
                    max_memory_gb=max_memory_gb,
                    timeout=600
                )

                # Update status
                metadata['status'] = 'completed' if result['success'] else 'failed'
                metadata['run_result'] = result
                metadata['completed_at'] = datetime.now().isoformat()

                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                logger.info(f"Simulation completed: {session_id}, success={result['success']}")

            except Exception as e:
                logger.error(f"Simulation failed: {session_id}, error={e}", exc_info=True)

                metadata['status'] = 'failed'
                metadata['error'] = str(e)
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

        import threading
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "Simulation started"
        })

    except Exception as e:
        logger.error(f"Failed to run uploaded file: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def override_run_steps(content: str, max_steps: int) -> str:
    """
    Override run command in SPARTA input file

    Replaces: run 1000
    With: run <max_steps>
    """
    import re

    lines = []
    for line in content.split('\n'):
        # Match run command with any number of steps
        match = re.match(r'^(\s*run\s+)\d+(.*)$', line)
        if match:
            # Replace steps
            lines.append(f"{match.group(1)}{max_steps}{match.group(2)}")
        else:
            lines.append(line)

    return '\n'.join(lines)


def generate_session_id() -> str:
    """Generate session ID: YYYYMMDD_HHMMSS_randomhex"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_hex = uuid.uuid4().hex[:8]
    return f"{timestamp}_{random_hex}"
```

**Step 2: Manual verification with curl**

Run: Server should already be running

Test:
```bash
# First upload a file to get temp_id
TEMP_ID=$(curl -s -X POST http://localhost:21000/api/dsmc/upload-input \
  -F "file=@/tmp/test_valid.sparta" | jq -r '.temp_id')

echo "Temp ID: $TEMP_ID"

# Now run it
curl -X POST http://localhost:21000/api/dsmc/run-uploaded \
  -H "Content-Type: application/json" \
  -d "{
    \"temp_id\": \"$TEMP_ID\",
    \"num_cores\": 4,
    \"max_steps\": 500,
    \"max_memory_gb\": 50,
    \"max_fix_attempts\": 2
  }"
```

Expected output:
```json
{
  "success": true,
  "session_id": "20260115_143022_abc12345",
  "message": "Simulation started"
}
```

Check session created:
```bash
SESSION_ID=<from_above>
ls -la llm-chat-app/data/dsmc_sessions/$SESSION_ID/
```

Expected files:
- `input.sparta` (with modified run command)
- `metadata.json`
- `log.sparta` (after run starts)

**Step 3: Check override_run_steps function**

Test the override function:
```python
# In Python REPL
content = """
dimension 3
run 1000
# comment
run 2000
"""

from app import override_run_steps
result = override_run_steps(content, 5000)
print(result)
```

Expected:
```
dimension 3
run 5000
# comment
run 5000
```

**Step 4: Commit**

```bash
git add llm-chat-app/app.py
git commit -m "feat(dsmc): add endpoint for running uploaded files directly

- POST /api/dsmc/run-uploaded endpoint
- Accept temp_id and run parameters
- Override 'run' command steps in input file
- Create new session with metadata
- Execute SPARTA in background thread
- Update session status (pending → running → completed/failed)
- Return session_id for monitoring

Run parameters:
- num_cores: MPI parallelism
- max_steps: Override file's run command
- max_memory_gb: Memory limit
- max_fix_attempts: Auto-fix retry count

Session metadata includes:
- source: 'uploaded'
- run_params
- timestamps
- status tracking

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 4: Version Control Integration (4 days)

### Task 4.1: Create Version Manager JavaScript Component

**Files:**
- Create: `llm-chat-app/static/components/version-manager.js`
- Modify: `llm-chat-app/templates/index.html` (add script reference)

**Step 1: Create VersionManager class**

Create `llm-chat-app/static/components/version-manager.js`:

```javascript
/**
 * Version Manager Component
 * Manages iteration history and version control for DSMC sessions
 */

class VersionManager {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.iterations = [];
        this.activeIterationId = null;
        this.container = null;
    }

    /**
     * Initialize version manager
     * @param {string} containerId - DOM element ID for version list
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Version container not found: ${containerId}`);
            return false;
        }

        this.loadIterations();
        return true;
    }

    /**
     * Load iterations from backend
     */
    async loadIterations() {
        try {
            const response = await fetch(`/api/dsmc/sessions/${this.sessionId}/iterations`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                this.iterations = data.iterations || [];
                this.activeIterationId = data.current_iteration_id;
                this.render();

                console.log(`Loaded ${this.iterations.length} iterations for session ${this.sessionId}`);
            } else {
                console.error('Failed to load iterations:', data.error);
            }
        } catch (error) {
            console.error('Failed to load iterations:', error);
            this.renderError('Failed to load version history');
        }
    }

    /**
     * Render version history list
     */
    render() {
        if (!this.container) return;

        if (this.iterations.length === 0) {
            this.container.innerHTML = `
                <div class="version-empty">
                    <p>No iterations yet</p>
                </div>
            `;
            return;
        }

        // Sort by iteration number descending (newest first)
        const sortedIterations = [...this.iterations].sort((a, b) =>
            b.iteration_number - a.iteration_number
        );

        this.container.innerHTML = sortedIterations.map(iter =>
            this.renderIterationItem(iter)
        ).join('');

        // Attach event listeners
        this.attachEventListeners();
    }

    /**
     * Render a single iteration item
     */
    renderIterationItem(iter) {
        const isActive = iter.iteration_id === this.activeIterationId;
        const statusIcon = this.getStatusIcon(iter.status);
        const statusText = this.getStatusText(iter);

        return `
            <div class="version-item ${isActive ? 'active' : ''}" data-iteration-id="${iter.iteration_id}">
                <div class="version-header">
                    <span class="version-indicator">${isActive ? '●' : '○'}</span>
                    <span class="version-label">
                        v${iter.iteration_number} ${iter.modification_description || 'Initial'}
                    </span>
                    ${isActive ? '<span class="badge-current">Current</span>' : ''}
                </div>
                <div class="version-status">
                    <span class="status-icon">${statusIcon}</span>
                    <span class="status-text">${statusText}</span>
                </div>
                <div class="version-actions">
                    ${this.renderActions(iter, isActive)}
                </div>
            </div>
        `;
    }

    /**
     * Get status icon emoji
     */
    getStatusIcon(status) {
        const icons = {
            'completed': '✅',
            'failed': '❌',
            'running': '⏳',
            'fixing': '🔄',
            'pending': '⏸️'
        };
        return icons[status] || '❓';
    }

    /**
     * Get status text with details
     */
    getStatusText(iter) {
        if (iter.status === 'completed') {
            const time = (iter.timing?.total_time || 0).toFixed(1);
            return `Success | ${time}s`;
        } else if (iter.status === 'failed') {
            const attempts = iter.fix_history?.length || 0;
            return `Failed | ${attempts} fix attempts`;
        } else if (iter.status === 'running') {
            const current = iter.run_result?.current_step || 0;
            const total = iter.run_result?.total_steps || 1000;
            return `Running... ${current}/${total}`;
        } else if (iter.status === 'fixing') {
            return 'Auto-fixing errors...';
        } else if (iter.status === 'pending') {
            return 'Ready to run';
        }
        return iter.status;
    }

    /**
     * Render action buttons for iteration
     */
    renderActions(iter, isActive) {
        if (isActive) {
            if (iter.status === 'running' || iter.status === 'fixing') {
                return `
                    <button class="btn-version-action" data-action="view">View</button>
                    <button class="btn-version-action" data-action="compare">Compare</button>
                    <button class="btn-version-action danger" data-action="stop">Stop</button>
                `;
            } else {
                return `
                    <button class="btn-version-action" data-action="view">View</button>
                    <button class="btn-version-action" data-action="compare">Compare</button>
                    <button class="btn-version-action danger" data-action="delete">Delete</button>
                `;
            }
        } else {
            return `
                <button class="btn-version-action primary" data-action="restore">Restore</button>
                <button class="btn-version-action" data-action="view">View</button>
                <button class="btn-version-action danger" data-action="delete">Delete</button>
            `;
        }
    }

    /**
     * Attach event listeners to action buttons
     */
    attachEventListeners() {
        const buttons = this.container.querySelectorAll('.btn-version-action');

        buttons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();

                const action = btn.dataset.action;
                const versionItem = btn.closest('.version-item');
                const iterationId = versionItem.dataset.iterationId;

                await this.handleAction(action, iterationId);
            });
        });
    }

    /**
     * Handle action button clicks
     */
    async handleAction(action, iterationId) {
        console.log(`Version action: ${action} on ${iterationId}`);

        switch (action) {
            case 'restore':
                await this.restoreVersion(iterationId);
                break;
            case 'view':
                await this.viewIteration(iterationId);
                break;
            case 'compare':
                await this.compareIterations(iterationId);
                break;
            case 'delete':
                await this.deleteIteration(iterationId);
                break;
            case 'stop':
                await this.stopIteration(iterationId);
                break;
            default:
                console.warn(`Unknown action: ${action}`);
        }
    }

    /**
     * Restore to a previous version
     */
    async restoreVersion(iterationId) {
        if (!confirm('Restore to this version? Current unsaved changes will be lost.')) {
            return;
        }

        showStatus('Restoring version...');

        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}/restore`,
                { method: 'POST' }
            );

            const result = await response.json();

            if (result.success) {
                this.activeIterationId = iterationId;
                await this.loadIterations();

                // Reload input file in main view if available
                if (typeof loadInputFileContent === 'function') {
                    await loadInputFileContent(this.sessionId);
                }

                showStatus('Version restored successfully', 'success');
            } else {
                showStatus('Restore failed: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Restore failed:', error);
            showStatus('Restore failed: ' + error.message, 'error');
        }
    }

    /**
     * View iteration details
     */
    async viewIteration(iterationId) {
        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}`
            );

            const iteration = await response.json();

            if (typeof showIterationDetailModal === 'function') {
                showIterationDetailModal(iteration);
            } else {
                console.log('Iteration details:', iteration);
                alert('Iteration detail viewer not implemented yet');
            }
        } catch (error) {
            console.error('Failed to load iteration:', error);
            showStatus('Failed to load iteration: ' + error.message, 'error');
        }
    }

    /**
     * Compare with another iteration
     */
    async compareIterations(iterationId) {
        if (typeof showCompareModal === 'function') {
            showCompareModal(this.sessionId, iterationId, this.iterations);
        } else {
            alert('Version comparison not implemented yet');
        }
    }

    /**
     * Delete an iteration
     */
    async deleteIteration(iterationId) {
        const iteration = this.iterations.find(i => i.iteration_id === iterationId);
        const isActive = iterationId === this.activeIterationId;

        let message = `Delete iteration v${iteration?.iteration_number || '?'}?`;
        if (isActive) {
            message += '\n\nThis is the current active version. You cannot delete it.';
            alert(message);
            return;
        }

        if (!confirm(message + '\n\nThis action cannot be undone.')) {
            return;
        }

        showStatus('Deleting iteration...');

        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}`,
                { method: 'DELETE' }
            );

            const result = await response.json();

            if (result.success) {
                await this.loadIterations();
                showStatus('Iteration deleted', 'success');
            } else {
                showStatus('Delete failed: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Delete failed:', error);
            showStatus('Delete failed: ' + error.message, 'error');
        }
    }

    /**
     * Stop running iteration
     */
    async stopIteration(iterationId) {
        if (!confirm('Stop this simulation?')) {
            return;
        }

        try {
            await fetch(`/api/dsmc/stop/${this.sessionId}`, { method: 'POST' });
            showStatus('Simulation stopped', 'info');

            // Reload to update status
            setTimeout(() => this.loadIterations(), 1000);
        } catch (error) {
            console.error('Stop failed:', error);
            showStatus('Stop failed: ' + error.message, 'error');
        }
    }

    /**
     * Render error message
     */
    renderError(message) {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="version-error">
                <p>❌ ${message}</p>
            </div>
        `;
    }

    /**
     * Update iteration status in real-time
     * Called by SSE listeners
     */
    updateIterationStatus(iterationId, statusData) {
        const iteration = this.iterations.find(i => i.iteration_id === iterationId);
        if (iteration) {
            Object.assign(iteration, statusData);
            this.render();
        }
    }

    /**
     * Add new iteration to list
     */
    addIteration(iteration) {
        this.iterations.push(iteration);
        this.render();
    }
}

// Export for use in app.js
window.VersionManager = VersionManager;
```

**Step 2: Add version manager styles**

Add to `llm-chat-app/static/style.css`:

```css
/* Version Manager Styles */
.version-item {
    padding: 12px;
    margin-bottom: 8px;
    background: var(--bg-tertiary);
    border: 1px solid transparent;
    border-radius: 8px;
    transition: all 0.2s ease;
}

.version-item:hover {
    background: var(--bg-card);
    border-color: var(--border-color);
}

.version-item.active {
    background: var(--bg-card);
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.1);
}

.version-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}

.version-indicator {
    font-size: 0.8rem;
    color: var(--accent-primary);
}

.version-label {
    flex: 1;
    font-weight: 600;
    color: var(--text-primary);
    font-size: 0.9rem;
}

.badge-current {
    padding: 2px 8px;
    background: var(--accent-primary);
    color: white;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
}

.version-status {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.status-icon {
    font-size: 1rem;
}

.version-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}

.btn-version-action {
    padding: 4px 10px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-secondary);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-version-action:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border-color: var(--accent-primary);
}

.btn-version-action.primary {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

.btn-version-action.primary:hover {
    background: var(--accent-secondary);
}

.btn-version-action.danger {
    color: var(--error-color);
    border-color: var(--error-color);
}

.btn-version-action.danger:hover {
    background: var(--error-color);
    color: white;
}

.version-empty,
.version-error {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.9rem;
}

.version-error p {
    color: var(--error-color);
}
```

**Step 3: Add script reference to HTML**

Modify `llm-chat-app/templates/index.html`, add before app.js:

```html
<script src="{{ url_for('static', filename='components/theme-manager.js') }}"></script>
<script src="{{ url_for('static', filename='components/version-manager.js') }}"></script>
<script src="{{ url_for('static', filename='app.js') }}?v=20260115"></script>
```

**Step 4: Manual verification**

Since backend endpoints don't exist yet, we'll test the rendering:

Add to `llm-chat-app/static/app.js` (temporary test code):

```javascript
// Test VersionManager rendering
function testVersionManager() {
    const vm = new VersionManager('test-session-123');

    // Mock data
    vm.iterations = [
        {
            iteration_id: 'iter-1',
            iteration_number: 1,
            modification_description: 'Initial generation',
            status: 'completed',
            timing: { total_time: 120.5 }
        },
        {
            iteration_id: 'iter-2',
            iteration_number: 2,
            modification_description: 'Fixed collision model',
            status: 'failed',
            fix_history: [{}, {}, {}]
        },
        {
            iteration_id: 'iter-3',
            iteration_number: 3,
            modification_description: 'AI optimized grid',
            status: 'running',
            run_result: { current_step: 450, total_steps: 1000 }
        }
    ];
    vm.activeIterationId = 'iter-3';

    // Find a container to render in (use existing or create temp)
    let container = document.getElementById('versionHistoryList');
    if (!container) {
        container = document.createElement('div');
        container.id = 'versionHistoryList';
        container.style.cssText = 'position:fixed; top:100px; right:20px; width:300px; background:var(--bg-secondary); padding:16px; border-radius:8px; z-index:1000;';
        document.body.appendChild(container);
    }

    vm.init('versionHistoryList');

    console.log('VersionManager test rendered');
}

// Add button to test
document.addEventListener('DOMContentLoaded', () => {
    const testBtn = document.createElement('button');
    testBtn.textContent = 'Test Version Manager';
    testBtn.style.cssText = 'position:fixed; top:20px; right:20px; z-index:10000; padding:8px 16px; background:var(--accent-primary); color:white; border:none; border-radius:6px; cursor:pointer;';
    testBtn.onclick = testVersionManager;
    document.body.appendChild(testBtn);
});
```

Run: Refresh `http://localhost:21000`
Test:
1. Click "Test Version Manager" button
2. Version list appears on right side
3. Three iterations displayed:
   - v3 (current, running status)
   - v2 (failed with fix attempts)
   - v1 (completed with time)
4. Click "View" button → Console log or alert
5. Click "Restore" on v1 → Confirmation dialog

Expected:
- Clean rendering of version list
- Active version highlighted
- Status icons and text display correctly
- Action buttons interactive
- Hover states work

**Step 5: Commit**

```bash
git add llm-chat-app/static/components/version-manager.js
git add llm-chat-app/static/style.css
git add llm-chat-app/templates/index.html
git commit -m "feat(dsmc): create VersionManager JavaScript component

- VersionManager class for iteration history UI
- Load iterations from backend API
- Render version list with status indicators
- Action buttons: restore, view, compare, delete, stop
- Status icons: ✅ completed, ❌ failed, ⏳ running, 🔄 fixing
- Active version highlighting
- Confirmation dialogs for destructive actions
- Real-time status updates (prepared for SSE)

Features:
- Sort iterations newest first
- Show iteration number, description, status, time
- Different actions for active vs. historical versions
- Prevent deleting active version
- Error handling and loading states

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

Due to length constraints, I'll save this part and create a summary document for the remaining tasks. The pattern is established - each remaining task will follow the same detailed TDD approach.

Would you like me to:
1. **Continue with Part 3** (more Phase 4 tasks + Phase 5-6)
2. **Create a condensed summary** of remaining tasks
3. **Package what we have** and provide execution guidance

The current plan is already very comprehensive with ~102K tokens. What's your preference?