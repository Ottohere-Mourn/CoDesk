# Source this file in the current A6000 shell to enable/disable the forwarded proxy.
# The actual proxy remains on the 4090 development host; no VPN credentials are copied.

_codesk_a6000_proxy_tunnel_ready() {
  python3 - <<PY
import socket, sys
s = socket.socket()
s.settimeout(1)
try:
    s.connect(("127.0.0.1", 17891))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

a6000_proxy_on() {
  if ! _codesk_a6000_proxy_tunnel_ready; then
    printf "%s\n" "CoDesk proxy tunnel is not available. On 4090 run: codesk-a6000-proxy-tunnel on" >&2
    return 1
  fi
  export HTTP_PROXY=http://127.0.0.1:17891
  export HTTPS_PROXY=http://127.0.0.1:17891
  export ALL_PROXY=http://127.0.0.1:17891
  export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY" all_proxy="$ALL_PROXY"
  if [[ -z "${NO_PROXY:-${no_proxy:-}}" ]]; then
    export NO_PROXY=localhost,127.0.0.1,::1
  fi
  export no_proxy="$NO_PROXY"
  printf "%s\n" "A6000 proxy enabled through the 4090 SSH-forwarded proxy."
}

a6000_proxy_off() {
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
  printf "%s\n" "A6000 shell proxy variables disabled."
}

a6000_proxy_status() {
  if [[ "${HTTP_PROXY:-}" == "http://127.0.0.1:17891" ]] && _codesk_a6000_proxy_tunnel_ready; then
    printf "%s\n" "enabled (forward is reachable)"
  elif _codesk_a6000_proxy_tunnel_ready; then
    printf "%s\n" "tunnel ready; proxy variables are off in this shell"
  else
    printf "%s\n" "off (no 4090-to-A6000 tunnel)"
  fi
}
