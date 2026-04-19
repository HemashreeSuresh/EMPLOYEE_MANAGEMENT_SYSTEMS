"""Vercel serverless handler for Flask app."""

import sys
import os

# Add backend to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import app

# Export the app for Vercel
export_app = app

# Vercel will call this handler
def handler(request):
    """Handler for Vercel serverless function."""
    with app.app_context():
        return app.wsgi_app(environ=request.environ, start_response=request.start_response)
