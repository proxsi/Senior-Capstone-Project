# DeepSeek HTTP chat adapter with legacy Gemini-compatible import names.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""DeepSeek chat adapter retaining the gemini_client name for existing imports."""
import http.client
import json
import logging
import socket
import time
from typing import Optional, List, Dict, Any

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek HTTP chat-completion client."""

    # Class-level timestamp shared across instances to keep provider calls throttled.
    _last_request_time = 0.0
    _min_interval = 0.3

    def __init__(self, api_key: Optional[str] = None):
        """Resolve the API key, base URL, model names, and endpoint from configuration."""
        self.api_key = api_key or config.DEEPSEEK_API_KEY
        self.base_url = config.DEEPSEEK_BASE_URL
        self.model = config.DEEPSEEK_MODEL
        self.vision_model = config.VISION_MODEL or self.model
        self.endpoint = config.CHAT_API_ENDPOINT

    def _wait_for_rate_limit(self):
        """Wait until the minimum interval since the previous provider request has elapsed."""
        elapsed = time.time() - DeepSeekClient._last_request_time
        if elapsed < DeepSeekClient._min_interval:
            time.sleep(DeepSeekClient._min_interval - elapsed)
        DeepSeekClient._last_request_time = time.time()

    def _build_messages(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        image_data_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Combine the system instruction, history, and current text or image into chat messages."""
        messages: List[Dict[str, Any]] = []

        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        if conversation_history:
            for item in conversation_history:
                role = item.get("role", "user")
                content = item.get("content", "")
                if not content:
                    continue
                messages.append({"role": role, "content": content})

        if image_data_url:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        return messages

    def _build_payload(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        image_data_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate legacy generation options into the provider chat-completion payload."""
        # Start from the shared defaults, then let the caller override individual keys.
        config_dict = config.DEFAULT_GENERATION_CONFIG.copy()
        if generation_config:
            config_dict.update(generation_config)

        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": self._build_messages(
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                image_data_url=image_data_url,
            ),
            "stream": stream,
            "temperature": config_dict.get("temperature", 1),
            "top_p": config_dict.get("topP", 1),
        }

        if "maxOutputTokens" in config_dict:
            payload["max_tokens"] = config_dict["maxOutputTokens"]

        return payload

    def _parse_response(self, data: str) -> str:
        """Extract assistant content from the provider JSON, returning an error message on malformed responses."""
        try:
            response_json = json.loads(data)
            choices = response_json.get("choices", [])
            if not choices:
                logger.warning(f"响应格式异常: {data[:500]}")
                return ""

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if isinstance(content, str):
                return content

            if isinstance(content, list):
                # Multimodal replies may arrive as parts; only text parts are concatenated.
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                return "".join(text_parts)

            return str(content)
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return ""

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        max_retries: int = 3,
        timeout: int = 120,
        image_data_url: Optional[str] = None,
        model: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Send an HTTP chat request with bounded retries; return complete text rather than incremental tokens."""
        # Tool calling is accepted for interface compatibility but not implemented by this adapter.
        del tools
        conn = None
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                payload = self._build_payload(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    generation_config=generation_config,
                    conversation_history=conversation_history,
                    stream=stream,
                    image_data_url=image_data_url,
                    model=model,
                )
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                conn = http.client.HTTPSConnection(self.base_url, timeout=timeout)
                conn.request("POST", self.endpoint, json.dumps(payload), headers)
                response = conn.getresponse()
                data = response.read().decode("utf-8")
                status = response.status
                conn.close()
                conn = None

                if status == 200:
                    return self._parse_response(data)
                if status == 429 and attempt < max_retries - 1:
                    wait_time = min(2 ** (attempt + 1), 20)
                    logger.warning(f"DeepSeek 限流，{wait_time} 秒后重试")
                    time.sleep(wait_time)
                    continue

                logger.error(f"DeepSeek 请求失败: {status} - {data[:500]}")
                if attempt < max_retries - 1:
                    # Non-retryable statuses still get exponential backoff before the last attempt.
                    time.sleep(2 ** (attempt + 1))
                    continue
                # The final attempt returns an in-band error string instead of raising.
                return f"抱歉，API请求失败（状态码: {status}）"
            except socket.timeout:
                logger.error(f"DeepSeek 请求超时 (timeout={timeout}s)")
                if conn:
                    conn.close()
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return "抱歉，请求超时，请稍后再试。"
            except Exception as e:
                logger.error(f"DeepSeek 调用失败: {e}")
                if conn:
                    conn.close()
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                return f"抱歉，生成内容时出现错误：{str(e)}"

        return "抱歉，服务暂时繁忙，请稍后再试。"

    def describe_image(
        self,
        prompt: str,
        image_data_url: str,
        system_instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        timeout: int = 180,
    ) -> str:
        """Send base64 image content through the configured vision model; provider vision support is required."""
        return self.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            generation_config=generation_config,
            stream=False,
            timeout=timeout,
            image_data_url=image_data_url,
            model=self.vision_model,
        )

    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Delegate a conversation turn to the shared content-generation implementation."""
        return self.generate_content(
            prompt=message,
            conversation_history=conversation_history,
            system_instruction=system_instruction,
            stream=False,
        )


# Shared instance preserving the historical gemini_client interface.
gemini_client = DeepSeekClient()


if __name__ == "__main__":
    print("测试 DeepSeek 对话模型...")
    response = gemini_client.generate_content(
        prompt="你好，请介绍一下你自己。",
        system_instruction="你是一个有用的助手。",
        stream=False,
    )
    print(f"AI回复: {response}")
