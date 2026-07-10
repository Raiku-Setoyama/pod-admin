"""サーバサイド取得URLの安全性検証（SSRF対策）.

外部注文元が渡す `source_images[].url` を pod-admin がサーバサイドで取得する前に、
内部・クラウドメタデータ等の危険な宛先を弾く。方針:

- スキームは http/https のみ。
- 明示的な許可ホスト（allowed_hosts）は信頼して素通し（内部アセットサーバ / dev スタブ用）。
- 許可ホスト以外は https 必須、かつ名前解決した全IPが public でなければ拒否
  （private / loopback / link-local / reserved / multicast / unspecified を遮断）。

resolver は差し替え可能（テストではネットワークに触れずに検証するため）。
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlparse

# 非public判定に使う ipaddress の属性
_BLOCKED_ATTRS = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
    "is_unspecified",
)

Resolver = Callable[[str], list[str]]


class UnsafeUrlError(ValueError):
    """取得を許可できないURL（SSRF等）."""


def _ip_is_blocked(ip_str: str) -> bool:
    """IP文字列が非public（内部宛先）なら True."""
    addr = ipaddress.ip_address(ip_str)
    return any(getattr(addr, attr) for attr in _BLOCKED_ATTRS)


def _default_resolver(host: str) -> list[str]:
    """host を解決して全ての A/AAAA レコード（IP文字列）を返す."""
    infos = socket.getaddrinfo(host, None)
    return [str(info[4][0]) for info in infos]


def validate_source_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] = frozenset(),
    require_https: bool = True,
    resolver: Resolver = _default_resolver,
) -> None:
    """url がサーバサイド取得に安全でなければ UnsafeUrlError を送出する.

    Args:
        url: 検証対象URL。
        allowed_hosts: 信頼して素通しするホスト名の集合。
        require_https: 許可ホスト以外に https を要求するか。
        resolver: ホスト名→IP文字列リスト。テスト差し替え用。
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname

    if scheme not in ("http", "https"):
        raise UnsafeUrlError(f"unsupported URL scheme: {scheme!r}")
    if not host:
        raise UnsafeUrlError(f"URL has no host: {url!r}")

    allowed = {h.lower() for h in allowed_hosts}
    if host.lower() in allowed:
        return  # 明示的に信頼されたホスト

    if require_https and scheme != "https":
        raise UnsafeUrlError(f"non-allowlisted URL must use https: {url!r}")

    try:
        ips = resolver(host)
    except OSError as exc:
        raise UnsafeUrlError(f"DNS resolution failed for {host!r}: {exc}") from exc

    if not ips:
        raise UnsafeUrlError(f"no addresses resolved for host {host!r}")

    for ip in ips:
        if _ip_is_blocked(ip):
            raise UnsafeUrlError(f"host {host!r} resolves to a blocked address: {ip}")
