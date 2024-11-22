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
from concurrent.futures import ThreadPoolExecutor

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
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Initialize database pool
            self.db_pool = DatabasePool('databases/interaction_logs.db')
            
            # Initialize rate limiting
            self.rate_limit_lock = asyncio.Lock()
            self.last_request_time = 0
            self.min_request_interval = 0.1  # 100ms between requests

            # Initialize database schema
            self._init_db()
            
            # Mark as initialized
            self._initialized = True
            
            # These will be initialized in setup()
            self.session = None
            self.openai_client = None
            self.infermatic_client = None

    async def setup(self):
        """Async initialization"""
        if self.session is None:
            # Initialize aiohttp session with custom headers and timeout
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
            self.session = aiohttp.ClientSession(
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Helicone-Auth': f'Bearer {HELICONE_API_KEY}',
                    'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                    'X-Title': 'SplinterTree by GwynTel'
                },
                timeout=timeout
            )
            
            # Initialize OpenAI client with Helicone Gateway URL
            self.openai_client = AsyncOpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url="https://gateway.helicone.ai/v1",
                default_headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Helicone-Auth': f'Bearer {HELICONE_API_KEY}',
                    'Helicone-Target-Url': "https://openrouter.ai/api",
                    'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                    'X-Title': 'SplinterTree by GwynTel',
                },
                timeout=30.0
            )

            # Initialize Infermatic client
            self.infermatic_client = AsyncOpenAI(
                api_key=HELICONE_API_KEY,
                base_url="https://gateway.helicone.ai/v1",
                default_headers={
                    'Authorization': f'Bearer {HELICONE_API_KEY}',
                    'Helicone-Auth': f'Bearer {HELICONE_API_KEY}',
                    'Helicone-Target-Url': "https://api.totalgpt.ai",
                    'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                    'X-Title': 'SplinterTree by GwynTel',
                },
                timeout=30.0
            )

    def _init_db(self):
        """Initialize database schema"""
        try:
            # Create the database directory if it doesn't exist
            os.makedirs('databases', exist_ok=True)
            
            with open('databases/schema.sql', 'r') as schema_file:
                schema_sql = schema_file.read()
            
            # Apply schema synchronously
            conn = sqlite3.connect('databases/interaction_logs.db')
            cursor = conn.cursor()
            
            # Split and execute each statement separately
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            for statement in statements:
                try:
                    cursor.execute(statement)
                    conn.commit()  # Commit after each statement
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):  # Ignore "table already exists" errors
                        raise
            
            conn.close()
            logger.info("[API] Successfully initialized database schema")
        except Exception as e:
            logger.error(f"[API] Failed to initialize database schema: {str(e)}")
            raise

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        async with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
            self.last_request_time = time.time()

    async def _validate_message_roles(self, messages: List[Dict]) -> List[Dict]:
        """Validate and normalize message roles for API compatibility"""
        if self.session is None:
            await self.setup()

        valid_roles = {"system", "user", "assistant", "tool"}
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

            # Handle tool messages
            if role == "tool":
                if "tool_call_id" in msg:
                    normalized_msg["tool_call_id"] = msg["tool_call_id"]
                if "name" in msg:
                    normalized_msg["name"] = msg["name"]
            
            # Handle multimodal content
            if isinstance(normalized_msg['content'], list):
                valid_content = []
                for item in normalized_msg['content']:
                    if isinstance(item, dict) and 'type' in item:
                        if item['type'] == 'text' and 'text' in item:
                            valid_content.append(item)
                        elif item['type'] == 'image_url' and 'image_url' in item:
                            if isinstance(item['image_url'], str):
                                url = item['image_url']
                            else:
                                url = item['image_url'].get('url', '')
                            
                            base64_image = await self._convert_image_to_base64(url)
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

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL with timeout and retries"""
        if self.session is None:
            await self.setup()

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

    async def _stream_response(self, stream, requested_at: int, payload: Dict, provider: str, user_id: str, guild_id: str, prompt_file: str, model_cog: str) -> AsyncGenerator[str, None]:
        """Handle streaming response with improved chunk handling"""
        full_response = ""
        try:
            async for chunk in stream:
                if not chunk or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    full_response += delta.content
                    yield delta.content
                elif hasattr(delta, 'tool_calls') and delta.tool_calls:
                    tool_call = delta.tool_calls[0]
                    if hasattr(tool_call, 'function'):
                        tool_data = {
                            'name': tool_call.function.name if hasattr(tool_call.function, 'name') else None,
                            'arguments': tool_call.function.arguments if hasattr(tool_call.function, 'arguments') else None
                        }
                        yield json.dumps(tool_data)
                        full_response += json.dumps(tool_data)

            # Log completion with full accumulated response
            received_at = int(time.time() * 1000)
            await self.report(
                requested_at=requested_at,
                received_at=received_at,
                req_payload=payload,
                resp_payload={"choices": [{"message": {"content": full_response}}]},
                status_code=200,
                tags={
                    "source": provider or "openrouter",
                    "user_id": str(user_id) if user_id else None,
                    "guild_id": str(guild_id) if guild_id else None,
                    "prompt_file": prompt_file,
                    "model_cog": model_cog,
                    "streaming": True
                },
                user_id=user_id,
                guild_id=guild_id
            )
        except Exception as e:
            logger.error(f"[API] Error in stream response: {str(e)}")
            error_msg = f"Error: {str(e)}"
            yield error_msg
            full_response += error_msg

    async def call_openpipe(self, messages: List[Dict[str, Union[str, List[Dict[str, Any]]]]], model: str, temperature: float = None, stream: bool = False, max_tokens: int = None, provider: str = None, user_id: str = None, guild_id: str = None, prompt_file: str = None, model_cog: str = None, tools: List[Dict] = None, tool_choice: Union[str, Dict] = None) -> Union[Dict, AsyncGenerator[str, None]]:
        """Call OpenRouter API with improved streaming support"""
        if self.session is None:
            await self.setup()

        try:
            await self._enforce_rate_limit()
            
            logger.debug(f"[API] Making OpenRouter request to model: {model}")
            logger.debug(f"[API] Stream mode: {stream}")
            
            validated_messages = await self._validate_message_roles(messages)
            
            # Prepare request payload
            payload = {
                "model": model,
                "messages": validated_messages,
                "temperature": temperature if temperature is not None else 0.7,
                "max_tokens": max_tokens if max_tokens is not None else 1000,
                "stream": stream
            }

            # Add tools if provided
            if tools:
                payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

            requested_at = int(time.time() * 1000)

            try:
                response = await self.openai_client.chat.completions.create(**payload)
                
                if stream:
                    return self._stream_response(response, requested_at, payload, provider, user_id, guild_id, prompt_file, model_cog)
                else:
                    received_at = int(time.time() * 1000)
                    
                    if not hasattr(response, 'choices') or not response.choices:
                        error_msg = f"Invalid response structure from OpenRouter API: {response}"
                        logger.error(f"[API] {error_msg}")
                        raise ValueError(error_msg)
                    
                    result = {
                        'choices': [{
                            'message': {
                                'content': response.choices[0].message.content,
                                'role': 'assistant'
                            }
                        }]
                    }

                    # Add tool calls if present
                    if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                        result['choices'][0]['message']['tool_calls'] = [
                            {
                                'id': tool_call.id,
                                'type': tool_call.type,
                                'function': {
                                    'name': tool_call.function.name,
                                    'arguments': tool_call.function.arguments
                                }
                            }
                            for tool_call in response.choices[0].message.tool_calls
                        ]
                    
                    # Log completion
                    await self.report(
                        requested_at=requested_at,
                        received_at=received_at,
                        req_payload=payload,
                        resp_payload=result,
                        status_code=200,
                        tags={
                            "source": provider or "openrouter",
                            "user_id": str(user_id) if user_id else None,
                            "guild_id": str(guild_id) if guild_id else None,
                            "prompt_file": prompt_file,
                            "model_cog": model_cog,
                            "streaming": False
                        },
                        user_id=user_id,
                        guild_id=guild_id
                    )
                    
                    return result

            except Exception as e:
                error_msg = f"OpenRouter API error: {str(e)}"
                logger.error(f"[API] {error_msg}")
                raise ValueError(error_msg)
            
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
        if self.session:
            await self.session.close()
        await self.db_pool.close()

# Global API instance
api = API()
