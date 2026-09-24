"""SimCES simulation component that runs PowerFactory PTDF analysis each epoch."""

import asyncio
from typing import Any, Optional, Union

import init  # noqa: F401  (adds simulation-tools/tools to sys.path)

from tools.components import AbstractSimulationComponent
from tools.messages import BaseMessage, ResultMessage
from tools.tools import FullLogger, load_environmental_variables, log_exception

from ecadec_pw.simulate import connect_and_activate_project, get_coordination_payload

LOGGER = FullLogger(__name__)

PROJECT_NAME = "PROJECT_NAME"
PTDF_RESULT_TOPIC = "PTDF_RESULT_TOPIC"
ENERGY_COMMUNITY_BUSES = "ENERGY_COMMUNITY_BUSES"

TIMEOUT = 1.0


class PtdfSimulationComponent(AbstractSimulationComponent):
    """Runs a PowerFactory load flow + PTDF sensitivity analysis once per epoch
    and publishes the results to the message bus."""

    def __init__(self, project_name: str, result_topic: str = "PtdfResult", bus_names: Optional[list] = None):
        super().__init__()

        self._project_name = project_name
        self._result_topic = result_topic
        self._bus_names = bus_names or []
        self._other_topics = []

        # Connect to PowerFactory once and keep the connection for all epochs.
        try:
            self._app = connect_and_activate_project(self._project_name)
        except Exception as error:  # pylint: disable=broad-except
            self.initialization_error = f"Could not connect to PowerFactory: {error}"
            LOGGER.error(self.initialization_error)
            self._app = None

    def clear_epoch_variables(self) -> None:
        pass

    async def all_messages_received_for_epoch(self) -> bool:
        return True

    async def process_epoch(self) -> bool:
        try:
            # PowerFactory's scripting API is not thread-safe, so this must run
            # on the event loop thread rather than via run_in_executor.
            payloads = self._collect_bus_payloads()
        except Exception as error:  # pylint: disable=broad-except
            log_exception(error)
            await self.send_error_message(f"PowerFactory analysis failed: {error}")
            return False

        await self._send_result_message(payloads)
        return True

    def _collect_bus_payloads(self) -> dict:
        busbars = {
            t.loc_name: t
            for t in self._app.GetCalcRelevantObjects("ElmTerm")
            if t.iUsage == 0
        }
        return {
            name: get_coordination_payload(self._app, busbars[name])
            for name in self._bus_names
            if name in busbars
        }

    async def general_message_handler(
        self, message_object: Union[BaseMessage, Any], message_routing_key: str
    ) -> None:
        LOGGER.debug(f"Received unexpected message from topic {message_routing_key}")

    async def _send_result_message(self, payloads: dict) -> None:
        result_message = self._message_generator.get_message(
            ResultMessage,
            EpochNumber=self._latest_epoch,
            TriggeringMessageIds=self._triggering_message_ids,
            Buses=payloads,
        )
        await self._rabbitmq_client.send_message(
            topic_name=self._result_topic,
            message_bytes=result_message.bytes(),
        )


def create_component() -> PtdfSimulationComponent:
    environment_variables = load_environmental_variables(
        (PROJECT_NAME, str, "SIM_CIGREHvdcBenchmark_v2"),
        (PTDF_RESULT_TOPIC, str, "PtdfResult"),
        (ENERGY_COMMUNITY_BUSES, str, ""),
    )

    bus_names = [
        name.strip()
        for name in environment_variables[ENERGY_COMMUNITY_BUSES].split(",")
        if name.strip()
    ]

    return PtdfSimulationComponent(
        project_name=environment_variables[PROJECT_NAME],
        result_topic=environment_variables[PTDF_RESULT_TOPIC],
        bus_names=bus_names,
    )


async def start_component():
    try:
        component = create_component()
        await component.start()
        while not component.is_stopped:
            await asyncio.sleep(TIMEOUT)
    except BaseException as error:  # pylint: disable=broad-except
        log_exception(error)
        LOGGER.info("Component will now exit.")


if __name__ == "__main__":
    asyncio.run(start_component())
