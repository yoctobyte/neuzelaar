import subprocess


def test_architectural_guardrails_pass() -> None:
    subprocess.run(["tools/check_guardrails.sh"], check=True)
