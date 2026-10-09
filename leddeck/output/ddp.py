"""Envoi DDP (Distributed Display Protocol) vers les controleurs WLED, en UDP."""

from __future__ import annotations

import socket
from typing import Iterable

import numpy as np

# En-tete DDP : 10 octets
#   0 : flags1  (version 1 = 0x40, bit PUSH = 0x01)
#   1 : flags2  (numero de sequence, 1..15 ; 0 = pas de sequence)
#   2 : type de donnees (0x0B = RGB 8 bits par canal)
#   3 : identifiant de destination (1 = afficheur par defaut)
# 4-7 : offset des donnees, en octets (big endian)
# 8-9 : longueur des donnees (big endian)
HEADER_LEN = 10
VER1 = 0x40
PUSH = 0x01
TYPE_RGB24 = 0x0B
ID_DISPLAY = 1
MAX_DATA = 1440  # 480 LED RGB par paquet : limite usuelle du protocole


class DDPSender:
    """Emetteur UDP sans etat cote reseau (fire and forget), un socket partage."""

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._seq: dict[tuple[str, int], int] = {}
        self.packets_sent = 0
        self.errors = 0

    def _next_seq(self, key: tuple[str, int]) -> int:
        seq = self._seq.get(key, 0) % 15 + 1  # 1..15
        self._seq[key] = seq
        return seq

    def send_pixels(self, ip: str, port: int, pixels: np.ndarray) -> None:
        """`pixels` : tableau (n, 3) uint8. Decoupe en paquets si besoin."""
        data = np.ascontiguousarray(pixels, dtype=np.uint8).tobytes()
        self.send_bytes(ip, port, data)

    def send_bytes(self, ip: str, port: int, data: bytes) -> None:
        key = (ip, port)
        total = len(data)
        offset = 0
        while offset < total:
            chunk = data[offset : offset + MAX_DATA]
            last = offset + len(chunk) >= total
            header = bytes(
                (
                    VER1 | (PUSH if last else 0),
                    self._next_seq(key),
                    TYPE_RGB24,
                    ID_DISPLAY,
                    (offset >> 24) & 0xFF,
                    (offset >> 16) & 0xFF,
                    (offset >> 8) & 0xFF,
                    offset & 0xFF,
                    (len(chunk) >> 8) & 0xFF,
                    len(chunk) & 0xFF,
                )
            )
            try:
                self._sock.sendto(header + chunk, (ip, port))
                self.packets_sent += 1
            except OSError:
                # Un ESP absent ou un buffer plein ne doit jamais stopper le moteur.
                self.errors += 1
            offset += len(chunk)

    def send_many(self, frames: Iterable[tuple[str, int, np.ndarray]]) -> None:
        for ip, port, pixels in frames:
            self.send_pixels(ip, port, pixels)

    def close(self) -> None:
        self._sock.close()
