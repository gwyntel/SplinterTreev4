import os
import logging
import time
import json
import asyncio
import sqlite3
import base64
from typing import Dict, Any, List, Union, AsyncGenerator, Optional
import aiohttp
import backoff
from contextlib import asynccontextmanager
from urllib.parse import urlparse, urljoin
from config import OPENROUTER_API_KEY, HELICONE_API_KEY
from openai import AsyncOpenAI

# Create required directories before configuring logging
os.makedirs('logs', exist_ok=True)
os.makedirs('databases', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = database_path
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.executor = ThreadPoolExecutor(max_workers=max_connections)
        
        # Initialize the pool with connections
        for _ in range(max_connections):
            conn = sqlite3.connect(database_path)
            conn.row_factory = sqlite3.Row
            self.pool.put_nowait(conn)
    
    @asynccontextmanager
    async def acquire(self):
        conn = await self.pool.get()
        try:
            yield conn
        finally:
            # Reset the connection state before returning it to the pool
            conn.rollback()
            await self.pool.put(conn)
    
    async def close(self):
        while not self.pool.empty():
            conn = await self.pool.get()
            conn.close()
        self.executor.shutdown()

class API:
    def __init__(self):
        # Initialize database pool
        self.db_pool = DatabasePool('databases/interaction_logs.db')
        
        # Initialize aiohttp session with custom headers and timeout
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
        self.session = aiohttp.ClientSession(
            headers={
                'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                'X-Title': 'SplinterTree by GwynTel'
            },
            timeout=timeout
        )
        
        # Initialize OpenAI client with OpenRouter base URL and OpenRouter API key
        self.openai_client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                'X-Title': 'SplinterTree by GwynTel',
            },
            timeout=30.0
        )
        
        # Rate limiting
        self.rate_limit_lock = asyncio.Lock()
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests

        # Initialize database schema
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        try:
            with open('databases/schema.sql', 'r') as schema_file:
                schema_sql = schema_file.read()
            
            async def init_schema():
                async with self.db_pool.acquire() as conn:
                    cursor = conn.cursor()
                    statements = schema_sql.split(';')
                    for statement in statements:
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)
                    conn.commit()
            
            # Run schema initialization in event loop
            loop = asyncio.get_event_loop()
            loop.run_until_complete(init_schema())
            logger.info("[API] Successfully initialized database schema")
        except Exception as e:
            logger.error(f"[API] Failed to initialize database schema: {str(e)}")
            raise

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL with timeout and retries"""
        @backoff.on_exception(
            backoff.expo,
            (aiohttp.ClientError, asyncio.TimeoutError),
            max_tries=3
        )
        async def _download():
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"[API] Failed to download image. Status code: {response.status}")
                    return None
            except Exception as e:
                logger.error(f"[API] Error downloading image: {str(e)}")
                return None
        
        return await _download()

    async def _convert_image_to_base64(self, url: str) -> Optional[str]:
        """Convert image URL to base64 with error handling"""
        try:
            image_data = await self._download_image(url)
            if image_data:
                mime_type = self._detect_mime_type(image_data)
                base64_image = base64.b64encode(image_data).decode('utf-8')
                return f"data:{mime_type};base64,{base64_image}"
            return None
        except Exception as e:
            logger.error(f"[API] Error converting image to base64: {str(e)}")
            return None

    def _detect_mime_type(self, image_data: bytes) -> str:
        """Detect MIME type of image data"""
        signatures = {
            b'\xFF\xD8\xFF': 'image/jpeg',
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif',
            b'RIFF': 'image/webp'
        }
        
        for signature, mime_type in signatures.items():
            if image_data.startswith(signature):
                return mime_type
        
        return 'application/octet-stream'

    async def _validate_message_roles(self, messages: List[Dict]) -> List[Dict]:
        """Validate and normalize message roles for API compatibility"""
        valid_roles = {"system", "user", "assistant"}
        normalized_messages = []
        
        for msg in messages:
            role = msg.get('role', '').lower()
            
            if role not in valid_roles:
                logger.warning(f"[API] Skipping message with invalid role: {role}")
                continue
            
            normalized_msg = {
                "role": role,
                "content": msg.get('content', '')
            }
            
            if isinstance(normalized_msg['content'], list):
                valid_content = []
                for item in normalized_msg['content']:
                    if isinstance(item, dict) and 'type' in item:
                        if item['type'] == 'text' and 'text' in item:
                            valid_content.append(item)
                        elif item['type'] == 'image_url' and 'image_url' in item:
                            base64_image = await self._convert_image_to_base64(item['image_url'])
                            if base64_image:
                                valid_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": base64_image
                                    }
                                })
                normalized_msg['content'] = valid_content
            
            normalized_messages.append(normalized_msg)
        
        return normalized_messages

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        async with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
            self.last_request_time = time.time()

    async def _stream_openrouter_request(self, messages, model, temperature, max_tokens, user_id=None, guild_id=None, prompt_file=None, model_cog=None):
        """Stream responses from OpenRouter API"""
        logger.debug(f"[API] Making OpenRouter streaming request to model: {model}")
        
        try:
            await self._enforce_rate_limit()
            
            validated_messages = await self._validate_message_roles(messages)
            
            extra_headers = {
                'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                'X-Title': 'SplinterTree by GwynTel'
            }
            
            stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=validated_messages,
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=max_tokens if max_tokens is not None else 1000,
                stream=True,
                extra_headers=extra_headers
            )
            requested_at = int(time.time() * 1000)
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.get('content'):
                    yield chunk.choices[0].delta['content']
            
            received_at = int(time.time() * 1000)
            
            tags = {
                "source": "openrouter",
                "user_id": str(user_id) if user_id else None,
                "guild_id": str(guild_id) if guild_id else None,
                "prompt_file": prompt_file,
                "model_cog": model_cog
            }
            
            completion_obj = {
                'choices': [{
                    'message': {
                        'content': "Streaming response completed"
                    }
                }]
            }
            
            await self.report(
                requested_at=requested_at,
                received_at=received_at,
                req_payload={
                    "model": model,
                    "messages": validated_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                resp_payload=completion_obj,
                status_code=200,
                tags=tags,
                user_id=user_id,
                guild_id=guild_id
            )
        except Exception as e:
            error_message = str(e)
            logger.error(f"[API] OpenRouter streaming error: {error_message}")
            raise Exception(f"OpenRouter API error: {error_message}")

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError, Exception),
        max_tries=5,
        max_time=60
    )
    async def call_openrouter(self, messages: List[Dict[str, Union[str, List[Dict[str, Any]]]]], model: str, temperature: float = None, stream: bool = False, max_tokens: int = None, user_id: str = None, guild_id: str = None, prompt_file: str = None, model_cog: str = None) -> Union[Dict, AsyncGenerator[str, None]]:
        try:
            await self._enforce_rate_limit()
            
            logger.debug(f"[API] Making OpenRouter request to model: {model}")
            logger.debug(f"[API] Request messages structure:")
            for msg in messages:
                logger.debug(f"[API] Message role: {msg.get('role')}")
                logger.debug(f"[API] Message content: {msg.get('content')}")
            
            validated_messages = await self._validate_message_roles(messages)
            
            extra_headers = {
                'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                'X-Title': 'SplinterTree by GwynTel'
            }
            
            if stream:
                return self._stream_openrouter_request(messages, model, temperature, max_tokens, user_id, guild_id, prompt_file, model_cog)
            else:
                requested_at = int(time.time() * 1000)
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=validated_messages,
                    temperature=temperature if temperature is not None else 0.7,
                    max_tokens=max_tokens if max_tokens is not None else 1000,
                    extra_headers=extra_headers
                )
                received_at = int(time.time() * 1000)
                
                result = {
                    'choices': [{
                        'message': {
                            'content': response.choices[0].message.content
                        }
                    }]
                }
                
                tags = {
                    "source": "openrouter",
                    "user_id": str(user_id) if user_id else None,
                    "guild_id": str(guild_id) if guild_id else None,
                    "prompt_file": prompt_file,
                    "model_cog": model_cog
                }
                
                await self.report(
                    requested_at=requested_at,
                    received_at=received_at,
                    req_payload={
                        "model": model,
                        "messages": validated_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    resp_payload=result,
                    status_code=200,
                    tags=tags,
                    user_id=user_id,
                    guild_id=guild_id
                )
                
                return result
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"[API] OpenRouter error: {error_message}")
            raise Exception(f"OpenRouter API error: {error_message}")

    async def report(self, requested_at: int, received_at: int, req_payload: Dict, resp_payload: Dict, status_code: int, tags: Dict = None, user_id: str = None, guild_id: str = None):
        """Report interaction metrics with improved error handling"""
        try:
            if tags is None:
                tags = {}
            tags_str = json.dumps(tags)

            async with self.db_pool.acquire() as conn:
                cursor = conn.cursor()
                sql = """
                    INSERT INTO logs (
                        requested_at, received_at, request, response, 
                        status_code, tags, user_id, guild_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                values = (
                    requested_at, received_at, json.dumps(req_payload),
                    json.dumps(resp_payload), status_code, tags_str,
                    user_id, guild_id
                )

                cursor.execute(sql, values)
                conn.commit()
                logger.debug(f"[API] Logged interaction with status code {status_code}")

        except Exception as e:
            logger.error(f"[API] Failed to report interaction: {str(e)}")

    async def close(self):
        """Cleanup resources"""
        await self.session.close()
        await self.db_pool.close()

# Global API instance
api = API()
