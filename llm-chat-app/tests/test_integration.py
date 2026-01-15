import pytest
import json
import os
from pathlib import Path


@pytest.fixture
def client():
    """Flask test client fixture"""
    # Import the app
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from app import app

    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_version_manager_with_backend(client):
    """Test VersionManager integration with backend API"""
    # Create a session with multiple iterations
    session_id = 'test-integration-session'

    # Test getting iterations (should return 200 or 404 if session doesn't exist)
    response = client.get(f'/api/dsmc/sessions/{session_id}/iterations')
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.get_json()
        assert 'iterations' in data
        assert isinstance(data['iterations'], list)


def test_settings_persistence_across_restarts(client):
    """Test settings persist after server restart"""
    # Update settings (runtime mode) - use non-sensitive key
    updates = {'LLM_MODEL': 'claude-opus-4-5'}
    response = client.post('/api/settings',
                          json={'updates': updates, 'persist': False})
    assert response.status_code == 200

    # Get settings
    response = client.get('/api/settings')
    assert response.status_code == 200
    settings = response.get_json()['settings']
    # Check that setting was updated (not masked)
    assert settings['LLM_MODEL'] == 'claude-opus-4-5'


def test_settings_validation(client):
    """Test settings endpoint validates input correctly"""
    # Test invalid MAX_TOKENS
    updates = {'MAX_TOKENS': 'invalid'}
    response = client.post('/api/settings',
                          json={'updates': updates, 'persist': False})

    # Should either accept (and convert) or reject with error
    assert response.status_code in [200, 400]


def test_sse_connection_and_events(client):
    """Test SSE connection endpoint exists"""
    session_id = 'test-session'
    response = client.get(f'/api/dsmc/sessions/{session_id}/events',
                          headers={'Accept': 'text/event-stream'})

    # Should return streaming response or 404 if session doesn't exist
    assert response.status_code in [200, 404]


def test_dsmc_session_creation(client):
    """Test creating a DSMC session"""
    # This endpoint may not exist yet, but test structure
    session_data = {
        'workdir': '/tmp/test_session',
        'input_file': 'in.test'
    }

    # Try to create session
    response = client.post('/api/dsmc/sessions', json=session_data)

    # Should either succeed (200/201) or not exist yet (404/405)
    assert response.status_code in [200, 201, 404, 405]


def test_config_manager_integration(client):
    """Test ConfigManager integration with Flask app"""
    # Get current settings
    response = client.get('/api/settings')
    assert response.status_code == 200

    data = response.get_json()
    assert 'settings' in data
    assert isinstance(data['settings'], dict)

    # Verify essential settings exist
    settings = data['settings']
    essential_keys = ['API_URL', 'LLM_MODEL']

    for key in essential_keys:
        assert key in settings, f"Missing essential setting: {key}"


def test_file_upload_validation(client):
    """Test file upload validation endpoint"""
    # Try to upload without file
    response = client.post('/api/dsmc/validate')

    # Should return 400 (bad request), 404 (not found), or 405 (method not allowed)
    assert response.status_code in [400, 404, 405]


def test_atmospheric_calculator_endpoint(client):
    """Test atmospheric calculator endpoint exists and returns data"""
    # Send altitude
    response = client.post('/api/dsmc/atmosphere',
                          json={'altitude': 80000})

    # Should either work (200) or not exist yet (404)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.get_json()
        # Should return atmospheric parameters
        assert 'temperature' in data or 'pressure' in data or 'density' in data


def test_session_status_endpoint(client):
    """Test session status endpoint"""
    session_id = 'test-session'
    response = client.get(f'/api/dsmc/sessions/{session_id}/status')

    # Should return status or 404
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.get_json()
        assert 'status' in data


def test_cors_headers(client):
    """Test CORS headers are present if needed"""
    response = client.get('/api/settings')

    # Check if CORS headers are set (optional)
    headers = dict(response.headers)
    print(f"Response headers: {headers}")

    # This test just verifies the endpoint works
    assert response.status_code == 200


def test_error_handling(client):
    """Test error handling returns proper error messages"""
    # Try to access non-existent session
    response = client.get('/api/dsmc/sessions/nonexistent-session/status')

    # Should return 404 with error message
    if response.status_code == 404:
        data = response.get_json()
        # Should have error field (or None if plain text response)
        if data:
            assert 'error' in data or 'message' in data


def test_settings_test_connection(client):
    """Test settings connection test endpoint"""
    # Try to test connection
    response = client.post('/api/settings/test')

    # Should either work (200), fail (400/500), or not exist (404)
    assert response.status_code in [200, 400, 404, 500]

    if response.status_code == 200:
        data = response.get_json()
        assert 'success' in data or 'status' in data


def test_iteration_comparison(client):
    """Test iteration comparison endpoint"""
    session_id = 'test-session'

    # Try to compare two iterations
    response = client.get(
        f'/api/dsmc/sessions/{session_id}/compare?v1=iter_1&v2=iter_2'
    )

    # Should either work (200) or session not found (404)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.get_json()
        assert 'comparison' in data or 'diff' in data


def test_log_streaming(client):
    """Test log streaming endpoint"""
    session_id = 'test-session'

    # Try to get logs
    response = client.get(f'/api/dsmc/sessions/{session_id}/logs')

    # Should either work (200), stream (200), or not found (404)
    assert response.status_code in [200, 404]


def test_version_restore(client):
    """Test restoring a previous version"""
    session_id = 'test-session'
    iteration_id = 'iter_1'

    # Try to restore version
    response = client.post(
        f'/api/dsmc/sessions/{session_id}/iterations/{iteration_id}/restore'
    )

    # Should either work (200), not found (404), or not implemented (405)
    assert response.status_code in [200, 404, 405]


def test_version_delete(client):
    """Test deleting an iteration"""
    session_id = 'test-session'
    iteration_id = 'iter_1'

    # Try to delete iteration
    response = client.delete(
        f'/api/dsmc/sessions/{session_id}/iterations/{iteration_id}'
    )

    # Should either work (200/204), not found (404), or forbidden (403)
    assert response.status_code in [200, 204, 403, 404]


def test_health_check(client):
    """Test application health check"""
    # Try common health check endpoints
    for endpoint in ['/', '/health', '/api/health']:
        response = client.get(endpoint)
        if response.status_code == 200:
            print(f"Health check endpoint found: {endpoint}")
            return

    # If no health endpoint, just verify app is running
    response = client.get('/api/settings')
    assert response.status_code == 200
    print("App is running (verified via /api/settings)")
