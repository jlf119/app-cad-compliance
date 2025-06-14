import json
import os
import httpx
from typing import Optional

ONSHAPE_API_URL = os.environ.get("API_URL", "https://cad.onshape.com/api")

# In-memory store for translation state (not persistent in serverless)
in_memory_data_store = {}

def handler(request):
    method = request.get("method", "GET")
    path = request.get("path", "")
    query = request.get("query", {})
    headers = request.get("headers", {})
    # For POST/PUT, parse body
    try:
        body = json.loads(request.get("body", "{}")) if method in ("POST", "PUT") else None
    except Exception:
        body = None

    # /api/elements (GET)
    if path == "/api/elements" and method == "GET":
        documentId = query.get("documentId")
        workspaceId = query.get("workspaceId")
        if not documentId or not workspaceId:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing documentId or workspaceId"}), "headers": {"Content-Type": "application/json"}}
        url = f"{ONSHAPE_API_URL}/documents/d/{documentId}/w/{workspaceId}/elements"
        resp = httpx.get(url, headers=headers)
        return {"statusCode": resp.status_code, "body": resp.text, "headers": {"Content-Type": resp.headers.get("content-type", "application/json")}}

    # /api/elements/{eid}/parts (GET)
    if path.startswith("/api/elements/") and path.endswith("/parts") and method == "GET":
        # Extract eid from path
        parts = path.split("/")
        eid = parts[3] if len(parts) > 3 else None
        documentId = query.get("documentId")
        workspaceId = query.get("workspaceId")
        if not eid or not documentId or not workspaceId:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing eid, documentId or workspaceId"}), "headers": {"Content-Type": "application/json"}}
        url = f"{ONSHAPE_API_URL}/parts/d/{documentId}/w/{workspaceId}/e/{eid}"
        resp = httpx.get(url, headers=headers)
        return {"statusCode": resp.status_code, "body": resp.text, "headers": {"Content-Type": resp.headers.get("content-type", "application/json")}}

    # /api/parts (GET)
    if path == "/api/parts" and method == "GET":
        documentId = query.get("documentId")
        workspaceId = query.get("workspaceId")
        if not documentId or not workspaceId:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing documentId or workspaceId"}), "headers": {"Content-Type": "application/json"}}
        url = f"{ONSHAPE_API_URL}/parts/d/{documentId}/w/{workspaceId}"
        resp = httpx.get(url, headers=headers)
        return {"statusCode": resp.status_code, "body": resp.text, "headers": {"Content-Type": resp.headers.get("content-type", "application/json")}}

    # /api/gltf (GET) - trigger translation
    if path == "/api/gltf" and method == "GET":
        documentId = query.get("documentId")
        workspaceId = query.get("workspaceId")
        gltfElementId = query.get("gltfElementId")
        partId = query.get("partId")
        if not documentId or not workspaceId or not gltfElementId:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing documentId, workspaceId, or gltfElementId"}), "headers": {"Content-Type": "application/json"}}
        translation_params = {
            "resolution": "medium",
            "distanceTolerance": 0.00012,
            "angularTolerance": 0.1090830782496456,
            "maximumChordLength": 10,
            "workspaceId": workspaceId,
            "documentId": documentId
        }
        # Compose URL and body for translation
        if partId:
            url = f"{ONSHAPE_API_URL}/partstudios/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
            body_data = {
                "linkDocumentWorkspaceId": workspaceId,
                "partIds": partId,
                **translation_params
            }
        else:
            url = f"{ONSHAPE_API_URL}/assemblies/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
            body_data = {
                "linkDocumentWorkspaceId": workspaceId,
                "elementId": gltfElementId,
                **translation_params
            }
        body_data.update({
            "includeExportIds": False,
            "formatName": "GLTF",
            "flattenAssemblies": False,
            "yAxisIsUp": False,
            "triggerAutoDownload": False,
            "storeInDocument": False,
            "grouping": True,
            "configuration": "default"
        })
        resp = httpx.post(url, headers={**headers, "Content-Type": "application/json", "Accept": "application/json"}, json=body_data)
        if resp.status_code == 200:
            data = resp.json()
            tid = data.get("id")
            if tid:
                in_memory_data_store[tid] = "in-progress"
            return {"statusCode": 200, "body": json.dumps(data), "headers": {"Content-Type": "application/json"}}
        return {"statusCode": resp.status_code, "body": json.dumps({"error": resp.text}), "headers": {"Content-Type": "application/json"}}

    # /api/gltf/{tid} (GET) - get translation result
    if path.startswith("/api/gltf/") and method == "GET":
        tid = path.split("/")[-1]
        results = in_memory_data_store.get(tid)
        if results is None:
            return {"statusCode": 404, "body": "", "headers": {}}
        if results == "in-progress":
            return {"statusCode": 202, "body": "", "headers": {}}
        # Otherwise, fetch translation result from Onshape
        trans_url = f"{ONSHAPE_API_URL}/translations/{tid}"
        trans_resp = httpx.get(trans_url, headers=headers)
        trans_json = trans_resp.json()
        if trans_json.get("requestState") == "FAILED":
            return {"statusCode": 500, "body": json.dumps({"error": trans_json.get("failureReason")}), "headers": {"Content-Type": "application/json"}}
        doc_id = trans_json.get("documentId")
        ext_id = trans_json.get("resultExternalDataIds", [None])[0]
        if not doc_id or not ext_id:
            return {"statusCode": 500, "body": json.dumps({"error": "Missing translation result info."}), "headers": {"Content-Type": "application/json"}}
        data_url = f"{ONSHAPE_API_URL}/documents/d/{doc_id}/externaldata/{ext_id}"
        data_resp = httpx.get(data_url, headers=headers)
        del in_memory_data_store[tid]
        return {"statusCode": data_resp.status_code, "body": data_resp.content, "headers": {"Content-Type": data_resp.headers.get("content-type", "application/octet-stream")}}

    # /api/event (POST) - receive event
    if path == "/api/event" and method == "POST":
        if body and body.get("event") == "onshape.model.translation.complete":
            in_memory_data_store[body.get("translationId")] = body.get("webhookId")
        return {"statusCode": 200, "body": "", "headers": {}}

    # Default: Not found
    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not found"})
    }
