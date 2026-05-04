"""Tests for check_ai_rate_limit (Redis INCR + TTL pattern)."""
from unittest.mock import AsyncMock, patch

import pytest


def _make_redis(incr_value: int) -> AsyncMock:
    r = AsyncMock()
    r.incr = AsyncMock(return_value=incr_value)
    r.expire = AsyncMock()
    return r


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch("app.core.redis_client.settings") as mock_cfg:
        mock_cfg.AI_DAILY_RATE_LIMIT = 10
        yield mock_cfg


async def test_first_request_is_allowed():
    redis = _make_redis(1)
    with patch("app.core.redis_client.get_redis", return_value=redis):
        from app.core.redis_client import check_ai_rate_limit
        result = await check_ai_rate_limit("user-abc")
    assert result is True


async def test_request_at_limit_is_allowed():
    redis = _make_redis(10)
    with patch("app.core.redis_client.get_redis", return_value=redis):
        from app.core.redis_client import check_ai_rate_limit
        result = await check_ai_rate_limit("user-abc")
    assert result is True


async def test_request_over_limit_is_rejected():
    redis = _make_redis(11)
    with patch("app.core.redis_client.get_redis", return_value=redis):
        from app.core.redis_client import check_ai_rate_limit
        result = await check_ai_rate_limit("user-abc")
    assert result is False


async def test_ttl_is_set_on_first_request():
    redis = _make_redis(1)
    with patch("app.core.redis_client.get_redis", return_value=redis):
        from app.core.redis_client import check_ai_rate_limit
        await check_ai_rate_limit("user-abc")
    redis.expire.assert_awaited_once()
    key_arg = redis.expire.call_args[0][0]
    assert "user-abc" in key_arg


async def test_ttl_not_reset_on_subsequent_requests():
    redis = _make_redis(5)
    with patch("app.core.redis_client.get_redis", return_value=redis):
        from app.core.redis_client import check_ai_rate_limit
        await check_ai_rate_limit("user-abc")
    redis.expire.assert_not_awaited()
