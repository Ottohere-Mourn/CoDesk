# A6000 Proxy Toggle

This forwards the existing 4090 user-level HTTP proxy to A6000 over SSH. It does not install a VPN client, alter system networking, copy credentials, or use the unidentified proxy listeners already present on A6000.

## Enable

On the 4090 development host:

```bash
/home/mjh/.local/bin/codesk-a6000-proxy-tunnel on
```

In the A6000 shell that should use the proxy:

```bash
source /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk/scripts/a6000_proxy_env.sh
a6000_proxy_on
a6000_proxy_status
```

The environment is enabled only in the shell where `a6000_proxy_on` is called (and child processes launched from it).

## Disable

In each A6000 shell using the proxy:

```bash
a6000_proxy_off
```

Then, on the 4090 host, close the forwarding tunnel:

```bash
/home/mjh/.local/bin/codesk-a6000-proxy-tunnel off
```

Tunnel state can be checked on the 4090 host with `.../codesk-a6000-proxy-tunnel status`.

The tunnel binds only to A6000 loopback port 17891 and forwards to the 4090 loopback proxy port 7891. It is not exposed to the network. A6000 proxy environment variables are off by default. Enabling the environment requires the tunnel to be live.
