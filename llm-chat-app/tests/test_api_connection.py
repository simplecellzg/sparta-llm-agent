"""
Tests for API connection testing functionality
"""
import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAPIConnectionTesting:
    """Test API connection testing for different API types"""

    @patch('requests.post')
    def test_anthropic_api_connection_success(self, mock_post):
        """Should successfully test Anthropic API connection"""
        from api_utils import test_api_connection

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'content': [{'text': 'test'}]}
        mock_post.return_value = mock_response

        result = test_api_connection(
            api_type='anthropic',
            api_url='https://api.anthropic.com/v1',
            api_key='sk-ant-test-key',
            model='claude-sonnet-4-5'
        )

        assert result['success'] is True
        assert 'message' in result

        # Verify correct endpoint was called
        call_args = mock_post.call_args
        assert '/messages' in call_args[0][0]

        # Verify correct headers
        headers = call_args[1]['headers']
        assert headers['x-api-key'] == 'sk-ant-test-key'
        assert headers['anthropic-version'] == '2023-06-01'
        assert headers['content-type'] == 'application/json'

        # Verify correct payload
        payload = call_args[1]['json']
        assert payload['model'] == 'claude-sonnet-4-5'
        assert payload['max_tokens'] == 10
        assert payload['messages'][0]['role'] == 'user'

    @patch('requests.post')
    def test_openai_api_connection_success(self, mock_post):
        """Should successfully test OpenAI API connection"""
        from api_utils import test_api_connection

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': 'test'}}]}
        mock_post.return_value = mock_response

        result = test_api_connection(
            api_type='openai',
            api_url='https://api.openai.com/v1',
            api_key='sk-test-key',
            model='gpt-4'
        )

        assert result['success'] is True

        # Verify correct endpoint was called
        call_args = mock_post.call_args
        assert '/chat/completions' in call_args[0][0]

        # Verify correct headers
        headers = call_args[1]['headers']
        assert headers['Authorization'] == 'Bearer sk-test-key'
        assert headers['Content-Type'] == 'application/json'

        # Verify correct payload
        payload = call_args[1]['json']
        assert payload['model'] == 'gpt-4'
        assert payload['max_tokens'] == 10

    @patch('requests.post')
    def test_api_connection_failure(self, mock_post):
        """Should handle API connection failures"""
        from api_utils import test_api_connection

        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Invalid API key'
        mock_post.return_value = mock_response

        result = test_api_connection(
            api_type='anthropic',
            api_url='https://api.anthropic.com/v1',
            api_key='invalid-key',
            model='claude-sonnet-4-5'
        )

        assert result['success'] is False
        assert 'error' in result
        assert '401' in result['error']

    @patch('requests.post')
    def test_api_connection_timeout(self, mock_post):
        """Should handle connection timeouts"""
        from api_utils import test_api_connection
        import requests

        # Mock timeout exception
        mock_post.side_effect = requests.Timeout('Connection timeout')

        result = test_api_connection(
            api_type='openai',
            api_url='https://api.openai.com/v1',
            api_key='sk-test-key',
            model='gpt-4'
        )

        assert result['success'] is False
        assert 'error' in result
        assert 'timeout' in result['error'].lower()

    def test_default_api_type(self):
        """Should default to openai API type if not specified"""
        from api_utils import test_api_connection

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            test_api_connection(
                api_url='https://api.test.com/v1',
                api_key='sk-test',
                model='test-model'
            )

            # Should call OpenAI endpoint by default
            assert '/chat/completions' in mock_post.call_args[0][0]
