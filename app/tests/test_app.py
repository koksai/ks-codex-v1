from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app


def test_full_flow(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)

    res = client.post(
        "/register",
        data={"full_name": "Admin A", "username": "admin", "password": "1234", "role": "admin"},
        follow_redirects=False,
    )
    assert res.status_code == 303

    res = client.post("/login", data={"username": "admin", "password": "1234"}, follow_redirects=False)
    assert res.status_code == 303
    cookie = res.cookies.get("access_token")
    assert cookie

    headers = {"cookie": f"access_token={cookie}"}

    res = client.post(
        "/cases",
        headers=headers,
        data={
            "case_code": "C-001",
            "title": "ผู้ป่วยฉุกเฉิน",
            "description": "เจ็บหน้าอก",
            "reporter_name": "สมชาย",
            "status_value": "open",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303

    async def fake_line(_: str):
        return True, "ok"

    monkeypatch.setattr("app.main.send_line_group_message", fake_line)

    res = client.post(
        "/incidents",
        headers=headers,
        data={
            "title": "อุบัติเหตุรถชน",
            "details": "มีผู้บาดเจ็บ",
            "latitude": "13.7563",
            "longitude": "100.5018",
            "severity": "high",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200
    assert "เคสทั้งหมด" in res.text

    res = client.get("/reports", headers=headers)
    assert res.status_code == 200
    assert "ประวัติแจ้งเหตุ" in res.text

    app.dependency_overrides.clear()
