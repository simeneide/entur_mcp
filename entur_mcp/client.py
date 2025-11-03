import asyncio
from pprint import pprint

from fastmcp import Client

client = Client("http://localhost:3456/mcp")


def _as_dict(result: object) -> object:
    data = getattr(result, "data", None)
    if data is not None:
        return _as_dict(data)
    dump = getattr(result, "model_dump", None)
    return dump() if callable(dump) else result


async def call_tool(name: str):
    async with client:
        result = await client.call_tool("greet", {"name": name})
        print(result)


async def plan_trip_example() -> None:
    async with client:
        plan_arguments = {
            "arguments": {
                "from_text": "Oslo Central Station",
                "to_text": "Bergen busstasjon",
                "num_trip_patterns": 1,
            }
        }
        trip_plan = await client.call_tool(
            "plan_trip",
            arguments=plan_arguments,
        )
        pprint(_as_dict(trip_plan))


if __name__ == "__main__":
    # asyncio.run(call_tool("Ford"))
    asyncio.run(plan_trip_example())
