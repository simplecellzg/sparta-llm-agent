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


def sanitize_error_message(error_text: str) -> str:
    """
    Remove sensitive information (API keys, tokens) from error messages.

    This function replaces patterns that look like partially masked or full API keys
    with a generic placeholder to prevent sensitive information leakage.

    Args:
        error_text: The error message text that may contain sensitive info

    Returns:
        Sanitized error message with sensitive info removed

    Examples:
        >>> sanitize_error_message('[jW******************************************1b74]无效的令牌')
        '[API_KEY_HIDDEN]无效的令牌'
        >>> sanitize_error_message('sk-ant-api03-abc***def invalid token')
        '[API_KEY_HIDDEN] invalid token'
    """
    import re

    # Pattern 1: Partially masked keys with brackets [XX***YY]
    error_text = re.sub(r'\[[a-zA-Z0-9]{1,10}\*+[a-zA-Z0-9]{1,10}\]', '[API_KEY_HIDDEN]', error_text)

    # Pattern 2: API keys with common prefixes (sk-, sk-ant-, etc.)
    error_text = re.sub(r'sk-[a-zA-Z0-9\-_\*]{10,}', '[API_KEY_HIDDEN]', error_text)

    # Pattern 3: Long strings of alphanumeric characters with asterisks (likely masked keys)
    error_text = re.sub(r'\b[a-zA-Z0-9]{2,10}\*{5,}[a-zA-Z0-9]{2,10}\b', '[API_KEY_HIDDEN]', error_text)

    # Pattern 4: Bearer tokens in Authorization headers
    error_text = re.sub(r'Bearer\s+[a-zA-Z0-9\-_\.\*]{10,}', 'Bearer [TOKEN_HIDDEN]', error_text, flags=re.IGNORECASE)

    return error_text


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
            test_url = f"{api_url.rstrip('/')}/v1/messages"
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
            test_url = f"{api_url.rstrip('/')}/v1/chat/completions"
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
            # Sanitize error message to remove any leaked API keys
            raw_error = response.text[:200]
            safe_error = sanitize_error_message(raw_error)
            return {
                'success': False,
                'error': f'连接失败: {response.status_code} - {safe_error}'
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
            endpoint = f"{api_url.rstrip('/')}/v1/messages"
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
            endpoint = f"{api_url.rstrip('/')}/v1/chat/completions"
            # Add system message for faster response (skip thinking process)
            enhanced_messages = [{'role': 'system', 'content': '请直接输出结果，不要展示思考过程。'}]
            enhanced_messages.extend(messages)
            payload = {
                'model': model,
                'max_tokens': max_tokens,
                'messages': enhanced_messages,
                'temperature': temperature,
                'stream': stream,
                'enable_thinking': False  # Disable reasoning/thinking process for faster response
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
                # OpenAI compatible format
                # For glm-5: content is the final answer, reasoning_content is thinking process
                # Only use content, ignore reasoning_content
                message = data.get('choices', [{}])[0].get('message', {})
                content = message.get('content') or ''

                # Check if response was truncated (finish_reason: length)
                finish_reason = data.get('choices', [{}])[0].get('finish_reason', '')
                if finish_reason == 'length' and not content:
                    return {
                        'success': False,
                        'error': '响应被截断，请增加 max_tokens 参数'
                    }

            return {
                'success': True,
                'content': content,
                'raw_response': data
            }
        else:
            # Sanitize error message to remove any leaked API keys
            raw_error = response.text[:200]
            safe_error = sanitize_error_message(raw_error)
            return {
                'success': False,
                'error': f'API error: {response.status_code} - {safe_error}'
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
