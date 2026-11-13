from oscombo.human_agent_mail_case_runner import Backend


def test_mail_backend_host_healthcheck_uses_loopback_not_docker_gateway(tmp_path):
    backend = Backend(tmp_path, "guest-test", "mail-health-test", "192.0.2.1")
    try:
        backend.healthcheck()
    finally:
        backend.close()
