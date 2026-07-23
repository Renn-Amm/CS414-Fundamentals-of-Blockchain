import os
import random
from dataclasses import dataclass

from ipv8.community import CommunitySettings
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.peer import Peer

from da_types import Blockchain, message_wrapper


STRATEGY = os.environ.get("GOSSIP_STRATEGY", "push")
FANOUT = int(os.environ.get("GOSSIP_FANOUT", "3"))


@dataclass
class PushMessage(DataClassPayload[10]):
    txid: str
    content: str

PushMessage("", "")


@dataclass
class HaveMessage(DataClassPayload[11]):
    txid: str

HaveMessage("")


@dataclass
class WantMessage(DataClassPayload[12]):
    txid: str

WantMessage("")


@dataclass
class DigestMessage(DataClassPayload[13]):
    ids_csv: str

DigestMessage("")


class GossipNode(Blockchain):

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.add_message_handler(PushMessage, self.on_push)
        self.add_message_handler(HaveMessage, self.on_have)
        self.add_message_handler(WantMessage, self.on_want)
        self.add_message_handler(DigestMessage, self.on_digest)

        self.known: dict[str, str] = {}
        self.outstanding_wants: set[str] = set()
        self.told_neighbour: dict[int, set[str]] = {}

        self.packets_sent = 0
        self.packets_received = 0
        self.duplicates_received = 0

    def _random_neighbours(self, k: int, exclude: set[int] | None = None) -> list[Peer]:
        exclude = exclude or set()
        pool = [peer for node_id, peer in self.nodes.items() if node_id not in exclude]
        if not pool:
            return []
        return random.sample(pool, min(k, len(pool)))

    def _send(self, peer: Peer, payload) -> None:
        self.ez_send(peer, payload)
        self.packets_sent += 1

    def _remember(self, txid: str, content: str) -> bool:
        if txid in self.known:
            self.duplicates_received += 1
            return False
        self.known[txid] = content
        print(
            f"[Node {self.node_id}] delivered txid={txid} "
            f"(sent={self.packets_sent}, recv={self.packets_received}, "
            f"dupes={self.duplicates_received})"
        )
        return True

    def on_start(self) -> None:
        if self.node_id == 0:
            txid = "tx0"
            content = "hello-from-node-0"
            self.known[txid] = content
            print(f"[Node 0] injecting message {txid}")
            if STRATEGY in ("push", "hybrid"):
                for peer in self._random_neighbours(FANOUT):
                    self._send(peer, PushMessage(txid, content))

        if STRATEGY == "pull":
            self.register_task("advertise", self._advertise, interval=2.0, delay=1.0)

    def _advertise(self) -> None:
        for txid in list(self.known.keys()):
            candidates = [
                (nid, peer) for nid, peer in self.nodes.items()
                if txid not in self.told_neighbour.get(nid, set())
            ]
            if not candidates:
                continue
            picked = random.sample(candidates, min(FANOUT, len(candidates)))
            for nid, peer in picked:
                self._send(peer, HaveMessage(txid))
                self.told_neighbour.setdefault(nid, set()).add(txid)

    @message_wrapper(PushMessage)
    async def on_push(self, peer: Peer, payload: PushMessage) -> None:
        self.packets_received += 1
        sender_id = self.node_id_from_peer(peer)
        was_new = self._remember(payload.txid, payload.content)
        self.outstanding_wants.discard(payload.txid)

        if not was_new:
            return

        exclude = {sender_id} if sender_id is not None else set()
        if STRATEGY == "push":
            for p in self._random_neighbours(FANOUT, exclude=exclude):
                self._send(p, PushMessage(payload.txid, payload.content))
        elif STRATEGY == "hybrid":
            digest = ",".join(self.known.keys())
            for p in self._random_neighbours(FANOUT, exclude=exclude):
                self._send(p, DigestMessage(digest))

    @message_wrapper(HaveMessage)
    async def on_have(self, peer: Peer, payload: HaveMessage) -> None:
        self.packets_received += 1
        if payload.txid in self.known or payload.txid in self.outstanding_wants:
            return
        self._send(peer, WantMessage(payload.txid))
        self.outstanding_wants.add(payload.txid)

    @message_wrapper(WantMessage)
    async def on_want(self, peer: Peer, payload: WantMessage) -> None:
        self.packets_received += 1
        if payload.txid in self.known:
            self._send(peer, PushMessage(payload.txid, self.known[payload.txid]))

    @message_wrapper(DigestMessage)
    async def on_digest(self, peer: Peer, payload: DigestMessage) -> None:
        self.packets_received += 1
        ids = payload.ids_csv.split(",") if payload.ids_csv else []
        for mid in ids:
            mid = mid.strip()
            if not mid or mid in self.known or mid in self.outstanding_wants:
                continue
            self._send(peer, WantMessage(mid))
            self.outstanding_wants.add(mid)
