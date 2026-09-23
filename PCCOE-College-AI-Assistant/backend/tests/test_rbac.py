import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import timedelta

from app.main import app
from app.models.enums import RoleEnum
from app.api.deps import require_roles, get_current_user
from app.core.security import create_access_token

# Add test endpoints directly to the app for testing RBAC
@app.get("/api/v1/test/admin", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def admin_endpoint():
    return {"message": "Admin access"}

@app.get("/api/v1/test/authenticated", dependencies=[Depends(get_current_user)])
def authenticated_endpoint():
    return {"message": "Authenticated access"}

client = TestClient(app)

def create_test_token(user_id: int, role: RoleEnum) -> str:
    return create_access_token(subject=user_id, role=role.value)

@pytest.fixture
def mock_users(mocker):
    # Mock get_current_user logic so we don't need real DB users for RBAC testing
    # We just mock the DB query part inside get_current_user
    # Actually, simpler is to just override the get_current_user dependency
    pass

# We will override the `get_current_user` dependency for different tests
def override_get_current_user_admin():
    from app.models.user import User
    return User(id=1, email="admin@test.com", role=RoleEnum.ADMIN, is_active=True)

def override_get_current_user_faculty():
    from app.models.user import User
    return User(id=2, email="faculty@test.com", role=RoleEnum.FACULTY, is_active=True)

def override_get_current_user_staff():
    from app.models.user import User
    return User(id=3, email="staff@test.com", role=RoleEnum.STAFF, is_active=True)


def test_unauthenticated_user_receives_401():
    response = client.get("/api/v1/test/admin")
    assert response.status_code in (401, 403)
    
    response = client.get("/api/v1/test/authenticated")
    assert response.status_code in (401, 403)


def test_admin_can_access_admin_endpoint():
    app.dependency_overrides[get_current_user] = override_get_current_user_admin
    response = client.get("/api/v1/test/admin")
    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_faculty_cannot_access_admin_endpoint():
    app.dependency_overrides[get_current_user] = override_get_current_user_faculty
    response = client.get("/api/v1/test/admin")
    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_staff_cannot_access_admin_endpoint():
    app.dependency_overrides[get_current_user] = override_get_current_user_staff
    response = client.get("/api/v1/test/admin")
    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_normal_authenticated_endpoint_accessible_to_faculty():
    app.dependency_overrides[get_current_user] = override_get_current_user_faculty
    response = client.get("/api/v1/test/authenticated")
    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_normal_authenticated_endpoint_accessible_to_staff():
    app.dependency_overrides[get_current_user] = override_get_current_user_staff
    response = client.get("/api/v1/test/authenticated")
    assert response.status_code == 200
    app.dependency_overrides.clear()

