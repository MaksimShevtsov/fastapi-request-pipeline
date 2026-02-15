"""
Real-world application example.

Demonstrates:
- Complete blog API with authentication, permissions, rate limiting
- Multiple routers with different flows
- Pagination and filtering
- Custom components for real use cases
"""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, FastAPI

from fastapi_request_pipeline import (
    AllowAnonymous,
    ComponentCategory,
    Flow,
    FlowComponent,
    HasPermission,
    HasRole,
    JWTAuthentication,
    LimitOffset,
    OverrideFlow,
    QueryFilter,
    RateLimit,
    RequestContext,
    enrich_openapi,
    flow_dependency,
    merge_flows,
)

# ========== Domain Models ==========


@dataclass
class User:
    """User model."""

    id: int
    username: str
    email: str
    role: str
    permissions: list[str]


@dataclass
class Post:
    """Blog post model."""

    id: int
    title: str
    content: str
    author_id: int
    status: str
    created_at: str


# ========== Mock Database ==========

USERS_DB = {
    "admin": User(
        id=1,
        username="admin",
        email="admin@example.com",
        role="admin",
        permissions=["posts:read", "posts:write", "posts:delete", "users:manage"],
    ),
    "author": User(
        id=2,
        username="author",
        email="author@example.com",
        role="author",
        permissions=["posts:read", "posts:write"],
    ),
    "reader": User(
        id=3,
        username="reader",
        email="reader@example.com",
        role="reader",
        permissions=["posts:read"],
    ),
}

POSTS_DB = [
    Post(1, "First Post", "Content 1", 2, "published", "2024-01-01"),
    Post(2, "Draft Post", "Content 2", 2, "draft", "2024-01-02"),
    Post(3, "Second Post", "Content 3", 1, "published", "2024-01-03"),
]


# ========== Authentication ==========


async def decode_jwt(token: str) -> User:
    """Decode JWT and return user."""
    # Mock: token is username
    user = USERS_DB.get(token)
    if not user:
        raise ValueError("Invalid token")
    return user


# ========== Custom Components ==========


class OwnershipCheck(FlowComponent):
    """Check if user owns the resource."""

    category = ComponentCategory.PERMISSION

    def __init__(self, resource_type: str):
        self.resource_type = resource_type

    async def resolve(self, ctx: RequestContext) -> None:
        """Check ownership."""
        # Store for later use in endpoint
        ctx.state["ownership_required"] = self.resource_type


class CacheControl(FlowComponent):
    """Add cache control to public endpoints."""

    category = ComponentCategory.CUSTOM

    def __init__(self, max_age: int):
        self.max_age = max_age

    async def resolve(self, ctx: RequestContext) -> None:
        """Set cache control."""
        ctx.state["cache_control"] = f"public, max-age={self.max_age}"


# ========== Application Setup ==========

app = FastAPI(
    title="Blog API",
    description=(
        "A complete blog API with authentication, permissions, and rate limiting"
    ),
    version="1.0.0",
)

# Application-level flow: all endpoints require auth and basic rate limit
app_flow = Flow(
    JWTAuthentication(decode=decode_jwt), RateLimit(rate=100, window_seconds=60)
)


# ========== Public Router ==========
# Public endpoints - no authentication required

public_router = APIRouter(prefix="/public", tags=["Public"])
public_flow = Flow(
    OverrideFlow(AllowAnonymous()),
    CacheControl(max_age=300),
    RateLimit(rate=50, window_seconds=60),  # Stricter limit for public
)


@public_router.get("/posts")
async def list_public_posts(
    ctx: RequestContext = Depends(
        flow_dependency(
            merge_flows(
                app_flow,
                public_flow,
                Flow(
                    QueryFilter(allowed_fields={"status"}),
                    LimitOffset(default_limit=10, max_limit=50),
                ),
            )
        )
    ),
):
    """List published posts (public access)."""
    # Apply filters
    posts = [p for p in POSTS_DB if p.status == "published"]

    # Apply pagination
    offset = ctx.state.get("offset", 0)
    limit = ctx.state.get("limit", 10)
    paginated = posts[offset : offset + limit]

    return {
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "author_id": p.author_id,
                "created_at": p.created_at,
            }
            for p in paginated
        ],
        "total": len(posts),
        "offset": offset,
        "limit": limit,
        "cache_control": ctx.state.get("cache_control"),
    }


@public_router.get("/posts/{post_id}")
async def get_public_post(
    post_id: int,
    ctx: RequestContext = Depends(flow_dependency(merge_flows(app_flow, public_flow))),
):
    """Get published post by ID."""
    post = next(
        (p for p in POSTS_DB if p.id == post_id and p.status == "published"), None
    )
    if not post:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Post not found")

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author_id": post.author_id,
        "created_at": post.created_at,
    }


app.include_router(public_router)


# ========== Posts Router ==========
# Authenticated post management

posts_router = APIRouter(prefix="/posts", tags=["Posts"])


@posts_router.get("/")
async def list_posts(
    ctx: RequestContext = Depends(
        flow_dependency(
            merge_flows(
                app_flow,
                Flow(
                    HasPermission("posts:read"),
                    QueryFilter(allowed_fields={"status", "author_id"}),
                    LimitOffset(default_limit=20, max_limit=100),
                ),
            )
        )
    ),
):
    """List all posts (authenticated users see drafts too)."""
    posts = POSTS_DB

    # Apply filters
    filters = ctx.state.get("filters", [])
    for f in filters:
        if f["field"] == "status":
            posts = [p for p in posts if p.status == f["value"]]
        elif f["field"] == "author_id":
            posts = [p for p in posts if p.author_id == int(f["value"])]

    # Apply pagination
    offset = ctx.state.get("offset", 0)
    limit = ctx.state.get("limit", 20)
    paginated = posts[offset : offset + limit]

    return {
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "content": p.content[:100] + "...",
                "author_id": p.author_id,
                "status": p.status,
                "created_at": p.created_at,
            }
            for p in paginated
        ],
        "total": len(posts),
        "offset": offset,
        "limit": limit,
    }


@posts_router.post("/")
async def create_post(
    title: str,
    content: str,
    ctx: RequestContext = Depends(
        flow_dependency(
            merge_flows(
                app_flow,
                Flow(
                    HasPermission("posts:write"),
                    RateLimit(rate=10, window_seconds=60),  # Limit post creation
                ),
            )
        )
    ),
):
    """Create a new post."""
    user: User = ctx.user
    new_post = Post(
        id=len(POSTS_DB) + 1,
        title=title,
        content=content,
        author_id=user.id,
        status="draft",
        created_at="2024-01-04",
    )
    POSTS_DB.append(new_post)

    return {"post": new_post, "created_by": user.username}


@posts_router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, Flow(HasPermission("posts:delete"))))
    ),
):
    """Delete a post (admin or post owner)."""
    user: User = ctx.user
    post = next((p for p in POSTS_DB if p.id == post_id), None)

    if not post:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Post not found")

    # Check ownership (unless admin)
    if user.role != "admin" and post.author_id != user.id:
        from fastapi_request_pipeline import PermissionDenied

        raise PermissionDenied("Can only delete your own posts")

    POSTS_DB.remove(post)
    return {"message": "Post deleted", "deleted_by": user.username}


app.include_router(posts_router)


# ========== Admin Router ==========
# Admin-only endpoints

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
admin_flow = Flow(HasRole("admin"))


@admin_router.get("/users")
async def list_users(
    ctx: RequestContext = Depends(flow_dependency(merge_flows(app_flow, admin_flow))),
):
    """List all users (admin only)."""
    return {
        "users": [
            {"id": u.id, "username": u.username, "email": u.email, "role": u.role}
            for u in USERS_DB.values()
        ]
    }


@admin_router.get("/stats")
async def get_stats(
    ctx: RequestContext = Depends(flow_dependency(merge_flows(app_flow, admin_flow))),
):
    """Get platform statistics (admin only)."""
    return {
        "total_users": len(USERS_DB),
        "total_posts": len(POSTS_DB),
        "published_posts": len([p for p in POSTS_DB if p.status == "published"]),
        "draft_posts": len([p for p in POSTS_DB if p.status == "draft"]),
    }


app.include_router(admin_router)


# ========== User Router ==========
# User account management

user_router = APIRouter(prefix="/me", tags=["Account"])


@user_router.get("/")
async def get_profile(ctx: RequestContext = Depends(flow_dependency(app_flow))):
    """Get current user profile."""
    user: User = ctx.user
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "permissions": user.permissions,
    }


@user_router.get("/posts")
async def get_my_posts(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, Flow(LimitOffset(default_limit=10))))
    ),
):
    """Get current user's posts."""
    user: User = ctx.user
    posts = [p for p in POSTS_DB if p.author_id == user.id]

    offset = ctx.state.get("offset", 0)
    limit = ctx.state.get("limit", 10)
    paginated = posts[offset : offset + limit]

    return {"posts": paginated, "total": len(posts), "offset": offset, "limit": limit}


app.include_router(user_router)


# Enrich OpenAPI documentation
enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # Public endpoints:
    #   curl http://localhost:8000/public/posts
    #   curl http://localhost:8000/public/posts?limit=5&offset=0
    #   curl http://localhost:8000/public/posts/1
    #
    # Authenticated posts:
    #   curl -H "Authorization: Bearer author" http://localhost:8000/posts/
    #   curl -H "Authorization: Bearer author" "http://localhost:8000/posts/?status=draft"
    #   curl -X POST -H "Authorization: Bearer author" \
    #     "http://localhost:8000/posts/?title=New Post&content=Content here"
    #
    # Admin:
    #   curl -H "Authorization: Bearer admin" http://localhost:8000/admin/users
    #   curl -H "Authorization: Bearer admin" http://localhost:8000/admin/stats
    #   curl -H "Authorization: Bearer reader" http://localhost:8000/admin/stats  # 403
    #
    # User profile:
    #   curl -H "Authorization: Bearer author" http://localhost:8000/me/
    #   curl -H "Authorization: Bearer author" http://localhost:8000/me/posts
    #
    # Delete post:
    #   curl -X DELETE -H "Authorization: Bearer author" http://localhost:8000/posts/1
    #   curl -X DELETE -H "Authorization: Bearer admin" http://localhost:8000/posts/1
