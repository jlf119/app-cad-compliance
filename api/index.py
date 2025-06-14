import json
import os
import httpx
from typing import Optional

ONSHAPE_API_URL = os.environ.get("API_URL", "https://cad.onshape.com/api")

# In-memory store for translation state (not persistent in serverless)
in_memory_data_store = {}

# --- Helper Functions ---

def _json_response(status_code: int, data: dict, headers: Optional[dict] = None) -> dict:
    """Creates a standardized JSON response for the Vercel handler."""
    response_headers = {"Content-Type": "application/json"}
    if headers:
        response_headers.update(headers)
    return {"statusCode": status_code, "body": json.dumps(data), "headers": response_headers}

def _raw_response(status_code: int, body: bytes | str, content_type: str, headers: Optional[dict] = None) -> dict:
    """Creates a general raw response for the Vercel handler."""
    response_headers = {"Content-Type": content_type}
    if headers:
        response_headers.update(headers)
    return {"statusCode": status_code, "body": body, "headers": response_headers}

def _validate_required_params(query_data: dict, required: list[str]) -> Optional[str]:
    """Checks for missing required query parameters. Returns error message string or None."""
    missing = [param for param in required if not query_data.get(param)]
    if missing:
        return f"Missing required query parameters: {', '.join(missing)}"
    return None

def _onshape_api_request(
    method: str, 
    onshape_endpoint: str, 
    incoming_headers: dict, 
    params: Optional[dict] = None, 
    json_data: Optional[dict] = None
) -> httpx.Response | dict:
    """
    Makes a request to the Onshape API.
    Returns an httpx.Response object on success, or a Vercel error response dict on failure.
    """
    url = f"{ONSHAPE_API_URL}{onshape_endpoint}"
    
    onshape_req_headers = {"Accept": "application/json"} # Default for most Onshape metadata APIs
    
    auth_header = incoming_headers.get("authorization")
    if auth_header:
        onshape_req_headers["Authorization"] = auth_header
    
    user_agent_header = incoming_headers.get("user-agent")
    if user_agent_header:
        onshape_req_headers["User-Agent"] = user_agent_header

    if method.upper() in ("POST", "PUT") and json_data:
        onshape_req_headers["Content-Type"] = "application/json"
        
    try:
        if method.upper() == "GET":
            resp = httpx.get(url, headers=onshape_req_headers, params=params)
        elif method.upper() == "POST":
            resp = httpx.post(url, headers=onshape_req_headers, json=json_data, params=params)
        else:
            # This error is for the _onshape_api_request helper itself
            return _json_response(405, {"error": f"HTTP method {method} not implemented in API request helper."})
        
        return resp # Return the raw httpx.Response object
        
    except httpx.RequestError as e:
        print(f"Onshape API request error to {url}: {e}")
        return _json_response(502, {"error": f"Onshape API request failed: {str(e)}"}) # 502 Bad Gateway
    except Exception as e:
        print(f"Unexpected error during Onshape API request to {url}: {e}")
        return _json_response(500, {"error": f"An unexpected error occurred: {str(e)}"})

# --- Main Handler ---

def handler(request):
    method = request.get("method", "GET")
    path = request.get("path", "")
    query = request.get("query", {})
    headers = request.get("headers", {}) # These are incoming headers from the client
    
    try:
        body_str = request.get("body", "{}")
        # Ensure body_str is not None before trying to load it, and only parse for relevant methods
        parsed_body = json.loads(body_str) if body_str and method in ("POST", "PUT") else {}
    except json.JSONDecodeError:
        return _json_response(400, {"error": "Invalid JSON in request body."})
    except Exception: # Catch any other parsing errors
        return _json_response(400, {"error": "Could not parse request body."})


    # /api/elements (GET)
    if path == "/api/elements" and method == "GET":
        param_error = _validate_required_params(query, ["documentId", "workspaceId"])
        if param_error:
            return _json_response(400, {"error": param_error})
        
        doc_id = query["documentId"]
        ws_id = query["workspaceId"]
        
        onshape_endpoint = f"/documents/d/{doc_id}/w/{ws_id}/elements"
        # Pass client's headers to the helper, which will pick relevant ones (e.g., Authorization)
        onshape_resp = _onshape_api_request("GET", onshape_endpoint, incoming_headers=headers)

        if isinstance(onshape_resp, dict): # Means _onshape_api_request returned an error dict
            return onshape_resp 
            
        return _raw_response(
            onshape_resp.status_code,
            onshape_resp.text, # Use .text for text-based content like JSON
            onshape_resp.headers.get("content-type", "application/json") # Default if Onshape doesn't specify
        )

    # /api/elements/{eid}/parts (GET)
    path_parts = path.split("/")
    # Expected path: /api/elements/<eid>/parts
    if method == "GET" and len(path_parts) == 5 and path_parts[0] == "" and path_parts[1] == "api" and \
       path_parts[2] == "elements" and path_parts[4] == "parts":
        eid = path_parts[3]
        
        param_error = _validate_required_params(query, ["documentId", "workspaceId"])
        if param_error:
            return _json_response(400, {"error": f"For element {eid}: {param_error}"})

        doc_id = query["documentId"]
        ws_id = query["workspaceId"]
        
        onshape_endpoint = f"/parts/d/{doc_id}/w/{ws_id}/e/{eid}"
        onshape_resp = _onshape_api_request("GET", onshape_endpoint, incoming_headers=headers)

        if isinstance(onshape_resp, dict): # Error from helper
            return onshape_resp
            
        return _raw_response(
            onshape_resp.status_code,
            onshape_resp.text,
            onshape_resp.headers.get("content-type", "application/json")
        )

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
        partId = query.get("partId") # Optional
        
        required_main = ["documentId", "workspaceId", "gltfElementId"]
        param_error = _validate_required_params(query, required_main)
        if param_error:
            return _json_response(400, {"error": param_error})

        # Construct the Onshape API endpoint and body for translation request
        # This part is more complex and might use _onshape_api_request for its POST,
        # or might need specific handling if the response isn't simple JSON.
        # For now, keeping original logic structure for this complex endpoint.
        # Consider refactoring this part carefully.
        
        translation_params = {
            "resolution": "medium",
            "distanceTolerance": 0.00012,
            "angularTolerance": 0.1090830782496456,
            "maximumChordLength": 10,
        }
        # Note: The original code used workspaceId and documentId from query inside translation_params.
        # Onshape API docs should be checked if these are part of the body or URL for translations.
        # Assuming they are part of the body as per original structure.

        onshape_req_body_common = {
            "linkDocumentWorkspaceId": workspaceId, # From query
            **translation_params,
            "includeExportIds": False,
            "formatName": "GLTF",
            "flattenAssemblies": False,
            "yAxisIsUp": False,
            "triggerAutoDownload": False,
            "storeInDocument": False, # Important for not cluttering Onshape doc
            "grouping": True,
            "configuration": "default" # Or from query if configurable
        }

        if partId:
            onshape_endpoint = f"/partstudios/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
            onshape_req_body = {
                **onshape_req_body_common,
                "partIds": [partId], # API expects a list
                # "elementId": gltfElementId, # For partstudios, elementId is in URL
            }
        else: # Assembly
            onshape_endpoint = f"/assemblies/d/{documentId}/w/{workspaceId}/e/{gltfElementId}/translations"
            onshape_req_body = {
                **onshape_req_body_common,
                "elementId": gltfElementId, # For assemblies, elementId is in body
            }
        
        # Using _onshape_api_request for the POST call
        onshape_resp = _onshape_api_request("POST", onshape_endpoint, incoming_headers=headers, json_data=onshape_req_body)

        if isinstance(onshape_resp, dict): # Error from helper
            return onshape_resp

        if onshape_resp.status_code == 200: # Successfully initiated translation
            try:
                data = onshape_resp.json()
                tid = data.get("id")
                if tid:
                    in_memory_data_store[tid] = "in-progress" # Mark as in-progress
                # Forward Onshape's response to the client
                return _json_response(200, data) 
            except json.JSONDecodeError:
                return _json_response(500, {"error": "Failed to parse Onshape translation initiation response."})
        else:
            # Forward Onshape's error
            try:
                error_details = onshape_resp.json()
            except json.JSONDecodeError:
                error_details = {"error_text": onshape_resp.text[:200]} # Truncate if not JSON
            return _json_response(onshape_resp.status_code, {"error": "Failed to initiate GLTF translation.", "onshape_details": error_details})


    # /api/gltf/{tid} (GET) - get translation result
    # Path: /api/gltf/someTranslationId
    if path.startswith("/api/gltf/") and method == "GET" and len(path.split("/")) == 4:
        tid = path.split("/")[-1]
        
        # Check local store first (simplistic polling state)
        translation_status = in_memory_data_store.get(tid)
        if translation_status is None:
            # Could mean completed and cleared, or never existed, or instance restarted.
            # For robust polling, client should handle 404 from Onshape if we proceed.
            # Or, if we are sure it should exist, return 404 now.
            # Let's assume we try Onshape if not "in-progress".
            pass # Proceed to check Onshape directly
        elif translation_status == "in-progress":
            return _json_response(202, {"status": "Translation in progress."}) # Accepted, but not complete

        # Fetch translation status from Onshape
        onshape_status_endpoint = f"/translations/{tid}"
        onshape_status_resp = _onshape_api_request("GET", onshape_status_endpoint, incoming_headers=headers)

        if isinstance(onshape_status_resp, dict): # Error from helper
            return onshape_status_resp
        
        if onshape_status_resp.status_code != 200:
            return _json_response(onshape_status_resp.status_code, {"error": "Failed to get translation status from Onshape.", "details": onshape_status_resp.text[:200]})

        try:
            trans_json = onshape_status_resp.json()
        except json.JSONDecodeError:
            return _json_response(500, {"error": "Failed to parse Onshape translation status response."})

        request_state = trans_json.get("requestState")
        if request_state == "FAILED":
            in_memory_data_store.pop(tid, None) # Clear state
            return _json_response(500, {"error": "Onshape translation failed.", "reason": trans_json.get("failureReason", "Unknown")})
        elif request_state != "DONE": # e.g. ACTIVE, PENDING
            # Update local store if it was missing or stale
            in_memory_data_store[tid] = "in-progress" 
            return _json_response(202, {"status": f"Translation is {request_state.lower()}."})

        # Translation is DONE, fetch the actual GLTF data
        doc_id = trans_json.get("documentId")
        ext_id_list = trans_json.get("resultExternalDataIds") # This is a list
        
        if not doc_id or not ext_id_list or not ext_id_list[0]:
            return _json_response(500, {"error": "Translation result info missing from Onshape response."})
        
        ext_id = ext_id_list[0] # Assuming one result data ID

        # IMPORTANT: Fetching external data might not return JSON.
        # The _onshape_api_request helper sets "Accept: application/json".
        # This might be problematic for file downloads.
        # We need a way to make a request that accepts other content types.
        # For now, let's make a direct httpx call for this specific case.
        
        gltf_data_url = f"{ONSHAPE_API_URL}/documents/d/{doc_id}/externaldata/{ext_id}"
        
        # Prepare headers for GLTF data request (forward auth, but don't force Accept: application/json)
        gltf_req_headers = {}
        auth_h = headers.get("authorization")
        if auth_h: gltf_req_headers["Authorization"] = auth_h
        ua_h = headers.get("user-agent")
        if ua_h: gltf_req_headers["User-Agent"] = ua_h
        # Do NOT set Accept: application/json here

        try:
            gltf_data_resp = httpx.get(gltf_data_url, headers=gltf_req_headers)
            gltf_data_resp.raise_for_status() # Raise HTTPStatusError for bad responses (4xx or 5xx)
        except httpx.HTTPStatusError as e:
            in_memory_data_store.pop(tid, None) # Clear state on final failure
            return _json_response(e.response.status_code, {"error": f"Failed to download GLTF data from Onshape: {e.response.text[:200]}"})
        except httpx.RequestError as e:
            in_memory_data_store.pop(tid, None) # Clear state
            return _json_response(502, {"error": f"Network error downloading GLTF data: {str(e)}"})


        in_memory_data_store.pop(tid, None) # Clear from store after successful retrieval
        
        # Return raw GLTF content
        return _raw_response(
            gltf_data_resp.status_code,
            gltf_data_resp.content, # Use .content for binary/octet-stream
            gltf_data_resp.headers.get("content-type", "application/octet-stream")
        )

    # /api/event (POST) - receive event
    if path == "/api/event" and method == "POST":
        # Ensure parsed_body is used here
        if parsed_body and parsed_body.get("event") == "onshape.model.translation.complete":
            translation_id = parsed_body.get("translationId")
            if translation_id:
                # Mark as completed (or store webhookId if that's more useful)
                # Storing a simple "completed" status might be better than webhookId
                # if webhookId isn't directly used for fetching.
                in_memory_data_store[translation_id] = "completed_by_webhook" 
        return _json_response(200, {"status": "Webhook event received."})


    # Default: Not found
    return _json_response(404, {"error": "API endpoint not found."})
