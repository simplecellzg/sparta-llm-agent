"""
Tests for unified LLM calling interface
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestUnifiedLLMInterface:
    """Test unified LLM calling interface that handles both API types"""

    @patch('api_utils.get_config_manager')
    @patch('requests.post')
    def test_call_llm_with_anthropic_config(self, mock_post, mock_config):
        """Should call Anthropic API when API_TYPE is anthropic"""
        from api_utils import call_llm

        # Mock config
        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_TYPE': 'anthropic',
            'API_URL': 'https://api.anthropic.com/v1',
            'API_KEY': 'sk-ant-test',
            'LLM_MODEL': 'claude-sonnet-4-5'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': 'Hello from Claude'}]
        }
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Hi'}]
        result = call_llm(messages)

        # Verify Anthropic endpoint was called
        call_args = mock_post.call_args
        assert '/messages' in call_args[0][0]

        # Verify Anthropic headers
        headers = call_args[1]['headers']
        assert 'x-api-key' in headers
        assert headers['anthropic-version'] == '2023-06-01'

        # Verify result
        assert result['success'] is True
        assert 'content' in result

    @patch('api_utils.get_config_manager')
    @patch('requests.post')
    def test_call_llm_with_openai_config(self, mock_post, mock_config):
        """Should call OpenAI API when API_TYPE is openai"""
        from api_utils import call_llm

        # Mock config
        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_TYPE': 'openai',
            'API_URL': 'https://api.openai.com/v1',
            'API_KEY': 'sk-test',
            'LLM_MODEL': 'gpt-4'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Hello from GPT'}}]
        }
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Hi'}]
        result = call_llm(messages)

        # Verify OpenAI endpoint was called
        call_args = mock_post.call_args
        assert '/chat/completions' in call_args[0][0]

        # Verify OpenAI headers
        headers = call_args[1]['headers']
        assert 'Authorization' in headers
        assert headers['Authorization'].startswith('Bearer ')

        # Verify result
        assert result['success'] is True
        assert 'content' in result

    @patch('api_utils.get_config_manager')
    def test_call_llm_defaults_to_openai(self, mock_config):
        """Should default to OpenAI if API_TYPE not set"""
        from api_utils import call_llm

        # Mock config without API_TYPE
        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_URL': 'https://api.test.com/v1',
            'API_KEY': 'sk-test',
            'LLM_MODEL': 'test-model'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'test'}}]
            }
            mock_post.return_value = mock_response

            messages = [{'role': 'user', 'content': 'test'}]
            call_llm(messages)

            # Should use OpenAI format
            assert '/chat/completions' in mock_post.call_args[0][0]

    @patch('api_utils.get_config_manager')
    @patch('requests.post')
    def test_call_llm_with_custom_params(self, mock_post, mock_config):
        """Should support custom model, max_tokens, and temperature"""
        from api_utils import call_llm

        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_TYPE': 'openai',
            'API_URL': 'https://api.test.com/v1',
            'API_KEY': 'sk-test',
            'LLM_MODEL': 'default-model'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'test'}}]
        }
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'test'}]
        call_llm(
            messages,
            model='custom-model',
            max_tokens=2000,
            temperature=0.5
        )

        payload = mock_post.call_args[1]['json']
        assert payload['model'] == 'custom-model'
        assert payload['max_tokens'] == 2000
        assert payload['temperature'] == 0.5

    @patch('api_utils.get_config_manager')
    @patch('requests.post')
    def test_call_llm_handles_api_error(self, mock_post, mock_config):
        """Should handle API errors gracefully"""
        from api_utils import call_llm

        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_TYPE': 'openai',
            'API_URL': 'https://api.test.com/v1',
            'API_KEY': 'sk-test',
            'LLM_MODEL': 'test-model'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'test'}]
        result = call_llm(messages)

        assert result['success'] is False
        assert 'error' in result

    @patch('api_utils.get_config_manager')
    @patch('requests.post')
    def test_call_llm_stream_mode(self, mock_post, mock_config):
        """Should support streaming responses"""
        from api_utils import call_llm

        mock_cfg = Mock()
        mock_cfg.get.side_effect = lambda key, default=None: {
            'API_TYPE': 'openai',
            'API_URL': 'https://api.test.com/v1',
            'API_KEY': 'sk-test',
            'LLM_MODEL': 'test-model'
        }.get(key, default)
        mock_config.return_value = mock_cfg

        # Mock streaming response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'test'}]
        result = call_llm(messages, stream=True)

        # Should return the response object for streaming
        assert result is mock_response
        # Verify stream parameter was set
        assert mock_post.call_args[1]['json']['stream'] is True
