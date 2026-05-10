from fastapi import Request

from src.db.session import get_session


def get_trace_id(request: Request) -> str:
    return request.state.trace_id


def get_run_id(request: Request) -> str:
    return request.state.run_id


__all__ = ["get_session", "get_trace_id", "get_run_id"]
