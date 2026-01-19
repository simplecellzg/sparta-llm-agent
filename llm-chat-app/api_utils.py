"""
API utility functions
"""
import requests
from typing import Dict, Optional, List, Union, Any
from config_manager import get_config_manager


def mask_api_key(value: str) -> str:
    """
    Mask API key, showing first 5 and last 4 characters.

    Args:
        value: The API key to mask

    Returns:
        Masked API key string

    Examples:
        >>> mask_api_key("sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d")
        'sk-LG****************************E12d'
        >>> mask_api_key("short")
        '***'
    """
    if len(value) <= 9:
        return '***'

    return value[:5] + '*' * (len(value) - 9) + value[-4:]


def test_api_connection(
    api_url: str,
    api_key: str,
    model: str,
    api_type: str = 'openai'
) -> Dict[str, any]:
    """
    Test API connection with provided credentials.

    Args:
        api_url: The base API URL
        api_key: The API key
        model: The model name to test with
        api_type: The API type ('anthropic' or 'openai')

    Returns:
        Dictionary with 'success' boolean and optional 'message' or 'error'

    Examples:
        >>> result = test_api_connection(
        ...     api_url='https://api.anthropic.com/v1',
        ...     api_key='sk-ant-test',
        ...     model='claude-sonnet-4-5',
        ...     api_type='anthropic'
        ... )
        >>> result['success']
        True
    """
    try:
        if api_type == 'anthropic':
            # Anthropic API format
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            }
            test_url = f"{api_url.rstrip('/')}/messages"
            payload = {
                'model': model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'test'}]
            }
        else:
            # OpenAI compatible API format
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            test_url = f"{api_url.rstrip('/')}/chat/completions"
            payload = {
                'model': model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'test'}]
            }

        response = requests.post(
            test_url,
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            return {'success': True, 'message': '连接成功'}
        else:
            return {
                'success': False,
                'error': f'连接失败: {response.status_code} - {response.text[:100]}'
            }

    except requests.Timeout:
        return {
            'success': False,
            'error': 'Connection timeout'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Connection error: {str(e)}'
        }


def call_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    stream: bool = False
) -> Union[Dict[str, Any], requests.Response]:
    """
    Unified LLM API calling interface that handles both Anthropic and OpenAI formats.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        model: Model name (defaults to config LLM_MODEL)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        stream: Whether to stream the response

    Returns:
        If stream=False: Dictionary with 'success' and 'content' or 'error'
        If stream=True: requests.Response object for streaming

    Examples:
        >>> result = call_llm([{'role': 'user', 'content': 'Hello'}])
        >>> result['success']
        True
        >>> result['content']
        'Hello! How can I help you today?'
    """
    config = get_config_manager()
    api_type = config.get('API_TYPE', 'openai')
    api_url = config.get('API_URL')
    api_key = config.get('API_KEY')
    model = model or config.get('LLM_MODEL')

    try:
        if api_type == 'anthropic':
            # Anthropic API format
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            }
            endpoint = f"{api_url.rstrip('/')}/messages"
            payload = {
                'model': model,
                'max_tokens': max_tokens,
                'messages': messages,
                'stream': stream
            }
            if temperature != 0.7:  # Only include if not default
                payload['temperature'] = temperature

        else:
            # OpenAI compatible API format
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            endpoint = f"{api_url.rstrip('/')}/chat/completions"
            payload = {
                'model': model,
                'max_tokens': max_tokens,
                'messages': messages,
                'temperature': temperature,
                'stream': stream
            }

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            stream=stream,
            timeout=90
        )

        # If streaming, return the response object directly
        if stream:
            return response

        # For non-streaming, parse the response
        if response.status_code == 200:
            data = response.json()

            # Extract content based on API type
            if api_type == 'anthropic':
                content = data.get('content', [{}])[0].get('text', '')
            else:
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')

            return {
                'success': True,
                'content': content,
                'raw_response': data
            }
        else:
            return {
                'success': False,
                'error': f'API error: {response.status_code} - {response.text[:200]}'
            }

    except requests.Timeout:
        return {
            'success': False,
            'error': 'Request timeout'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error calling LLM: {str(e)}'
        }
