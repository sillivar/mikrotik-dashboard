import os
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import get_current_user, create_access_token, verify_token
from app.database import init_db, get_all_routers, get_router_by_id, add_router, delete_router
from app.mikrotik_client import MikroTikClient

app = FastAPI(title="MikroTik Router Dashboard", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()

class LoginPayload(BaseModel):
    username: str
    password: str

class RouterPayload(BaseModel):
    name: str = Field(..., min_length=1)
    host: str = Field(..., min_length=1)
    port: int = Field(..., gt=0)
    connection_type: str = Field("rest")
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    snmp_community: str = Field("public")
    snmp_port: int = Field(161, gt=0)

@app.post("/api/auth/login")
async def login(response: Response, payload: LoginPayload):
    eu, ep = os.getenv("APP_USER", "admin"), os.getenv("APP_PASSWORD", "admin123")
    if payload.username == eu and payload.password == ep:
        t = create_access_token({"sub": payload.username})
        response.set_cookie("session_token", t, httponly=True, max_age=86400, expires=86400, samesite="lax")
        return {"status": "success", "username": payload.username}
    raise HTTPException(401, "Incorrect username or password")

@app.get("/api/auth/me")
async def me(user: str = Depends(get_current_user)):
    return {"username": user}

@app.get("/logout")
async def logout(response: Response):
    res = RedirectResponse("/login", status_code=303)
    res.delete_cookie("session_token")
    return res

def _serve_page(filename: str) -> HTMLResponse:
    path = os.path.join("app", "static", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(f"{filename} not found", status_code=404)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    t = request.cookies.get("session_token")
    if t and verify_token(t):
        return RedirectResponse("/", status_code=303)
    return _serve_page("login.html")

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    t = request.cookies.get("session_token")
    if not t or verify_token(t) != os.getenv("APP_USER", "admin"):
        return RedirectResponse("/login", status_code=303)
    return _serve_page("index.html")

@app.get("/api/routers")
async def list_routers(user: str = Depends(get_current_user)):
    return get_all_routers()

@app.post("/api/routers")
async def create_router(p: RouterPayload, user: str = Depends(get_current_user)):
    client = MikroTikClient(p.host, p.port, p.username, p.password, p.connection_type, p.snmp_community, p.snmp_port)
    try:
        await client.test_connection()
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Connection failed", "detail": str(e)})
    try:
        rid = add_router(p.name, p.host, p.port, p.connection_type, p.username, p.password, p.snmp_community, p.snmp_port)
        return {
            "id": rid, "name": p.name, "host": p.host, "port": p.port,
            "connection_type": p.connection_type, "username": p.username,
            "snmp_community": p.snmp_community, "snmp_port": p.snmp_port
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to save: {str(e)}")

@app.delete("/api/routers/{rid}")
async def remove_router(rid: int, user: str = Depends(get_current_user)):
    if not delete_router(rid):
        raise HTTPException(404, "Router not found")
    return {"status": "deleted", "id": rid}

async def _get_client(rid: int) -> MikroTikClient:
    r = get_router_by_id(rid)
    if not r:
        raise HTTPException(404, "Router not found")
    return MikroTikClient(r["host"], r["port"], r["username"], r["password"], r["connection_type"], r["snmp_community"], r["snmp_port"])

@app.get("/api/routers/{rid}/info")
async def router_info(rid: int, user: str = Depends(get_current_user)):
    c = await _get_client(rid)
    try:
        return await c.get_system_info()
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch system info", "detail": str(e)})

@app.get("/api/routers/{rid}/updates")
async def router_updates(rid: int, user: str = Depends(get_current_user)):
    c = await _get_client(rid)
    try:
        return await c.get_updates()
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch updates", "detail": str(e)})

@app.get("/api/routers/{rid}/ntp")
async def router_ntp(rid: int, user: str = Depends(get_current_user)):
    c = await _get_client(rid)
    try:
        return await c.get_ntp()
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch NTP status", "detail": str(e)})

@app.get("/api/routers/{rid}/snmp")
async def router_snmp(rid: int, user: str = Depends(get_current_user)):
    c = await _get_client(rid)
    try:
        return await c.get_snmp_stats()
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "Failed to fetch SNMP stats", "detail": str(e)})

# Mount /static for index.html assets (must make directory if it doesn't exist)
os.makedirs(os.path.join("app", "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

