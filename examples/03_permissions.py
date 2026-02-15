"""
Permission and authorization examples.

Demonstrates:
- Role-based access control (RBAC)
- Permission checks
- Combining authentication with permissions
"""

from typing import Any

from fastapi import Depends, FastAPI

from fastapi_request_pipeline import (
    Authenticated,
    Flow,
    HasPermission,
    HasRole,
    JWTAuthentication,
    RequestContext,
    enrich_openapi,
    flow_dependency,
)

app = FastAPI(title="Permission Examples")


# Mock user database
USERS = {
    "admin-token": {
        "sub": "admin",
        "role": "admin",
        "permissions": ["read", "write", "delete"],
    },
    "user-token": {"sub": "user", "role": "user", "permissions": ["read", "write"]},
    "readonly-token": {"sub": "readonly", "role": "viewer", "permissions": ["read"]},
}


async def decode_jwt(token: str) -> dict[str, Any]:
    """Decode JWT and return user with role and permissions."""
    if token in USERS:
        return USERS[token]
    raise ValueError("Invalid token")


# Basic authentication check - just verify user exists
auth_only_flow = Flow(JWTAuthentication(decode=decode_jwt), Authenticated())


@app.get("/authenticated")
async def authenticated_endpoint(
    ctx: RequestContext = Depends(flow_dependency(auth_only_flow)),
):
    """Requires authentication but no specific role or permission."""
    return {
        "message": "You are authenticated",
        "user": ctx.user["sub"],
        "role": ctx.user["role"],
    }


# Role-based access control
admin_flow = Flow(JWTAuthentication(decode=decode_jwt), HasRole("admin"))


@app.get("/admin")
async def admin_endpoint(ctx: RequestContext = Depends(flow_dependency(admin_flow))):
    """Admin-only endpoint."""
    return {"message": "Admin access granted", "user": ctx.user["sub"]}


user_or_admin_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("user"),  # Note: in production, you'd want OR logic for multiple roles
)


@app.get("/users")
async def users_endpoint(
    ctx: RequestContext = Depends(flow_dependency(user_or_admin_flow)),
):
    """User or admin access."""
    return {
        "message": "User access granted",
        "user": ctx.user["sub"],
        "role": ctx.user["role"],
    }


# Permission-based access control
write_flow = Flow(JWTAuthentication(decode=decode_jwt), HasPermission("write"))


@app.post("/posts")
async def create_post(ctx: RequestContext = Depends(flow_dependency(write_flow))):
    """Requires 'write' permission."""
    return {
        "message": "Post created",
        "author": ctx.user["sub"],
        "permissions": ctx.user["permissions"],
    }


delete_flow = Flow(JWTAuthentication(decode=decode_jwt), HasPermission("delete"))


@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: int, ctx: RequestContext = Depends(flow_dependency(delete_flow))
):
    """Requires 'delete' permission."""
    return {"message": f"Post {post_id} deleted", "deleted_by": ctx.user["sub"]}


read_flow = Flow(JWTAuthentication(decode=decode_jwt), HasPermission("read"))


@app.get("/posts")
async def list_posts(ctx: RequestContext = Depends(flow_dependency(read_flow))):
    """Requires 'read' permission (everyone has it)."""
    return {
        "message": "Posts list",
        "user": ctx.user["sub"],
        "can_write": "write" in ctx.user["permissions"],
        "can_delete": "delete" in ctx.user["permissions"],
    }


enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # Admin only:
    #   curl -H "Authorization: Bearer admin-token" http://localhost:8000/admin
    #   curl -H "Authorization: Bearer user-token" http://localhost:8000/admin  # 403
    #
    # Write permission:
    #   curl -X POST -H "Authorization: Bearer user-token" http://localhost:8000/posts
    #   curl -X POST -H "Authorization: Bearer readonly-token" \
    #     http://localhost:8000/posts  # 403
    #
    # Delete permission:
    #   curl -X DELETE -H "Authorization: Bearer admin-token" \
    #     http://localhost:8000/posts/1
    #   curl -X DELETE -H "Authorization: Bearer user-token" \
    #     http://localhost:8000/posts/1  # 403
    #
    # Read permission:
    #   curl -H "Authorization: Bearer readonly-token" http://localhost:8000/posts
