"""ASGI entry point:  uvicorn hq.main:app  (or: python -m hq)"""
from hq.api.app import create_app

app = create_app()
