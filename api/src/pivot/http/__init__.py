"""Thin HTTP assembly for liveness and readiness. No /api/v1 business routes."""

from pivot.http.app import create_app

__all__ = ["create_app"]
