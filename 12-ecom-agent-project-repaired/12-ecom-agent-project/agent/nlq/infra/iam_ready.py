"""Retry an AWS call while IAM is still propagating a role or a policy put on it.

    deploy step ──► call ──► ok ──────────────────────────────────────► return
                     │
                     ├─ error names a PROPAGATION symptom (below) ─► wait 10 s ─► call again
                     │                                               (up to 2 minutes)
                     └─ any other error ───────────────────────────► raised at once

WHY THIS EXISTS
    IAM is eventually consistent. A role created, or a policy put on it, a
    few seconds ago is not yet visible to the service that checks it —
    AgentCore, Lambda, the Gateway. The check fails with a message that
    reads like a real permission error, although the same call succeeds a
    minute later. A fixed sleep(10) after creating a role is not enough:
    propagation regularly takes 20-60 seconds, and a policy changed on an
    EXISTING role gets no sleep at all.

    Students hit this as "run the same step again" failures. This makes the
    deploy wait for IAM instead of failing.

THE SYMPTOMS — each one seen from a real deploy
    RUNTIME          create/update_agent_runtime with a new runtime role
    LAMBDA           create_function / update_function_configuration with a new
                     Lambda role (the VPC one also needs ec2 network-interface rights)
    GATEWAY_TARGET   create/update_gateway_target before the Gateway role's
                     lambda:InvokeFunction has propagated

WHAT THIS DOES NOT DO
    It grants nothing. A permission that is really missing still fails: after
    the wait, with AWS's own message and a line saying what to check. It
    never retries an error that is not in the symptom list.

    This file is identical in every agent's infra/ folder — change all copies together.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

RUNTIME = ("Role validation failed", "Access denied while validating ECR URI")
LAMBDA = ("cannot be assumed by Lambda",
          "does not have permissions to call CreateNetworkInterface",
          "does not have permission to call CreateNetworkInterface")
GATEWAY_TARGET = ("lacks permission to invoke Lambda",)

ATTEMPTS = 12          # 12 x 10 s = 2 minutes — longer than IAM has taken in practice
WAIT_S = 10


def until_ready(call: Callable[[], T], symptoms: tuple[str, ...], what: str,
                attempts: int = ATTEMPTS, wait_s: float = WAIT_S) -> T:
    """Run `call`; while it fails with one of `symptoms`, wait and run it again.

    what  — a few words for the progress line and the final error, e.g.
            "the Gateway role to invoke ecom-nlq-sql".
    """
    from botocore.exceptions import ClientError

    for attempt in range(1, attempts + 1):
        try:
            return call()
        except ClientError as exc:
            message = str(exc)
            if not any(s in message for s in symptoms):
                raise                                          # a real error: no retry
            if attempt == attempts:
                raise RuntimeError(
                    f"waited {int(attempts * wait_s)} s for IAM to allow {what}, and AWS still says:\n"
                    f"  {message}\n"
                    f"IAM never takes this long, so the permission is really missing: check that the "
                    f"role's policy names this exact resource, and that no permissions boundary or "
                    f"organization policy blocks it.") from exc
            print(f"  waiting for IAM to allow {what} ({int(attempt * wait_s)} s)…")
            time.sleep(wait_s)
    raise AssertionError("unreachable")
