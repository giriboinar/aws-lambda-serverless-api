"""Serverless Tasks API — AWS Lambda handler.

Fronted by API Gateway HTTP API (payload format 2.0). All routes are served
by this single function; persistence is a DynamoDB table whose name is passed
via the TASKS_TABLE environment variable (set by Terraform).
"""

import json
import os
import uuid

import boto3

_table = None


def _get_table():
    """Lazily resolve the DynamoDB table (keeps cold starts and tests simple)."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TASKS_TABLE"])
    return _table


def _response(status_code, body=None):
    response = {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
    }
    # 204 must not carry a body.
    response["body"] = "" if status_code == 204 else json.dumps(body)
    return response


def _get_task(task_id):
    result = _get_table().get_item(Key={"id": task_id})
    return result.get("Item")


def lambda_handler(event, context):
    """Route API Gateway HTTP API (v2 payload) events to task operations."""
    try:
        http = event["requestContext"]["http"]
        method, path = http["method"], http["path"]
    except (KeyError, TypeError):
        return _response(400, {"error": "invalid event"})

    if method == "GET" and path == "/health":
        return _response(200, {"status": "ok", "service": "tasks-api"})

    if path == "/tasks":
        if method == "GET":
            items = _get_table().scan(Limit=50).get("Items", [])
            return _response(200, {"tasks": items})
        if method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _response(400, {"error": "invalid JSON body"})
            title = str(body.get("title") or "").strip()
            if not title:
                return _response(400, {"error": "title is required"})
            item = {"id": str(uuid.uuid4()), "title": title, "done": False}
            _get_table().put_item(Item=item)
            return _response(201, item)
        return _response(405, {"error": "method not allowed"})

    if path.startswith("/tasks/"):
        task_id = path[len("/tasks/"):]
        if not task_id or "/" in task_id:
            return _response(404, {"error": "not found"})
        if method == "GET":
            item = _get_task(task_id)
            return _response(200, item) if item else _response(404, {"error": "not found"})
        if method == "DELETE":
            if _get_task(task_id) is None:
                return _response(404, {"error": "not found"})
            _get_table().delete_item(Key={"id": task_id})
            return _response(204)
        return _response(405, {"error": "method not allowed"})

    return _response(404, {"error": "not found"})
