from fastapi import FastAPI
from .config import Settings
from .models import Display
from .provider import MockProvider
from .service import Service

def create_app(service=None):
    if service is None:
        settings = Settings.load()
        service = Service(settings.db, MockProvider(settings.scenario, settings), settings=settings)
    app = FastAPI(title="Flight Display POC", version="0.1.0")
    @app.get("/api/v1/display", response_model=Display)
    def display():
        return service.get()
    return app
