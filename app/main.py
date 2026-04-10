from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .database import get_session, init_db
from .models import CaseRecord, Incident, Notification, User
from .security import create_token, decode_token, hash_password, verify_password
from .services import send_line_group_message

app = FastAPI(title="Rescue Command Center")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup() -> None:
    init_db()


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401)
    try:
        payload = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401) from exc

    username = payload.get("sub")
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=401)
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("officer"),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(full_name=full_name, username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()

    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.username)
    response = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    total_cases = len(session.exec(select(CaseRecord)).all())
    open_cases = len(session.exec(select(CaseRecord).where(CaseRecord.status == "open")).all())
    incidents_today = len(
        [x for x in session.exec(select(Incident)).all() if x.created_at.date() == datetime.utcnow().date()]
    )
    latest_notifications = (
        session.exec(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()[:8]
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "total_cases": total_cases,
            "open_cases": open_cases,
            "incidents_today": incidents_today,
            "notifications": latest_notifications,
        },
    )


@app.get("/cases", response_class=HTMLResponse)
def case_page(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    records = session.exec(select(CaseRecord).order_by(CaseRecord.created_at.desc())).all()
    return templates.TemplateResponse("cases.html", {"request": request, "user": user, "records": records})


@app.post("/cases")
def create_case(
    case_code: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    reporter_name: str = Form(...),
    status_value: str = Form("open"),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    exists = session.exec(select(CaseRecord).where(CaseRecord.case_code == case_code)).first()
    if exists:
        raise HTTPException(status_code=400, detail="Case code already exists")

    record = CaseRecord(
        case_code=case_code,
        title=title,
        description=description,
        reporter_name=reporter_name,
        status=status_value,
        created_by=user.id,
    )
    session.add(record)
    session.commit()
    return RedirectResponse("/cases", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/incidents", response_class=HTMLResponse)
def incident_page(request: Request, user: User = Depends(admin_only), session: Session = Depends(get_session)):
    incidents = session.exec(select(Incident).order_by(Incident.created_at.desc())).all()
    return templates.TemplateResponse("incidents.html", {"request": request, "user": user, "incidents": incidents})


@app.post("/incidents")
async def create_incident(
    title: str = Form(...),
    details: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    severity: str = Form("high"),
    user: User = Depends(admin_only),
    session: Session = Depends(get_session),
):
    incident = Incident(
        title=title,
        details=details,
        latitude=latitude,
        longitude=longitude,
        severity=severity,
        reported_by=user.id,
    )
    session.add(incident)
    session.commit()

    all_users = session.exec(select(User)).all()
    msg = f"แจ้งเหตุ: {title} | ระดับ: {severity} | พิกัด: {latitude},{longitude}"
    for target in all_users:
        session.add(Notification(user_id=target.id, message=msg, lat=latitude, lng=longitude))
    session.commit()

    await send_line_group_message(msg)
    return RedirectResponse("/incidents", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    case_status: Optional[str] = None,
):
    statement = select(CaseRecord).order_by(CaseRecord.created_at.desc())
    if case_status:
        statement = statement.where(CaseRecord.status == case_status)
    case_rows = session.exec(statement).all()
    incident_rows = session.exec(select(Incident).order_by(Incident.created_at.desc())).all()
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "user": user,
            "case_rows": case_rows,
            "incident_rows": incident_rows,
            "case_status": case_status,
        },
    )
