# Task 5: Subnet Allocation

Base address block: `10.20.0.0/16`

Subnets are allocated from largest to smallest, contiguously, using the smallest prefix that accommodates the required hosts.

## Subnet allocation table

| Subnet | Hosts required | Network address | Prefix | Usable host range | Broadcast address | Usable hosts |
|---|---:|---|---|---|---|---:|
| app | 1000 | 10.20.0.0 | /22 | 10.20.0.1 - 10.20.3.254 | 10.20.3.255 | 1022 |
| public | 250 | 10.20.4.0 | /24 | 10.20.4.1 - 10.20.4.254 | 10.20.4.255 | 254 |
| data | 100 | 10.20.5.0 | /25 | 10.20.5.1 - 10.20.5.126 | 10.20.5.127 | 126 |
| management | 20 | 10.20.5.128 | /27 | 10.20.5.129 - 10.20.5.158 | 10.20.5.159 | 30 |

## Working

Usable hosts = 2^(32 - prefix) - 2.

1. app: 1000 hosts require at least 1002 addresses. A /22 provides 1024 addresses and 1022 usable hosts.
2. public: 250 hosts require at least 252 addresses. A /24 provides 256 addresses and 254 usable hosts.
3. data: 100 hosts require at least 102 addresses. A /25 provides 128 addresses and 126 usable hosts.
4. management: 20 hosts require at least 22 addresses. A /27 provides 32 addresses and 30 usable hosts.

The allocation starts at 10.20.0.0 and each subnet begins immediately after the preceding subnet.
