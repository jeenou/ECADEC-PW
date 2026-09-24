"""Listens to messages on a RabbitMQ topic and forwards each one as HTTP POST JSON."""

import asyncio
from typing import Any, Dict, Union

import aiohttp

import init  # noqa: F401  (adds simulation-tools/tools to sys.path)

from tools.clients import RabbitmqClient
from tools.messages import BaseMessage
from tools.tools import FullLogger, load_environmental_variables

LOGGER = FullLogger(__name__)

FORWARD_URL = "FORWARD_URL"
FORWARD_TOPIC = "FORWARD_TOPIC"

SLEEP_TIME = 1.0


class MessageForwarder:
    """Forwards every received message as JSON via HTTP POST to forward_url."""

    def __init__(self, forward_url: str):
        self._forward_url = forward_url
        self._session = aiohttp.ClientSession()

    async def callback(self, message_object: Union[BaseMessage, Dict[str, Any], str], topic_name: str) -> None:
        if isinstance(message_object, BaseMessage):
            payload = message_object.json()
        elif isinstance(message_object, dict):
            payload = message_object
        else:
            LOGGER.warning(f"Ignoring non-JSON message from topic '{topic_name}': {message_object}")
            return

        try:
            async with self._session.post(
                self._forward_url, json={"topic": topic_name, "message": payload}
            ) as response:
                if response.status >= 400:
                    LOGGER.warning(f"Forwarding to '{self._forward_url}' failed with status {response.status}")
                else:
                    LOGGER.info(f"Forwarded message from topic '{topic_name}' to '{self._forward_url}'")
        except Exception as error:  # pylint: disable=broad-except
            LOGGER.error(f"Could not forward message to '{self._forward_url}': {error}")

    async def close(self) -> None:
        await self._session.close()


async def start_forwarder():
    environment_variables = load_environmental_variables(
        (FORWARD_URL, str, "http://localhost:8000/messages"),
        (FORWARD_TOPIC, str, "#"),
    )
    forward_url = environment_variables[FORWARD_URL]
    forward_topic = environment_variables[FORWARD_TOPIC]

    client = RabbitmqClient()
    forwarder = MessageForwarder(forward_url)
    client.add_listener(forward_topic, forwarder.callback)

    LOGGER.info(f"Forwarding messages from topic '{forward_topic}' to '{forward_url}'")

    try:
        while not client.is_closed:
            await asyncio.sleep(SLEEP_TIME)
    finally:
        await forwarder.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(start_forwarder())
