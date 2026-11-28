# Package exports for api server.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""FastAPI service package for the Qiang heritage question-answering application."""

from .server import app, start_server

__all__ = ['app', 'start_server']
