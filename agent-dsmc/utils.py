"""
工具函数模块
============

提供DSMC代理所需的通用工具函数。
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


# ==================== LLM调用 ====================

# 从环境变量或配置文件加载
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.mjdjourney.cn")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-4-5-20251101")
LLM_API_TYPE = os.getenv("LLM_API_TYPE", "anthropic")  # 'openai' or 'anthropic'


def call_llm(prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 16384, stream: bool = False, timeout: int = 60) -> str:
    """
    调用LLM API

    Args:
        prompt: 提示词
        model: 模型名称，默认使用环境变量配置
        temperature: 温度参数
        max_tokens: 最大token数
        stream: 是否流式输出
        timeout: 超时时间（秒），默认60秒

    Returns:
        LLM响应文本
    """
    if model is None:
        model = LLM_MODEL

    try:
        if LLM_API_TYPE == 'anthropic':
            # Anthropic API 格式
            endpoint = f"{LLM_API_URL.rstrip('/')}/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": LLM_API_KEY,
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "system": "请直接输出结果，不要展示思考过程。",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            if temperature != 0.7:
                payload["temperature"] = temperature
        else:
            # OpenAI 兼容格式
            endpoint = f"{LLM_API_URL.rstrip('/')}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "请直接输出结果，不要展示思考过程。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
                "enable_thinking": False
            }

        print(f"正在调用LLM API ({LLM_API_TYPE}格式, 超时: {timeout}秒)...")
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()

        if stream:
            return response  # 返回response对象供流式处理
        else:
            data = response.json()

            if LLM_API_TYPE == 'anthropic':
                # Anthropic 响应格式
                content = data.get('content', [{}])[0].get('text', '')
            else:
                # OpenAI 响应格式
                message = data['choices'][0]['message']
                content = message.get('content') or ''

                # Check if response was truncated
                finish_reason = data['choices'][0].get('finish_reason', '')
                if finish_reason == 'length' and not content:
                    print(f"LLM响应被截断，请增加 max_tokens")
                    return ""

            print(f"LLM调用成功，返回{len(content)}字符")
            return content

    except requests.exceptions.Timeout:
        print(f"LLM调用超时 (>{timeout}秒)")
        return ""
    except requests.exceptions.RequestException as e:
        print(f"LLM网络请求失败: {e}")
        return ""
    except (KeyError, IndexError, ValueError) as e:
        print(f"LLM响应解析失败: {e}")
        return ""
    except Exception as e:
        print(f"LLM调用失败: {e}")
        return ""


def call_llm_stream(prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 16384, timeout: int = 90):
    """
    流式调用LLM API

    Args:
        prompt: 提示词
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        timeout: 超时时间（秒），默认90秒

    Yields:
        文本片段
    """
    if model is None:
        model = LLM_MODEL

    try:
        if LLM_API_TYPE == 'anthropic':
            # Anthropic API 格式
            endpoint = f"{LLM_API_URL.rstrip('/')}/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": LLM_API_KEY,
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "system": "请直接输出结果，不要展示思考过程。",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            if temperature != 0.7:
                payload["temperature"] = temperature
        else:
            # OpenAI 兼容格式
            endpoint = f"{LLM_API_URL.rstrip('/')}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "请直接输出结果，不要展示思考过程。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }

        print(f"正在流式调用LLM API ({LLM_API_TYPE}格式, 超时: {timeout}秒)...")
        response = requests.post(endpoint, json=payload, headers=headers, stream=True, timeout=timeout)
        response.raise_for_status()

        chunk_count = 0

        if LLM_API_TYPE == 'anthropic':
            # Anthropic 流式响应格式
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]
                        try:
                            event = json.loads(data_str)
                            event_type = event.get('type', '')

                            if event_type == 'content_block_delta':
                                delta = event.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    content = delta.get('text', '')
                                    if content:
                                        chunk_count += 1
                                        yield content
                            elif event_type == 'message_stop':
                                break
                        except json.JSONDecodeError:
                            continue
        else:
            # OpenAI 流式响应格式
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    chunk_count += 1
                                    yield content
                        except json.JSONDecodeError:
                            continue

        print(f"流式LLM调用完成，共{chunk_count}个片段")

    except requests.exceptions.Timeout:
        print(f"流式LLM调用超时 (>{timeout}秒)")
        yield ""
    except requests.exceptions.RequestException as e:
        print(f"流式LLM网络请求失败: {e}")
        yield ""
    except Exception as e:
        print(f"流式LLM调用失败: {e}")
        yield ""


# ==================== 文件处理 ====================

def ensure_dir(path: str) -> Path:
    """
    确保目录存在，如不存在则创建

    Args:
        path: 目录路径

    Returns:
        Path对象
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json(file_path: str) -> Dict:
    """
    加载JSON文件

    Args:
        file_path: 文件路径

    Returns:
        JSON内容（字典）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON失败: {file_path}, 错误: {e}")
        return {}


def save_json(data: Dict, file_path: str):
    """
    保存JSON文件

    Args:
        data: 要保存的数据
        file_path: 文件路径
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存JSON失败: {file_path}, 错误: {e}")


def read_text_file(file_path: str) -> str:
    """
    读取文本文件

    Args:
        file_path: 文件路径

    Returns:
        文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败: {file_path}, 错误: {e}")
        return ""


def write_text_file(content: str, file_path: str):
    """
    写入文本文件

    Args:
        content: 文件内容
        file_path: 文件路径
    """
    try:
        # 确保父目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"写入文件失败: {file_path}, 错误: {e}")


# ==================== 数据验证 ====================

def validate_parameters(params: Dict, required_keys: List[str]) -> Tuple[bool, str]:
    """
    验证参数字典

    Args:
        params: 参数字典
        required_keys: 必需的键列表

    Returns:
        (is_valid: bool, error_message: str)
    """
    missing_keys = [key for key in required_keys if key not in params or params[key] is None]

    if missing_keys:
        return False, f"缺少必需参数: {', '.join(missing_keys)}"

    return True, ""


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    import re
    # 移除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除前后空格
    filename = filename.strip()
    return filename


# ==================== 时间处理 ====================

from datetime import datetime


def get_timestamp(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """
    获取当前时间戳

    Args:
        fmt: 时间格式

    Returns:
        格式化的时间字符串
    """
    return datetime.now().strftime(fmt)


def get_iso_timestamp() -> str:
    """
    获取ISO格式时间戳

    Returns:
        ISO格式时间字符串
    """
    return datetime.now().isoformat()


# ==================== UUID生成 ====================

import uuid


def generate_session_id() -> str:
    """
    生成会话ID，格式：时间戳_随机数

    Returns:
        格式为 YYYYMMDD_HHMMSS_随机数 的字符串
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]  # 取UUID的前8位作为随机数
    return f"{timestamp}_{random_suffix}"


# ==================== 辅助函数 ====================

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_code_block(text: str, language: str = None) -> str:
    """
    从Markdown文本中提取代码块

    Args:
        text: Markdown文本
        language: 代码语言（可选）

    Returns:
        提取的代码
    """
    import re

    if language:
        pattern = rf'```{language}\s*\n(.*?)```'
    else:
        pattern = r'```.*?\n(.*?)```'

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return text


# ==================== 网络请求 ====================

def download_file(url: str, save_path: str, timeout: int = 300) -> bool:
    """
    下载文件

    Args:
        url: 文件URL
        save_path: 保存路径
        timeout: 超时时间（秒）

    Returns:
        是否成功
    """
    try:
        print(f"正在下载: {url}")
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        # 确保父目录存在
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"下载成功: {save_path}")
        return True

    except Exception as e:
        print(f"下载失败: {e}")
        return False
