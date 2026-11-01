# NACL Explanation

A Network Access Control List is stateless, meaning it does not remember previously allowed connections. Therefore, request and reply packets are evaluated independently.

For example, when a client sends an HTTP request to TCP port 443, the inbound rule allows it. The response travels outbound to the client's ephemeral port (1024-65535), so a separate outbound rule is needed to allow that reply. Similarly, traffic returning from the application subnet is allowed inbound through the ephemeral-port rule.

Rule order matters because the NACL evaluates rules in ascending rule-number order and applies the first matching rule. The deny rule for 198.51.100.0/24 must therefore appear before the general TCP 80 and TCP 443 allow rules. Otherwise, traffic from that abusive range could match a web allow rule before reaching the deny rule.

All traffic not matched by an allow rule is denied by default.
