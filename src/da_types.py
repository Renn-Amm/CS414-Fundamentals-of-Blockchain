from __future__ import annotations

import random
from asyncio import Event
from collections.abc import Callable
from typing import Any, TypeVar

from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper
from ipv8.peer import Peer


Handler = TypeVar("Handler", bound=Callable[..., Any])


def message_wrapper(*payloads: type[Any]) -> Callable[[Handler], Handler]:
    """Type-friendly alias for IPv8's lazy_wrapper decorator."""

    return lazy_wrapper(*payloads)


class Blockchain(Community):
    community_id = b"\x05" * 20

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)

        self.event: Event | None = None
        self.nodes: dict[int, Peer] = {}
        self.node_id: int = -1
        self.connections: list[tuple[int, int]] = []
        self.on_start_delay: float = 0.0

    def node_id_from_peer(self, peer: Peer) -> int | None:
        return next(
            (
                node_id
                for node_id, registered_peer in self.nodes.items()
                if registered_peer == peer
            ),
            None,
        )

    async def started(
        self,
        node_id: int,
        connections: list[tuple[int, int]],
        event: Event,
        use_localhost: bool = True,
    ) -> None:
        self.event = event
        self.node_id = node_id
        self.connections = connections
        self.on_start_delay = random.uniform(1.0, 3.0)

        host_network = self._get_lan_address()[0]
        host_network_base = ".".join(host_network.split(".")[:3])

        async def ensure_nodes_connected() -> None:
            # Initiate connections to all configured peers.
            for connected_node_id, port in self.connections:
                ip_address = f"{host_network_base}.{connected_node_id + 10}"

                if use_localhost:
                    ip_address = host_network

                self.walk_to((ip_address, port))

            discovered_nodes: dict[int, Peer] = {}

            # Verify that every configured node has been discovered.
            for connected_node_id, node_port in self.connections:
                matching_peers = [
                    peer
                    for peer in self.get_peers()
                    if peer.address[1] == node_port
                ]

                if not matching_peers:
                    return

                discovered_nodes[connected_node_id] = matching_peers[0]

            if not discovered_nodes:
                return

            self.nodes.update(discovered_nodes)
            self.cancel_pending_task("ensure_nodes_connected")

            print(f"[Node {self.node_id}] Starting")

            self.register_anonymous_task(
                "delayed_start",
                self.on_start,
                delay=self.on_start_delay,
            )

        self.register_task(
            "ensure_nodes_connected",
            ensure_nodes_connected,
            interval=0.5,
            delay=1,
        )

    def on_start(self) -> None:
        """Override this method in an algorithm implementation."""

    def stop(self, delay: int | float = 0) -> None:
        async def delayed_stop() -> None:
            print(f"[Node {self.node_id}] Stopping algorithm")

            if self.event is not None:
                self.event.set()

        self.register_anonymous_task(
            "delayed_stop",
            delayed_stop,
            delay=delay,
        )