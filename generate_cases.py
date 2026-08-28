"""
One-time generator for backend/data/cases.csv.

Not part of the runtime app — this script is run once (see bottom) to
produce the dataset file. Kept here so the dataset's provenance/logic is
transparent and the cases can be regenerated/extended later.
"""
import csv
import os

CASES = [
    dict(
        case_id="NET-001",
        symptom="PC1 cannot reach Server1 in VLAN 30.",
        topology_note="PC1 (VLAN 10) and Server1 (VLAN 30) are on the same L3 switch with router-on-a-stick sub-interfaces for inter-VLAN routing.",
        show_outputs=(
            "R1# show interfaces GigabitEthernet0/0.10\n"
            "GigabitEthernet0/0.10 is up, line protocol is up\n"
            "  Internet address is 192.168.10.1/24\n"
            "  Encapsulation 802.1Q Virtual LAN, Vlan ID 10.\n\n"
            "R1# show interfaces GigabitEthernet0/0.30\n"
            "GigabitEthernet0/0.30 is administratively down, line protocol is down\n"
            "  Internet address is 192.168.30.1/24\n"
            "  Encapsulation 802.1Q Virtual LAN, Vlan ID 30.\n"
        ),
        expected_fault="Inter-VLAN routing failure because the VLAN 30 router sub-interface is administratively down.",
        osi_layer="Layer 3",
        concept_tag="VLAN",
        severity="High",
    ),
    dict(
        case_id="NET-002",
        symptom="New laptop on the Sales VLAN cannot get an IP address and shows APIPA (169.254.x.x).",
        topology_note="Sales VLAN 20 uses a DHCP relay (ip helper-address) pointing to a central DHCP server on VLAN 1.",
        show_outputs=(
            "SW1# show running-config interface vlan 20\n"
            "interface Vlan20\n"
            " ip address 192.168.20.1 255.255.255.0\n"
            " no ip helper-address\n\n"
            "SW1# show ip dhcp binding\n"
            "IP address       Client-ID/       Lease expiration        Type\n"
            "                  Hardware address\n"
            "(no bindings for VLAN 20 clients)\n"
        ),
        expected_fault="Missing 'ip helper-address' on VLAN 20 SVI, so DHCP DISCOVER broadcasts never reach the DHCP server.",
        osi_layer="Layer 3",
        concept_tag="DHCP",
        severity="High",
    ),
    dict(
        case_id="NET-003",
        symptom="Users can browse to internal servers by IP but not by hostname (e.g. intranet.corp.local fails).",
        topology_note="All internal hosts use DHCP-assigned DNS pointing to the internal DNS server 10.10.1.53.",
        show_outputs=(
            "PC1> ipconfig /all\n"
            "   IPv4 Address. . . . . . . . . . : 10.10.5.44\n"
            "   Default Gateway . . . . . . . . : 10.10.5.1\n"
            "   DNS Servers . . . . . . . . . . : 10.10.1.53\n\n"
            "PC1> ping 10.10.1.53\n"
            "Request timed out. (4/4 lost)\n\n"
            "R1# show ip route 10.10.1.53\n"
            "% Network not in table\n"
        ),
        expected_fault="No route to the DNS server subnet (10.10.1.0/24) in the routing table, so DNS queries silently fail while direct IP traffic to reachable hosts works.",
        osi_layer="Layer 3",
        concept_tag="DNS",
        severity="Medium",
    ),
    dict(
        case_id="NET-004",
        symptom="Branch office (192.168.50.0/24) cannot reach HQ subnet (192.168.1.0/24) over the WAN link.",
        topology_note="Branch and HQ routers are connected via a point-to-point serial link running static routing.",
        show_outputs=(
            "BranchR# show ip route\n"
            "Gateway of last resort is not set\n\n"
            "     192.168.50.0/24 is directly connected, GigabitEthernet0/0\n"
            "     10.0.0.0/30 is directly connected, Serial0/0/0\n"
            "(no route to 192.168.1.0/24)\n\n"
            "BranchR# show run | include ip route\n"
            "(no static routes configured)\n"
        ),
        expected_fault="Missing static route (or default route) toward the HQ subnet 192.168.1.0/24 via the serial WAN link.",
        osi_layer="Layer 3",
        concept_tag="Routing",
        severity="High",
    ),
    dict(
        case_id="NET-005",
        symptom="HR staff can reach the file server but Finance staff on a different VLAN are unexpectedly blocked from it too.",
        topology_note="An ACL was recently applied on the L3 switch's Finance VLAN interface to restrict access to the HR subnet only.",
        show_outputs=(
            "SW1# show access-lists 101\n"
            "Extended IP access list 101\n"
            "    10 deny ip 192.168.40.0 0.0.0.255 192.168.10.0 0.0.0.255\n"
            "    20 deny ip any any\n\n"
            "SW1# show ip interface Vlan40 | include access list\n"
            "  Outgoing access list is 101\n"
        ),
        expected_fault="ACL 101 ends with an explicit 'deny ip any any' with no preceding permit statements, blocking all Finance VLAN traffic, not just the intended HR subnet restriction.",
        osi_layer="Layer 3",
        concept_tag="ACL",
        severity="Critical",
    ),
    dict(
        case_id="NET-006",
        symptom="Internal hosts behind the edge router cannot reach any Internet websites.",
        topology_note="Edge router R1 connects the internal LAN (10.0.0.0/24) to the ISP via Gi0/1; NAT overload was configured to translate to the public interface.",
        show_outputs=(
            "R1# show ip nat translations\n"
            "(no translations present)\n\n"
            "R1# show run | section ip nat\n"
            "ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
            "interface GigabitEthernet0/0\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "interface GigabitEthernet0/1\n"
            " ip address 203.0.113.5 255.255.255.252\n\n"
            "R1# show ip access-lists 1\n"
            "Standard IP access list 1\n"
            "    10 permit 10.0.0.0 0.0.0.255\n"
        ),
        expected_fault="Neither Gi0/0 nor Gi0/1 has been marked as 'ip nat inside' / 'ip nat outside', so NAT overload never triggers even though the translation rule and ACL are correct.",
        osi_layer="Layer 3",
        concept_tag="NAT",
        severity="High",
    ),
    dict(
        case_id="NET-007",
        symptom="Guest wireless users can see and print to an internal office printer, violating guest isolation policy.",
        topology_note="The WLC maps the 'Guest-WiFi' SSID to VLAN 99, which should be isolated from the internal VLANs.",
        show_outputs=(
            "WLC# show wlan 2\n"
            "WLAN Identifier.......... 2\n"
            "Profile Name.............. Guest-WiFi\n"
            "Network Name (SSID)........ Guest-WiFi\n"
            "Interface.................. management\n\n"
            "WLC# show interface summary\n"
            "Interface Name    VLAN Identifier\n"
            "management         99\n"
            "guest-vlan         99\n"
        ),
        expected_fault="Guest-WiFi WLAN is bound to the 'management' interface instead of the dedicated 'guest-vlan' interface, placing guest traffic on the same VLAN as management/internal traffic.",
        osi_layer="Layer 2",
        concept_tag="Wireless",
        severity="Critical",
    ),
    dict(
        case_id="NET-008",
        symptom="PC2 has full connectivity to the local subnet but cannot reach any remote network.",
        topology_note="PC2 is a statically configured host on 192.168.5.0/24 behind gateway router R2.",
        show_outputs=(
            "PC2> ipconfig\n"
            "   IPv4 Address. . . . . . . . . . : 192.168.5.50\n"
            "   Subnet Mask . . . . . . . . . . : 255.255.255.0\n"
            "   Default Gateway . . . . . . . . : 192.168.6.1\n\n"
            "PC2> ping 192.168.5.1\n"
            "Reply from 192.168.5.1: bytes=32 time=1ms TTL=255\n\n"
            "PC2> ping 8.8.8.8\n"
            "Request timed out. (4/4 lost)\n"
        ),
        expected_fault="Default gateway on PC2 (192.168.6.1) is outside its own subnet (192.168.5.0/24) and does not match the real gateway (192.168.5.1), so all off-subnet traffic fails.",
        osi_layer="Layer 3",
        concept_tag="Gateway",
        severity="Medium",
    ),
    dict(
        case_id="NET-009",
        symptom="Two devices on the same VLAN intermittently lose connectivity and event logs show duplicate address warnings.",
        topology_note="Servers on VLAN 10 are statically addressed; a new server was added by a junior admin last week.",
        show_outputs=(
            "SW1# show ip arp | include Vlan10\n"
            "Internet  192.168.10.20      -   0050.56aa.1122  ARPA   Vlan10\n"
            "Internet  192.168.10.20      -   0050.56bb.3344  ARPA   Vlan10\n\n"
            "%IP-4-DUPADDR: Duplicate address 192.168.10.20 on Vlan10, sourced by 0050.56bb.3344\n"
        ),
        expected_fault="Duplicate IP address 192.168.10.20 assigned to two different MAC addresses on VLAN 10, causing ARP conflicts and intermittent loss.",
        osi_layer="Layer 3",
        concept_tag="Routing",
        severity="Medium",
    ),
    dict(
        case_id="NET-010",
        symptom="Trunk link between two switches is dropping VLAN 30 traffic only; other VLANs cross fine.",
        topology_note="SW1 and SW2 are connected via a trunk carrying VLANs 10, 20, and 30.",
        show_outputs=(
            "SW1# show interfaces trunk\n"
            "Port        Mode       Encapsulation  Status       Native vlan\n"
            "Gi0/1       on         802.1q         trunking     1\n\n"
            "Port        Vlans allowed on trunk\n"
            "Gi0/1       10,20\n\n"
            "SW1# show vlan brief | include 30\n"
            "30   Servers                          active\n"
        ),
        expected_fault="VLAN 30 is not included in the trunk's allowed VLAN list on Gi0/1, so its traffic is pruned from the trunk even though the VLAN exists on the switch.",
        osi_layer="Layer 2",
        concept_tag="VLAN",
        severity="High",
    ),
    dict(
        case_id="NET-011",
        symptom="Newly connected PC in the Marketing office gets no DHCP address at all, not even APIPA.",
        topology_note="Marketing VLAN 25 access port was just patched into a new switch port by facilities staff.",
        show_outputs=(
            "SW2# show interfaces GigabitEthernet0/5 status\n"
            "Port      Name               Status       Vlan       Duplex  Speed\n"
            "Gi0/5                        disabled     25         auto    auto\n\n"
            "SW2# show run interface Gi0/5\n"
            "interface GigabitEthernet0/5\n"
            " switchport access vlan 25\n"
            " switchport mode access\n"
            " shutdown\n"
        ),
        expected_fault="Access port Gi0/5 is administratively shut down, so the PC has no Layer 1/2 connectivity at all and never sends a DHCP request.",
        osi_layer="Layer 1",
        concept_tag="DHCP",
        severity="Medium",
    ),
    dict(
        case_id="NET-012",
        symptom="Remote office users report that internal web app URLs resolve to the wrong (old) IP address.",
        topology_note="DNS was recently migrated to a new internal server; app record was repointed to a new load balancer IP.",
        show_outputs=(
            "DNS1# show hosts\n"
            "Default domain is corp.local\n"
            "Name/address lookup uses domain service\n"
            "Host                       Flags      Age Type   Address\n"
            "app.corp.local             (perm, OK)  40 IP     10.10.2.15\n\n"
            "# Load balancer's actual current address:\n"
            "# 10.10.2.115\n"
        ),
        expected_fault="Stale/incorrect A record for app.corp.local still points to the decommissioned IP 10.10.2.15 instead of the current load balancer address 10.10.2.115.",
        osi_layer="Layer 7",
        concept_tag="DNS",
        severity="Medium",
    ),
    dict(
        case_id="NET-013",
        symptom="Remote branch loses connectivity to HQ every time the primary WAN link flaps; backup link never takes over.",
        topology_note="Branch router has a primary route via Serial0/0/0 and a floating static backup route via Serial0/0/1.",
        show_outputs=(
            "BranchR# show ip route static\n"
            "S    192.168.1.0/24 [1/0] via 10.0.0.1\n"
            "S    192.168.1.0/24 [1/0] via 10.0.1.1\n\n"
            "BranchR# show run | include ip route\n"
            "ip route 192.168.1.0 255.255.255.0 10.0.0.1\n"
            "ip route 192.168.1.0 255.255.255.0 10.0.1.1\n"
        ),
        expected_fault="The backup static route was configured with the same administrative distance (1) as the primary instead of a higher floating AD, so it is never truly a backup and both routes load-balance/conflict instead of failing over cleanly.",
        osi_layer="Layer 3",
        concept_tag="Routing",
        severity="Medium",
    ),
    dict(
        case_id="NET-014",
        symptom="External partners cannot reach the company's public-facing web server even though it works fine internally.",
        topology_note="Web server sits in a DMZ behind the edge router; static NAT should map its private IP to a public IP.",
        show_outputs=(
            "EdgeR# show ip nat translations\n"
            "(no static translations present)\n\n"
            "EdgeR# show run | include ip nat\n"
            "ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
            "(no static NAT entry for the web server)\n"
        ),
        expected_fault="No static NAT (ip nat inside source static) entry exists for the DMZ web server, so only outbound-initiated overload NAT works; inbound connections from the Internet have nothing to translate to.",
        osi_layer="Layer 3",
        concept_tag="NAT",
        severity="Critical",
    ),
    dict(
        case_id="NET-015",
        symptom="A subset of hosts on the Accounting VLAN cannot reach the printer server; others on the same VLAN work fine.",
        topology_note="Affected hosts were recently re-imaged and given static IPs by IT following a naming convention change.",
        show_outputs=(
            "PC5> ipconfig\n"
            "   IPv4 Address. . . . . . . . . . : 192.168.15.80\n"
            "   Subnet Mask . . . . . . . . . . : 255.255.255.192\n"
            "   Default Gateway . . . . . . . . : 192.168.15.1\n\n"
            "# Printer server address: 192.168.15.140\n"
            "# VLAN 15 subnet is documented as /26 (255.255.255.192), 4 blocks of 64\n"
        ),
        expected_fault="Incorrect subnet mask (/26) puts PC5 (192.168.15.80, third /26 block) and the printer server (192.168.15.140, fourth /26 block) in different subnets, even though they appear to share VLAN 15.",
        osi_layer="Layer 3",
        concept_tag="Gateway",
        severity="Medium",
    ),
    dict(
        case_id="NET-016",
        symptom="Voice VLAN phones register fine but data VLAN traffic from PCs behind the phones is being dropped intermittently.",
        topology_note="Access ports use a single switchport with both a voice VLAN and a data VLAN configured (phone daisy-chained to PC).",
        show_outputs=(
            "SW3# show run interface Gi0/12\n"
            "interface GigabitEthernet0/12\n"
            " switchport access vlan 12\n"
            " switchport voice vlan 112\n"
            " switchport mode access\n"
            " spanning-tree portfast\n\n"
            "SW3# show vlan brief | include 12\n"
            "12   Data-Floor2                     active\n"
            "112  Voice-Floor2                     active\n"
        ),
        expected_fault="Configuration matches the intended design (data VLAN 12 + voice VLAN 112); insufficient evidence points to a VLAN misconfiguration — additional evidence (interface error counters / duplex-speed) is needed before concluding root cause.",
        osi_layer="Layer 2",
        concept_tag="VLAN",
        severity="Low",
    ),
    dict(
        case_id="NET-017",
        symptom="A pool of DHCP addresses runs out every Monday morning and new employees cannot get an IP until afternoon.",
        topology_note="Office VLAN 30 (192.168.30.0/24) uses a locally-scoped DHCP pool on the L3 switch with an 8-hour default lease.",
        show_outputs=(
            "SW1# show ip dhcp pool OFFICE-30\n"
            "Pool OFFICE-30 :\n"
            " Utilization mark (high/low)    : 100 / 0\n"
            " Subnet size (first/last)       : 0 / 0\n"
            " Total addresses                : 254\n"
            " Leased addresses               : 254\n"
            " Excluded addresses             : 10\n"
            " Pending event                  : none\n\n"
            "SW1# show run | section dhcp pool OFFICE-30\n"
            "ip dhcp pool OFFICE-30\n"
            " network 192.168.30.0 255.255.255.0\n"
            " lease 8\n"
        ),
        expected_fault="DHCP pool OFFICE-30 is fully exhausted (254/254 leased) with an 8-hour lease that doesn't expire quickly enough for morning turnover, causing new devices to be denied addresses until leases age out.",
        osi_layer="Layer 3",
        concept_tag="DHCP",
        severity="High",
    ),
    dict(
        case_id="NET-018",
        symptom="Employees can access internal file shares by IP, and DNS resolves fine, but browsing internal sites by name still times out.",
        topology_note="An ACL was added to the core switch last week to restrict a set of ports for a security audit.",
        show_outputs=(
            "Core# show access-lists 110\n"
            "Extended IP access list 110\n"
            "    10 permit tcp any any eq 445\n"
            "    20 permit tcp any any eq 22\n"
            "    30 deny tcp any any eq 80\n"
            "    40 deny tcp any any eq 443\n"
            "    50 permit ip any any\n"
        ),
        expected_fault="ACL 110 explicitly denies TCP ports 80 and 443 (HTTP/HTTPS), blocking web traffic to internal sites while unrelated protocols like SMB (445) and SSH (22) remain unaffected.",
        osi_layer="Layer 4",
        concept_tag="ACL",
        severity="High",
    ),
    dict(
        case_id="NET-019",
        symptom="A newly deployed AP's SSID broadcasts but no client can successfully associate; they see the network but authentication always fails.",
        topology_note="The new AP was configured to match the existing corporate SSID using WPA2-Enterprise with RADIUS.",
        show_outputs=(
            "AP1# show running-config | section wlan\n"
            "wlan Corp-Secure 3 Corp-Secure\n"
            " security wpa wpa2\n"
            " security dot1x authentication-list default\n\n"
            "AP1# show aaa servers\n"
            "RADIUS: id 1, priority 1, host 10.10.9.9, auth-port 1812\n"
            "  State: current UP, duration 00h02m, previous duration 0h\n"
            "  Dead: total time 0h0m, count 0\n"
            "  Quarantined: No\n"
            "  Authen: request 0 timeouts 0\n"
        ),
        expected_fault="RADIUS server shows zero authentication requests received despite clients attempting to connect, suggesting a shared-secret or authentication-list mismatch between the new AP and RADIUS server — additional evidence (client-side EAP logs) is needed to confirm.",
        osi_layer="Layer 2",
        concept_tag="Wireless",
        severity="High",
    ),
    dict(
        case_id="NET-020",
        symptom="After a router reload, all remote sites became unreachable from HQ even though local HQ subnets work fine.",
        topology_note="HQ router uses OSPF for dynamic routing to reach all branch subnets.",
        show_outputs=(
            "HQ-R1# show ip route ospf\n"
            "(no OSPF routes in routing table)\n\n"
            "HQ-R1# show ip ospf neighbor\n"
            "(no output)\n\n"
            "HQ-R1# show run | section router ospf\n"
            "(no OSPF process configured)\n"
        ),
        expected_fault="OSPF process configuration was lost after the reload (not saved to startup-config), so no dynamic routes to branch subnets are being learned.",
        osi_layer="Layer 3",
        concept_tag="Routing",
        severity="Critical",
    ),
    dict(
        case_id="NET-021",
        symptom="Contractor laptop plugged into a conference room port cannot reach the Internet, but reaches internal servers fine.",
        topology_note="Conference room port is on VLAN 40 which uses NAT overload via a dedicated ACL matching only IT-approved subnets.",
        show_outputs=(
            "R1# show ip access-lists 5\n"
            "Standard IP access list 5\n"
            "    10 permit 192.168.10.0 0.0.0.255\n"
            "    20 permit 192.168.20.0 0.0.0.255\n\n"
            "R1# show run | include ip nat inside source\n"
            "ip nat inside source list 5 interface GigabitEthernet0/1 overload\n\n"
            "# Conference room VLAN 40 subnet: 192.168.40.0/24\n"
        ),
        expected_fault="NAT ACL 5 does not include the conference room subnet 192.168.40.0/24, so its traffic is never translated and cannot reach the Internet, while pre-approved subnets 10 and 20 work normally.",
        osi_layer="Layer 3",
        concept_tag="NAT",
        severity="Medium",
    ),
    dict(
        case_id="NET-022",
        symptom="Two switches connected by a redundant link pair are experiencing a broadcast storm and flooding the network.",
        topology_note="SW1 and SW2 have two physical links between them for redundancy.",
        show_outputs=(
            "SW1# show spanning-tree summary\n"
            "Switch is in pvst mode\n"
            "Root bridge for: none\n"
            "EtherChannel misconfig guard is enabled\n"
            "Spanning tree protocol is disabled\n\n"
            "SW1# show interfaces status | include connected\n"
            "Gi0/1      connected    1          a-full  a-1000\n"
            "Gi0/2      connected    1          a-full  a-1000\n"
        ),
        expected_fault="Spanning Tree Protocol is disabled on SW1, so the redundant link pair between SW1 and SW2 forms a Layer 2 loop with no blocking mechanism, causing a broadcast storm.",
        osi_layer="Layer 2",
        concept_tag="Routing",
        severity="Critical",
    ),
    dict(
        case_id="NET-023",
        symptom="Wireless guest users report very slow speeds and frequent disconnects near the lobby, but not elsewhere in the building.",
        topology_note="Lobby AP was recently changed from channel 6 to match a neighboring tenant's suggestion.",
        show_outputs=(
            "LobbyAP# show controllers dot11Radio 0 | include Channel\n"
            "Channel: 6 (interference detected: HIGH)\n\n"
            "LobbyAP# show wireless statistics | include retries\n"
            "Tx retries: 41% (elevated)\n"
        ),
        expected_fault="High channel interference and elevated Tx retry rate on channel 6 in the lobby suggest RF interference from a neighboring network — additional evidence (spectrum/site survey) is needed to fully confirm before recommending a channel change.",
        osi_layer="Layer 1",
        concept_tag="Wireless",
        severity="Low",
    ),
    dict(
        case_id="NET-024",
        symptom="A single PC on the Engineering VLAN cannot reach anything, including its own default gateway, while neighboring ports work.",
        topology_note="Engineering VLAN 18 access port was recently moved to a new patch panel location.",
        show_outputs=(
            "SW4# show interfaces GigabitEthernet0/9 status\n"
            "Port      Name               Status       Vlan       Duplex  Speed\n"
            "Gi0/9                        notconnect   18         auto    auto\n\n"
            "SW4# show interfaces GigabitEthernet0/9\n"
            "GigabitEthernet0/9 is down, line protocol is down (notconnect)\n"
        ),
        expected_fault="Physical link is down on Gi0/9 (notconnect) — most likely a bad patch cable or wrong patch-panel port following the recent move — preventing any Layer 2/3 connectivity from that PC.",
        osi_layer="Layer 1",
        concept_tag="Gateway",
        severity="Medium",
    ),
    dict(
        case_id="NET-025",
        symptom="Internal DNS resolves external domains (like google.com) but internal corp.local domains fail to resolve.",
        topology_note="Internal DNS server is configured as a forwarder-only setup for external queries and should be authoritative for corp.local.",
        show_outputs=(
            "DNS1# show running-config | section dns\n"
            "ip domain lookup\n"
            "ip name-server 8.8.8.8\n"
            "(no local DNS zone or host entries for corp.local configured)\n"
        ),
        expected_fault="The DNS server has no authoritative zone or static host entries configured for corp.local, so internal name resolution silently falls through to the external forwarder, which has no record of internal hosts.",
        osi_layer="Layer 7",
        concept_tag="DNS",
        severity="High",
    ),
    dict(
        case_id="NET-026",
        symptom="After enabling a new security ACL, remote administrators using SSH to manage the router were unexpectedly locked out.",
        topology_note="ACL 115 was applied inbound on the WAN interface to restrict management access to a single admin subnet.",
        show_outputs=(
            "R1# show access-lists 115\n"
            "Extended IP access list 115\n"
            "    10 permit tcp 203.0.113.0 0.0.0.255 any eq 22\n"
            "    20 deny ip any any log\n\n"
            "R1# show run | include access-group\n"
            "ip access-group 115 in\n\n"
            "# Admin subnet is actually 203.0.113.64/26, not 203.0.113.0/24\n"
        ),
        expected_fault="ACL 115's permit statement uses the wrong source subnet (203.0.113.0/24 instead of the actual admin subnet 203.0.113.64/26), so legitimate SSH traffic falls through to the deny-all and is blocked.",
        osi_layer="Layer 4",
        concept_tag="ACL",
        severity="Critical",
    ),
    dict(
        case_id="NET-027",
        symptom="Hosts in the new Warehouse VLAN can ping each other but cannot reach any other VLAN, including the server VLAN.",
        topology_note="Warehouse VLAN 60 was newly created and an SVI was added to the L3 switch for inter-VLAN routing.",
        show_outputs=(
            "SW1# show vlan brief | include 60\n"
            "60   Warehouse                        active\n\n"
            "SW1# show ip interface brief | include Vlan60\n"
            "Vlan60                 unassigned      YES unset  down                  down\n"
        ),
        expected_fault="VLAN 60's SVI (interface Vlan60) has no IP address assigned and is administratively/operationally down, so there is no Layer 3 gateway for inter-VLAN routing despite Layer 2 connectivity within the VLAN working.",
        osi_layer="Layer 3",
        concept_tag="VLAN",
        severity="High",
    ),
    dict(
        case_id="NET-028",
        symptom="Remote workers using the site-to-site VPN can reach HQ servers, but HQ users cannot initiate connections back to the remote site's servers.",
        topology_note="Site-to-site NAT and routing are configured; some asymmetric traffic pattern is suspected.",
        show_outputs=(
            "HQ-R1# show ip route 192.168.99.0\n"
            "% Network not in table\n\n"
            "HQ-R1# show crypto session\n"
            "Interface: Tunnel0\n"
            "Session status: UP-ACTIVE\n"
            "Peer: 198.51.100.10\n"
        ),
        expected_fault="VPN tunnel is up, but HQ has no route to the remote site's subnet 192.168.99.0/24, so HQ-initiated traffic has nowhere to be routed even though the remote site can reach HQ (likely due to a default route there).",
        osi_layer="Layer 3",
        concept_tag="Routing",
        severity="High",
    ),
    dict(
        case_id="NET-029",
        symptom="Guest WiFi users occasionally get an internal corporate IP address instead of the intended guest range.",
        topology_note="Guest VLAN 99 and internal VLAN 10 both have DHCP pools configured on the same central DHCP server.",
        show_outputs=(
            "DHCP1# show ip dhcp pool\n"
            "Pool GUEST-99 :\n"
            " Network 172.16.99.0 255.255.255.0\n"
            "Pool CORP-10 :\n"
            " Network 172.16.99.0 255.255.255.0\n"
        ),
        expected_fault="DHCP pool CORP-10 is misconfigured with the same network (172.16.99.0/24) as GUEST-99, causing an overlapping scope that randomly hands out addresses meant for the corporate pool to guest devices.",
        osi_layer="Layer 3",
        concept_tag="DHCP",
        severity="Critical",
    ),
    dict(
        case_id="NET-030",
        symptom="A branch office's outbound web traffic works, but all inbound VoIP calls from HQ fail to connect.",
        topology_note="Branch uses PAT (NAT overload) for general Internet traffic; VoIP requires a static NAT mapping for its SIP trunk IP.",
        show_outputs=(
            "BranchR# show ip nat translations | include 5060\n"
            "(no translations for port 5060)\n\n"
            "BranchR# show run | include ip nat\n"
            "ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
            "(no static port-forward entry for SIP/5060)\n"
        ),
        expected_fault="No static NAT/port-forward rule exists for SIP signaling (UDP/TCP 5060) toward the VoIP gateway, so inbound call setup from HQ has no translation target even though general outbound PAT works fine.",
        osi_layer="Layer 4",
        concept_tag="NAT",
        severity="High",
    ),
]

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cases.csv")

FIELDS = [
    "case_id", "symptom", "topology_note", "show_outputs",
    "expected_fault", "osi_layer", "concept_tag", "severity",
]

def main():
    assert len(CASES) == 30, f"Expected 30 cases, got {len(CASES)}"
    concept_tags = {c["concept_tag"] for c in CASES}
    required = {"VLAN", "Gateway", "DHCP", "DNS", "Routing", "ACL", "NAT", "Wireless"}
    missing = required - concept_tags
    assert not missing, f"Missing concept coverage: {missing}"

    out_path = os.path.abspath(OUT_PATH)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for case in CASES:
            writer.writerow(case)

    print(f"Wrote {len(CASES)} cases to {out_path}")
    print("Concept tag coverage:", sorted(concept_tags))


if __name__ == "__main__":
    main()
