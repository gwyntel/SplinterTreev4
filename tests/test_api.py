import pytest
import aiohttp
import json
from unittest.mock import Mock, patch, AsyncMock
from shared.api import API
from config import HELICONE_API_KEY, OPENROUTER_API_KEY, OPENPIPE_API_KEY

@pytest.fixture
async def api():
    api_instance = API()
    await api_instance.setup()
    yield api_instance
    await api_instance.close()

def test_helicone_headers():
    """Test Helicone header construction"""
    api = API()
    
    # Test with all parameters
    headers = api._get_helicone_headers(
        provider="test_provider",
        user_id="123",
        guild_id="456",
        prompt_file="test.txt",
        model_cog="test_cog"
    )
    
    assert headers['Helicone-Auth'] == f'Bearer {HELICONE_API_KEY}'
    assert headers['Helicone-Cache-Enabled'] == 'true'
    assert headers['Helicone-Target-Url'] == 'https://api.openpipe.ai/api/v1'
    assert headers['Helicone-Property-Source'] == 'test_provider'
    assert headers['Helicone-Property-User-Id'] == '123'
    assert headers['Helicone-Property-Guild-Id'] == '456'
    assert headers['Helicone-Property-Prompt-File'] == 'test.txt'
    assert headers['Helicone-Property-Model-Cog'] == 'test_cog'
    
    # Test with minimal parameters
    headers = api._get_helicone_headers()
    assert headers['Helicone-Property-Source'] == 'unknown'
    assert headers['Helicone-Property-User-Id'] == 'unknown'

@pytest.mark.asyncio
async def test_api_client_initialization(api):
    """Test API clients are properly initialized with Helicone headers"""
    assert api.session is not None
    assert 'Helicone-Auth' in api.session._default_headers
    assert 'Helicone-Target-Url' in api.session._default_headers
    
    assert api.openai_client is not None
    assert api.openai_client.base_url == "https://gateway.helicone.ai/v1"
    assert 'Helicone-Auth' in api.openai_client.default_headers
    
    assert api.openpipe_client is not None
    assert api.openpipe_client.base_url == "https://gateway.helicone.ai/v1"
    assert 'Helicone-Auth' in api.openpipe_client.default_headers

@pytest.mark.asyncio
async def test_rate_limiting(api):
    """Test rate limiting functionality"""
    # Test rapid requests are properly delayed
    start_time = api.last_request_time
    await api._enforce_rate_limit()
    first_delay = api.last_request_time - start_time
    
    await api._enforce_rate_limit()
    second_delay = api.last_request_time - start_time
    
    assert second_delay - first_delay >= api.min_request_interval

@pytest.mark.asyncio
async def test_openpipe_call_with_helicone(api):
    """Test OpenPipe API call with Helicone integration"""
    messages = [{"role": "user", "content": "Hello"}]
    
    # Mock the OpenPipe client response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content="Hello! How can I help you?",
                role="assistant"
            )
        )
    ]
    
    with patch.object(api.openpipe_client.chat.completions, 'create', 
                     new_callable=AsyncMock, return_value=mock_response) as mock_create:
        
        result = await api.call_openpipe(
            messages=messages,
            model="test-model",
            provider="test",
            user_id="123",
            guild_id="456"
        )
        
        # Verify the call was made with correct parameters
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['model'] == "test-model"
        assert call_kwargs['messages'] == messages
        
        # Verify Helicone headers were included
        assert 'Helicone-Auth' in api.openpipe_client.default_headers
        assert 'Helicone-Target-Url' in api.openpipe_client.default_headers
        
        # Verify response structure
        assert result['choices'][0]['message']['content'] == "Hello! How can I help you?"
        assert result['choices'][0]['message']['role'] == "assistant"

@pytest.mark.asyncio
async def test_helicone_rate_limit_handling(api):
    """Test handling of Helicone rate limits"""
    messages = [{"role": "user", "content": "Hello"}]
    
    # Mock response with rate limit header
    mock_response = Mock()
    mock_response.headers = {'Retry-After': '1'}
    mock_response.choices = [
        Mock(
            message=Mock(
                content="Rate limited response",
                role="assistant"
            )
        )
    ]
    
    # Mock the create method to first return rate limit, then success
    with patch.object(api.openpipe_client.chat.completions, 'create', 
                     new_callable=AsyncMock, 
                     side_effect=[mock_response, mock_response]) as mock_create:
        
        result = await api.call_openpipe(
            messages=messages,
            model="test-model"
        )
        
        # Verify retry was attempted
        assert mock_create.call_count == 2
        assert result['choices'][0]['message']['content'] == "Rate limited response"

@pytest.mark.asyncio
async def test_streaming_response(api):
    """Test streaming response handling"""
    messages = [{"role": "user", "content": "Hello"}]
    
    # Mock streaming response chunks
    chunks = [
        Mock(choices=[Mock(delta=Mock(content="Hello"))]),
        Mock(choices=[Mock(delta=Mock(content=" world"))]),
        Mock(choices=[Mock(delta=Mock(content="!"))])
    ]
    
    mock_response = AsyncMock()
    mock_response.__aiter__.return_value = chunks
    
    with patch.object(api.openpipe_client.chat.completions, 'create',
                     new_callable=AsyncMock,
                     return_value=mock_response):
        
        accumulated_response = ""
        async for chunk in await api.call_openpipe(
            messages=messages,
            model="test-model",
            stream=True
        ):
            accumulated_response += chunk
        
        assert accumulated_response == "Hello world!"

@pytest.mark.asyncio
async def test_error_handling(api):
    """Test API error handling"""
    messages = [{"role": "user", "content": "Hello"}]
    
    # Mock API error
    with patch.object(api.openpipe_client.chat.completions, 'create',
                     new_callable=AsyncMock,
                     side_effect=Exception("API Error")):
        
        with pytest.raises(Exception) as exc_info:
            await api.call_openpipe(
                messages=messages,
                model="test-model"
            )
        
        assert "OpenPipe API error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_message_role_validation(api):
    """Test message role validation"""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "invalid_role", "content": "Should be filtered"},
        {"role": "assistant", "content": "Hi"}
    ]
    
    validated = await api._validate_message_roles(messages)
    
    assert len(validated) == 2
    assert validated[0]['role'] == "user"
    assert validated[1]['role'] == "assistant"

@pytest.mark.asyncio
async def test_report_interaction(api):
    """Test interaction reporting"""
    await api.report(
        requested_at=123,
        received_at=456,
        req_payload={"test": "request"},
        resp_payload={"test": "response"},
        status_code=200,
        tags={"source": "test"},
        user_id="123",
        guild_id="456"
    )
    
    # Verify database connection was properly handled
    # Note: Since we're using an in-memory database for tests,
    # we mainly verify no exceptions were raised
