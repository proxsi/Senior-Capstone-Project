# Sign iFlytek WebSocket requests and collect MP3 audio frames.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""iFlytek WebSocket text-to-speech adapter for digital-human audio replies."""
import base64
import hashlib
import hmac
import json
import logging
from email.utils import formatdate
from typing import Optional

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XFTTSClient:
    """Sign iFlytek TTS requests and collect synthesized audio frames."""

    def __init__(self):
        """Load iFlytek credentials and select the voice and WebSocket target."""
        self.app_id = getattr(config, 'XF_APP_ID', 'your_xfyun_app_id')
        self.api_key = getattr(config, 'XF_API_KEY', 'your_xfyun_api_key')
        self.api_secret = getattr(config, 'XF_API_SECRET', 'your_xfyun_api_secret')
        self.voice_name = 'x4_lingxiaoxuan'
        self.url_host = 'tts-api.xfyun.cn'
        self.url_path = '/v2/tts'

    def _build_auth_url(self) -> str:
        """Build a date-stamped HMAC-SHA256 authorization URL for the iFlytek WebSocket."""
        # The signature covers host, date, and request line, and the server rejects stale dates.
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        signature_origin = f"host: {self.url_host}\ndate: {date}\nGET {self.url_path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode()
        auth_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(auth_origin.encode()).decode()
        return (
            f"wss://{self.url_host}{self.url_path}?authorization={authorization}"
            f"&date={date}&host={self.url_host}"
        )

    def synthesize(self, text: str) -> Optional[bytes]:
        """Send UTF-8 text, collect decoded audio frames until completion, and return MP3 bytes or None."""
        try:
            import websocket

            audio_chunks = []

            def on_message(ws, message):
                """Append successful audio frames and close the socket after completion or a provider error."""
                data = json.loads(message)
                code = data.get('code', -1)
                if code == 0:
                    audio_b64 = data['data']['audio']
                    audio_chunks.append(base64.b64decode(audio_b64))
                    if data['data'].get('status') == 2:
                        ws.close()
                else:
                    logger.error(f"讯飞 TTS 错误: {data.get('message')}")
                    ws.close()

            payload = {
                'common': {'app_id': self.app_id},
                # `aue: lame` requests MP3 frames; the text itself is base64 because the frame is JSON.
                'business': {
                    'aue': 'lame',
                    'auf': 'audio/L16;rate=16000',
                    'vcn': self.voice_name,
                    'speed': 50,
                    'volume': 80,
                    'pitch': 50,
                    'tte': 'UTF8',
                },
                'data': {
                    'status': 2,
                    'text': base64.b64encode(text.encode('utf-8')).decode(),
                },
            }

            ws = websocket.WebSocketApp(
                self._build_auth_url(),
                on_open=lambda ws: ws.send(json.dumps(payload)),
                on_message=on_message,
            )
            # run_forever blocks until on_message closes the socket or the connection drops.
            ws.run_forever()
            return b''.join(audio_chunks) if audio_chunks else None
        except Exception as e:
            logger.error(f"讯飞 TTS 合成失败: {e}")
            return None

    def synthesize_to_base64(self, text: str) -> Optional[str]:
        """Encode synthesized MP3 bytes for the JSON API response, or return None on failure."""
        audio = self.synthesize(text)
        return base64.b64encode(audio).decode('utf-8') if audio else None


tts_client = XFTTSClient()
