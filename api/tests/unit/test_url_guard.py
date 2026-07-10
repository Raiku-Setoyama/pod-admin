"""Unit tests for the server-side-fetch URL guard (SSRF protection)."""

import pytest

from app.utils.url_guard import UnsafeUrlError, _ip_is_blocked, validate_source_url


class TestIpIsBlocked:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",  # loopback
            "::1",  # loopback v6
            "10.0.0.5",  # private
            "192.168.1.10",  # private
            "172.16.0.1",  # private
            "169.254.169.254",  # link-local (cloud metadata)
            "0.0.0.0",  # unspecified
            "224.0.0.1",  # multicast
        ],
    )
    def test_blocks_non_public_addresses(self, ip):
        assert _ip_is_blocked(ip) is True

    @pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"])
    def test_allows_public_addresses(self, ip):
        assert _ip_is_blocked(ip) is False


class TestValidateSourceUrl:
    def _resolver(self, mapping):
        def resolve(host):
            if host not in mapping:
                raise OSError(f"no such host {host}")
            return mapping[host]

        return resolve

    def test_rejects_non_http_scheme(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url("file:///etc/passwd", resolver=self._resolver({}))
        with pytest.raises(UnsafeUrlError):
            validate_source_url("ftp://example.com/x.png", resolver=self._resolver({}))

    def test_rejects_missing_host(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url("https:///x.png", resolver=self._resolver({}))

    def test_rejects_plain_http_when_not_allowlisted(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url(
                "http://cdn.example.com/color.png",
                resolver=self._resolver({"cdn.example.com": ["93.184.216.34"]}),
            )

    def test_allows_public_https_host(self):
        # should not raise
        validate_source_url(
            "https://cdn.example.com/color.png",
            resolver=self._resolver({"cdn.example.com": ["93.184.216.34"]}),
        )

    def test_rejects_host_resolving_to_private_ip(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url(
                "https://evil.example.com/color.png",
                resolver=self._resolver({"evil.example.com": ["10.0.0.9"]}),
            )

    def test_rejects_metadata_ip_literal(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url(
                "https://169.254.169.254/latest/meta-data/",
                resolver=self._resolver({"169.254.169.254": ["169.254.169.254"]}),
            )

    def test_rejects_if_any_resolved_ip_is_private(self):
        # DNS returning a mix — must reject if ANY address is unsafe (rebinding defense)
        with pytest.raises(UnsafeUrlError):
            validate_source_url(
                "https://mixed.example.com/color.png",
                resolver=self._resolver({"mixed.example.com": ["93.184.216.34", "127.0.0.1"]}),
            )

    def test_allowlisted_host_bypasses_ip_and_scheme_checks(self):
        # An explicitly trusted host is allowed even over http / private IP (e.g. internal asset server, dev stub)
        validate_source_url(
            "http://host.docker.internal:9099/layers/color.png",
            allowed_hosts=frozenset({"host.docker.internal"}),
            resolver=self._resolver({"host.docker.internal": ["192.168.65.2"]}),
        )

    def test_dns_failure_is_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_source_url(
                "https://nxdomain.example.com/x.png",
                resolver=self._resolver({}),
            )
