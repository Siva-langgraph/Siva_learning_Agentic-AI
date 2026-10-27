"""Deploy-time IAM handling — the errors students hit on a fresh account.

    "Gateway execution role lacks permission to invoke Lambda"   (CreateGatewayTarget)
    "The role defined for the function cannot be assumed by Lambda"  (CreateFunction)

    iam_ready     retries ONLY the propagation symptoms, gives up with a clear message
    deploy.py     grants the Lambda resource policy BEFORE creating the gateway target
    gateway       an existing gateway on another role is switched to the deploy's role
    lambda        a stale grant for an older gateway is replaced
    every boto3 call in infra/ matches the service model (names + required params)

No AWS: botocore's Stubber answers the calls.
"""
import ast
import json
import os
import sys
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from infra import gateway, iam_ready, lambda_deploy  # noqa: E402

LAMBDA_ARN = "arn:aws:lambda:us-east-1:111122223333:function:ecom-nlq-sql"
GW_ARN = "arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/ecom-nlq-gateway-abc"
ROLE = "arn:aws:iam::111122223333:role/ecom-nlq-gateway-role"
LACKS = ("Gateway execution role lacks permission to invoke Lambda function "
         f"{LAMBDA_ARN}. Update the permission and retry")


def _err(code, message, op):
    return ClientError({"Error": {"Code": code, "Message": message}}, op)


# ── iam_ready ────────────────────────────────────────────────────────────────

def test_a_propagation_symptom_is_retried_until_it_succeeds():
    calls = []

    def call():
        calls.append(1)
        if len(calls) < 3:
            raise _err("ValidationException", LACKS, "CreateGatewayTarget")
        return "ok"
    assert iam_ready.until_ready(call, iam_ready.GATEWAY_TARGET, "x", wait_s=0) == "ok" and len(calls) == 3


def test_any_other_error_is_raised_at_once():
    calls = []

    def call():
        calls.append(1)
        raise _err("ValidationException", "name must match pattern", "CreateGatewayTarget")
    with pytest.raises(ClientError):
        iam_ready.until_ready(call, iam_ready.GATEWAY_TARGET, "x", wait_s=0)
    assert len(calls) == 1


def test_a_permission_that_never_arrives_ends_with_what_to_check():
    def call():
        raise _err("ValidationException", LACKS, "CreateGatewayTarget")
    with pytest.raises(RuntimeError, match="permission is really missing"):
        iam_ready.until_ready(call, iam_ready.GATEWAY_TARGET, "the gateway to invoke ecom-nlq-sql",
                              attempts=3, wait_s=0)


def test_lambda_symptoms_cover_both_messages_aws_sends():
    for msg in ("The role defined for the function cannot be assumed by Lambda.",
                "The provided execution role does not have permissions to call CreateNetworkInterface on EC2"):
        assert any(s in msg for s in iam_ready.LAMBDA)


# ── gateway target ───────────────────────────────────────────────────────────

def test_target_creation_waits_for_iam(monkeypatch):
    monkeypatch.setattr(iam_ready, "WAIT_S", 0)
    monkeypatch.setattr(iam_ready.time, "sleep", lambda s: None)
    with Stubber(gateway.client) as st:
        st.add_response("list_gateway_targets", {"items": []}, {"gatewayIdentifier": "gw1", "maxResults": 100})
        st.add_client_error("create_gateway_target", "ValidationException", LACKS)
        st.add_response("create_gateway_target", {"targetId": "t1", "gatewayArn": GW_ARN, "name": "nlq-sql-tools",
                                                  "status": "READY", "createdAt": "2026-10-17T00:00:00Z",
                                                  "updatedAt": "2026-10-17T00:00:00Z",
                                                  "targetConfiguration": {"mcp": {"lambda": {"lambdaArn": LAMBDA_ARN,
                                                                                            "toolSchema": {"inlinePayload": []}}}},
                                                  "credentialProviderConfigurations": [
                                                      {"credentialProviderType": "GATEWAY_IAM_ROLE"}]})
        assert gateway.create_lambda_target("gw1", LAMBDA_ARN) == "t1"
        st.assert_no_pending_responses()


def test_an_existing_gateway_on_another_role_is_switched(monkeypatch):
    monkeypatch.setattr(gateway.time, "sleep", lambda s: None)
    gw = {"gatewayId": "gw1", "gatewayArn": GW_ARN, "gatewayUrl": "https://gw", "name": "ecom-nlq-gateway",
          "status": "READY", "createdAt": "2026-10-17T00:00:00Z", "updatedAt": "2026-10-17T00:00:00Z",
          "authorizerType": "AWS_IAM", "protocolType": "MCP"}
    with Stubber(gateway.client) as st:
        st.add_response("list_gateways", {"items": [{"gatewayId": "gw1", "name": "ecom-nlq-gateway", "status": "READY",
                                                     "createdAt": "2026-10-17T00:00:00Z",
                                                     "updatedAt": "2026-10-17T00:00:00Z",
                                                     "authorizerType": "AWS_IAM", "protocolType": "MCP"}]})
        st.add_response("get_gateway", {**gw, "roleArn": "arn:aws:iam::111122223333:role/some-old-role"})
        st.add_response("update_gateway", {**gw, "roleArn": ROLE})
        st.add_response("get_gateway", {**gw, "roleArn": ROLE})
        assert gateway.create_gateway(ROLE)["gatewayArn"] == GW_ARN
        st.assert_no_pending_responses()


# ── the Lambda's resource policy ─────────────────────────────────────────────

def _policy(source_arn):
    return {"Policy": json.dumps({"Statement": [{"Sid": lambda_deploy.STATEMENT_ID, "Effect": "Allow",
            "Condition": {"ArnLike": {"AWS:SourceArn": source_arn}}}]}), "RevisionId": "r1"}


def test_the_grant_is_added_when_missing():
    with Stubber(lambda_deploy.lambda_client) as st:
        st.add_client_error("get_policy", "ResourceNotFoundException", "no policy")
        st.add_response("add_permission", {"Statement": "{}"})
        lambda_deploy.allow_gateway_invoke(GW_ARN)
        st.assert_no_pending_responses()


def test_a_grant_for_an_older_gateway_is_replaced():
    with Stubber(lambda_deploy.lambda_client) as st:
        st.add_response("get_policy", _policy(GW_ARN.replace("abc", "old")))
        st.add_response("remove_permission", {})
        st.add_response("add_permission", {"Statement": "{}"})
        lambda_deploy.allow_gateway_invoke(GW_ARN)
        st.assert_no_pending_responses()


def test_the_right_grant_is_left_alone():
    with Stubber(lambda_deploy.lambda_client) as st:
        st.add_response("get_policy", _policy(GW_ARN))
        lambda_deploy.allow_gateway_invoke(GW_ARN)
        st.assert_no_pending_responses()


# ── deploy.py order ──────────────────────────────────────────────────────────

def test_deploy_grants_the_lambda_policy_before_creating_the_target():
    src = (HERE / "deploy.py").read_text(encoding="utf-8")
    assert src.index("lambda_deploy.allow_gateway_invoke(") < src.index("gateway.create_lambda_target(")


# ── every boto3 call in infra/ is a real call ────────────────────────────────

RECEIVERS = {"iam": "iam", "lambda_client": "lambda", "client": "bedrock-agentcore-control",
             "runtime_client": "bedrock-agentcore-control", "ecr": "ecr"}


def _sites():
    for path in sorted((HERE / "infra").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in RECEIVERS:
                yield path.name, node, RECEIVERS[node.func.value.id]


@pytest.mark.parametrize("name,node,service", list(_sites()),
                         ids=[f"{n}:{c.lineno}:{c.func.attr}" for n, c, _ in _sites()])
def test_call_matches_service_model(name, node, service):
    model = boto3.client(service, region_name="us-east-1").meta.service_model
    op = "".join(p.title() for p in node.func.attr.split("_"))
    if op not in model.operation_names:
        pytest.skip("not an API operation")
    shape = model.operation_model(op).input_shape
    passed = {k.arg for k in node.keywords if k.arg}
    assert not passed - set(shape.members), f"unknown params {passed - set(shape.members)}"
    if all(k.arg for k in node.keywords):
        assert not set(shape.required_members) - passed, f"missing {set(shape.required_members) - passed}"
