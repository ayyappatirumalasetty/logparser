import os
import sys
from pathlib import Path

# Ensure app package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_invalid_credentials():
    response = client.post("/api/auth/login", json={"username": "wronguser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert "Invalid username" in response.json()["detail"]

def test_login_valid_credentials():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["username"] == username
    return data["token"]

def test_protected_route_unauthorized():
    response = client.get("/api/auth/verify")
    assert response.status_code == 401

def test_protected_route_authorized():
    token = test_login_valid_credentials()
    response = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": os.getenv("ADMIN_USERNAME", "admin")}

if __name__ == "__main__":
    test_login_invalid_credentials()
    print("[PASS] test_login_invalid_credentials passed")
    test_login_valid_credentials()
    print("[PASS] test_login_valid_credentials passed")
    test_protected_route_unauthorized()
    print("[PASS] test_protected_route_unauthorized passed")
    test_protected_route_authorized()
    print("[PASS] test_protected_route_authorized passed")
    print("\nALL AUTH TESTS PASSED SUCCESSFULLY!")

