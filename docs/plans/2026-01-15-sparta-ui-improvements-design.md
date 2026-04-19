# SPARTA LLM Agent v2.0 - Comprehensive UI & System Improvements

**Design Document**
**Date:** 2026-01-15
**Status:** Approved
**Version:** 1.0

---

## Executive Summary

This design addresses 8 critical improvement areas for the SPARTA LLM Agent system:

1. **UI Color Modernization** - Replace outdated purple gradients with professional blue/teal tech aesthetic
2. **Dark/Light Theme System** - Implement theme switcher with user preference persistence
3. **Environment Variable Management** - Settings panel for runtime API configuration
4. **DSMC Form Robustness** - Enhanced guided form with validation and SPARTA manual integration
5. **Atmospheric Model** - NRLMSISE-00 as robust default with auto-calculation
6. **File Upload & Direct Run** - Dual-path workflow with run parameter configuration
7. **Version Iteration Flow** - Integrated version control in persistent control panel
8. **Chat UI Optimization** - Right-aligned user messages with adaptive bubble sizing

**Estimated Implementation Time:** 14-18 days
**Impact:** High - Addresses user experience, reliability, and workflow efficiency

---

## Design Rationale

### Problem Analysis

**Current Pain Points:**
- Outdated purple gradient color scheme feels "tacky and old-fashioned" (用户反馈)
- No theme options - only dark mode available
- API configuration requires manual .env editing and server restart
- LLM-generated SPARTA scripts frequently fail to run due to parameter errors
- Uploaded SPARTA files cannot be executed properly
- Version iteration lacks visibility and smooth workflow
- User chat messages stretch full width, poor alignment
- Control panel doesn't integrate well with direct run workflow

**User Impact:**
- Poor visual experience reduces trust in the system
- Difficult to modify API settings
- High failure rate on generated simulations wastes time
- Confusion about version history and recovery
- Cluttered chat interface

### Solution Approach

**Design Principles:**
1. **Modern & Professional** - Clean, technical aesthetic inspired by VS Code/GitHub
2. **User Control** - Give users visibility and control over all system aspects
3. **Robustness First** - Validate inputs before execution, prevent failures
4. **Workflow Integration** - All components work together seamlessly
5. **Progressive Enhancement** - New features don't break existing functionality

---

## 1. Theme System & Color Palette

### Color Scheme: Modern Tech (Blue/Teal)

**Dark Theme (Default):**
```css
--bg-primary: #0f172a        /* Deep slate background */
--bg-secondary: #1e293b      /* Card/sidebar background */
--bg-tertiary: #334155       /* Hover states */
--accent-primary: #06b6d4    /* Cyan/teal - primary actions */
--accent-secondary: #0891b2  /* Darker teal - hover */
--accent-blue: #3b82f6       /* Blue highlights */
--text-primary: #f8fafc      /* Primary text */
--text-secondary: #cbd5e1    /* Secondary text */
--text-muted: #64748b        /* Muted text */
--border: rgba(6, 182, 212, 0.3)  /* Teal borders */
```

**Light Theme:**
```css
--bg-primary: #ffffff        /* White background */
--bg-secondary: #f8fafc      /* Light gray */
--bg-tertiary: #e2e8f0       /* Hover states */
--accent-primary: #0891b2    /* Teal (slightly darker for contrast) */
--accent-secondary: #0e7490  /* Darker teal hover */
--accent-blue: #2563eb       /* Darker blue */
--text-primary: #0f172a      /* Dark text */
--text-secondary: #475569    /* Gray text */
--text-muted: #94a3b8        /* Light gray text */
--border: rgba(8, 145, 178, 0.3)
```

### Theme Toggle Implementation

**UI Component:**
- Toggle button in header (🌙/☀️ icon)
- Smooth transition animation (0.3s)
- Preference saved to localStorage
- Auto-apply on page load

**Technical Implementation:**
```javascript
// Theme manager
const ThemeManager = {
    current: 'dark',

    init() {
        const saved = localStorage.getItem('theme') || 'dark';
        this.setTheme(saved);
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.current = theme;
    },

    toggle() {
        const newTheme = this.current === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }
};
```

**CSS Structure:**
```css
/* Base theme variables */
:root[data-theme="dark"] { /* dark colors */ }
:root[data-theme="light"] { /* light colors */ }

/* All components use CSS variables */
.button {
    background: var(--accent-primary);
    color: var(--text-primary);
}
```

---

## 2. Chat UI Redesign

### Message Layout

**User Messages:**
- **Alignment:** Right-aligned (flex-end)
- **Background:** Teal gradient (#0891b2 → #06b6d4)
- **Text Color:** White (#ffffff)
- **Max-width:** 70% (adaptive to content)
- **Border-radius:** 18px 18px 4px 18px (speech bubble style)
- **Padding:** 12px-20px (adapts to content size)

**Assistant Messages:**
- **Alignment:** Left-aligned
- **Background:**
  - Dark: Slate card (#1e293b) with cyan border glow
  - Light: White (#ffffff) with subtle shadow
- **Max-width:** 85% (more space for technical content)
- **Border-radius:** 18px 18px 18px 4px
- **Avatar:** 🤖 icon on left side
- **Padding:** 16px-24px

**Adaptive Sizing:**
```css
.message-bubble {
    width: fit-content;
    min-width: 60px;
    max-width: 70%;
}

.message-bubble.assistant {
    max-width: 85%;
}

/* Full width for code blocks */
.message-bubble.has-code {
    max-width: 95%;
}
```

**Visual Hierarchy:**
- User messages stand out with bright teal gradient
- Assistant messages blend with background for readability
- Clear left/right positioning prevents confusion
- Modern messaging app aesthetic (WhatsApp/Telegram inspired)

---

## 3. Enhanced DSMC Parameter Form

### Problem Statement

Current form generates SPARTA scripts via LLM that often fail to run due to:
- Invalid parameter combinations
- Missing required commands
- Incorrect command order
- Out-of-range values
- Atmospheric parameter mismatches

### Solution: Guided Template-Based Form

**Form Structure:**

```
┌─────────────────────────────────────────────┐
│ 🚀 DSMC仿真参数配置                         │
├─────────────────────────────────────────────┤
│ 📋 预设模板                                 │
│ [选择模板: Hypersonic Flow (Re-entry) ▼]   │
│                                             │
│ ├─ Hypersonic Flow (Re-entry)              │
│ ├─ Vacuum Chamber                           │
│ ├─ Atmospheric Flight (0-100km)            │
│ ├─ Shock Tube                               │
│ └─ Custom (手动配置)                        │
├─────────────────────────────────────────────┤
│ 📐 Geometry                                 │
│ Dimension:  ●3D  ○2D  ○Axisymmetric        │
│ Type:       [Cylinder ▼]                    │
│ Grid Size:  X[100] Y[50] Z[50]              │
│             [Auto-calculate ✓]              │
│                                             │
│ 💡 建议: 对于Re ≈ 10^5，网格密度已足够      │
├─────────────────────────────────────────────┤
│ 🌡️ Gas Properties                           │
│ Species:    [N2 ▼] [Air] [Ar] [CO2] [Mix]  │
│ Temp (K):   [300] ✅ (有效范围: 50-5000K)   │
│ Pressure:   [101325] Pa ✅                   │
│ Velocity:   [1000] m/s ✅                    │
│                                             │
│ ℹ️ SPARTA: species命令需在create_particles前│
├─────────────────────────────────────────────┤
│ 🌍 Atmospheric Model                        │
│ Model:      ●NRLMSISE-00  ○US76  ○ISA       │
│             ○Custom (手动输入)               │
│                                             │
│ Altitude:   [80] km [────●────] (0-500km)   │
│                                             │
│ Auto-calculated:                            │
│ ├─ Temperature:  196.4 K                    │
│ ├─ Pressure:     1.05 Pa                    │
│ ├─ Density:      1.87e-5 kg/m³              │
│ └─ Number Dens:  3.92e17 #/m³               │
│                                             │
│ [覆盖气体属性 ✓] ← 使用大气模型计算值        │
│                                             │
│ 💡 NRLMSISE-00适用0-500km，数据最可靠        │
├─────────────────────────────────────────────┤
│ ⚙️ Simulation Parameters                    │
│ Timestep:   [1e-6] s                        │
│             [Auto from mean free path ✓]    │
│ Steps:      [1000] [────●────] (100-100K)   │
│ Collision:  [VSS ▼] (VHS/VSS/HS)            │
│                                             │
│ ℹ️ VSS requires temperature and collision   │
│    cross-section data                       │
├─────────────────────────────────────────────┤
│ 📝 Custom Requirements (Optional)           │
│ [Advanced commands or modifications...]     │
│                                             │
├─────────────────────────────────────────────┤
│         [Reset] [Preview Script] [Generate] │
└─────────────────────────────────────────────┘
```

### Key Features

**1. Template Presets:**
- **Hypersonic Flow (Re-entry):** Altitude 80km, Mach 15, N2/O2 mix, fine grid
- **Vacuum Chamber:** Low pressure (0.1-10 Pa), 3D box, coarse grid
- **Atmospheric Flight:** Altitude 0-100km, NRLMSISE-00, standard air
- **Shock Tube:** 1D/2D, high-speed flow, temperature gradients
- **Custom:** Empty template for manual configuration

Each preset pre-fills validated parameters.

**2. Real-Time Validation:**
- ✅ **Green border:** Valid input
- ⚠️ **Yellow border:** Warning (works but not optimal)
- ❌ **Red border:** Invalid (prevents generation)
- Validation rules from SPARTA manual:
  - Temperature > 0K
  - Pressure > 0 Pa
  - Grid cells ≥ 10 in each dimension
  - Timestep < mean collision time
  - Command order: dimension → create_box → boundary → create_grid

**3. SPARTA Manual Integration:**
- Info icons (ℹ️) show relevant manual excerpts
- Tooltips explain parameters
- Examples from manual shown on hover
- Dependency warnings (e.g., "VSS requires temperature")

**4. Atmospheric Model (NRLMSISE-00 Default):**
- **NRLMSISE-00:** 0-500km, most accurate
- **US76:** Standard atmosphere to 1000km
- **ISA:** 0-86km, simple model
- **Custom:** Manual input

Altitude slider automatically calculates T, P, ρ, n using selected model.

Checkbox to "Override gas properties" - applies atmospheric values to form.

**5. Parameter Dependencies:**
- Auto-calculate grid size from geometry and Reynolds number
- Auto-calculate timestep from mean free path
- Update collision model options based on selected species
- Validate command order before generation

### Validation Module

**New File: `agent-dsmc/sparta_validator.py`**

```python
class SpartaValidator:
    """Validate SPARTA input files against manual rules"""

    REQUIRED_COMMANDS = ['dimension', 'create_box', 'create_grid', 'species']

    COMMAND_ORDER = [
        'dimension',
        'create_box',
        'boundary',
        'create_grid',
        'balance_grid',
        'species',
        'mixture',
        'global',
        'collide',
        'create_particles',
        'fix',
        'compute',
        'stats',
        'dump',
        'run'
    ]

    def validate(self, content: str) -> Dict:
        """
        Validate SPARTA input content

        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "suggestions": List[str]
            }
        """
        errors = []
        warnings = []
        suggestions = []

        # Check required commands
        for cmd in self.REQUIRED_COMMANDS:
            if not self._has_command(content, cmd):
                errors.append(f"Missing required command: {cmd}")

        # Check command order
        order_issues = self._check_order(content)
        warnings.extend(order_issues)

        # Validate parameters
        param_errors = self._validate_parameters(content)
        errors.extend(param_errors)

        # Generate suggestions
        if errors:
            suggestions = self._generate_suggestions(errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions
        }

    def _validate_parameters(self, content: str) -> List[str]:
        """Validate parameter ranges"""
        errors = []

        # Check dimension
        dim_match = re.search(r'dimension\s+(\d+)', content)
        if dim_match:
            dim = int(dim_match.group(1))
            if dim not in [2, 3]:
                errors.append(f"Invalid dimension: {dim} (must be 2 or 3)")

        # Check temperature in global command
        temp_match = re.search(r'global\s+.*temp\s+([\d.e+-]+)', content)
        if temp_match:
            temp = float(temp_match.group(1))
            if temp <= 0:
                errors.append(f"Invalid temperature: {temp}K (must be > 0)")

        # Add more parameter checks...

        return errors
```

### Benefits

- **Higher Success Rate:** Validated inputs reduce failures from 30-40% to <5%
- **User Guidance:** Templates and tooltips guide users to correct configurations
- **SPARTA Manual Integration:** Best practices built into the form
- **Faster Workflow:** Less trial-and-error, fewer iterations needed

---

## 4. File Upload & Direct Run Workflow

### Current Problem

- Uploaded SPARTA files fail to run
- No validation before execution
- Unclear backend/frontend logic
- Can't configure run parameters
- No visibility into file contents

### Solution: Dual-Path Upload Flow

**Upload Modal Design:**

```
┌──────────────────────────────────────────┐
│ 📄 SPARTA输入文件已上传            [×]  │
├──────────────────────────────────────────┤
│ File: hypersonic_flow.sparta            │
│ ✅ Validation Passed                    │
│ 245 lines | 18 commands                 │
│                                          │
│ [Preview ▼]                              │
│ ┌────────────────────────────────────┐   │
│ │ dimension        3                 │   │
│ │ create_box       0 10 0 5 0 5     │   │
│ │ species          air.species N2 O2│   │
│ │ collide          vss air vss.air  │   │
│ │ ...                               │   │
│ └────────────────────────────────────┘   │
│                                          │
├──────────────────────────────────────────┤
│ Choose action:                           │
│                                          │
│ ○ 📚 Use as Reference                    │
│   Extract parameters to form for editing │
│                                          │
│ ● 🚀 Run Directly                        │
│   ┌──────────────────────────────────┐   │
│   │ ⚙️ Run Configuration             │   │
│   ├──────────────────────────────────┤   │
│   │ CPU Cores:    [4   ] (1-128)    │   │
│   │ Max Steps:    [1000] steps      │   │
│   │               (overrides run cmd)│   │
│   │ Memory Limit: [100 ] GB         │   │
│   │ Max Fix Attempts: [3] times     │   │
│   │                                 │   │
│   │ ⚠️ Note: Steps setting will     │   │
│   │ override the 'run' command in   │   │
│   │ the input file                  │   │
│   └──────────────────────────────────┘   │
│                                          │
├──────────────────────────────────────────┤
│    [Cancel]  [Use as Reference]  [🚀 Run]│
└──────────────────────────────────────────┘
```

### Workflow

**1. Upload & Validate:**
```
User selects .sparta file
    ↓
POST /api/dsmc/upload-input
    ↓
Backend: Parse content
    ↓
SpartaValidator.validate(content)
    ↓
┌─────────────┬──────────────┐
│   Valid?    │   Invalid?   │
└─────┬───────┴──────┬───────┘
      ↓              ↓
  Show Modal    Show Errors
                with Suggestions
```

**2. Reference Path:**
```
User clicks "Use as Reference"
    ↓
Extract parameters from file:
  - Temperature, pressure, velocity
  - Grid dimensions
  - Species and collision model
  - Timestep and steps
    ↓
Populate form fields
    ↓
User modifies as needed
    ↓
Click "Generate" → Creates new input file
```

**3. Direct Run Path:**
```
User selects "Run Directly"
    ↓
Configure run parameters:
  - CPU cores
  - Max steps (overrides 'run' command)
  - Memory limit
  - Max fix attempts
    ↓
Click "Run"
    ↓
POST /api/dsmc/run-uploaded {
  temp_id, num_cores, max_steps, ...
}
    ↓
Backend:
  1. Read temp file
  2. Override 'run' command with max_steps
  3. Create session
  4. Copy to workdir
  5. Execute SPARTA
    ↓
Frontend:
  1. Close modal
  2. Open control panel
  3. Show v1 iteration
  4. Stream logs
  5. Monitor progress
```

### Backend Implementation

**New Endpoint: `/api/dsmc/upload-input`**

```python
@app.route('/api/dsmc/upload-input', methods=['POST'])
def upload_sparta_input():
    """
    Upload and validate SPARTA input file
    """
    file = request.files['file']
    content = file.read().decode('utf-8')

    # Validate
    from sparta_validator import SpartaValidator
    validator = SpartaValidator()
    result = validator.validate(content)

    if result['valid']:
        # Extract parameters
        params = parse_sparta_parameters(content)

        # Save to temp location
        temp_id = str(uuid.uuid4())
        temp_file = UPLOADS_DIR / f"{temp_id}.sparta"
        with open(temp_file, 'w') as f:
            f.write(content)

        return jsonify({
            "valid": True,
            "temp_id": temp_id,
            "params": params,
            "preview": content[:500],
            "stats": {
                "lines": len(content.split('\n')),
                "commands": count_commands(content)
            }
        })
    else:
        return jsonify({
            "valid": False,
            "errors": result['errors'],
            "warnings": result['warnings'],
            "suggestions": result['suggestions']
        }), 400

def parse_sparta_parameters(content: str) -> Dict:
    """Extract parameters from SPARTA input file"""
    params = {}

    # Dimension
    dim_match = re.search(r'dimension\s+(\d+)', content)
    if dim_match:
        params['dimension'] = f"{dim_match.group(1)}d"

    # Temperature
    temp_match = re.search(r'global\s+.*temp\s+([\d.e+-]+)', content)
    if temp_match:
        params['temperature'] = float(temp_match.group(1))

    # Grid size
    grid_match = re.search(r'create_grid\s+(\d+)\s+(\d+)\s+(\d+)', content)
    if grid_match:
        params['grid_size'] = [
            int(grid_match.group(1)),
            int(grid_match.group(2)),
            int(grid_match.group(3))
        ]

    # Species
    species_match = re.search(r'species\s+([\w.]+)', content)
    if species_match:
        species_file = species_match.group(1)
        if 'N2' in species_file:
            params['gas'] = 'N2'
        elif 'air' in species_file:
            params['gas'] = 'Air'
        # Add more species detection...

    # Steps
    run_match = re.search(r'run\s+(\d+)', content)
    if run_match:
        params['num_steps'] = int(run_match.group(1))

    return params
```

**New Endpoint: `/api/dsmc/run-uploaded`**

```python
@app.route('/api/dsmc/run-uploaded', methods=['POST'])
def run_uploaded_input():
    """
    Run uploaded SPARTA file directly
    """
    data = request.get_json()
    temp_id = data['temp_id']
    num_cores = data.get('num_cores', 4)
    max_steps = data.get('max_steps', 1000)
    max_memory_gb = data.get('max_memory_gb', 100)
    max_fix_attempts = data.get('max_fix_attempts', 3)

    # Read temp file
    temp_file = UPLOADS_DIR / f"{temp_id}.sparta"
    if not temp_file.exists():
        return jsonify({"success": False, "error": "File not found"}), 404

    with open(temp_file, 'r') as f:
        content = f.read()

    # Override run command
    modified_content = override_run_steps(content, max_steps)

    # Create session
    agent = get_dsmc_agent()
    session_id = agent.create_session_from_input(
        input_content=modified_content,
        source='uploaded',
        filename=temp_file.stem
    )

    # Save input file
    session_dir = DSMC_SESSIONS_DIR / session_id
    input_path = session_dir / 'input.sparta'
    with open(input_path, 'w') as f:
        f.write(modified_content)

    # Run async
    def run_async():
        try:
            agent.run_simulation(
                session_id=session_id,
                num_cores=num_cores,
                max_memory_gb=max_memory_gb,
                max_fix_attempts=max_fix_attempts
            )
        except Exception as e:
            logger.error(f"Run failed: {e}")

    import threading
    threading.Thread(target=run_async, daemon=True).start()

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Simulation started"
    })

def override_run_steps(content: str, max_steps: int) -> str:
    """Override run command in input file"""
    pattern = r'^(\s*run\s+)\d+(.*)$'

    lines = []
    for line in content.split('\n'):
        match = re.match(pattern, line)
        if match:
            lines.append(f"{match.group(1)}{max_steps}{match.group(2)}")
        else:
            lines.append(line)

    return '\n'.join(lines)
```

### Benefits

- ✅ **Validation before execution** prevents runtime errors
- ✅ **Dual-path workflow** supports both reference and direct run use cases
- ✅ **Run parameter control** gives users full configuration power
- ✅ **Clear feedback** shows validation results and file preview
- ✅ **Integrated experience** seamlessly connects to control panel

---

## 5. Version Iteration Management

### Current Problems

- Version history hidden in backend
- No visual representation of iterations
- Can't easily switch between versions
- Unclear what changed between versions
- Control panel doesn't show iteration context

### Solution: Integrated Version Control

**Enhanced Control Panel with Version Management:**

```
┌──────────────────────────────────┐
│ 🚀 DSMC Control Panel      [×]  │
├──────────────────────────────────┤
│ 📊 Session Status                │
│ ┌────────────────────────────┐   │
│ │ ID: 20260115_143022        │   │
│ │ Status: ●Running (450/1K)  │   │
│ │ Current: v3 (AI优化网格)   │   │
│ └────────────────────────────┘   │
├──────────────────────────────────┤
│ 🔄 Version History               │
│ ┌────────────────────────────┐   │
│ │ ● v3 AI优化网格 (Current)  │   │
│ │   ⏳ Running... 450/1000   │   │
│ │   [View] [Compare] [Stop]  │   │
│ │                            │   │
│ │ ○ v2 修复碰撞模型          │   │
│ │   ❌ Failed | 3 fix attempts│   │
│ │   [Restore] [View] [Delete]│   │
│ │                            │   │
│ │ ○ v1 初始生成              │   │
│ │   ✅ Success | 1.8min      │   │
│ │   [Restore] [View] [Compare]│  │
│ │                            │   │
│ │ [+ Create New Iteration]   │   │
│ └────────────────────────────┘   │
├──────────────────────────────────┤
│ ▶️ Run Control                   │
│ CPU:    [4  ] | Steps: [1000]   │
│ Memory: [100] | Fixes: [3   ]   │
│                                  │
│ [▶️ Run] [⏹️ Stop] [🤖 AI Edit] │
│ [📄 Download] [📦 Pack]         │
├──────────────────────────────────┤
│ ⏱️ Stats                         │
│ Total: 4.3s | Current: 2.5s | v3│
├──────────────────────────────────┤
│ 📁 Work Directory                │
│ /home/.../20260115_143022  [📋] │
├──────────────────────────────────┤
│ 📂 Files (5)                     │
│ ├─ input.sparta (3.2KB)         │
│ ├─ log.sparta (128KB)           │
│ └─ ...                          │
├──────────────────────────────────┤
│ 📜 Log Monitor [Auto-scroll ✓]  │
│ Step 450 CPU = 0.023             │
│ Particles = 45892                │
└──────────────────────────────────┘
```

### Version History Component

**Features:**

1. **Visual Status Indicators:**
   - ● Current active iteration
   - ○ Historical iterations
   - ✅ Success (green)
   - ❌ Failed (red)
   - ⏳ Running (yellow, animated)
   - 🔄 Fixing (orange, animated)

2. **Iteration Information:**
   - Version number (v1, v2, v3...)
   - Description/tag
   - Status and timing
   - Success metrics (steps completed, particles, etc.)
   - Fix history count if failed

3. **Actions per Iteration:**
   - **View:** Show input file and results in modal
   - **Restore:** Make this version current (with confirmation)
   - **Compare:** Side-by-side diff with another version
   - **Delete:** Remove iteration (with confirmation)
   - **Stop:** Stop running simulation (only for active)

4. **Create New Iteration:**
   - Button at bottom of version list
   - Opens AI Edit modal
   - Creates v(n+1) based on current version

### Frontend Implementation

**New File: `static/components/version-manager.js`**

```javascript
class VersionManager {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.iterations = [];
        this.activeIterationId = null;
        this.container = document.getElementById('versionHistoryList');
    }

    async loadIterations() {
        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations`
            );
            const data = await response.json();

            this.iterations = data.iterations;
            this.activeIterationId = data.current_iteration_id;
            this.render();
        } catch (error) {
            console.error('Failed to load iterations:', error);
        }
    }

    render() {
        this.container.innerHTML = this.iterations.map((iter) => {
            const isActive = iter.iteration_id === this.activeIterationId;
            return `
                <div class="version-item ${isActive ? 'active' : ''}">
                    <div class="version-header">
                        <span class="version-indicator">
                            ${isActive ? '●' : '○'}
                        </span>
                        <span class="version-label">
                            v${iter.iteration_number}
                            ${iter.modification_description || '初始生成'}
                        </span>
                        ${isActive ? '<span class="badge-current">Current</span>' : ''}
                    </div>
                    <div class="version-status">
                        ${this.renderStatus(iter)}
                    </div>
                    <div class="version-actions">
                        ${this.renderActions(iter, isActive)}
                    </div>
                </div>
            `;
        }).join('');

        // Attach event listeners
        this.attachEventListeners();
    }

    renderStatus(iter) {
        const icons = {
            'completed': '✅',
            'failed': '❌',
            'running': '⏳',
            'fixing': '🔄',
            'pending': '⏸️'
        };

        const icon = icons[iter.status] || '❓';

        if (iter.status === 'completed') {
            const time = (iter.timing?.total_time || 0).toFixed(1);
            return `${icon} Success | ${time}s`;
        } else if (iter.status === 'failed') {
            const attempts = iter.fix_history?.length || 0;
            return `${icon} Failed | ${attempts} fix attempts`;
        } else if (iter.status === 'running') {
            const current = iter.run_result?.current_step || 0;
            const total = iter.run_result?.total_steps || 1000;
            return `${icon} Running... ${current}/${total}`;
        }

        return `${icon} ${iter.status}`;
    }

    renderActions(iter, isActive) {
        if (isActive) {
            if (iter.status === 'running') {
                return `
                    <button class="btn-version-action" data-action="view" data-id="${iter.iteration_id}">View</button>
                    <button class="btn-version-action" data-action="compare" data-id="${iter.iteration_id}">Compare</button>
                    <button class="btn-version-action danger" data-action="stop" data-id="${iter.iteration_id}">Stop</button>
                `;
            } else {
                return `
                    <button class="btn-version-action" data-action="view" data-id="${iter.iteration_id}">View</button>
                    <button class="btn-version-action" data-action="compare" data-id="${iter.iteration_id}">Compare</button>
                    <button class="btn-version-action danger" data-action="delete" data-id="${iter.iteration_id}">Delete</button>
                `;
            }
        } else {
            return `
                <button class="btn-version-action primary" data-action="restore" data-id="${iter.iteration_id}">Restore</button>
                <button class="btn-version-action" data-action="view" data-id="${iter.iteration_id}">View</button>
                <button class="btn-version-action danger" data-action="delete" data-id="${iter.iteration_id}">Delete</button>
            `;
        }
    }

    attachEventListeners() {
        const buttons = this.container.querySelectorAll('.btn-version-action');
        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                const iterationId = e.target.dataset.id;
                this.handleAction(action, iterationId);
            });
        });
    }

    async handleAction(action, iterationId) {
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
        }
    }

    async restoreVersion(iterationId) {
        if (!confirm('Restore to this version? Unsaved changes will be lost.')) {
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

                // Reload input file in main view
                await loadInputFileContent(this.sessionId);

                showStatus('Version restored successfully', 'success');
            } else {
                showStatus('Restore failed: ' + result.error, 'error');
            }
        } catch (error) {
            showStatus('Restore failed: ' + error.message, 'error');
        }
    }

    async viewIteration(iterationId) {
        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}`
            );
            const iteration = await response.json();

            showIterationDetailModal(iteration);
        } catch (error) {
            showStatus('Failed to load iteration: ' + error.message, 'error');
        }
    }

    async compareIterations(iterationId) {
        // Open compare selector modal
        showCompareModal(this.sessionId, iterationId, this.iterations);
    }

    async deleteIteration(iterationId) {
        if (!confirm('Delete this iteration? This cannot be undone.')) {
            return;
        }

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
            showStatus('Delete failed: ' + error.message, 'error');
        }
    }

    async stopIteration(iterationId) {
        if (!confirm('Stop this simulation?')) {
            return;
        }

        try {
            await fetch(`/api/dsmc/stop/${this.sessionId}`, { method: 'POST' });
            showStatus('Simulation stopped', 'info');
        } catch (error) {
            showStatus('Stop failed: ' + error.message, 'error');
        }
    }
}

// Global instance
let versionManager = null;

// Initialize when control panel opens
function showDSMCControlPanel(sessionId) {
    // ... existing code ...

    // Initialize version manager
    versionManager = new VersionManager(sessionId);
    versionManager.loadIterations();

    // Start real-time updates
    monitorVersionUpdates(sessionId);
}

// Real-time updates via SSE
function monitorVersionUpdates(sessionId) {
    const eventSource = new EventSource(`/api/dsmc/monitor/${sessionId}`);

    eventSource.addEventListener('iteration_updated', (e) => {
        const data = JSON.parse(e.data);
        if (versionManager) {
            versionManager.loadIterations();
        }
    });

    eventSource.addEventListener('status_change', (e) => {
        const data = JSON.parse(e.data);
        // Update session status card
        updateSessionStatusCard(data);
    });
}
```

### Backend Enhancements

**Updated Endpoint: `/api/dsmc/sessions/<session_id>/iterations`**

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations', methods=['GET'])
def get_iterations(session_id):
    """Get all iterations for a session"""
    agent = get_dsmc_agent()

    try:
        iterations = agent.get_iterations(session_id)

        # Get current iteration ID from metadata
        metadata_file = DSMC_SESSIONS_DIR / session_id / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        current_iteration_id = metadata.get('current_iteration_id')

        return jsonify({
            "success": True,
            "iterations": iterations,
            "current_iteration_id": current_iteration_id,
            "total": len(iterations)
        })
    except Exception as e:
        logger.error(f"Failed to get iterations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**New Endpoint: `/api/dsmc/sessions/<session_id>/iterations/<iteration_id>/restore`**

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations/<iteration_id>/restore', methods=['POST'])
def restore_iteration(session_id, iteration_id):
    """Restore to a specific iteration"""
    agent = get_dsmc_agent()

    try:
        result = agent.restore_iteration(session_id, iteration_id)

        # Update metadata
        metadata_file = DSMC_SESSIONS_DIR / session_id / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        metadata['current_iteration_id'] = iteration_id
        metadata['updated_at'] = datetime.now().isoformat()

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return jsonify({
            "success": True,
            "message": "Version restored",
            "iteration": result
        })
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**SSE Event Emission:**

```python
# In sparta_runner.py or dsmc_agent.py
def emit_sse_event(session_id, event_type, data):
    """Emit SSE event for real-time updates"""
    # This would be integrated with your existing SSE mechanism
    sse_data = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

    # Send to all connected clients monitoring this session
    # Implementation depends on your SSE setup

# Usage examples:
emit_sse_event(session_id, 'iteration_updated', {
    "iteration_id": iteration_id,
    "status": "completed"
})

emit_sse_event(session_id, 'status_change', {
    "status": "running",
    "current_step": 450,
    "total_steps": 1000
})
```

### Control Panel Integration

**Persistent Display:**
- Control panel opens when:
  1. DSMC parameter form generates input file
  2. User uploads and runs SPARTA file directly
  3. User clicks existing session in chat history
- Control panel stays visible until:
  1. User explicitly closes it (× button)
  2. User starts new conversation
  3. Page refresh (can be restored from localStorage)

**Session Context:**
- Session status card always shows:
  - Session ID and creation time
  - Current status (ready/generating/running/completed/failed)
  - Real-time progress (steps/particles)
  - Current active iteration version

**Version History Always Visible:**
- Shows all iterations in chronological order
- Real-time status updates via SSE
- Quick actions for each version
- Scroll if more than 5 iterations

### Benefits

- ✅ **Full visibility** into iteration history
- ✅ **One-click restore** to any previous version
- ✅ **Real-time updates** via SSE
- ✅ **Integrated workflow** - all controls in one place
- ✅ **Persistent panel** - no context switching
- ✅ **Version comparison** - understand what changed
- ✅ **Smooth iteration flow** - create/run/analyze/iterate

---

## 6. Settings & Configuration Management

### Problem

- API configuration hardcoded in .env file
- Requires manual editing and server restart
- No UI for changing settings
- Users can't test API connection
- Theme preference not saved

### Solution: Runtime Configuration Panel

**Settings Modal:**

```
┌────────────────────────────────────────┐
│ ⚙️ Settings                      [×]  │
├────────────────────────────────────────┤
│ 🔑 API Configuration                   │
│                                        │
│ API URL:                               │
│ [https://api.mjdjourney.cn/v1      ]  │
│                                        │
│ API Key:                               │
│ [sk-LGxr...E12d] [👁️] [Test Connection]│
│ ✅ Connected (Last tested: 2s ago)     │
│                                        │
│ Default Model:                         │
│ [claude-opus-4-5-20251101 ▼]          │
│ ├─ claude-opus-4-5-20251101            │
│ ├─ gemini-3-pro-preview                │
│ └─ deepseek-v3-250324                  │
│                                        │
├────────────────────────────────────────┤
│ 🎨 Appearance                          │
│                                        │
│ Theme:                                 │
│ ● Dark  ○ Light  ○ Auto (System)      │
│                                        │
│ Font Size:                             │
│ [Medium ▼] (Small/Medium/Large)        │
│                                        │
│ Animation:                             │
│ [Enabled ▼] (Enabled/Reduced/Disabled) │
│                                        │
├────────────────────────────────────────┤
│ 🚀 DSMC Defaults                       │
│                                        │
│ Default CPU Cores:   [4    ] (1-128)  │
│ Default Max Steps:   [1000 ]          │
│ Default Memory (GB): [100  ]          │
│ Default Fix Attempts:[3    ]          │
│                                        │
│ Atmospheric Model:                     │
│ [NRLMSISE-00 ▼]                        │
│                                        │
│ Work Directory:                        │
│ [/home/.../dsmc_sessions] [📁 Browse] │
│                                        │
├────────────────────────────────────────┤
│ 💾 Data & Storage                      │
│                                        │
│ Auto-save sessions:    [✓]             │
│ Keep session history:  [30] days       │
│ Max log file size:     [100] MB        │
│                                        │
│ [Clear All Sessions] [Export Settings] │
│                                        │
├────────────────────────────────────────┤
│           [Cancel]  [Save Settings]    │
└────────────────────────────────────────┘
```

### Implementation

**New File: `agent-dsmc/config_manager.py`**

```python
import os
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv, set_key

class ConfigManager:
    """Manage runtime configuration"""

    def __init__(self):
        self.env_file = Path('.env')
        self.settings_file = Path('data/settings.json')
        self.config = {}
        self.load()

    def load(self):
        """Load configuration from .env and settings.json"""
        load_dotenv()

        # Load from environment
        self.config = {
            'api_url': os.getenv('API_URL', 'https://api.mjdjourney.cn/v1'),
            'api_key': os.getenv('API_KEY', ''),
            'llm_model': os.getenv('LLM_MODEL', 'claude-opus-4-5-20251101'),
            'port': int(os.getenv('PORT', 21000)),
            'models': os.getenv('MODELS', '').split(',')
        }

        # Load user preferences from settings.json
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                user_settings = json.load(f)
                self.config.update(user_settings)

    def save(self, updates: Dict[str, Any]):
        """Save configuration updates"""
        # Update in-memory config
        self.config.update(updates)

        # Save to .env file (API config)
        env_keys = ['API_URL', 'API_KEY', 'LLM_MODEL', 'PORT', 'MODELS']
        for key in env_keys:
            if key.lower() in updates:
                value = updates[key.lower()]
                if key == 'MODELS' and isinstance(value, list):
                    value = ','.join(value)
                set_key(self.env_file, key, str(value))

        # Save to settings.json (user preferences)
        user_settings = {
            k: v for k, v in self.config.items()
            if k not in ['api_url', 'api_key', 'llm_model', 'port', 'models']
        }

        self.settings_file.parent.mkdir(exist_ok=True)
        with open(self.settings_file, 'w') as f:
            json.dump(user_settings, f, indent=2)

    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def update(self, **kwargs):
        """Update configuration at runtime"""
        self.config.update(kwargs)

    def test_api_connection(self) -> Dict:
        """Test API connection"""
        import requests

        try:
            response = requests.post(
                f"{self.config['api_url']}/chat/completions",
                headers={
                    'Authorization': f"Bearer {self.config['api_key']}",
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.config['llm_model'],
                    'messages': [{'role': 'user', 'content': 'test'}],
                    'max_tokens': 5
                },
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'latency_ms': response.elapsed.total_seconds() * 1000
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# Global instance
config_manager = ConfigManager()
```

**Backend Endpoints:**

```python
# In app.py

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    from config_manager import config_manager

    # Don't expose full API key
    safe_config = config_manager.config.copy()
    if safe_config.get('api_key'):
        key = safe_config['api_key']
        safe_config['api_key'] = f"{key[:8]}...{key[-4:]}"

    return jsonify(safe_config)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    from config_manager import config_manager

    data = request.get_json()

    try:
        config_manager.save(data)
        return jsonify({
            "success": True,
            "message": "Settings saved"
        })
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/settings/test-connection', methods=['POST'])
def test_connection():
    """Test API connection"""
    from config_manager import config_manager

    result = config_manager.test_api_connection()
    return jsonify(result)
```

**Frontend Component:**

```javascript
// Settings panel management
class SettingsPanel {
    constructor() {
        this.modal = document.getElementById('settingsModal');
        this.settings = {};
    }

    async load() {
        const response = await fetch('/api/settings');
        this.settings = await response.json();
        this.populate();
    }

    populate() {
        document.getElementById('apiUrl').value = this.settings.api_url || '';
        document.getElementById('apiKey').value = this.settings.api_key || '';
        document.getElementById('llmModel').value = this.settings.llm_model || '';

        // Theme
        const theme = this.settings.theme || 'dark';
        document.querySelector(`input[name="theme"][value="${theme}"]`).checked = true;

        // DSMC defaults
        document.getElementById('defaultCores').value = this.settings.default_cores || 4;
        document.getElementById('defaultSteps').value = this.settings.default_steps || 1000;
        document.getElementById('defaultMemory').value = this.settings.default_memory_gb || 100;
        document.getElementById('defaultFixAttempts').value = this.settings.default_fix_attempts || 3;
    }

    async save() {
        const updates = {
            api_url: document.getElementById('apiUrl').value,
            api_key: document.getElementById('apiKey').value,
            llm_model: document.getElementById('llmModel').value,
            theme: document.querySelector('input[name="theme"]:checked').value,
            default_cores: parseInt(document.getElementById('defaultCores').value),
            default_steps: parseInt(document.getElementById('defaultSteps').value),
            default_memory_gb: parseInt(document.getElementById('defaultMemory').value),
            default_fix_attempts: parseInt(document.getElementById('defaultFixAttempts').value)
        };

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(updates)
        });

        const result = await response.json();

        if (result.success) {
            showStatus('Settings saved successfully', 'success');
            this.close();

            // Apply theme immediately
            ThemeManager.setTheme(updates.theme);
        } else {
            showStatus('Failed to save: ' + result.error, 'error');
        }
    }

    async testConnection() {
        const btn = document.getElementById('testConnectionBtn');
        btn.disabled = true;
        btn.textContent = 'Testing...';

        try {
            const response = await fetch('/api/settings/test-connection', {
                method: 'POST'
            });
            const result = await response.json();

            const indicator = document.getElementById('connectionIndicator');
            if (result.success) {
                indicator.innerHTML = `✅ Connected (${result.latency_ms.toFixed(0)}ms)`;
                indicator.className = 'connection-indicator success';
            } else {
                indicator.innerHTML = `❌ Failed: ${result.error}`;
                indicator.className = 'connection-indicator error';
            }
        } finally {
            btn.disabled = false;
            btn.textContent = 'Test Connection';
        }
    }

    show() {
        this.load();
        this.modal.classList.remove('hidden');
    }

    close() {
        this.modal.classList.add('hidden');
    }
}

// Global instance
const settingsPanel = new SettingsPanel();

// Settings button in header
document.getElementById('settingsBtn').addEventListener('click', () => {
    settingsPanel.show();
});
```

### Benefits

- ✅ **No restart needed** - changes apply immediately
- ✅ **User-friendly UI** - no manual .env editing
- ✅ **Connection testing** - verify API before saving
- ✅ **Preference persistence** - theme and defaults saved
- ✅ **Security** - API key masked in UI
- ✅ **Flexible configuration** - all settings in one place

---

## 7. Implementation Roadmap

### Phase 1: UI Foundation (3-4 days)

**Tasks:**
1. Create theme system CSS variables
2. Implement theme toggle component
3. Apply new blue/teal color scheme
4. Redesign chat message layout (right-align user, adaptive sizing)
5. Create settings modal UI

**Deliverables:**
- `static/themes.css`
- Updated `static/style.css`
- Theme toggle in header
- Settings panel UI (no backend yet)

**Testing:**
- Theme switching works smoothly
- All colors consistent across components
- Chat messages display correctly in both themes
- Responsive on different screen sizes

---

### Phase 2: DSMC Form Enhancement (4-5 days)

**Tasks:**
1. Design template preset system
2. Implement NRLMSISE-00 atmospheric model calculations
3. Build parameter validation logic
4. Add SPARTA manual tooltip integration
5. Create form field dependencies (auto-calculate)
6. Build `sparta_validator.py` module

**Deliverables:**
- Enhanced parameter form UI
- `agent-dsmc/sparta_validator.py`
- `agent-dsmc/atmospheric_models.py`
- Validation error display components

**Testing:**
- All templates load correct parameters
- Atmospheric model calculations accurate
- Validation catches common errors
- Tooltips show relevant manual content
- Dependencies update correctly (e.g., altitude → T/P/ρ)

---

### Phase 3: File Upload & Validation (3 days)

**Tasks:**
1. Create upload modal with dual-path UI
2. Implement file validation endpoint
3. Build parameter extraction logic
4. Add run configuration inputs
5. Implement "Run Directly" flow
6. Connect to control panel

**Deliverables:**
- Updated upload modal
- `/api/dsmc/upload-input` endpoint
- `/api/dsmc/run-uploaded` endpoint
- Parameter extraction functions

**Testing:**
- Upload validates SPARTA files correctly
- Errors shown with helpful suggestions
- Reference path populates form
- Direct run creates session and executes
- Run parameters override file settings
- Control panel opens and shows progress

---

### Phase 4: Version Control Integration (4 days)

**Tasks:**
1. Build version history component
2. Implement restore/compare/delete actions
3. Add real-time SSE updates for iterations
4. Integrate with control panel
5. Create iteration detail modal
6. Add version comparison view

**Deliverables:**
- `static/components/version-manager.js`
- Enhanced control panel with version section
- `/api/dsmc/sessions/<id>/iterations/<id>/restore` endpoint
- SSE event emission for iteration updates
- Iteration detail modal
- Version comparison UI

**Testing:**
- All iterations display correctly
- Restore switches to previous version
- Real-time status updates work
- Compare shows diffs accurately
- Delete removes iteration
- Control panel stays synchronized

---

### Phase 5: Configuration Management (2 days)

**Tasks:**
1. Create `config_manager.py`
2. Implement settings save/load
3. Build API connection testing
4. Add settings modal backend
5. Integrate with existing code

**Deliverables:**
- `agent-dsmc/config_manager.py`
- `/api/settings` GET/POST endpoints
- `/api/settings/test-connection` endpoint
- Settings persistence to .env and settings.json

**Testing:**
- Settings save and load correctly
- API connection test works
- Changes apply without restart
- Theme preference persists
- DSMC defaults propagate to form

---

### Phase 6: Integration & Polish (2-3 days)

**Tasks:**
1. Integration testing across all features
2. Bug fixes and edge case handling
3. Performance optimization
4. Documentation updates (README)
5. User acceptance testing

**Deliverables:**
- Integrated system working end-to-end
- Bug fix report
- Updated README.md
- User guide for new features

**Testing Checklist:**
- [ ] Complete workflow: Form → Generate → Run → Iterate
- [ ] Upload workflow: Upload → Validate → Run → Monitor
- [ ] Version management: Create → Run → Restore → Compare
- [ ] Theme switching during active simulation
- [ ] Settings changes apply immediately
- [ ] All validations catch errors
- [ ] Real-time updates work reliably
- [ ] Control panel integrates with all workflows

---

### Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| 1. UI Foundation | 3-4 days | None |
| 2. DSMC Form | 4-5 days | Phase 1 (themes) |
| 3. File Upload | 3 days | Phase 2 (validation) |
| 4. Version Control | 4 days | Phase 3 (sessions) |
| 5. Config Management | 2 days | None (parallel) |
| 6. Integration & Polish | 2-3 days | All phases |

**Total: ~14-18 days**

---

## 8. Risk Assessment & Mitigation

### High-Risk Areas

**1. Environment Variable Hot Reload**
- **Risk:** Modifying .env at runtime may cause instability
- **Mitigation:**
  - Use ConfigManager class to handle updates safely
  - Validate all changes before applying
  - Keep in-memory cache synchronized
  - Add rollback mechanism if update fails

**2. Run Parameter Override**
- **Risk:** Overriding 'run' command in uploaded files may break logic
- **Mitigation:**
  - Use regex-based replacement with careful testing
  - Preserve original file in version history
  - Show clear warning to user about override
  - Allow user to disable override if needed

**3. Real-Time Version Updates**
- **Risk:** SSE events may get lost or arrive out of order
- **Mitigation:**
  - Add sequence numbers to events
  - Implement client-side reconciliation
  - Fall back to polling if SSE fails
  - Add reconnection logic with exponential backoff

### Medium-Risk Areas

**4. Form Validation Complexity**
- **Risk:** SPARTA has many edge cases; validation may be incomplete
- **Mitigation:**
  - Start with common cases, expand over time
  - Allow "expert mode" to bypass validation
  - Log validation misses for future improvements
  - Provide manual override option

**5. File Upload State Management**
- **Risk:** Complex modal state may have edge cases
- **Mitigation:**
  - Use clear state machine pattern
  - Clean up temp files after timeout
  - Add comprehensive error handling
  - Test all paths thoroughly

### Low-Risk Areas

**6. Theme System**
- **Risk:** CSS variables not supported in old browsers
- **Mitigation:** Target modern browsers only (documented)

**7. Chat Message Layout**
- **Risk:** Long code blocks may break layout
- **Mitigation:** Use overflow-x: auto, test with real content

---

## 9. Testing Strategy

### Unit Tests

**Backend:**
- `SpartaValidator.validate()` - various input files
- `ConfigManager.save()` - config persistence
- `override_run_steps()` - parameter override
- `parse_sparta_parameters()` - extraction logic
- Atmospheric model calculations (NRLMSISE-00, US76, ISA)

**Frontend:**
- `VersionManager.render()` - DOM output
- `ThemeManager.toggle()` - theme switching
- `SettingsPanel.save()` - form validation

### Integration Tests

**Complete Workflows:**
1. **Form Generation Flow:**
   - Select template → Fill form → Validate → Generate → Run → Monitor
2. **Upload Direct Run:**
   - Upload file → Validate → Configure params → Run → Control panel → Logs
3. **Version Iteration:**
   - Generate v1 → Run → AI Edit → Create v2 → Run → Compare → Restore v1
4. **Settings Change:**
   - Open settings → Change API key → Test connection → Save → Verify reload

### User Acceptance Tests

**Scenarios:**
1. New user creates first simulation using Hypersonic template
2. Advanced user uploads custom SPARTA file and runs directly
3. User switches theme during active simulation
4. User creates 5 iterations, compares versions, restores v2
5. User changes API settings and continues working without restart

---

## 10. Success Metrics

### Quantitative

- **SPARTA script success rate:** 30-40% → 95%+
- **Time to first successful run:** ~10 min → ~3 min
- **User iterations per session:** 2-3 → 5-7
- **Error recovery time:** 5-10 min → <1 min
- **Settings change time:** 2-3 min (manual) → 30 sec (UI)

### Qualitative

- **Visual appeal:** "Outdated" → "Modern and professional"
- **User confidence:** Low → High (validated inputs)
- **Workflow smoothness:** Fragmented → Integrated
- **Version visibility:** Hidden → Clear and accessible
- **Configuration ease:** Manual → User-friendly UI

---

## 11. Future Enhancements

**Not in Current Scope (Post-v2.0):**

1. **Collaborative Features:**
   - Share sessions with other users
   - Export/import configurations
   - Public template gallery

2. **Advanced Visualizations:**
   - 3D flow field rendering
   - Interactive ParaView integration
   - Real-time particle animation

3. **AI Improvements:**
   - Learn from successful configurations
   - Auto-suggest optimizations
   - Predict simulation outcomes

4. **Performance Monitoring:**
   - Resource usage graphs
   - Performance profiling
   - Bottleneck detection

5. **Mobile Support:**
   - Responsive design for tablets
   - Mobile-optimized controls
   - Touch gesture support

---

## Appendix A: Color Palette Reference

### Dark Theme
```css
/* Backgrounds */
--bg-primary: #0f172a
--bg-secondary: #1e293b
--bg-tertiary: #334155
--bg-card: rgba(30, 41, 59, 0.9)

/* Accents */
--accent-primary: #06b6d4
--accent-secondary: #0891b2
--accent-blue: #3b82f6

/* Text */
--text-primary: #f8fafc
--text-secondary: #cbd5e1
--text-muted: #64748b

/* Status */
--success: #10b981
--warning: #f59e0b
--error: #ef4444
--info: #3b82f6

/* Borders */
--border: rgba(6, 182, 212, 0.3)
--border-glow: rgba(6, 182, 212, 0.5)
```

### Light Theme
```css
/* Backgrounds */
--bg-primary: #ffffff
--bg-secondary: #f8fafc
--bg-tertiary: #e2e8f0
--bg-card: rgba(255, 255, 255, 0.95)

/* Accents */
--accent-primary: #0891b2
--accent-secondary: #0e7490
--accent-blue: #2563eb

/* Text */
--text-primary: #0f172a
--text-secondary: #475569
--text-muted: #94a3b8

/* Status */
--success: #059669
--warning: #d97706
--error: #dc2626
--info: #1d4ed8

/* Borders */
--border: rgba(8, 145, 178, 0.3)
--border-glow: rgba(8, 145, 178, 0.5)
```

---

## Appendix B: File Structure Changes

**New Files:**
```
agent_code/
├── docs/
│   └── plans/
│       └── 2026-01-15-sparta-ui-improvements-design.md
├── agent-dsmc/
│   ├── sparta_validator.py
│   ├── atmospheric_models.py
│   └── config_manager.py
└── llm-chat-app/
    ├── data/
    │   └── settings.json
    ├── static/
    │   ├── themes.css
    │   └── components/
    │       ├── version-manager.js
    │       └── settings-panel.js
    └── templates/
        └── components/
            ├── settings-modal.html
            └── version-history.html
```

**Modified Files:**
```
agent_code/
├── agent-dsmc/
│   └── dsmc_agent.py (iteration management)
└── llm-chat-app/
    ├── app.py (new endpoints)
    ├── static/
    │   ├── style.css (theme system)
    │   └── app.js (version manager, upload flow)
    └── templates/
        └── index.html (form layout, control panel)
```

---

## Conclusion

This comprehensive design addresses all 8 improvement areas:

1. ✅ Modern blue/teal color scheme
2. ✅ Dark/light theme system
3. ✅ Runtime configuration management
4. ✅ Robust DSMC parameter form
5. ✅ NRLMSISE-00 atmospheric model
6. ✅ File upload with direct run
7. ✅ Integrated version control
8. ✅ Optimized chat UI

**Key Benefits:**
- Professional, modern appearance
- Significantly improved reliability (>95% success rate)
- Streamlined, integrated workflow
- Full visibility and control for users
- Flexible configuration without restarts

**Ready for implementation approval and detailed planning.**
