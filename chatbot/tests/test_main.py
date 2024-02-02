import pytest
from unittest.mock import AsyncMock

import grannymail.main as gm
from grannymail.utils.utils import get_prompt_from_sheet


def make_async_mock(original):
    mock = AsyncMock(spec=original)
    for attribute_name in dir(original):
        # Filter out magic methods and properties to avoid copying unintended behaviors
        if not attribute_name.startswith("__") and not callable(
            getattr(original, attribute_name)
        ):
            attribute_value = getattr(original, attribute_name)
            setattr(mock, attribute_name, attribute_value)
        elif callable(getattr(original, attribute_name)):
            # For methods, you might want to set them up individually based on your testing needs
            pass
    return mock


class TestTelegram:
    @pytest.mark.asyncio
    async def test_help(self, tg_send_text):
        update, context = await tg_send_text
        await gm.handle_help(update, context)


class TestWhatsapp:
    @pytest.mark.asyncio
    async def test_help(self, async_client, wa_text):
        response = await async_client.post(
            "/api/whatsapp", json=wa_text.model_dump(mode="json")
        )
