import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def decoded(result):
    if result.structuredContent is not None:
        data = result.structuredContent
        return data.get("result", data)
    return json.loads(result.content[0].text)


async def test_two_real_mcp_clients_share_memory_and_mail(project):
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "forge", "--project", str(project), "mcp"])
    async with stdio_client(parameters) as (read_a, write_a):
        async with ClientSession(read_a, write_a) as a:
            await a.initialize()
            async with stdio_client(parameters) as (read_b, write_b):
                async with ClientSession(read_b, write_b) as b:
                    await b.initialize()
                    tools = await a.list_tools()
                    assert len(tools.tools) == 6
                    memory = decoded(await a.call_tool("memory_add", {"text":"Fixture: shared convention", "author":"claude"}))
                    assert memory["verified"] is False
                    found = decoded(await b.call_tool("memory_search", {"query":"convention"}))
                    assert len(found) == 1
                    sent = decoded(await a.call_tool("message_send", {"sender":"claude", "recipient":"codex", "text":"Fixture: implementation ready"}))
                    inbox = decoded(await b.call_tool("message_inbox", {"recipient":"codex"}))
                    assert inbox[0]["id"] == sent["id"]
                    await b.call_tool("message_ack", {"identifier":sent["id"], "recipient":"codex"})
                    assert decoded(await b.call_tool("message_inbox", {"recipient":"codex"})) == []
