"""
Security Middleware
Implements various security measures for FastAPI application
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import status
import os
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS - only in production with HTTPS
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit the size of incoming requests to prevent memory exhaustion attacks
    """

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": f"Request body too large. Maximum size: {self.max_request_size / 1024 / 1024:.1f}MB"
                    }
                )

        response = await call_next(request)
        return response


class SecureErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Prevent internal error details from leaking to users
    Logs detailed errors internally
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log detailed error internally
            logger.error(
                f"Unhandled exception: {type(e).__name__}: {str(e)}",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown"
                },
                exc_info=True
            )

            # Return generic error to user
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An internal error occurred. Please contact support if the problem persists.",
                    "error_id": f"{type(e).__name__}",  # Generic error type only
                }
            )


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests with IP address and user agent for audit trail
    """

    async def dispatch(self, request: Request, call_next):
        # Extract client information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        path = request.url.path
        method = request.method

        # Log request
        logger.info(
            f"Request: {method} {path}",
            extra={
                "client_ip": client_ip,
                "user_agent": user_agent,
                "method": method,
                "path": path,
            }
        )

        # Process request
        response = await call_next(request)

        # Log response
        logger.info(
            f"Response: {method} {path} -> {response.status_code}",
            extra={
                "client_ip": client_ip,
                "status_code": response.status_code,
                "method": method,
                "path": path,
            }
        )

        return response
