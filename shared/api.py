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
            with open('databases/schema.sql', 'r') as schema_file:
                schema_sql = schema_file.read()
            
            # Apply schema synchronously
            conn = sqlite3.connect('databases/interaction_logs.db')
            cursor = conn.cursor()
            statements = schema_sql.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
            conn.commit()
            conn.close()
            logger.info("[API] Successfully initialized database schema")
        except Exception as e:
            logger.error(f"[API] Failed to initialize database schema: {str(e)}")
            raise

    async def call_openpipe(self, messages: List[Dict[str, Union[str, List[Dict[str, Any]]]]], model: str, temperature: float = None, stream: bool = False, max_tokens: int = None, provider: str = None, user_id: str = None, guild_id: str = None, prompt_file: str = None, model_cog: str = None, tools: List[Dict] = None, tool_choice: Union[str, Dict] = None) -> Union[Dict, AsyncGenerator[str, None]]:
        """Call OpenRouter API with support for all features"""
        if self.session is None:
            await self.setup()

        try:
            await self._enforce_rate_limit()
            
            logger.debug(f"[API] Making OpenRouter request to model: {model}")
            logger.debug(f"[API] Request messages structure:")
            for msg in messages:
                logger.debug(f"[API] Message role: {msg.get('role')}")
                logger.debug(f"[API] Message content: {msg.get('content')}")
            
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

            # Make API request
            if stream:
                stream = await self.openai_client.chat.completions.create(**payload)
                requested_at = int(time.time() * 1000)
                return self._stream_response(stream, requested_at, payload, provider, user_id, guild_id, prompt_file, model_cog)
            else:
                requested_at = int(time.time() * 1000)
                response = await self.openai_client.chat.completions.create(**payload)
                received_at = int(time.time() * 1000)
                
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
                        "model_cog": model_cog
                    },
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
        if self.session:
            await self.session.close()
        await self.db_pool.close()

# Global API instance
api = API()
