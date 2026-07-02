"""URL safety checks for network tools."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}
BLOCKED_IPS = {ipaddress.ip_address("169.254.169.254")}


def is_url_allowed(url: str) -> tuple[bool, str]:
    """Return whether a URL is safe for server-side fetch."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "only http and https URLs are allowed"
    if not parsed.hostname:
        return False, "URL hostname is required"

    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTNAMES:
        return False, f"blocked hostname: {hostname}"

    try:
        ip_addresses = _resolve_host(hostname)
    except OSError as exc:
        return False, f"DNS resolution failed: {exc}"

    for ip_address in ip_addresses:
        if ip_address in BLOCKED_IPS:
            return False, f"blocked metadata IP: {ip_address}"
        if (
            ip_address.is_loopback
            or ip_address.is_private
            or ip_address.is_link_local
            or ip_address.is_multicast
            or ip_address.is_reserved
            or ip_address.is_unspecified
        ):
            return False, f"blocked non-public IP: {ip_address}"
    return True, "allowed"


def _resolve_host(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in socket.getaddrinfo(hostname, None):
        address = info[4][0]
        ip_address = ipaddress.ip_address(address)
        if ip_address not in resolved:
            resolved.append(ip_address)
    return resolved
