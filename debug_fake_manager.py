"""Minimal fake Manager: sends SimState=running then one Epoch message to trigger
a single epoch on a running ecadec_pw.simces_component instance. For manual testing only."""

import asyncio
import os

os.environ.setdefault("RABBITMQ_EXCHANGE", "procem.ecadec_pw_exchange")

import init  # noqa: F401
from tools.clients import RabbitmqClient
from tools.messages import MessageGenerator, SimulationStateMessage

SIM_STATE_TOPIC = "SimState"
EPOCH_TOPIC = "Epoch"
SIMULATION_ID = "2020-01-01T00:00:00.000Z"


async def main():
    client = RabbitmqClient()
    generator = MessageGenerator(simulation_id=SIMULATION_ID, source_process_id="FakeManager")

    sim_state_message = generator.get_message(
        SimulationStateMessage,
        SimulationState="running",
    )
    await client.send_message(SIM_STATE_TOPIC, sim_state_message.bytes())
    await asyncio.sleep(1)

    epoch_message = generator.get_epoch_message(
        EpochNumber=1,
        TriggeringMessageIds=["fake-manager-epoch-1"],
        StartTime="2020-01-01T00:00:00.000Z",
        EndTime="2020-01-01T01:00:00.000Z",
    )
    await client.send_message(EPOCH_TOPIC, epoch_message.bytes())
    await asyncio.sleep(5)
    await client.close()


asyncio.run(main())
