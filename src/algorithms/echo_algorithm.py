from dataclasses import dataclass

from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.peer import Peer

from da_types import Blockchain, message_wrapper


@dataclass
class MyMessage(DataClassPayload[1]):
    """Echo message.

    Message ID 1 must be unique within this community.
    """

    counter: int

MyMessage(0)

class EchoAlgorithm(Blockchain):
    """Simple example that echoes messages between two nodes."""

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.echo_counter = 0
        self.max_echo_count = 10
        self.add_message_handler(MyMessage, self.on_message)

    def on_start(self) -> None:
        if self.node_id == 1:
            # Only node 1 starts.
            peer = self.nodes[0]
            self.ez_send(peer, MyMessage(self.echo_counter))

    @message_wrapper(MyMessage)
    async def on_message(self, peer: Peer, payload: MyMessage) -> None:
        sender_id = self.node_id_from_peer(peer)
        self.echo_counter = payload.counter + 1

        print(
            f"[Node {self.node_id}] Got a message from node: "
            f"{sender_id}.\tCurrent counter: {self.echo_counter}"
        )

        if self.echo_counter >= self.max_echo_count:
            print(f"Node {self.node_id} is stopping")
            self.stop()
            return

        self.ez_send(peer, MyMessage(self.echo_counter))