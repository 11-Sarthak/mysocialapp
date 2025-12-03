import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import uuid

from app.db import Post, get_async_session, User, create_db_and_tables
from app.images import imagekit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from app.users import auth_backend, current_active_user, fastapi_users
from app.schemas import UserRead, UserCreate, UserUpdate

load_dotenv()

# ----------------- Async lifespan -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    await create_db_and_tables()
    yield

# ----------------- FastAPI app -----------------
app = FastAPI(
    lifespan=lifespan,
    title="My App",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ----------------- CORS -----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Streamlit, localhost, Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Auth routes -----------------
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

# ----------------- Home -----------------
@app.get("/")
@app.head("/")
def home():
    return {"message": "FastAPI is running!"}

# ----------------- Upload -----------------
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        upload_result = imagekit.upload_file(
            file=open(temp_file_path, 'rb'),
            file_name=file.filename,
            options=UploadFileRequestOptions(
                use_unique_file_name=True,
                tags=['backend-upload']
            )
        )

        if upload_result.response_metadata.http_status_code == 200:
            post = Post(
                user_id=str(user.id),
                caption=caption,
                url=upload_result.url,
                file_type='video' if file.content_type.startswith("video/") else 'image',
                file_name=upload_result.name
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        file.file.close()

# ----------------- Feed -----------------
@app.get("/feed")
async def get_feed(user: User = Depends(current_active_user), session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]

    result = await session.execute(select(User))
    users = [row[0] for row in result.all()]
    user_dict = {str(u.id): u.email for u in users}

    posts_data = []
    for p in posts:
        posts_data.append({
            "id": str(p.id),
            "user_id": str(p.user_id),
            "caption": p.caption,
            "url": p.url,
            "file_type": p.file_type,
            "file_name": p.file_name,
            "created_at": p.created_at.isoformat(),
            "is_owner": p.user_id == str(user.id),
            "email": user_dict.get(str(p.user_id), "Unknown")
        })

    return {"posts": posts_data}

# ----------------- Delete -----------------
@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, user: User = Depends(current_active_user),
                      session: AsyncSession = Depends(get_async_session)):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == str(post_uuid)))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="post not found")

        if post.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="do not have permission to delete this post")

        # Delete from ImageKit
        try:
            imagekit.delete_file(post.file_name)
        except Exception as e:
            print("Warning: could not delete file from ImageKit:", e)

        await session.delete(post)
        await session.commit()
        session.expire_all()

        return {"success": True, "message": "post deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
