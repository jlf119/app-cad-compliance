from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from typing import Optional

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ONSHAPE_API_URL = os.environ.get("API_URL", "https://cad.onshape.com/api")

# In-memory store for translation state
in_memory_data_store = {}

# Helper to get auth header from request (simulate user session)
def get_auth_header(request: Request):
    auth = request.headers.get("authorization")
    if not auth:
        # Try cookie or other means if needed
        pass
    return {"Authorization": auth} if auth else {}

@app.get("/api/elements")
async def get_elements(documentId: str, workspaceId: str, request: Request):
    url = f"{ONSHAPE_API_URL}/documents/d/{documentId}/w/{workspaceId}/elements"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=request.headers)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))

@app.get("/api/elements/{eid}/parts")
async def get_element_parts(eid: str, documentId: str, workspaceId: str, request: Request):
    url = f"{ONSHAPE_API_URL}/parts/d/{documentId}/w/{workspaceId}/e/{eid}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=request.headers)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))

@app.get("/api/parts")
async def get_parts(documentId: str, workspaceId: str, request: Request):
    url = f"{ONSHAPE_API_URL}/parts/d/{documentId}/w/{workspaceId}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=request.headers)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))

# Placeholder for translation endpoints (to be expanded as needed)
@app.get("/api/gltf")
async def trigger_gltf_translation(documentId: str, workspaceId: str, gltfElementId: str = None, partId: Optional[str] = None, request: Request = None):
    # This endpoint triggers a translation job in Onshape
    # For demo, we use hardcoded translation params (as in Node.js)
    translation_params = {
        "resolution": "medium",
        "distanceTolerance": 0.00012,
        "angularTolerance": 0.1090830782496456,
        "maximumChordLength": 10,
        "workspaceId": workspaceId,
        "documentId": documentId
    }
    headers = get_auth_header(request)
    # Compose URL and body for translation
    if partId:
        url = f"{ONSHAPE_API_URL}/partstudios/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
        body = {
            "linkDocumentWorkspaceId": workspaceId,
            "partIds": partId,
            **translation_params
        }
    else:
        url = f"{ONSHAPE_API_URL}/assemblies/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
        body = {
            "linkDocumentWorkspaceId": workspaceId,
            "elementId": gltfElementId,
            **translation_params
        }
    # Add required fields for GLTF
    body.update({
        "includeExportIds": False,
        "formatName": "GLTF",
        "flattenAssemblies": False,
        "yAxisIsUp": False,
        "triggerAutoDownload": False,
        "storeInDocument": False,
        "grouping": True,
        "configuration": "default"
    })
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers={**headers, "Content-Type": "application/json", "Accept": "application/json"}, json=body)
        if resp.status_code == 200:
            data = resp.json()
            tid = data.get("id")
            if tid:
                in_memory_data_store[tid] = "in-progress"
            return JSONResponse(data, status_code=200)
        return JSONResponse({"error": resp.text}, status_code=resp.status_code)

@app.get("/api/gltf/{tid}")
async def get_gltf_translation(tid: str, request: Request):
    # Check in-memory store for translation state
    results = in_memory_data_store.get(tid)
    if results is None:
        return Response(status_code=404)
    if results == "in-progress":
        return Response(status_code=202)
    # Otherwise, fetch translation result from Onshape
    headers = get_auth_header(request)
    async with httpx.AsyncClient() as client:
        trans_url = f"{ONSHAPE_API_URL}/translations/{tid}"
        trans_resp = await client.get(trans_url, headers=headers)
        trans_json = trans_resp.json()
        if trans_json.get("requestState") == "FAILED":
            return JSONResponse({"error": trans_json.get("failureReason")}, status_code=500)
        # Download GLTF data
        doc_id = trans_json.get("documentId")
        ext_id = trans_json.get("resultExternalDataIds", [None])[0]
        if not doc_id or not ext_id:
            return JSONResponse({"error": "Missing translation result info."}, status_code=500)
        data_url = f"{ONSHAPE_API_URL}/documents/d/{doc_id}/externaldata/{ext_id}"
        data_resp = await client.get(data_url, headers=headers)
        # Clean up
        del in_memory_data_store[tid]
        return Response(content=data_resp.content, status_code=data_resp.status_code, media_type=data_resp.headers.get("content-type"))

@app.post("/api/event")
async def receive_event(request: Request):
    body = await request.json()
    if body.get("event") == "onshape.model.translation.complete":
        in_memory_data_store[body.get("translationId")] = body.get("webhookId")
    return Response(status_code=status.HTTP_200_OK)
