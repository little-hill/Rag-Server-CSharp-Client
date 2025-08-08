import requests
import logging
import aiohttp
import json

class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 360, max_tokens: int = 512, temperature: float = 0.1):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        # INITIALIZE HTTP SESSION
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
    def health_check(self):
        """CHECK OLLAMA SERVICE HEALTH"""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if not resp.ok:
                raise ConnectionError(f"Ollama service exception：{resp.text}")
        except Exception as e:
            self.logger.error(f"Ollama connection fails：{str(e)}")
            raise

    def generate(self, prompt: str, **kwargs):
        """GENERATE A RESPONSE FROM OLLAMA"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False, # STREAM RESPONSE
            "temperature": kwargs.get("temperature", self.temperature),  
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),    
        }
        
        try:
            self.logger.info(f"current timeout：{self.timeout} second")
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=(10, self.timeout) # CONNECTION TIMEOUT
                #stream=True # ACTIVATE STREAM RECIPIENCE
            )
            resp.raise_for_status()
            return resp.json().get("response", "cannot find validate response")  # PREVENT KEY ERROR
        except requests.exceptions.HTTPError as e:
            # RESPONSE IS AVAILABLE, BUT STATUS HAS EXCEPTION
            if e.response is not None:
                logging.error(f"HTTP error | state code：{e.response.status_code} | response content：{e.response.text}")
                return f"service response error：{e.response.text}"
            else:
                logging.error("HTTP error, but did not get response object")
                return "unknown HTTP error"
        except requests.exceptions.RequestException as e:
            # NETWORK ERROR (e.g., TIMEOUT, CONNECTION REJECTION）
            logging.error(f"network error | cause：{str(e)}")
            return "network connection fails.，please check service IP and port"
        except Exception as e:
            # UNKNOWN ERROR (e.g., JSON PARSE FAILURE）
            logging.error(f"unknown error | details：{str(e)}")
            return "exception when processing response"

    async def generate_stream(self, prompt: str):
        """流式生成响应"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,  # ACTIVATE STREAM
                "options": {"temperature": self.temperature, "max_tokens": self.max_tokens}
            }
            
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            ) as response:
                async for line in response.content:
                    if line:
                        chunk = line.decode('utf-8').strip()
                        if chunk:
                            try:
                                # EXTRACT CONTENT
                                data = json.loads(chunk)
                                yield data.get("response", "")
                            except json.JSONDecodeError:
                                yield ""

    