"""Loopback-only calibration UI with server-side environment selection."""
from dataclasses import replace
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import secrets
import tempfile
import threading
import json
from datetime import datetime
from dotenv import set_key
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .config import Settings
from .provider import make_provider
from .service import Service

WEB = Path(__file__).resolve().parents[2] / "calibration"
FIELDS = {"latitude":"FLIGHT_CENTER_LAT", "longitude":"FLIGHT_CENTER_LON", "airport":"FLIGHT_AIRPORT", "radius_km":"FLIGHT_RADIUS_KM"}
class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, hide_input_in_errors=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    airport: str = Field(pattern=r"^[A-Z]{3}$")
    radius_km: float = Field(ge=0.5, le=500)
    revision: str = Field(min_length=16, max_length=128)

class ConfigFile:
    def __init__(self, path):
        self.path = Path(path).absolute()
        # Require a deliberately private destination; never edit a tracked example.
        if not (self.path.name == ".env" or self.path.name.startswith(".env.")) or self.path.name.endswith(".example"):
            raise ValueError("calibration requires a private .env destination")
        self.lock = threading.Lock()
        self.revision = secrets.token_urlsafe(24)
        self.fingerprint = self.digest()
        self.read()
    def digest(self):
        return hashlib.sha256(self.path.read_bytes()).digest() if self.path.exists() else None
    def read(self):
        return Settings.load(self.path)
    def snapshot(self):
        with self.lock:
            settings = self.read()
            fingerprint = self.digest()
            if fingerprint != self.fingerprint:
                self.fingerprint = fingerprint
                self.revision = secrets.token_urlsafe(24)
            return settings, self.revision
    def save(self, selection):
        with self.lock:
            if selection.revision != self.revision or self.digest() != self.fingerprint:
                raise HTTPException(409,"Configuration changed; reload before saving")
            current = self.read()  # includes owner-only/symlink validation
            replace(current, center_lat=selection.latitude, center_lon=selection.longitude,
                    airport=selection.airport, radius_km=selection.radius_km)
            self.path.parent.mkdir(parents=True,exist_ok=True)
            fd,name = tempfile.mkstemp(prefix=".env.calibration-",dir=self.path.parent)
            try:
                with os.fdopen(fd,"w") as f:
                    if self.path.exists(): f.write(self.path.read_text())
                for field,key in FIELDS.items():
                    set_key(name,key,str(getattr(selection,field)),quote_mode="always")
                os.chmod(name,0o600)
                # Fail closed if another process changed the file during editing.
                if self.digest() != self.fingerprint: raise HTTPException(409,"Configuration changed; reload before saving")
                os.replace(name,self.path)
            finally:
                Path(name).unlink(missing_ok=True)
            self.fingerprint = self.digest()
            self.revision = secrets.token_urlsafe(24)

def create_app(env_file=None):
    store = ConfigFile(env_file or os.getenv("FLIGHT_ENV_FILE", ".env"))
    token = secrets.token_urlsafe(32)
    settings = store.read()
    service = Service(settings.runtime_db, make_provider(settings), settings=settings) if settings.environment != "mock" else None
    app = FastAPI(title="Local calibration",docs_url=None,redoc_url=None,openapi_url=None)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback
        except (ValueError,AttributeError): local = False
        host = request.url.hostname
        origin = request.headers.get("origin")
        same_origin = not origin or origin == f"{request.url.scheme}://{request.url.netloc}"
        if not local or host not in {"localhost","127.0.0.1","::1"} or not same_origin or request.headers.get("sec-fetch-site") == "cross-site":
            response=JSONResponse({"detail":"Local same-origin access required"},status_code=403)
        elif request.method == "POST" and not hmac.compare_digest(request.headers.get("x-calibration-token",""),token):
            response=JSONResponse({"detail":"Invalid session token"},status_code=403)
        elif request.method == "POST" and (request.headers.get("content-type","").split(";")[0] != "application/json" or len(await request.body()) > 4096):
            response=JSONResponse({"detail":"Invalid request"},status_code=400)
        else:
            response=await call_next(request)
        response.headers.update({"Cache-Control":"no-store", "Referrer-Policy":"no-referrer",
            "X-Content-Type-Options":"nosniff", "X-Frame-Options":"DENY", "Permissions-Policy":"geolocation=(self)",
            "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({"detail":"Invalid calibration settings"},status_code=422)

    @app.get("/")
    def index(): return FileResponse(WEB/"index.html")

    @app.get("/assets/{name}")
    def asset(name: str):
        if name not in {"app.mjs","model.mjs","style.css"}: raise HTTPException(404)
        return FileResponse(WEB/name,media_type="text/css" if name.endswith(".css") else "text/javascript")

    @app.get("/api/config")
    def config():
        try: s,revision=store.snapshot()
        except (ValueError,OSError):raise HTTPException(503,"Private configuration unavailable") from None
        return {"latitude":s.center_lat,"longitude":s.center_lon,"airport":s.airport,"radius_km":s.radius_km,
                "revision":revision,"token":token,"mode":settings.environment,
                "environment_overrides":[key for key in FIELDS.values() if key in os.environ]}

    @app.post("/api/snapshot")
    def snapshot():
        if service is None:
            return {"mode":"mock", "status":"empty", "flights":[]}
        result = service.get()
        flights = []
        if result.observed_at and result.status in {"ok", "empty"}:
            slot = int(datetime.fromisoformat(result.observed_at).timestamp()) // 300
            with service.connect() as c:
                row = c.execute("SELECT payload FROM candidates WHERE slot=?", (slot,)).fetchone()
            if row:
                flights = json.loads(row[0])
        return {"mode":settings.environment, "status":result.status, "flights":flights,
                "observed_at":result.observed_at, "next_poll_at":result.next_poll_at,
                "retry_after_s":result.retry_after_s}

    @app.post("/api/config")
    def save(selection: Selection):
        try: store.save(selection)
        except (ValueError,OSError):raise HTTPException(503,"Could not save private configuration") from None
        return {"saved":True,"revision":store.revision,"restart_required":True,
                "environment_overrides":[key for key in FIELDS.values() if key in os.environ]}
    return app
