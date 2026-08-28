"""
Unit tests for the deterministic rule checker. No database, no network,
no LLM — pure function tests, as befits a component that must never
depend on the AI engine.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rules.checker import run_rule_checks  # noqa: E402


def test_empty_evidence_returns_no_errors():
    result = run_rule_checks("", "")
    assert result.status == "NO_ERRORS_DETECTED"
    assert result.errors == []


def test_whitespace_only_evidence_returns_no_errors():
    result = run_rule_checks("   \n\n  ", "")
    assert result.status == "NO_ERRORS_DETECTED"


def test_detects_administratively_down_interface():
    evidence = (
        "R1# show interfaces GigabitEthernet0/0.30\n"
        "GigabitEthernet0/0.30 is administratively down, line protocol is down\n"
    )
    result = run_rule_checks(evidence)
    assert result.status == "ERRORS_DETECTED"
    types = [e.type for e in result.errors]
    assert "INTERFACE_ADMIN_DOWN" in types


def test_detects_missing_dhcp_helper():
    evidence = "interface Vlan20\n ip address 192.168.20.1 255.255.255.0\n no ip helper-address\n"
    result = run_rule_checks(evidence)
    assert result.status == "ERRORS_DETECTED"
    assert any(e.type == "DHCP_MISSING_HELPER" for e in result.errors)


def test_detects_broad_acl_deny():
    evidence = (
        "SW1# show access-lists 101\n"
        "Extended IP access list 101\n"
        "    10 deny ip 192.168.40.0 0.0.0.255 192.168.10.0 0.0.0.255\n"
        "    20 deny ip any any\n"
    )
    result = run_rule_checks(evidence)
    assert result.status == "ERRORS_DETECTED"
    assert any(e.type == "ACL_BROAD_DENY" for e in result.errors)


def test_detects_nat_interfaces_not_marked():
    evidence = (
        "ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
        "interface GigabitEthernet0/0\n"
        " ip address 10.0.0.1 255.255.255.0\n"
    )
    result = run_rule_checks(evidence)
    assert result.status == "ERRORS_DETECTED"
    assert any(e.type == "NAT_INTERFACE_NOT_MARKED" for e in result.errors)


def test_clean_config_produces_no_errors():
    """A syntactically fine, unremarkable config should not trip any rule."""
    evidence = (
        "R1# show interfaces GigabitEthernet0/12\n"
        "GigabitEthernet0/12 is up, line protocol is up\n"
        "  Internet address is 10.0.0.1/24\n"
    )
    result = run_rule_checks(evidence)
    assert result.status == "NO_ERRORS_DETECTED"


def test_never_raises_on_malformed_input():
    """The checker must degrade gracefully, never crash, on garbage input."""
    garbage_inputs = [None, "", "\x00\x01\x02", "a" * 100000, "{{{not valid anything"]
    for g in garbage_inputs:
        result = run_rule_checks(g or "")
        assert result.status in ("ERRORS_DETECTED", "NO_ERRORS_DETECTED")


def test_full_dataset_produces_reproducible_results():
    """Running the checker twice on the same input must give identical output (determinism)."""
    evidence = "GigabitEthernet0/0.30 is administratively down, line protocol is down\n"
    r1 = run_rule_checks(evidence)
    r2 = run_rule_checks(evidence)
    assert r1.status == r2.status
    assert [e.type for e in r1.errors] == [e.type for e in r2.errors]
