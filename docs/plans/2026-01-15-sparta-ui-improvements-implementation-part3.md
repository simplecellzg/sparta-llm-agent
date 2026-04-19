# SPARTA UI Improvements v2.0 - Implementation Plan (Part 3)

## Continuation from Part 2

This is Part 3 of the implementation plan, continuing with Phase 4 tasks 4.2-4.5.

---

## Phase 4: Version Control & Iteration Management (Continued)

### Task 4.2: Add Backend Iteration Management Endpoints

**Files:**
- Modify: `llm-chat-app/app.py` (add iteration endpoints after existing DSMC endpoints)

**Step 1: Write test for GET iterations endpoint**

Create `tests/test_iteration_api.py`:

```python
import pytest
from llm-chat-app.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_iterations_returns_list(client):
    """Test GET /api/dsmc/sessions/<id>/iterations returns iteration list"""
    # Setup: Create a session with iterations
    session_id = 'test-session-123'
    # Assume session exists with 2 iterations

    response = client.get(f'/api/dsmc/sessions/{session_id}/iterations')

    assert response.status_code == 200
    data = response.get_json()
    assert 'iterations' in data
    assert 'current_iteration_id' in data
    assert isinstance(data['iterations'], list)
    assert len(data['iterations']) >= 0

def test_get_iterations_nonexistent_session(client):
    """Test GET iterations for non-existent session returns 404"""
    response = client.get('/api/dsmc/sessions/nonexistent/iterations')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_iteration_api.py::test_get_iterations_returns_list -v`

Expected: `FAIL` - endpoint not implemented

**Step 3: Implement GET iterations endpoint**

Add to `llm-chat-app/app.py` (after existing `/api/dsmc/run` endpoint):

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations', methods=['GET'])
def get_session_iterations(session_id):
    """Get all iterations for a session"""
    try:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            return jsonify({"error": "Session not found"}), 404

        # Load session metadata
        metadata_file = session_dir / 'metadata.json'
        if not metadata_file.exists():
            return jsonify({"error": "Session metadata not found"}), 404

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        iterations = metadata.get('iterations', [])
        current_iteration_id = metadata.get('current_iteration_id', None)

        # Sort iterations by number (newest first)
        iterations_sorted = sorted(
            iterations,
            key=lambda x: x.get('iteration_number', 0),
            reverse=True
        )

        return jsonify({
            "iterations": iterations_sorted,
            "current_iteration_id": current_iteration_id,
            "total": len(iterations_sorted)
        })

    except Exception as e:
        logger.error(f"Error getting iterations for session {session_id}: {e}")
        return jsonify({"error": str(e)}), 500
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_iteration_api.py::test_get_iterations_returns_list -v`

Expected: `PASS`

Run: `pytest tests/test_iteration_api.py::test_get_iterations_nonexistent_session -v`

Expected: `PASS`

**Step 5: Write test for GET single iteration endpoint**

Add to `tests/test_iteration_api.py`:

```python
def test_get_single_iteration(client):
    """Test GET /api/dsmc/sessions/<id>/iterations/<iter_id> returns iteration details"""
    session_id = 'test-session-123'
    iteration_id = 'iter-1'

    response = client.get(f'/api/dsmc/sessions/{session_id}/iterations/{iteration_id}')

    assert response.status_code == 200
    data = response.get_json()
    assert 'iteration_id' in data
    assert data['iteration_id'] == iteration_id
    assert 'iteration_number' in data
    assert 'input_file_content' in data
    assert 'run_result' in data or 'error_log' in data

def test_get_iteration_not_found(client):
    """Test GET iteration that doesn't exist returns 404"""
    response = client.get('/api/dsmc/sessions/test-session/iterations/nonexistent')
    assert response.status_code == 404
```

Run: `pytest tests/test_iteration_api.py::test_get_single_iteration -v`

Expected: `FAIL` - endpoint not implemented

**Step 6: Implement GET single iteration endpoint**

Add to `llm-chat-app/app.py`:

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations/<iteration_id>', methods=['GET'])
def get_iteration_details(session_id, iteration_id):
    """Get detailed information about a specific iteration"""
    try:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            return jsonify({"error": "Session not found"}), 404

        # Load session metadata
        metadata_file = session_dir / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Find the iteration
        iteration = None
        for iter_data in metadata.get('iterations', []):
            if iter_data.get('iteration_id') == iteration_id:
                iteration = iter_data.copy()
                break

        if not iteration:
            return jsonify({"error": "Iteration not found"}), 404

        # Load input file content
        input_file = session_dir / f"{iteration_id}_input.sparta"
        if input_file.exists():
            iteration['input_file_content'] = input_file.read_text()

        # Load output files if available
        output_file = session_dir / f"{iteration_id}_output.log"
        if output_file.exists():
            iteration['output_log'] = output_file.read_text()

        error_file = session_dir / f"{iteration_id}_error.log"
        if error_file.exists():
            iteration['error_log'] = error_file.read_text()

        return jsonify(iteration)

    except Exception as e:
        logger.error(f"Error getting iteration {iteration_id}: {e}")
        return jsonify({"error": str(e)}), 500
```

Run: `pytest tests/test_iteration_api.py::test_get_single_iteration -v`

Expected: `PASS`

**Step 7: Write test for POST restore iteration endpoint**

Add to `tests/test_iteration_api.py`:

```python
def test_restore_iteration(client):
    """Test POST /api/dsmc/sessions/<id>/iterations/<iter_id>/restore"""
    session_id = 'test-session-123'
    iteration_id = 'iter-1'

    response = client.post(f'/api/dsmc/sessions/{session_id}/iterations/{iteration_id}/restore')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['current_iteration_id'] == iteration_id
    assert 'message' in data

def test_restore_iteration_while_running(client):
    """Test restore fails when simulation is running"""
    # Assume current iteration is running
    response = client.post('/api/dsmc/sessions/test-session/iterations/iter-1/restore')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'running' in data['error'].lower()
```

Run: `pytest tests/test_iteration_api.py::test_restore_iteration -v`

Expected: `FAIL`

**Step 8: Implement POST restore iteration endpoint**

Add to `llm-chat-app/app.py`:

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations/<iteration_id>/restore', methods=['POST'])
def restore_iteration(session_id, iteration_id):
    """Restore a previous iteration as the current active iteration"""
    try:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            return jsonify({"error": "Session not found"}), 404

        # Load session metadata
        metadata_file = session_dir / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Check if current iteration is running
        current_iter_id = metadata.get('current_iteration_id')
        if current_iter_id:
            for iter_data in metadata.get('iterations', []):
                if iter_data['iteration_id'] == current_iter_id:
                    if iter_data.get('status') in ['running', 'fixing']:
                        return jsonify({
                            "error": "Cannot restore while simulation is running. Please stop current iteration first."
                        }), 400

        # Find the iteration to restore
        target_iteration = None
        for iter_data in metadata.get('iterations', []):
            if iter_data['iteration_id'] == iteration_id:
                target_iteration = iter_data
                break

        if not target_iteration:
            return jsonify({"error": "Iteration not found"}), 404

        # Update current iteration ID
        metadata['current_iteration_id'] = iteration_id

        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Copy iteration files to current
        input_file = session_dir / f"{iteration_id}_input.sparta"
        if input_file.exists():
            current_input = session_dir / 'current_input.sparta'
            import shutil
            shutil.copy(input_file, current_input)

        return jsonify({
            "success": True,
            "current_iteration_id": iteration_id,
            "message": f"Restored to iteration {target_iteration.get('iteration_number', 'N/A')}"
        })

    except Exception as e:
        logger.error(f"Error restoring iteration {iteration_id}: {e}")
        return jsonify({"error": str(e)}), 500
```

Run: `pytest tests/test_iteration_api.py::test_restore_iteration -v`

Expected: `PASS`

**Step 9: Write test for DELETE iteration endpoint**

Add to `tests/test_iteration_api.py`:

```python
def test_delete_iteration(client):
    """Test DELETE /api/dsmc/sessions/<id>/iterations/<iter_id>"""
    session_id = 'test-session-123'
    iteration_id = 'iter-old'

    response = client.delete(f'/api/dsmc/sessions/{session_id}/iterations/{iteration_id}')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'deleted' in data['message'].lower()

def test_delete_current_iteration_fails(client):
    """Test cannot delete current active iteration"""
    response = client.delete('/api/dsmc/sessions/test-session/iterations/current-iter')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
```

Run: `pytest tests/test_iteration_api.py::test_delete_iteration -v`

Expected: `FAIL`

**Step 10: Implement DELETE iteration endpoint**

Add to `llm-chat-app/app.py`:

```python
@app.route('/api/dsmc/sessions/<session_id>/iterations/<iteration_id>', methods=['DELETE'])
def delete_iteration(session_id, iteration_id):
    """Delete an iteration (cannot delete current active iteration)"""
    try:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            return jsonify({"error": "Session not found"}), 404

        # Load session metadata
        metadata_file = session_dir / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Check if trying to delete current iteration
        if metadata.get('current_iteration_id') == iteration_id:
            return jsonify({
                "error": "Cannot delete the current active iteration. Please restore a different iteration first."
            }), 400

        # Find and remove the iteration
        iterations = metadata.get('iterations', [])
        iteration_index = None
        for i, iter_data in enumerate(iterations):
            if iter_data['iteration_id'] == iteration_id:
                iteration_index = i
                break

        if iteration_index is None:
            return jsonify({"error": "Iteration not found"}), 404

        # Remove from metadata
        deleted_iter = iterations.pop(iteration_index)

        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Delete associated files
        files_to_delete = [
            session_dir / f"{iteration_id}_input.sparta",
            session_dir / f"{iteration_id}_output.log",
            session_dir / f"{iteration_id}_error.log",
            session_dir / f"{iteration_id}_stats.json"
        ]

        deleted_files = []
        for file_path in files_to_delete:
            if file_path.exists():
                file_path.unlink()
                deleted_files.append(file_path.name)

        return jsonify({
            "success": True,
            "message": f"Deleted iteration {deleted_iter.get('iteration_number', 'N/A')}",
            "deleted_files": deleted_files
        })

    except Exception as e:
        logger.error(f"Error deleting iteration {iteration_id}: {e}")
        return jsonify({"error": str(e)}), 500
```

Run: `pytest tests/test_iteration_api.py -v`

Expected: All tests `PASS`

**Step 11: Manual verification**

Start server: `cd llm-chat-app && python app.py`

Test with curl:

```bash
# Get iterations list
curl http://localhost:21000/api/dsmc/sessions/test-session-123/iterations

# Expected: {"iterations": [...], "current_iteration_id": "...", "total": N}

# Get single iteration
curl http://localhost:21000/api/dsmc/sessions/test-session-123/iterations/iter-1

# Expected: {"iteration_id": "iter-1", "iteration_number": 1, "input_file_content": "...", ...}

# Restore iteration
curl -X POST http://localhost:21000/api/dsmc/sessions/test-session-123/iterations/iter-1/restore

# Expected: {"success": true, "current_iteration_id": "iter-1", "message": "Restored to iteration 1"}

# Delete iteration (non-current)
curl -X DELETE http://localhost:21000/api/dsmc/sessions/test-session-123/iterations/iter-2

# Expected: {"success": true, "message": "Deleted iteration 2", "deleted_files": [...]}
```

**Step 12: Commit**

```bash
git add llm-chat-app/app.py
git add tests/test_iteration_api.py
git commit -m "feat(api): add iteration management endpoints

- GET /api/dsmc/sessions/<id>/iterations - list all iterations
- GET /api/dsmc/sessions/<id>/iterations/<iter_id> - get iteration details
- POST /api/dsmc/sessions/<id>/iterations/<iter_id>/restore - restore iteration
- DELETE /api/dsmc/sessions/<id>/iterations/<iter_id> - delete iteration

Features:
- Load iteration data from session metadata
- Include input file content and logs in details
- Prevent restoring while simulation running
- Prevent deleting current active iteration
- Automatic file cleanup on deletion
- Error handling for not found cases

Tests:
- Full test coverage with pytest
- Happy path and error cases
- Running state protection

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 4.3: Integrate VersionManager with Control Panel

**Files:**
- Modify: `llm-chat-app/static/app.js` (wire VersionManager to existing code)
- Modify: `llm-chat-app/templates/index.html` (add version history section to control panel)
- Modify: `llm-chat-app/static/style.css` (add version history styles)

**Step 1: Add version history section to control panel HTML**

Modify `llm-chat-app/templates/index.html` (inside `#dsmcControlPanel`, after the "Log Monitoring" section):

```html
            <!-- Version History Section - Add after Log Monitoring section -->
            <div class="control-section version-section" id="versionSection">
                <div class="section-header">
                    <h5>📚 版本历史</h5>
                    <span id="versionCount" class="badge">0</span>
                </div>
                <div id="versionHistoryList" class="version-history-list">
                    <!-- Version items will be rendered by VersionManager -->
                </div>
            </div>
        </aside>
```

**Step 2: Add version history styles**

Add to `llm-chat-app/static/style.css`:

```css
/* Version History Section */
.version-section {
    margin-top: 12px;
}

.version-history-list {
    max-height: 300px;
    overflow-y: auto;
    padding: 8px 0;
}

.version-item {
    padding: 12px;
    margin-bottom: 8px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    transition: all 0.2s ease;
}

.version-item:hover {
    border-color: var(--accent-primary);
    box-shadow: 0 2px 8px rgba(6, 182, 212, 0.1);
}

.version-item.active {
    border-color: var(--accent-primary);
    background: linear-gradient(135deg,
        rgba(6, 182, 212, 0.05),
        rgba(8, 145, 178, 0.05));
}

.version-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.version-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
}

.version-status {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 500;
}

.version-status.completed {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
}

.version-status.failed {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
}

.version-status.running {
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
}

.version-status.fixing {
    background: rgba(251, 191, 36, 0.1);
    color: #fbbf24;
}

.version-description {
    font-size: 12px;
    color: var(--text-secondary);
    margin: 4px 0;
    line-height: 1.4;
}

.version-meta {
    display: flex;
    gap: 12px;
    font-size: 11px;
    color: var(--text-muted);
    margin: 4px 0;
}

.version-actions {
    display: flex;
    gap: 6px;
    margin-top: 8px;
    flex-wrap: wrap;
}

.btn-version-action {
    padding: 4px 10px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.btn-version-action:hover {
    border-color: var(--accent-primary);
    background: var(--accent-primary);
    color: white;
}

.btn-version-action.danger:hover {
    border-color: #ef4444;
    background: #ef4444;
}

.btn-version-action:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.btn-version-action:disabled:hover {
    border-color: var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-primary);
}
```

**Step 3: Wire VersionManager in app.js**

Modify `llm-chat-app/static/app.js` (add after global variables):

```javascript
// Import VersionManager (add script tag in index.html first)
let versionManager = null;

// Initialize VersionManager when session starts
function initializeVersionManager(sessionId) {
    if (!versionManager) {
        versionManager = new VersionManager(sessionId);
        versionManager.init('versionHistoryList');
    } else {
        versionManager.sessionId = sessionId;
        versionManager.loadIterations();
    }

    // Update version count badge
    updateVersionCount();
}

async function updateVersionCount() {
    if (!versionManager || !versionManager.iterations) {
        document.getElementById('versionCount').textContent = '0';
        return;
    }

    document.getElementById('versionCount').textContent = versionManager.iterations.length;
}

// Call initializeVersionManager when DSMC generation completes
function onDSMCGenerationComplete(sessionId) {
    currentSessionId = sessionId;

    // Initialize version manager
    initializeVersionManager(sessionId);

    // Show control panel
    showDSMCControlPanel();

    // Start monitoring
    startMonitoring(sessionId);
}

// Update version manager when new iteration starts
function onNewIterationStarted(sessionId, iterationId) {
    if (versionManager) {
        versionManager.loadIterations();
    }
}

// Update version manager when iteration completes
function onIterationComplete(sessionId, iterationId, status) {
    if (versionManager) {
        versionManager.loadIterations();
    }
}
```

**Step 4: Add VersionManager script tag to index.html**

Modify `llm-chat-app/templates/index.html` (in `<head>` section, after other scripts):

```html
    <!-- Version Manager Component -->
    <script src="{{ url_for('static', filename='components/version-manager.js') }}?v=20260115a"></script>

    <!-- Main App -->
    <script src="{{ url_for('static', filename='app.js') }}?v=20260115a"></script>
</body>
```

**Step 5: Manual verification**

Start server: `python llm-chat-app/app.py`

Open: `http://localhost:21000`

Test flow:
1. Generate DSMC input → Control panel appears
2. Version History section appears at bottom of control panel
3. Shows "v1" iteration
4. Run simulation → New iteration appears
5. Click "View" → Shows iteration details
6. Click "Restore" on v1 → Confirms and switches
7. Version count badge updates

Expected:
- Version history integrates seamlessly
- Real-time updates when iterations change
- Actions work correctly
- Styling matches control panel theme

**Step 6: Commit**

```bash
git add llm-chat-app/templates/index.html
git add llm-chat-app/static/style.css
git add llm-chat-app/static/app.js
git commit -m "feat(ui): integrate VersionManager with control panel

- Add version history section to DSMC control panel
- Wire VersionManager to session lifecycle events
- Auto-initialize when DSMC generation completes
- Update version count badge in real-time
- Refresh on new iteration start/complete
- Full styling for version items and actions

Features:
- Version history appears below log monitoring
- Shows iteration list with status and actions
- Active version highlighted
- Count badge in section header
- Responsive scrolling for long lists

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 4.4: Add Iteration Comparison Modal

**Files:**
- Create: `llm-chat-app/static/components/comparison-modal.js`
- Modify: `llm-chat-app/templates/index.html` (add comparison modal HTML)
- Modify: `llm-chat-app/static/style.css` (add comparison modal styles)

**Step 1: Create comparison modal HTML structure**

Add to `llm-chat-app/templates/index.html` (inside `#customModalOverlay`, after existing modals):

```html
        <!-- Iteration Comparison Modal -->
        <div id="iterationComparisonModal" class="custom-modal modal-large hidden">
            <div class="modal-header">
                <h3>📊 迭代对比</h3>
                <button class="modal-close-btn" onclick="closeComparisonModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="comparison-selector">
                    <div class="selector-group">
                        <label>版本 A:</label>
                        <select id="comparisonIterA" class="comparison-select">
                            <!-- Populated dynamically -->
                        </select>
                    </div>
                    <div class="selector-divider">vs</div>
                    <div class="selector-group">
                        <label>版本 B:</label>
                        <select id="comparisonIterB" class="comparison-select">
                            <!-- Populated dynamically -->
                        </select>
                    </div>
                    <button onclick="loadComparison()" class="btn-load-comparison">对比</button>
                </div>

                <div id="comparisonContent" class="comparison-content hidden">
                    <!-- Metadata comparison -->
                    <div class="comparison-section">
                        <h4>基本信息</h4>
                        <table class="comparison-table">
                            <thead>
                                <tr>
                                    <th>属性</th>
                                    <th id="headerIterA">版本 A</th>
                                    <th id="headerIterB">版本 B</th>
                                </tr>
                            </thead>
                            <tbody id="metadataComparisonBody">
                                <!-- Rows populated dynamically -->
                            </tbody>
                        </table>
                    </div>

                    <!-- Input file diff -->
                    <div class="comparison-section">
                        <h4>输入文件差异</h4>
                        <div id="inputFileDiff" class="diff-container">
                            <!-- Diff rendered here -->
                        </div>
                    </div>

                    <!-- Results comparison (if available) -->
                    <div class="comparison-section" id="resultsComparisonSection">
                        <h4>运行结果对比</h4>
                        <div id="resultsComparison" class="results-grid">
                            <!-- Results comparison -->
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button onclick="closeComparisonModal()" class="btn-modal-secondary">关闭</button>
                <button onclick="exportComparison()" class="btn-modal-primary">📥 导出对比</button>
            </div>
        </div>
    </div>
```

**Step 2: Add comparison modal styles**

Add to `llm-chat-app/static/style.css`:

```css
/* Comparison Modal */
.modal-large {
    width: 90%;
    max-width: 1200px;
    max-height: 90vh;
}

.comparison-selector {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    background: var(--bg-secondary);
    border-radius: 8px;
    margin-bottom: 20px;
}

.selector-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.selector-group label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
}

.comparison-select {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 13px;
}

.selector-divider {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-muted);
    padding-top: 20px;
}

.btn-load-comparison {
    padding: 8px 20px;
    background: var(--accent-primary);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    margin-top: 20px;
}

.btn-load-comparison:hover {
    background: var(--accent-secondary);
}

.comparison-content {
    margin-top: 20px;
}

.comparison-section {
    margin-bottom: 24px;
}

.comparison-section h4 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border-color);
}

.comparison-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.comparison-table th {
    background: var(--bg-secondary);
    padding: 10px;
    text-align: left;
    font-weight: 600;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

.comparison-table td {
    padding: 10px;
    border: 1px solid var(--border-color);
    color: var(--text-primary);
}

.comparison-table td:first-child {
    font-weight: 600;
    background: var(--bg-secondary);
    width: 200px;
}

.diff-container {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 16px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    max-height: 400px;
    overflow-y: auto;
}

.diff-line {
    padding: 2px 4px;
    margin: 1px 0;
}

.diff-line.added {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
}

.diff-line.removed {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
}

.diff-line.unchanged {
    color: var(--text-muted);
}

.results-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.result-card {
    background: var(--bg-secondary);
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
}

.result-card h5 {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 12px;
}

.result-stats {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
}

.stat-label {
    color: var(--text-secondary);
}

.stat-value {
    font-weight: 600;
    color: var(--text-primary);
}
```

**Step 3: Create ComparisonModal JavaScript class**

Create `llm-chat-app/static/components/comparison-modal.js`:

```javascript
class ComparisonModal {
    constructor() {
        this.modal = document.getElementById('iterationComparisonModal');
        this.overlay = document.getElementById('customModalOverlay');
        this.selectA = document.getElementById('comparisonIterA');
        this.selectB = document.getElementById('comparisonIterB');
        this.content = document.getElementById('comparisonContent');

        this.iterations = [];
        this.comparisonData = null;
    }

    show(iterations, defaultIterA = null, defaultIterB = null) {
        this.iterations = iterations;
        this.populateSelectors(defaultIterA, defaultIterB);
        this.overlay.classList.remove('hidden');
        this.modal.classList.remove('hidden');
    }

    hide() {
        this.modal.classList.add('hidden');
        this.overlay.classList.add('hidden');
        this.content.classList.add('hidden');
    }

    populateSelectors(defaultIterA, defaultIterB) {
        // Clear existing options
        this.selectA.innerHTML = '';
        this.selectB.innerHTML = '';

        // Add options for each iteration
        this.iterations.forEach(iter => {
            const optionA = document.createElement('option');
            optionA.value = iter.iteration_id;
            optionA.textContent = `v${iter.iteration_number} - ${iter.modification_description || 'N/A'}`;
            this.selectA.appendChild(optionA);

            const optionB = optionA.cloneNode(true);
            this.selectB.appendChild(optionB);
        });

        // Set default selections
        if (defaultIterA) this.selectA.value = defaultIterA;
        if (defaultIterB) this.selectB.value = defaultIterB;

        // Default: select last two iterations
        if (!defaultIterA && this.iterations.length >= 2) {
            this.selectA.value = this.iterations[0].iteration_id; // Newest
            this.selectB.value = this.iterations[1].iteration_id; // Second newest
        }
    }

    async loadComparison() {
        const iterIdA = this.selectA.value;
        const iterIdB = this.selectB.value;

        if (!iterIdA || !iterIdB) {
            alert('请选择两个版本进行对比');
            return;
        }

        if (iterIdA === iterIdB) {
            alert('请选择不同的版本进行对比');
            return;
        }

        try {
            // Fetch iteration details
            const [iterA, iterB] = await Promise.all([
                fetch(`/api/dsmc/sessions/${currentSessionId}/iterations/${iterIdA}`).then(r => r.json()),
                fetch(`/api/dsmc/sessions/${currentSessionId}/iterations/${iterIdB}`).then(r => r.json())
            ]);

            this.comparisonData = { iterA, iterB };
            this.renderComparison();
            this.content.classList.remove('hidden');

        } catch (error) {
            console.error('Error loading comparison:', error);
            alert('加载对比数据失败');
        }
    }

    renderComparison() {
        const { iterA, iterB } = this.comparisonData;

        // Update headers
        document.getElementById('headerIterA').textContent = `v${iterA.iteration_number}`;
        document.getElementById('headerIterB').textContent = `v${iterB.iteration_number}`;

        // Render metadata comparison
        this.renderMetadataComparison(iterA, iterB);

        // Render input file diff
        this.renderInputDiff(iterA.input_file_content, iterB.input_file_content);

        // Render results comparison if available
        if (iterA.run_result && iterB.run_result) {
            this.renderResultsComparison(iterA.run_result, iterB.run_result);
            document.getElementById('resultsComparisonSection').classList.remove('hidden');
        } else {
            document.getElementById('resultsComparisonSection').classList.add('hidden');
        }
    }

    renderMetadataComparison(iterA, iterB) {
        const tbody = document.getElementById('metadataComparisonBody');
        tbody.innerHTML = '';

        const fields = [
            { label: '迭代编号', keyA: 'iteration_number', keyB: 'iteration_number' },
            { label: '修改描述', keyA: 'modification_description', keyB: 'modification_description' },
            { label: '状态', keyA: 'status', keyB: 'status' },
            { label: '总时间', keyA: 'timing.total_time', keyB: 'timing.total_time', format: v => v ? `${v.toFixed(2)}s` : 'N/A' },
            { label: '创建时间', keyA: 'created_at', keyB: 'created_at', format: v => v ? new Date(v).toLocaleString() : 'N/A' }
        ];

        fields.forEach(field => {
            const tr = document.createElement('tr');

            const valueA = this.getNestedValue(iterA, field.keyA);
            const valueB = this.getNestedValue(iterB, field.keyB);

            const displayA = field.format ? field.format(valueA) : (valueA || 'N/A');
            const displayB = field.format ? field.format(valueB) : (valueB || 'N/A');

            const isDifferent = displayA !== displayB;

            tr.innerHTML = `
                <td>${field.label}</td>
                <td style="${isDifferent ? 'background: rgba(251, 191, 36, 0.1);' : ''}">${displayA}</td>
                <td style="${isDifferent ? 'background: rgba(251, 191, 36, 0.1);' : ''}">${displayB}</td>
            `;

            tbody.appendChild(tr);
        });
    }

    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current?.[key], obj);
    }

    renderInputDiff(contentA, contentB) {
        const container = document.getElementById('inputFileDiff');

        if (!contentA || !contentB) {
            container.innerHTML = '<p style="color: var(--text-muted);">输入文件内容不可用</p>';
            return;
        }

        // Simple line-by-line diff
        const linesA = contentA.split('\n');
        const linesB = contentB.split('\n');

        const maxLines = Math.max(linesA.length, linesB.length);
        let diffHtml = '';

        for (let i = 0; i < maxLines; i++) {
            const lineA = linesA[i] || '';
            const lineB = linesB[i] || '';

            if (lineA === lineB) {
                diffHtml += `<div class="diff-line unchanged">  ${this.escapeHtml(lineA)}</div>`;
            } else {
                if (lineA) {
                    diffHtml += `<div class="diff-line removed">- ${this.escapeHtml(lineA)}</div>`;
                }
                if (lineB) {
                    diffHtml += `<div class="diff-line added">+ ${this.escapeHtml(lineB)}</div>`;
                }
            }
        }

        container.innerHTML = diffHtml || '<p style="color: var(--text-muted);">文件内容相同</p>';
    }

    renderResultsComparison(resultA, resultB) {
        const container = document.getElementById('resultsComparison');

        const cardA = this.createResultCard('版本 A', resultA);
        const cardB = this.createResultCard('版本 B', resultB);

        container.innerHTML = '';
        container.appendChild(cardA);
        container.appendChild(cardB);
    }

    createResultCard(title, result) {
        const card = document.createElement('div');
        card.className = 'result-card';

        const stats = [
            { label: '完成步数', value: result.current_step || result.total_steps || 'N/A' },
            { label: '总步数', value: result.total_steps || 'N/A' },
            { label: '粒子数', value: result.particles_count ? result.particles_count.toLocaleString() : 'N/A' },
            { label: '碰撞次数', value: result.collisions ? result.collisions.toLocaleString() : 'N/A' },
            { label: '墙面碰撞', value: result.wall_collisions ? result.wall_collisions.toLocaleString() : 'N/A' }
        ];

        const statsHtml = stats.map(stat => `
            <div class="stat-row">
                <span class="stat-label">${stat.label}:</span>
                <span class="stat-value">${stat.value}</span>
            </div>
        `).join('');

        card.innerHTML = `
            <h5>${title}</h5>
            <div class="result-stats">
                ${statsHtml}
            </div>
        `;

        return card;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    exportComparison() {
        if (!this.comparisonData) {
            alert('请先加载对比数据');
            return;
        }

        const { iterA, iterB } = this.comparisonData;

        const report = `
# SPARTA DSMC 迭代对比报告

## 基本信息

### 版本 A (v${iterA.iteration_number})
- 修改描述: ${iterA.modification_description || 'N/A'}
- 状态: ${iterA.status}
- 总时间: ${iterA.timing?.total_time?.toFixed(2) || 'N/A'}s
- 创建时间: ${iterA.created_at ? new Date(iterA.created_at).toLocaleString() : 'N/A'}

### 版本 B (v${iterB.iteration_number})
- 修改描述: ${iterB.modification_description || 'N/A'}
- 状态: ${iterB.status}
- 总时间: ${iterB.timing?.total_time?.toFixed(2) || 'N/A'}s
- 创建时间: ${iterB.created_at ? new Date(iterB.created_at).toLocaleString() : 'N/A'}

## 输入文件差异

### 版本 A:
\`\`\`
${iterA.input_file_content || 'N/A'}
\`\`\`

### 版本 B:
\`\`\`
${iterB.input_file_content || 'N/A'}
\`\`\`

## 运行结果对比

### 版本 A:
${JSON.stringify(iterA.run_result, null, 2)}

### 版本 B:
${JSON.stringify(iterB.run_result, null, 2)}

---
生成时间: ${new Date().toLocaleString()}
        `.trim();

        // Download as markdown file
        const blob = new Blob([report], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `comparison_v${iterA.iteration_number}_vs_v${iterB.iteration_number}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Global instance
const comparisonModal = new ComparisonModal();

// Global functions for onclick handlers
function closeComparisonModal() {
    comparisonModal.hide();
}

function loadComparison() {
    comparisonModal.loadComparison();
}

function exportComparison() {
    comparisonModal.exportComparison();
}
```

**Step 4: Wire comparison to VersionManager**

Modify `llm-chat-app/static/components/version-manager.js` (update `compareIterations` method):

```javascript
    compareIterations(iterationId) {
        const currentIteration = this.iterations.find(i => i.iteration_id === iterationId);
        if (!currentIteration) return;

        // Show comparison modal with current iteration pre-selected
        comparisonModal.show(this.iterations, iterationId, this.activeIterationId);
    }
```

**Step 5: Add script tag to index.html**

Modify `llm-chat-app/templates/index.html` (add before version-manager.js):

```html
    <!-- Comparison Modal Component -->
    <script src="{{ url_for('static', filename='components/comparison-modal.js') }}?v=20260115a"></script>
    <!-- Version Manager Component -->
    <script src="{{ url_for('static', filename='components/version-manager.js') }}?v=20260115a"></script>
```

**Step 6: Manual verification**

Start server, open browser, generate DSMC session with multiple iterations.

Test flow:
1. Click "Compare" button on any iteration
2. Modal opens with version selectors
3. Select two different versions
4. Click "对比" button
5. Comparison content loads
6. Metadata table shows differences highlighted
7. Input file diff shows line-by-line changes
8. Results comparison shows stats side-by-side
9. Click "导出对比" → Downloads markdown report
10. Close modal

Expected:
- Modal is large and centered
- Selectors populated correctly
- Diff rendering clear and color-coded
- Export generates valid markdown
- Close button works

**Step 7: Commit**

```bash
git add llm-chat-app/static/components/comparison-modal.js
git add llm-chat-app/static/components/version-manager.js
git add llm-chat-app/templates/index.html
git add llm-chat-app/static/style.css
git commit -m "feat(ui): add iteration comparison modal

- ComparisonModal class for side-by-side comparison
- Select any two iterations to compare
- Metadata comparison table with diff highlighting
- Line-by-line input file diff (added/removed/unchanged)
- Results statistics side-by-side comparison
- Export comparison as markdown report

Features:
- Large modal with scrollable content
- Auto-select last two iterations by default
- Color-coded differences (yellow for metadata, green/red for diff)
- Simple line-based diff algorithm
- Downloadable comparison report
- Integrated with VersionManager 'Compare' button

Styling:
- Responsive grid layout for results
- Monospace font for diff view
- Proper scrolling for long files
- Themed colors matching overall design

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 4.5: Implement Server-Sent Events for Real-Time Updates

**Files:**
- Modify: `llm-chat-app/app.py` (add SSE endpoint)
- Modify: `llm-chat-app/static/app.js` (add SSE client)
- Create: `llm-chat-app/sse_manager.py` (SSE connection manager)

**Step 1: Create SSE manager module**

Create `llm-chat-app/sse_manager.py`:

```python
import queue
import json
import time
from typing import Dict, Set
from threading import Lock

class SSEManager:
    """Manages Server-Sent Events connections for real-time updates"""

    def __init__(self):
        self.clients: Dict[str, Set[queue.Queue]] = {}
        self.lock = Lock()

    def add_client(self, session_id: str, client_queue: queue.Queue):
        """Register a new SSE client for a session"""
        with self.lock:
            if session_id not in self.clients:
                self.clients[session_id] = set()
            self.clients[session_id].add(client_queue)

    def remove_client(self, session_id: str, client_queue: queue.Queue):
        """Remove an SSE client"""
        with self.lock:
            if session_id in self.clients:
                self.clients[session_id].discard(client_queue)
                if not self.clients[session_id]:
                    del self.clients[session_id]

    def send_event(self, session_id: str, event_type: str, data: dict):
        """Send an event to all clients subscribed to a session"""
        with self.lock:
            if session_id not in self.clients:
                return

            message = {
                'type': event_type,
                'timestamp': time.time(),
                'data': data
            }

            dead_clients = []
            for client_queue in self.clients[session_id]:
                try:
                    client_queue.put_nowait(message)
                except queue.Full:
                    dead_clients.append(client_queue)

            # Remove dead clients
            for dead in dead_clients:
                self.clients[session_id].discard(dead)

    def get_client_count(self, session_id: str) -> int:
        """Get number of connected clients for a session"""
        with self.lock:
            return len(self.clients.get(session_id, set()))

# Global instance
sse_manager = SSEManager()
```

**Step 2: Add SSE endpoint to app.py**

Add to `llm-chat-app/app.py` (import SSEManager first):

```python
from sse_manager import sse_manager
import queue

@app.route('/api/dsmc/sessions/<session_id>/events')
def session_events_stream(session_id):
    """Server-Sent Events endpoint for real-time session updates"""

    def event_stream():
        client_queue = queue.Queue(maxsize=50)
        sse_manager.add_client(session_id, client_queue)

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            last_heartbeat = time.time()

            while True:
                try:
                    # Check for new events (timeout to allow heartbeat)
                    message = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(message)}\n\n"
                    last_heartbeat = time.time()

                except queue.Empty:
                    # Send heartbeat
                    if time.time() - last_heartbeat >= 30:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        last_heartbeat = time.time()

        except GeneratorExit:
            # Client disconnected
            sse_manager.remove_client(session_id, client_queue)

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
```

**Step 3: Update DSMC execution to send SSE events**

Modify the `run_dsmc_simulation` function in `app.py` (add SSE event sending):

```python
def run_dsmc_simulation(session_id: str, input_file: str, max_steps: int, ...):
    """Background thread for running DSMC simulation"""
    try:
        # Send simulation started event
        sse_manager.send_event(session_id, 'simulation_started', {
            'iteration_id': iteration_id,
            'max_steps': max_steps
        })

        # ... existing simulation code ...

        # Send progress updates periodically
        for step in range(0, max_steps, 100):
            # ... run simulation steps ...

            sse_manager.send_event(session_id, 'progress_update', {
                'iteration_id': iteration_id,
                'current_step': step,
                'total_steps': max_steps,
                'percentage': (step / max_steps) * 100
            })

        # Send completion event
        sse_manager.send_event(session_id, 'simulation_completed', {
            'iteration_id': iteration_id,
            'status': 'completed',
            'total_time': elapsed_time,
            'result': result_data
        })

    except Exception as e:
        # Send error event
        sse_manager.send_event(session_id, 'simulation_failed', {
            'iteration_id': iteration_id,
            'status': 'failed',
            'error': str(e)
        })
```

**Step 4: Add SSE client in app.js**

Add to `llm-chat-app/static/app.js`:

```javascript
let sseConnection = null;

function connectSSE(sessionId) {
    // Close existing connection
    if (sseConnection) {
        sseConnection.close();
    }

    // Create new EventSource connection
    sseConnection = new EventSource(`/api/dsmc/sessions/${sessionId}/events`);

    sseConnection.onopen = () => {
        console.log('SSE connection opened');
        updateProcessTracker('已连接', 'connected');
    };

    sseConnection.addEventListener('connected', (e) => {
        const data = JSON.parse(e.data);
        console.log('SSE connected:', data);
    });

    sseConnection.addEventListener('heartbeat', (e) => {
        // Heartbeat - keep connection alive
        console.log('SSE heartbeat');
    });

    sseConnection.addEventListener('simulation_started', (e) => {
        const data = JSON.parse(e.data);
        console.log('Simulation started:', data);

        updateProcessTracker('仿真运行中', 'running');
        updateHeaderProgress(0, data.data.max_steps);
    });

    sseConnection.addEventListener('progress_update', (e) => {
        const data = JSON.parse(e.data);
        console.log('Progress update:', data);

        const { current_step, total_steps, percentage } = data.data;
        updateHeaderProgress(current_step, total_steps);
        updateProcessTracker(`运行中 ${percentage.toFixed(1)}%`, 'running');
    });

    sseConnection.addEventListener('simulation_completed', (e) => {
        const data = JSON.parse(e.data);
        console.log('Simulation completed:', data);

        updateProcessTracker('已完成', 'completed');
        updateHeaderProgress(data.data.total_steps, data.data.total_steps);

        // Reload version manager to show new iteration
        if (versionManager) {
            versionManager.loadIterations();
        }

        // Show completion notification
        showNotification('仿真完成', `总时间: ${data.data.total_time.toFixed(2)}s`, 'success');
    });

    sseConnection.addEventListener('simulation_failed', (e) => {
        const data = JSON.parse(e.data);
        console.log('Simulation failed:', data);

        updateProcessTracker('失败', 'failed');

        // Reload version manager
        if (versionManager) {
            versionManager.loadIterations();
        }

        // Show error notification
        showNotification('仿真失败', data.data.error, 'error');
    });

    sseConnection.addEventListener('iteration_updated', (e) => {
        const data = JSON.parse(e.data);
        console.log('Iteration updated:', data);

        // Reload version manager
        if (versionManager) {
            versionManager.loadIterations();
        }
    });

    sseConnection.onerror = (error) => {
        console.error('SSE error:', error);
        updateProcessTracker('连接错误', 'error');

        // Attempt reconnect after 5 seconds
        setTimeout(() => {
            if (currentSessionId) {
                console.log('Attempting SSE reconnect...');
                connectSSE(currentSessionId);
            }
        }, 5000);
    };
}

function disconnectSSE() {
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
        console.log('SSE connection closed');
    }
}

// Helper: Update header progress indicator
function updateHeaderProgress(current, total) {
    const progressEl = document.getElementById('headerSimProgress');
    const progressText = document.getElementById('progressText');
    const progressIcon = document.getElementById('progressIcon');

    if (current >= total) {
        progressEl.classList.add('hidden');
    } else {
        progressEl.classList.remove('hidden');
        progressText.textContent = `${current}/${total}`;

        // Animate icon
        progressIcon.textContent = current % 200 === 0 ? '⌛' : '⏳';
    }
}

// Helper: Show notification
function showNotification(title, message, type = 'info') {
    // Simple toast notification (can be enhanced with library)
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

// Update onDSMCGenerationComplete to connect SSE
function onDSMCGenerationComplete(sessionId) {
    currentSessionId = sessionId;

    // Initialize version manager
    initializeVersionManager(sessionId);

    // Connect SSE for real-time updates
    connectSSE(sessionId);

    // Show control panel
    showDSMCControlPanel();

    // Start monitoring
    startMonitoring(sessionId);
}

// Disconnect SSE when leaving page
window.addEventListener('beforeunload', () => {
    disconnectSSE();
});
```

**Step 5: Add toast animation CSS**

Add to `llm-chat-app/static/style.css`:

```css
/* Toast Notifications */
@keyframes slideIn {
    from {
        transform: translateX(400px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOut {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(400px);
        opacity: 0;
    }
}

.toast {
    animation: slideIn 0.3s ease;
}

.toast strong {
    display: block;
    font-size: 14px;
    margin-bottom: 4px;
    color: var(--text-primary);
}

.toast p {
    font-size: 12px;
    color: var(--text-secondary);
    margin: 0;
}

.toast-success {
    border-left: 4px solid #22c55e;
}

.toast-error {
    border-left: 4px solid #ef4444;
}

.toast-info {
    border-left: 4px solid var(--accent-primary);
}
```

**Step 6: Manual verification**

Start server, open browser, generate DSMC session.

Test flow:
1. Generate DSMC input → SSE connects
2. Console shows "SSE connection opened"
3. Run simulation → Progress updates in header
4. Process tracker shows "运行中 X%"
5. Version manager auto-refreshes when complete
6. Toast notification appears on completion
7. Close browser tab → SSE disconnects gracefully
8. Reopen → SSE reconnects automatically

Expected:
- Real-time progress updates without polling
- Smooth animations
- Automatic reconnection on errors
- Clean disconnection on page unload
- Version manager stays in sync

**Step 7: Commit**

```bash
git add llm-chat-app/sse_manager.py
git add llm-chat-app/app.py
git add llm-chat-app/static/app.js
git add llm-chat-app/static/style.css
git commit -m "feat(realtime): implement Server-Sent Events for live updates

- SSEManager class for connection management
- SSE endpoint /api/dsmc/sessions/<id>/events
- EventSource client in app.js
- Real-time progress updates during simulation
- Automatic version manager refresh on events
- Toast notifications for completion/errors
- Heartbeat mechanism to keep connections alive
- Auto-reconnect on connection loss

Event types:
- connected: Initial connection established
- heartbeat: Keep-alive every 30s
- simulation_started: Simulation begins
- progress_update: Step progress (every 100 steps)
- simulation_completed: Successful completion
- simulation_failed: Error occurred
- iteration_updated: Iteration metadata changed

Features:
- No polling required
- Sub-second latency for updates
- Graceful disconnect on page unload
- Error recovery with retry logic
- Header progress indicator updates
- Process tracker status sync

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 4 Complete

All tasks for Phase 4 (Version Control & Iteration Management) are now detailed. Next would be Phase 5 (Configuration Management) and Phase 6 (Integration & Polish).

Would you like me to continue with Part 4 covering Phases 5-6?
