import pytest
import aiohttp
import json
from unittest.mock import Mock, patch, AsyncMock
from shared.api import API, OPENPIPE_API_URL, HELICONE_API_URL
from config.config import HELICONE_API_KEY, OPENROUTER_API_KEY, OPENPIPE_API_KEY

@pytest.fixture
async def api():
    """Create and setup API instance for testing"""
    api_instance = API()
    await api_instance.setup()
    try:
        yield api_instance
    finally:
        await api_instance.close()

def test_helicone_headers():
    """Test Helicone header construction"""
    api = API()

    # Test with all parameters
    headers = api._get_helicone_headers(
        provider="openpipe:xai",
        user_id="123",
        guild_id="456",
        prompt_file="test.txt",
        model_cog="test_cog"
    )

    assert headers['Helicone-Auth'] == f'Bearer {HELICONE_API_KEY}'
    assert headers['Authorization'] == f'Bearer {OPENPIPE_API_KEY}'
    assert headers['Helicone-Cache-Enabled'] == 'true'
    assert headers['Helicone-OpenPipe-Path'] == '/xai/v1'
    assert headers['Helicone-Property-User-Id'] == '123'
    assert headers['Helicone-Property-Guild-Id'] == '456'
    assert headers['Helicone-Property-Prompt-File'] == 'test.txt'
    assert headers['Helicone-Property-Model-Cog'] == 'test_cog'

    # Test with minimal parameters
    headers = api._get_helicone_headers()
    assert headers['Helicone-OpenPipe-Path'] == '/xai/v1'
    assert headers['Helicone-Property-User-Id'] == 'unknown'

@pytest.mark.asyncio
async def test_api_client_initialization():
    """Test API clients are properly initialized with Helicone headers"""
    api = API()
    await api.setup()

    try:
        assert api.session is not None
        assert 'Helicone-Auth' in api.session._default_headers
        assert 'Authorization' in api.session._default_headers

        assert api.openai_client is not None
        assert str(api.openai_client.base_url).rstrip('/') == f"{HELICONE_API_URL}/v1"
        assert 'Helicone-Auth' in api.openai_client.default_headers

        assert api.openpipe_client is not None
        assert str(api.openpipe_client.base_url).rstrip('/') == f"{HELICONE_API_URL}/v1"
        assert 'Helicone-Auth' in api.openpipe_client.default_headers
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting functionality"""
    api = API()
    await api.setup()

    try:
        # Test rapid requests are properly delayed
        start_time = api.last_request_time
        await api._enforce_rate_limit()
        first_delay = api.last_request_time - start_time

        await api._enforce_rate_limit()
        second_delay = api.last_request_time - start_time

        assert second_delay - first_delay >= api.min_request_interval
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_openpipe_call_with_helicone():
    """Test OpenPipe API call with Helicone integration"""
    api = API()
    await api.setup()

    try:
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

        async def mock_create(**kwargs):
            return mock_response

        # Correctly patch the async method
        with patch.object(api.openpipe_client.chat.completions, 'create', new_callable=AsyncMock, return_value=mock_response) as mock_create:
            result = await api.call_openpipe(
                messages=messages,
                model="test-model",
                provider="openpipe:xai",
                user_id="123",
                guild_id="456"
            )

            # Verify the call was made with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs['model'] == "test-model"
            assert call_kwargs['messages'] == messages

            # Verify Helicone headers were included
            assert 'Helicone-Auth' in api.openpipe_client.default_headers
            assert 'Authorization' in api.openpipe_client.default_headers

            # Verify response structure
            assert result['choices'][0]['message']['content'] == "Hello! How can I help you?"
            assert result['choices'][0]['message']['role'] == "assistant"
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_helicone_rate_limit_handling():
    """Test handling of Helicone rate limits"""
    api = API()
    await api.setup()

    try:
        messages = [{"role": "user", "content": "Hello"}]

        # Mock responses to simulate rate limiting and then success
        mock_response_rate_limited = Mock()
        mock_response_rate_limited.choices = None  # Simulate rate limit (no choices)

        mock_response_success = Mock()
        mock_response_success.choices = [
            Mock(
                message=Mock(
                    content="Successful response",
                    role="assistant"
                )
            )
        ]

        async def mock_create_rate_limited(**kwargs):
            return mock_response_rate_limited

        async def mock_create_success(**kwargs):
            return mock_response_success

        with patch.object(api.openpipe_client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [mock_create_rate_limited(), mock_create_success()]

            result = await api.call_openpipe(
                messages=messages,
                model="test-model"
            )

            # Verify retry was attempted
            assert mock_create.call_count == 2
            assert result['choices'][0]['message']['content'] == "Successful response"
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_streaming_response():
    """Test streaming response handling"""
    api = API()
    await api.setup()

    try:
        messages = [{"role": "user", "content": "Hello"}]

        # Mock streaming response chunks
        chunks = [
            {'choices': [{'delta': {'content': 'Hello'}}]},
            {'choices': [{'delta': {'content': ' world'}}]},
            {'choices': [{'delta': {'content': '!'}}]}
        ]

        async def async_generator():
            for chunk in chunks:
                yield chunk

        mock_response = async_generator()

        async def mock_create(**kwargs):
            return mock_response

        with patch.object(api.openpipe_client.chat.completions, 'create', new_callable=AsyncMock, side_effect=mock_create):
            # Do not await call_openpipe here
            response_generator = api.call_openpipe(
                messages=messages,
                model="test-model",
                stream=True
            )

            accumulated_response = ""
            async for chunk in response_generator:
                accumulated_response += chunk

            assert accumulated_response == "Hello world!"
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_error_handling():
    """Test API error handling"""
    api = API()
    await api.setup()

    try:
        messages = [{"role": "user", "content": "Hello"}]

        # Mock API error
        async def mock_error(**kwargs):
            raise Exception("API Error")

        with patch.object(api.openpipe_client.chat.completions, 'create', new_callable=AsyncMock, side_effect=mock_error):
            with pytest.raises(Exception) as exc_info:
                await api.call_openpipe(
                    messages=messages,
                    model="test-model"
                )

            assert "OpenPipe API error" in str(exc_info.value)
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_message_role_validation():
    """Test message role validation"""
    api = API()
    await api.setup()

    try:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "invalid_role", "content": "Should be filtered"},
            {"role": "assistant", "content": "Hi"}
        ]

        validated = await api._validate_message_roles(messages)

        assert len(validated) == 2
        assert validated[0]['role'] == "user"
        assert validated[1]['role'] == "assistant"
    finally:
        await api.close()

@pytest.mark.asyncio
async def test_report_interaction():
    """Test interaction reporting"""
    api = API()
    await api.setup()

    try:
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
    finally:
        await api.close()
