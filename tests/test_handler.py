"""Unit tests for the Lambda handler — DynamoDB is faked, no AWS needed."""

import json
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["TASKS_TABLE"] = "test-tasks"

import handler


class FakeTable:
    """Minimal in-memory stand-in for a DynamoDB Table."""

    def __init__(self):
        self.items = {}

    def scan(self, Limit=None):
        values = list(self.items.values())
        return {"Items": values[:Limit] if Limit else values}

    def get_item(self, Key):
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[Item["id"]] = Item
        return {}

    def delete_item(self, Key):
        self.items.pop(Key["id"], None)
        return {}


@pytest.fixture()
def api():
    """Handler wired to a fresh fake table."""
    fake = FakeTable()
    with mock.patch.object(handler.boto3, "resource") as resource:
        resource.return_value.Table.return_value = fake
        handler._table = None  # force lazy re-resolution
        yield fake
    handler._table = None


def _event(method, path, body=None):
    return {
        "requestContext": {"http": {"method": method, "path": path}},
        "body": json.dumps(body) if body is not None else None,
    }


def test_health(api):
    resp = handler.lambda_handler(_event("GET", "/health"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["status"] == "ok"


def test_list_empty(api):
    resp = handler.lambda_handler(_event("GET", "/tasks"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"tasks": []}


def test_create_task(api):
    resp = handler.lambda_handler(_event("POST", "/tasks", {"title": "Buy milk"}), None)
    assert resp["statusCode"] == 201
    item = json.loads(resp["body"])
    assert item["title"] == "Buy milk"
    assert item["done"] is False
    assert item["id"]
    assert len(api.items) == 1


def test_create_task_trims_title(api):
    resp = handler.lambda_handler(_event("POST", "/tasks", {"title": "  Read  "}), None)
    assert json.loads(resp["body"])["title"] == "Read"


def test_create_task_missing_title(api):
    resp = handler.lambda_handler(_event("POST", "/tasks", {}), None)
    assert resp["statusCode"] == 400


def test_create_task_invalid_json(api):
    event = _event("POST", "/tasks")
    event["body"] = "{not-json"
    resp = handler.lambda_handler(event, None)
    assert resp["statusCode"] == 400


def test_get_task(api):
    created = json.loads(handler.lambda_handler(_event("POST", "/tasks", {"title": "x"}), None)["body"])
    resp = handler.lambda_handler(_event("GET", f"/tasks/{created['id']}"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["id"] == created["id"]


def test_get_task_not_found(api):
    resp = handler.lambda_handler(_event("GET", "/tasks/nope"), None)
    assert resp["statusCode"] == 404


def test_delete_task(api):
    created = json.loads(handler.lambda_handler(_event("POST", "/tasks", {"title": "x"}), None)["body"])
    resp = handler.lambda_handler(_event("DELETE", f"/tasks/{created['id']}"), None)
    assert resp["statusCode"] == 204
    assert resp["body"] == ""
    assert api.items == {}


def test_delete_task_not_found(api):
    resp = handler.lambda_handler(_event("DELETE", "/tasks/nope"), None)
    assert resp["statusCode"] == 404


def test_unknown_route(api):
    resp = handler.lambda_handler(_event("GET", "/nope"), None)
    assert resp["statusCode"] == 404


def test_method_not_allowed(api):
    resp = handler.lambda_handler(_event("POST", "/tasks/abc"), None)
    assert resp["statusCode"] == 405


def test_invalid_event(api):
    assert handler.lambda_handler({}, None)["statusCode"] == 400
    assert handler.lambda_handler(None, None)["statusCode"] == 400
