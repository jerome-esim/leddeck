"""Decouverte et interrogation des controleurs WLED (API JSON + mDNS)."""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import requests

from ..core.config import DDP_PORT, Output

HTTP_TIMEOUT = 0.6


@dataclass
class WledInfo:
    ip: str
    name: str = ""
    mac: str = ""
    leds: int = 0
    version: str = ""
    rssi: int = 0
    arch: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def ddp_ok(self) -> bool:
        """DDP est integre a WLED depuis la 0.13 (port 4048, toujours a l'ecoute)."""
        try:
            major, minor, *_ = (int(x) for x in self.version.split("-")[0].split(".")[:2])
        except ValueError:
            return False
        return (major, minor) >= (0, 13)

    def to_output(self, output_id: int) -> Output:
        return Output(
            id=output_id,
            name=self.name or self.ip,
            ip=self.ip,
            led_count=self.leds or 250,
            port=DDP_PORT,
            mac=self.mac,
        )


def info(ip: str, timeout: float = HTTP_TIMEOUT) -> WledInfo | None:
    """Interroge http://<ip>/json/info. None si ce n'est pas un WLED."""
    try:
        r = requests.get(f"http://{ip}/json/info", timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if not isinstance(data, dict) or "leds" not in data:
        return None
    return WledInfo(
        ip=ip,
        name=data.get("name", ""),
        mac=data.get("mac", ""),
        leds=int(data.get("leds", {}).get("count", 0)),
        version=data.get("ver", ""),
        rssi=int(data.get("wifi", {}).get("rssi", 0)),
        arch=data.get("arch", ""),
        raw=data,
    )


def local_ipv4() -> list[tuple[str, int]]:
    """Adresses IPv4 locales (hors loopback) avec leur prefixe."""
    import ifaddr

    found = []
    for adapter in ifaddr.get_adapters():
        for a in adapter.ips:
            if a.is_IPv4 and not a.ip.startswith("127."):
                found.append((a.ip, a.network_prefix))
    return found


def subnet_hosts(cidr: str | None = None, max_hosts: int = 512) -> list[str]:
    """Liste des adresses a sonder : un CIDR donne, sinon les sous-reseaux locaux."""
    nets = []
    if cidr:
        nets.append(ipaddress.ip_network(cidr, strict=False))
    else:
        for ip, prefix in local_ipv4():
            prefix = max(prefix, 24)  # on ne balaie pas plus large qu'un /24
            nets.append(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
    hosts: list[str] = []
    for net in nets:
        for h in net.hosts():
            if len(hosts) >= max_hosts:
                break
            hosts.append(str(h))
    return hosts


def scan(cidr: str | None = None, workers: int = 128, timeout: float = HTTP_TIMEOUT,
         on_found=None) -> list[WledInfo]:
    """Balaye le sous-reseau en parallele et retourne les WLED trouves."""
    hosts = subnet_hosts(cidr)
    found: list[WledInfo] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(lambda h: info(h, timeout), hosts):
            if res:
                found.append(res)
                if on_found:
                    on_found(res)
    return sorted(found, key=lambda w: tuple(int(x) for x in w.ip.split(".")))


def mdns_scan(timeout: float = 3.0) -> list[WledInfo]:
    """Decouverte mDNS `_wled._tcp.local.` (complement du balayage)."""
    from zeroconf import ServiceBrowser, Zeroconf

    ips: set[str] = set()

    class Listener:
        def add_service(self, zc, type_, name):
            svc = zc.get_service_info(type_, name, timeout=int(timeout * 1000))
            if svc:
                for addr in svc.parsed_addresses():
                    if ":" not in addr:
                        ips.add(addr)

        update_service = add_service

        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, "_wled._tcp.local.", Listener())
        import time

        time.sleep(timeout)
    finally:
        zc.close()

    with ThreadPoolExecutor(max_workers=16) as pool:
        return [w for w in pool.map(info, sorted(ips)) if w]


def discover(cidr: str | None = None, use_mdns: bool = True, timeout: float = HTTP_TIMEOUT) -> list[WledInfo]:
    """Balayage + mDNS, dedoublonnes par IP."""
    by_ip = {w.ip: w for w in scan(cidr, timeout=timeout)}
    if use_mdns:
        for w in mdns_scan():
            by_ip.setdefault(w.ip, w)
    return sorted(by_ip.values(), key=lambda w: tuple(int(x) for x in w.ip.split(".")))


# --- pilotage de l'etat WLED (API JSON) --------------------------------------
#
# Indispensable pour le blackout : 2,5 s apres le dernier paquet DDP, WLED sort
# du mode temps reel et reprend son propre etat (souvent un effet allume).
# Eteindre en DDP ne suffit donc pas, il faut aussi couper WLED lui-meme.


def set_state(ip: str, state: dict, timeout: float = 1.0) -> bool:
    """POST /json/state. False si l'ESP n'a pas repondu."""
    try:
        r = requests.post(f"http://{ip}/json/state", json=state, timeout=timeout)
        return r.ok
    except Exception:
        return False


def apply_all(outputs, state: dict, timeout: float = 1.0) -> tuple[int, int]:
    """Applique le meme etat a plusieurs sorties, en parallele -> (reussites, total)."""
    targets = [o for o in outputs if o.enabled and o.ip]
    if not targets:
        return 0, 0
    with ThreadPoolExecutor(max_workers=min(16, len(targets))) as pool:
        ok = list(pool.map(lambda o: set_state(o.ip, state, timeout), targets))
    return sum(ok), len(ok)


def set_power(ip: str, on: bool, timeout: float = 1.0) -> bool:
    return set_state(ip, {"on": bool(on)}, timeout)


def power_all(outputs, on: bool, timeout: float = 1.0) -> tuple[int, int]:
    return apply_all(outputs, {"on": bool(on)}, timeout)


# Etat de reference avant d'emettre : allume et luminosite WLED au maximum.
# Sans ca, un ESP dont le curseur de luminosite est a 128 rend deux fois plus
# sombre que les autres a donnees identiques (et l'option « Force max brightness »
# n'est pas toujours cochee). La luminosite est geree par le master de l'appli.
WAKE_STATE = {"on": True, "bri": 255}


def wake_all(outputs, timeout: float = 1.0) -> tuple[int, int]:
    return apply_all(outputs, WAKE_STATE, timeout)


# --- preparation pour le club ------------------------------------------------
#
# En sortant du mode temps reel, WLED revient a l'etat qu'il avait *avant* — pas
# a son preset de demarrage. Si on l'a mis a « allume » pour emettre, il se
# rallume donc tout seul 2,5 s apres un arret brutal de l'appli.
# La parade : le laisser eteint en permanence et activer « Force max brightness »,
# qui affiche le flux temps reel quel que soit l'etat on/off.

CLUB_CONFIG = {
    "if": {"live": {
        "maxbri": True,     # affiche le temps reel a fond, meme WLED eteint
        "no-gc": True,      # pas de gamma WLED : l'appli s'en charge
        "en": True,         # reception temps reel active
    }},
    "def": {"on": False},   # demarrage eteint apres une coupure de courant
}


def get_config(ip: str, timeout: float = HTTP_TIMEOUT) -> dict | None:
    try:
        r = requests.get(f"http://{ip}/json/cfg", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def set_config(ip: str, patch: dict, timeout: float = 2.0) -> bool:
    """POST /json/cfg. WLED fusionne le fragment avec sa configuration."""
    try:
        r = requests.post(f"http://{ip}/json/cfg", json=patch, timeout=timeout)
        return r.ok
    except Exception:
        return False


# Types de bus « reseau » de WLED : l'ESP relaie alors le flux vers d'autres IP.
# Une telle configuration (« virtual LED ») le fait ramer : il reçoit quatre fois
# trop de donnees et en reemet a chaque frame. Constate sur le materiel.
RELAY_BUS_TYPES = (80, 81, 82, 88, 89)


def led_buses(config: dict) -> tuple[int, int, list[str]]:
    """(total declare, LED locales, adresses relayees) d'apres la configuration."""
    hw = config.get("hw", {}).get("led", {})
    local, relays = 0, []
    for bus in hw.get("ins", []):
        length = int(bus.get("len", 0) or 0)
        if int(bus.get("type", 0) or 0) in RELAY_BUS_TYPES:
            pin = bus.get("pin") or []
            relays.append(".".join(str(v) for v in pin) if len(pin) == 4 else "?")
        else:
            local += length
    return int(hw.get("total", 0) or 0), local, relays


def inspect(ip: str, timeout: float = HTTP_TIMEOUT) -> tuple[int, int, list[str]] | None:
    config = get_config(ip, timeout)
    return None if config is None else led_buses(config)


def club_settings(config: dict) -> dict:
    """Extrait les reglages qui nous interessent, pour les afficher."""
    live = config.get("if", {}).get("live", {})
    return {
        "maxbri": bool(live.get("maxbri")),
        "no-gc": bool(live.get("no-gc")),
        "en": bool(live.get("en")),
        "boot_on": bool(config.get("def", {}).get("on")),
    }


# WLED applique et sauvegarde sa configuration de facon differee : relire tout
# de suite renvoie encore les anciennes valeurs. Constate en vrai — la commande
# annoncait un echec alors que l'ecriture avait fonctionne.
CONFIG_SETTLE = 1.5


def prepare(ip: str, settle: float = CONFIG_SETTLE) -> tuple[dict | None, dict | None]:
    """Applique la configuration club puis relit. Retourne (avant, apres)."""
    import time

    before = get_config(ip)
    if before is None:
        return None, None
    set_config(ip, CLUB_CONFIG)
    set_state(ip, {"on": False})      # etat de repos : eteint
    time.sleep(settle)
    after = get_config(ip)
    return club_settings(before), (club_settings(after) if after else None)


def hostname() -> str:
    return socket.gethostname()
