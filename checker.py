"""
Deterministic Cisco troubleshooting rule checker.

This module MUST NOT depend on the LLM in any way. It parses raw
`show`-command text with regex/string matching and returns a structured,
reproducible result. The AI diagnosis engine (Phase 4) consumes this
output as grounding evidence — it never replaces it.

Design: each `_check_*` function scans the evidence text independently and
appends any errors it finds to a shared list. This keeps each rule isolated
and easy to test/extend.
"""
import re
from typing import Callable, List

from app.schemas.diagnosis_schemas import RuleCheckResult, RuleError

# ---------------------------------------------------------------------------
# Individual rule checks
# ---------------------------------------------------------------------------


def _check_interface_status(text: str, errors: List[RuleError]) -> None:
    """Administratively down interfaces, and interfaces with line protocol down."""
    # e.g. "GigabitEthernet0/0.30 is administratively down, line protocol is down"
    for match in re.finditer(
        r"([\w/.\-]*(?:Ethernet|Serial|Vlan|Fast|Gig|Ten|Loopback|Tunnel)[\w/.\-]*)"
        r"\s+is\s+administratively down,\s*line protocol is down",
        text,
        re.IGNORECASE,
    ):
        errors.append(RuleError(
            type="INTERFACE_ADMIN_DOWN",
            interface=match.group(1),
            severity="HIGH",
            evidence=match.group(0).strip(),
        ))

    # "is down, line protocol is down (notconnect)" -> physical/Layer1 issue
    for match in re.finditer(
        r"([\w/.\-]*(?:Ethernet|Serial|Vlan|Fast|Gig|Ten)[\w/.\-]*)"
        r"\s+is down, line protocol is down\s*(\(notconnect\))?",
        text,
        re.IGNORECASE,
    ):
        errors.append(RuleError(
            type="INTERFACE_DOWN",
            interface=match.group(1),
            severity="HIGH",
            evidence=match.group(0).strip(),
        ))

    # Explicit "shutdown" in a running-config interface block
    for match in re.finditer(
        r"interface\s+([\w/.\-]+)\s*\n(?:[^\n]*\n){0,6}?\s*shutdown",
        text,
        re.IGNORECASE,
    ):
        errors.append(RuleError(
            type="INTERFACE_SHUTDOWN_CONFIGURED",
            interface=match.group(1),
            severity="MEDIUM",
            evidence="shutdown command present in interface configuration",
        ))

    # status table style: "Gi0/9 ... notconnect"
    for match in re.finditer(
        r"^(Gi\S*|Fa\S*|Te\S*|Vlan\S*)\s+\S*\s*notconnect",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        errors.append(RuleError(
            type="INTERFACE_NOT_CONNECTED",
            interface=match.group(1),
            severity="MEDIUM",
            evidence=match.group(0).strip(),
        ))

    # status table style: "Gi0/5 ... disabled"
    for match in re.finditer(
        r"^(Gi\S*|Fa\S*|Te\S*|Vlan\S*)\s+\S*\s*disabled",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        errors.append(RuleError(
            type="INTERFACE_DISABLED",
            interface=match.group(1),
            severity="MEDIUM",
            evidence=match.group(0).strip(),
        ))


def _check_vlan(text: str, errors: List[RuleError]) -> None:
    """VLAN SVI with no IP / down, and trunk allowed-VLAN mismatches."""
    # SVI unassigned/down: "Vlan60  unassigned  YES unset  down  down"
    for match in re.finditer(
        r"(Vlan\d+)\s+unassigned\s+\S+\s+\S+\s+down\s+down",
        text,
        re.IGNORECASE,
    ):
        errors.append(RuleError(
            type="VLAN_SVI_NO_IP",
            interface=match.group(1),
            severity="HIGH",
            evidence=match.group(0).strip(),
        ))

    # Trunk allowed-vlan list vs a VLAN that exists but isn't in that list.
    trunk_match = re.search(r"(Gi\S+|Fa\S+|Te\S+)\s+Vlans allowed on trunk\s*\n?\s*\S*\s*([\d,\-]+)", text)
    if not trunk_match:
        trunk_match = re.search(r"(Gi\S+|Fa\S+|Te\S+)\s+([\d,]+)\s*$", text, re.MULTILINE)
    if trunk_match:
        allowed_raw = trunk_match.group(2)
        allowed_vlans = set()
        for part in allowed_raw.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    lo, hi = part.split("-")
                    allowed_vlans.update(range(int(lo), int(hi) + 1))
                except ValueError:
                    continue
            elif part.isdigit():
                allowed_vlans.add(int(part))

        for vlan_match in re.finditer(r"^(\d+)\s+\S.*\bactive\b", text, re.MULTILINE):
            vlan_id = int(vlan_match.group(1))
            if vlan_id not in allowed_vlans and vlan_id != 1:
                errors.append(RuleError(
                    type="VLAN_TRUNK_MISMATCH",
                    interface=trunk_match.group(1),
                    severity="HIGH",
                    evidence=f"VLAN {vlan_id} exists but is not in the trunk's allowed VLAN list ({allowed_raw})",
                ))


def _check_ip_and_gateway(text: str, errors: List[RuleError]) -> None:
    """Duplicate IP addresses and gateway/subnet mismatches."""
    if re.search(r"%IP-4-DUPADDR|Duplicate address", text, re.IGNORECASE):
        match = re.search(r"Duplicate address ([\d.]+)", text)
        ip = match.group(1) if match else "unknown"
        errors.append(RuleError(
            type="DUPLICATE_IP",
            interface=None,
            severity="MEDIUM",
            evidence=f"Duplicate IP address detected: {ip}",
        ))

    # Gateway not in the same /24 as the host's own IP (best-effort heuristic
    # for the common classroom mistake of a typo'd gateway octet).
    ip_match = re.search(r"IPv4 Address[.\s]*:\s*([\d.]+)", text)
    mask_match = re.search(r"Subnet Mask[.\s]*:\s*([\d.]+)", text)
    gw_match = re.search(r"Default Gateway[.\s]*:\s*([\d.]+)", text)
    if ip_match and gw_match and mask_match:
        ip_octets = ip_match.group(1).split(".")
        gw_octets = gw_match.group(1).split(".")
        mask_octets = mask_match.group(1).split(".")
        # Simple /24-and-coarser check: compare octets where mask octet == 255
        mismatch = False
        for i in range(4):
            if i < len(mask_octets) and mask_octets[i] == "255":
                if ip_octets[i] != gw_octets[i]:
                    mismatch = True
                    break
        if mismatch:
            errors.append(RuleError(
                type="GATEWAY_SUBNET_MISMATCH",
                interface=None,
                severity="MEDIUM",
                evidence=f"Host IP {ip_match.group(1)} and gateway {gw_match.group(1)} are not in the same subnet ({mask_match.group(1)})",
            ))


def _check_routing(text: str, errors: List[RuleError]) -> None:
    if re.search(r"%\s*Network not in table", text, re.IGNORECASE):
        errors.append(RuleError(
            type="MISSING_ROUTE",
            interface=None,
            severity="HIGH",
            evidence="'% Network not in table' — destination network has no route",
        ))

    if re.search(r"\(no route to ([\w./]+)\)", text, re.IGNORECASE):
        match = re.search(r"\(no route to ([\w./]+)\)", text, re.IGNORECASE)
        errors.append(RuleError(
            type="MISSING_ROUTE",
            interface=None,
            severity="HIGH",
            evidence=f"No route present to destination network {match.group(1)}",
        ))
    elif re.search(r"no static routes configured", text, re.IGNORECASE) and \
            re.search(r"Gateway of last resort is not set", text, re.IGNORECASE):
        errors.append(RuleError(
            type="MISSING_DEFAULT_ROUTE",
            interface=None,
            severity="HIGH",
            evidence="Gateway of last resort is not set and no static routes are configured",
        ))

    if re.search(r"no OSPF (routes|process)|no OSPF process configured", text, re.IGNORECASE):
        errors.append(RuleError(
            type="ROUTING_PROTOCOL_MISSING",
            interface=None,
            severity="CRITICAL",
            evidence="No OSPF process/routes found in configuration or routing table",
        ))

    if re.search(r"Spanning tree protocol is disabled", text, re.IGNORECASE):
        errors.append(RuleError(
            type="STP_DISABLED",
            interface=None,
            severity="CRITICAL",
            evidence="Spanning Tree Protocol is disabled — risk of Layer 2 loop on redundant links",
        ))


def _check_dhcp(text: str, errors: List[RuleError]) -> None:
    if re.search(r"no ip helper-address", text, re.IGNORECASE):
        errors.append(RuleError(
            type="DHCP_MISSING_HELPER",
            interface=None,
            severity="HIGH",
            evidence="'no ip helper-address' — DHCP relay not configured on this SVI",
        ))

    if re.search(r"Leased addresses\s*:\s*254", text) and re.search(r"Total addresses\s*:\s*254", text):
        errors.append(RuleError(
            type="DHCP_POOL_EXHAUSTED",
            interface=None,
            severity="HIGH",
            evidence="DHCP pool shows 254/254 addresses leased (pool exhausted)",
        ))

    # Overlapping DHCP pool networks (two 'Network x.x.x.x' lines with the same value)
    networks = re.findall(r"Network\s+([\d.]+\s+[\d.]+)", text)
    if len(networks) >= 2 and len(set(networks)) < len(networks):
        errors.append(RuleError(
            type="DHCP_POOL_OVERLAP",
            interface=None,
            severity="CRITICAL",
            evidence=f"Multiple DHCP pools configured with the same network ({networks[0]})",
        ))


def _check_acl(text: str, errors: List[RuleError]) -> None:
    if re.search(r"deny ip any any", text, re.IGNORECASE) and re.search(r"access[- ]list", text, re.IGNORECASE):
        errors.append(RuleError(
            type="ACL_BROAD_DENY",
            interface=None,
            severity="HIGH",
            evidence="ACL contains a broad 'deny ip any any' statement that may block unintended traffic",
        ))

    for match in re.finditer(r"deny tcp any any eq (\d+)", text, re.IGNORECASE):
        port = match.group(1)
        if port in ("80", "443"):
            errors.append(RuleError(
                type="ACL_BLOCKS_WEB_TRAFFIC",
                interface=None,
                severity="HIGH",
                evidence=f"ACL explicitly denies TCP port {port} (web traffic)",
            ))


def _check_nat(text: str, errors: List[RuleError]) -> None:
    if re.search(r"ip nat inside source", text, re.IGNORECASE):
        has_inside = re.search(r"ip nat inside\b", text, re.IGNORECASE) is not None
        has_outside = re.search(r"ip nat outside\b", text, re.IGNORECASE) is not None
        if not (has_inside and has_outside):
            errors.append(RuleError(
                type="NAT_INTERFACE_NOT_MARKED",
                interface=None,
                severity="HIGH",
                evidence="NAT rule exists but interfaces are not marked 'ip nat inside'/'ip nat outside'",
            ))

    if re.search(r"no translations present|no static translations present", text, re.IGNORECASE):
        errors.append(RuleError(
            type="NAT_NO_TRANSLATIONS",
            interface=None,
            severity="MEDIUM",
            evidence="No active NAT translations found despite NAT configuration being present",
        ))

    if re.search(r"no static NAT entry|no static port-forward entry", text, re.IGNORECASE):
        errors.append(RuleError(
            type="NAT_MISSING_STATIC_ENTRY",
            interface=None,
            severity="HIGH",
            evidence="No static NAT / port-forward entry found for the required service",
        ))


def _check_wireless(text: str, errors: List[RuleError]) -> None:
    if re.search(r"Interface\.+\s*management", text, re.IGNORECASE) and re.search(r"Guest", text, re.IGNORECASE):
        errors.append(RuleError(
            type="WIRELESS_GUEST_NOT_ISOLATED",
            interface=None,
            severity="CRITICAL",
            evidence="Guest WLAN is bound to the management interface instead of an isolated guest VLAN interface",
        ))

    if re.search(r"interference detected:\s*HIGH", text, re.IGNORECASE):
        errors.append(RuleError(
            type="WIRELESS_RF_INTERFERENCE",
            interface=None,
            severity="LOW",
            evidence="High RF interference detected on the configured channel",
        ))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_ALL_CHECKS: List[Callable[[str, List[RuleError]], None]] = [
    _check_interface_status,
    _check_vlan,
    _check_ip_and_gateway,
    _check_routing,
    _check_dhcp,
    _check_acl,
    _check_nat,
    _check_wireless,
]


def run_rule_checks(show_outputs: str, topology_note: str = "") -> RuleCheckResult:
    """
    Run all deterministic checks against the combined evidence text.
    Never raises for malformed input — returns NO_ERRORS_DETECTED if evidence
    is empty or no patterns match, so callers (API layer) don't need to guard
    against this separately.
    """
    if not show_outputs or not show_outputs.strip():
        return RuleCheckResult(status="NO_ERRORS_DETECTED", errors=[])

    combined_text = f"{show_outputs}\n{topology_note or ''}"
    errors: List[RuleError] = []

    for check_fn in _ALL_CHECKS:
        try:
            check_fn(combined_text, errors)
        except Exception:
            # A single faulty regex/check should never crash the whole
            # rule-check pass; skip it and continue with the rest.
            continue

    # De-duplicate identical (type, interface, evidence) triples that can
    # arise when multiple regexes match overlapping text.
    seen = set()
    deduped: List[RuleError] = []
    for err in errors:
        key = (err.type, err.interface, err.evidence)
        if key not in seen:
            seen.add(key)
            deduped.append(err)

    status = "ERRORS_DETECTED" if deduped else "NO_ERRORS_DETECTED"
    return RuleCheckResult(status=status, errors=deduped)
