import re
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from tenacity import retry, wait_fixed, stop_after_attempt
from config import SERVICE_ACCOUNT_FILE

SCOPES = ["https://www.googleapis.com/auth/drive"]

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return service

def extract_folder_id(url: str) -> str:
    pattern = r"/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    pattern = r"/folders/([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    pattern = r"id=([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def extract_file_id(url: str) -> str:
    pattern = r"/file/d/([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    pattern = r"id=([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def list_files_in_folder(folder_id: str) -> list:
    service = get_drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()
    return results.get("files", [])

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def copy_file(file_id: str, file_name: str, dest_folder_id: str) -> dict:
    service = get_drive_service()
    body = {"name": file_name, "parents": [dest_folder_id]}
    new_file = service.files().copy(
        fileId=file_id,
        body=body,
        supportsAllDrives=True
    ).execute()
    return new_file

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def delete_file(file_id: str) -> None:
    service = get_drive_service()
    service.files().delete(
        fileId=file_id,
        supportsAllDrives=True
    ).execute()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def set_file_permission(file_id: str, email: str, role: str) -> str:
    service = get_drive_service()
    permission_body = {
        "type": "user",
        "role": role,
        "emailAddress": email
    }
    result = service.permissions().create(
        fileId=file_id,
        body=permission_body,
        fields="id",
        supportsAllDrives=True
    ).execute()
    return result.get("id")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_file_hierarchy(file_id: str) -> str:
    service = get_drive_service()
    file = service.files().get(
        fileId=file_id,
        fields="id, name, parents, mimeType",
        supportsAllDrives=True
    ).execute()
    report = f"Object: {file.get('name')} (ID: {file.get('id')})\n"
    parents = file.get("parents", [])
    parent_chain = []
    while parents:
        parent_id = parents[0]
        parent = service.files().get(
            fileId=parent_id,
            fields="id, name, parents",
            supportsAllDrives=True
        ).execute()
        parent_chain.append(f"{parent.get('name')} (ID: {parent.get('id')})")
        parents = parent.get("parents", [])
    if parent_chain:
        report += "Parent hierarchy:\n" + " -> ".join(parent_chain) + "\n"
    else:
        report += "No parent hierarchy.\n"
    if file.get("mimeType") == "application/vnd.google-apps.folder":
        children = list_files_in_folder(file_id)
        if children:
            child_list = "\n".join([f"{c.get('name')} (ID: {c.get('id')})" for c in children])
            report += "Child files/folders:\n" + child_list
        else:
            report += "No child files/folders.\n"
    return report

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def find_folder(name: str, parent_id: str) -> str:
    service = get_drive_service()
    safe_name = name.replace("'", "\\'")
    query = f"name = '{safe_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(
         q=query,
         fields="files(id, name)",
         includeItemsFromAllDrives=True,
         supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    if files:
         return files[0]["id"]
    return None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def create_folder(name: str, parent_id: str) -> str:
    existing_folder_id = find_folder(name, parent_id)
    if existing_folder_id:
        return existing_folder_id
    service = get_drive_service()
    metadata = {
        "name": name,
        "parents": [parent_id],
        "mimeType": "application/vnd.google-apps.folder"
    }
    try:
        folder = service.files().create(
            body=metadata,
            fields="id",
            supportsAllDrives=True
        ).execute()
    except Exception as e:
        print("Folder creation error:", e)
        raise Exception(f"Error creating folder {name}: {e}")
    return folder.get("id")

def copy_new_items(src_id: str, dest_id: str, copied_map: dict, base_path="") -> dict:
    items = list_files_in_folder(src_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        current_name = item.get("name", "")
        current_id = item.get("id", "")
        current_mime = item.get("mimeType", "")
        current_path = f"{base_path}/{current_name}" if base_path else current_name
        if current_mime == "application/vnd.google-apps.folder":
            if current_path not in copied_map:
                new_folder_id = create_folder(current_name, dest_id)
                copied_map[current_path] = {"id": new_folder_id, "name": current_name}
            else:
                new_folder_id = copied_map[current_path]["id"]
            copy_new_items(current_id, new_folder_id, copied_map, current_path)
        else:
            if current_path not in copied_map:
                new_file = copy_file(current_id, current_name, dest_id)
                new_id = new_file.get("id")
                if not new_id:
                    raise Exception(f"No ID returned for file {current_name}")
                copied_map[current_path] = {"id": new_id, "name": current_name}
    return copied_map
