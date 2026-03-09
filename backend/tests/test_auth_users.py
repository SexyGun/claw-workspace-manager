from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login


def test_admin_can_manage_users(client: TestClient):
    login(client, "admin", "admin-password")

    create_response = client.post(
        "/api/users",
        json={"username": "alice", "password": "alice-password", "role": "user", "is_active": True},
    )
    assert create_response.status_code == 201, create_response.text
    user_id = create_response.json()["id"]

    list_response = client.get("/api/users")
    assert list_response.status_code == 200
    usernames = {user["username"] for user in list_response.json()}
    assert {"admin", "alice"} <= usernames

    patch_response = client.patch(f"/api/users/{user_id}", json={"is_active": False})
    assert patch_response.status_code == 200
    assert patch_response.json()["is_active"] is False

    reset_response = client.post(f"/api/users/{user_id}/reset-password", json={"password": "new-password-1"})
    assert reset_response.status_code == 200
