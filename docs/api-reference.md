# API Reference

**Base URL**: `http://localhost:21000/api`

**Version**: 2.0.0

## Table of Contents
- [Settings Management](#settings-management)
- [DSMC Session Management](#dsmc-session-management)
- [File Operations](#file-operations)
- [Real-Time Events (SSE)](#real-time-events-sse)
- [Atmospheric Calculations](#atmospheric-calculations)
- [Error Handling](#error-handling)

---

## Settings Management

### GET /api/settings
Get current application settings with masking for sensitive data.

**Response 200**:
```json
{
  "settings": {
    "API_URL": "https://api.example.com/v1",
    "API_KEY": "sk-abc...***",
    "LLM_MODEL": "claude-sonnet-4-5",
    "MAX_TOKENS": "4096",
    "DEFAULT_TEMPERATURE": "0.7"
  },
  "editable_keys": ["API_URL", "LLM_MODEL", "MAX_TOKENS", "DEFAULT_TEMPERATURE"]
}
```

### POST /api/settings
Update application settings (runtime or persistent).

**Request Body**:
```json
{
  "updates": {
    "MAX_TOKENS": "8192",
    "DEFAULT_TEMPERATURE": "0.8"
  },
  "persist": false
}
```

**Response 200**:
```json
{
  "success": true,
  "message": "Settings updated (runtime only)",
  "updated_keys": ["MAX_TOKENS", "DEFAULT_TEMPERATURE"],
  "persisted": false
}
```

**Parameters**:
- `updates` (object, required): Key-value pairs of settings to update
- `persist` (boolean, optional): If true, writes to .env file; if false, saves to settings.json

### POST /api/settings/test-connection
Test API connection with provided or current credentials.

**Request Body**:
```json
{
  "API_URL": "https://api.anthropic.com/v1",
  "API_KEY": "sk-test-key",
  "LLM_MODEL": "claude-sonnet-4-5"
}
```

**Response 200** (Success):
```json
{
  "success": true,
  "message": "API connection successful",
  "model": "claude-sonnet-4-5"
}
```

**Response 400** (Failure):
```json
{
  "success": false,
  "error": "Connection timeout - check API_URL"
}
```

---

## DSMC Session Management

### GET /api/dsmc/sessions/{session_id}/iterations
Get all iterations for a DSMC session.

**Path Parameters**:
- `session_id` (string): Session identifier

**Response 200**:
```json
{
  "iterations": [
    {
      "iteration_id": "iter_1",
      "iteration_number": 1,
      "modification_description": "Initial generation",
      "status": "completed",
      "timestamp": "2026-01-15T10:30:00Z",
      "timing": {
        "total_time": 120.5,
        "start_time": "2026-01-15T10:28:00Z",
        "end_time": "2026-01-15T10:30:00Z"
      }
    }
  ],
  "current_iteration_id": "iter_1",
  "total": 1
}
```

**Response 404**: Session not found

### GET /api/dsmc/sessions/{session_id}/iterations/{iteration_id}
Get detailed information about a specific iteration.

**Response 200**:
```json
{
  "iteration_id": "iter_1",
  "iteration_number": 1,
  "modification_description": "Initial generation",
  "status": "completed",
  "input_file_content": "# SPARTA Input File\ndimension 3\n...",
  "output_log": "SPARTA (10 Jan 2023)\n...",
  "run_result": {
    "current_step": 1000,
    "total_steps": 1000,
    "particles_count": 50000,
    "cpu_time": 120.5
  },
  "timing": {
    "total_time": 120.5
  }
}
```

### POST /api/dsmc/sessions/{session_id}/iterations/{iteration_id}/restore
Restore a previous iteration as the current active version.

**Response 200**:
```json
{
  "success": true,
  "current_iteration_id": "iter_1",
  "message": "Restored to iteration 1"
}
```

**Response 403**: Cannot restore the iteration that's already active

### DELETE /api/dsmc/sessions/{session_id}/iterations/{iteration_id}
Delete an iteration. Cannot delete the active version.

**Response 200**:
```json
{
  "success": true,
  "message": "Deleted iteration 2",
  "deleted_files": ["iter_2_input.sparta", "iter_2_output.log", "iter_2_data.dat"]
}
```

**Response 403**: Attempted to delete active iteration
**Response 404**: Iteration not found

### GET /api/dsmc/sessions/{session_id}/compare
Compare two iterations side-by-side.

**Query Parameters**:
- `v1` (string, required): First iteration ID
- `v2` (string, required): Second iteration ID

**Response 200**:
```json
{
  "comparison": {
    "v1": {
      "iteration_id": "iter_1",
      "metadata": {...},
      "input_content": "..."
    },
    "v2": {
      "iteration_id": "iter_2",
      "metadata": {...},
      "input_content": "..."
    },
    "diff": {
      "metadata_changes": ["temperature", "pressure"],
      "input_changes": 15,
      "results_summary": "..."
    }
  }
}
```

### GET /api/dsmc/sessions/{session_id}/status
Get current status of a session.

**Response 200**:
```json
{
  "status": "running",
  "current_iteration": "iter_2",
  "progress": {
    "current_step": 500,
    "total_steps": 1000,
    "percentage": 50.0
  }
}
```

---

## File Operations

### POST /api/dsmc/validate
Validate SPARTA input file without running.

**Request**: multipart/form-data with `file` field

**Response 200**:
```json
{
  "valid": true,
  "warnings": [],
  "errors": [],
  "stats": {
    "lines": 50,
    "commands": 15,
    "particles": 10000
  }
}
```

**Response 400** (Invalid file):
```json
{
  "valid": false,
  "warnings": ["Temperature may be too low"],
  "errors": ["Missing 'dimension' command", "Invalid grid size"],
  "stats": {...}
}
```

### POST /api/dsmc/upload-input
Upload and process SPARTA input file.

**Request**: multipart/form-data with `file` field

**Response 200**:
```json
{
  "valid": true,
  "temp_id": "temp_abc123",
  "params": {
    "dimension": "3d",
    "temperature": 300,
    "pressure": 101325,
    "grid_size": [100, 100, 100]
  },
  "preview": "# SPARTA input file\ndimension 3\n...",
  "stats": {
    "lines": 50,
    "commands": 15
  }
}
```

### POST /api/dsmc/run-uploaded
Run an uploaded file directly with configuration.

**Request Body**:
```json
{
  "temp_id": "temp_abc123",
  "max_steps": 2000,
  "num_cores": 8,
  "max_memory_gb": 16,
  "modification_description": "Test run with increased steps"
}
```

**Response 200**:
```json
{
  "success": true,
  "session_id": "session_xyz789",
  "iteration_id": "iter_1"
}
```

---

## Real-Time Events (SSE)

### GET /api/dsmc/sessions/{session_id}/events
Server-Sent Events stream for real-time simulation updates.

**Headers**:
```
Accept: text/event-stream
```

**Event Format**: Each event is a JSON object prefixed with `data:`

**Event Types**:

**Connected**:
```
data: {"type": "connected", "session_id": "session_xyz", "timestamp": "2026-01-15T10:30:00Z"}
```

**Heartbeat** (every 30s):
```
data: {"type": "heartbeat", "timestamp": "2026-01-15T10:30:30Z"}
```

**Simulation Started**:
```
data: {"type": "simulation_started", "data": {"iteration_id": "iter_2", "max_steps": 1000, "cores": 8}}
```

**Progress Update**:
```
data: {"type": "progress_update", "data": {"current_step": 500, "total_steps": 1000, "percentage": 50.0, "elapsed_time": 60.5}}
```

**Log Message**:
```
data: {"type": "log", "data": {"message": "Step 500 completed", "level": "info"}}
```

**Simulation Completed**:
```
data: {"type": "simulation_completed", "data": {"status": "success", "total_time": 120.5, "final_step": 1000}}
```

**Simulation Failed**:
```
data: {"type": "simulation_failed", "data": {"error": "Memory limit exceeded", "step": 750}}
```

**Connection Notes**:
- Connections timeout after 5 minutes of inactivity
- Client should reconnect on connection loss
- Multiple clients can connect to same session

---

## Atmospheric Calculations

### POST /api/atmosphere/calculate
Calculate atmospheric properties for given altitude and model.

**Request Body**:
```json
{
  "altitude_km": 80,
  "model": "NRLMSISE-00"
}
```

**Response 200**:
```json
{
  "temperature": 196.0,
  "pressure": 1.05,
  "density": 1.85e-5,
  "sound_speed": 281.3,
  "model": "NRLMSISE-00",
  "altitude_km": 80
}
```

**Supported Models**:
- `NRLMSISE-00`: NASA atmospheric model (default)
- `US76`: US Standard Atmosphere 1976
- `ISA`: International Standard Atmosphere

---

## Error Handling

### HTTP Status Codes
- `200 OK`: Request succeeded
- `400 Bad Request`: Invalid input or parameters
- `403 Forbidden`: Operation not allowed (e.g., delete active iteration)
- `404 Not Found`: Resource doesn't exist
- `500 Internal Server Error`: Server-side error

### Error Response Format
```json
{
  "error": "Detailed error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "value",
    "reason": "explanation"
  }
}
```

### Common Error Codes
- `INVALID_SESSION`: Session ID not found
- `INVALID_ITERATION`: Iteration ID not found
- `VALIDATION_FAILED`: Input file validation failed
- `SIMULATION_ERROR`: Simulation execution failed
- `FILE_NOT_FOUND`: Referenced file doesn't exist
- `PERMISSION_DENIED`: Operation not permitted

---

## Rate Limiting

**Current**: No rate limiting implemented

**Recommendations for Production**:
- Limit API calls to 100/minute per IP
- Limit SSE connections to 5 per session
- Limit file uploads to 10MB max size

---

## Authentication

**Current**: No authentication required

**Recommendations for Production**:
- Add JWT or API key authentication
- Implement per-user session isolation
- Add role-based access control (RBAC)

---

## Versioning

**Current Version**: 2.0.0
**API Stability**: Unstable (may change without notice)

**Changelog**:
- `2.0.0` (2026-01-15): Added settings management, version control, SSE events
- `1.0.0` (2025-12-01): Initial release with basic DSMC workflow

---

## Examples

### Example: Complete Workflow

```javascript
// 1. Upload input file
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const uploadResp = await fetch('/api/dsmc/upload-input', {
  method: 'POST',
  body: formData
});
const { temp_id, valid } = await uploadResp.json();

if (!valid) {
  console.error('File validation failed');
  return;
}

// 2. Run simulation
const runResp = await fetch('/api/dsmc/run-uploaded', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    temp_id,
    max_steps: 1000,
    num_cores: 4
  })
});
const { session_id } = await runResp.json();

// 3. Connect to SSE for updates
const eventSource = new EventSource(`/api/dsmc/sessions/${session_id}/events`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.type, data);
};

// 4. Get iterations after completion
const iterResp = await fetch(`/api/dsmc/sessions/${session_id}/iterations`);
const { iterations } = await iterResp.json();
console.log('Iterations:', iterations);
```

---

**Documentation Version**: 2.0.0
**Last Updated**: 2026-01-15
**Maintained By**: SPARTA LLM Agent Team
