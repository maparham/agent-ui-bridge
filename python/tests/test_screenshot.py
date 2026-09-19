import base64

import pytest
from mcp.server import MCPServer

from agent_ui_bridge.hub import NoTabError
from agent_ui_bridge.tools import register_ui_tools


class FakeHub:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    async def request(self, kind, payload, session_id=None):
        self.calls.append((kind, payload, session_id))
        if self.exc:
            raise self.exc
        return self.result

    def title_of(self, session_id=None):
        # The title gate runs before the request; a missing tab surfaces here.
        if isinstance(self.exc, NoTabError):
            raise self.exc
        return "🤖 test"


def tools_for(hub):
    return register_ui_tools(
        MCPServer("test-shot"), hub, screenshot_action="page.screenshot", app_name="app"
    )


@pytest.mark.anyio
async def test_ui_screenshot_returns_image_block():
    png = base64.b64encode(b"\x89PNG fake").decode()
    hub = FakeHub(result={
        "caption": "US100 HOUR (cell c1)",
        "mime": "image/png", "image_base64": png, "via": "extension",
    })
    blocks = await tools_for(hub)["ui_screenshot"]()
    image = next(b for b in blocks if getattr(b, "type", "") == "image")
    text = next(b for b in blocks if getattr(b, "type", "") == "text")
    assert image.data == png
    assert image.mime_type == "image/png"
    assert text.text == "US100 HOUR (cell c1) via extension"
    # It must go through the readOnly invoke path:
    kind, payload, _ = hub.calls[0]
    assert kind == "invoke"
    assert payload == {"action": "page.screenshot", "args": {}, "readOnly": True}


@pytest.mark.anyio
async def test_ui_screenshot_without_a_caption_still_labels_the_image():
    png = base64.b64encode(b"\x89PNG fake").decode()
    hub = FakeHub(result={"mime": "image/png", "image_base64": png, "via": "canvas"})
    blocks = await tools_for(hub)["ui_screenshot"]()
    text = next(b for b in blocks if getattr(b, "type", "") == "text")
    assert text.text == "screenshot via canvas"


@pytest.mark.anyio
async def test_ui_screenshot_no_tab_is_friendly():
    hub = FakeHub(exc=NoTabError("no UI session connected"))
    with pytest.raises(RuntimeError, match="no UI session"):
        await tools_for(hub)["ui_screenshot"]()
