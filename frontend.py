import streamlit as st
import requests
import base64
import urllib.parse
import os  # For environment variables

st.set_page_config(page_title="Simple Social", layout="wide")

# ----------------- Configuration -----------------
# Use BACKEND_URL environment variable if set, otherwise default to local
BASE_URL = os.getenv("BACKEND_URL", "https://mysocialapp-eh6p.onrender.com")

# ----------------- Session State -----------------
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None
if 'refresh_feed' not in st.session_state:
    st.session_state.refresh_feed = True  # Initially load feed

# ----------------- Utility Functions -----------------
def get_headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def encode_text_for_overlay(text):
    if not text:
        return ""
    base64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    return urllib.parse.quote(base64_text)

def create_transformed_url(original_url, transformation_params="", caption=None):
    if caption:
        encoded_caption = encode_text_for_overlay(caption)
        text_overlay = f"l-text,ie-{encoded_caption},ly-N20,lx-20,fs-100,co-white,bg-000000A0,l-end"
        transformation_params = text_overlay

    if not transformation_params:
        return original_url

    parts = original_url.split("/")
    base_url = "/".join(parts[:4])
    file_path = "/".join(parts[4:])
    return f"{base_url}/tr:{transformation_params}/{file_path}"

# ----------------- Pages -----------------
def login_page():
    st.title("🚀 Welcome to Mediatube")
    email = st.text_input("Email:")
    password = st.text_input("Password:", type="password")

    if email and password:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                login_data = {"username": email, "password": password}
                try:
                    response = requests.post(f"{BASE_URL}/auth/jwt/login", data=login_data)
                    if response.status_code == 200:
                        token_data = response.json()
                        st.session_state.token = token_data["access_token"]

                        user_response = requests.get(f"{BASE_URL}/users/me", headers=get_headers())
                        if user_response.status_code == 200:
                            st.session_state.user = user_response.json()
                            st.session_state.refresh_feed = True
                            st.stop()
                        else:
                            st.error("Failed to get user info")
                    else:
                        st.error("Invalid email or password!")
                except requests.ConnectionError:
                    st.error(f"Cannot connect to backend at {BASE_URL}")

        with col2:
            if st.button("Sign Up", type="secondary", use_container_width=True):
                signup_data = {"email": email, "password": password}
                try:
                    response = requests.post(f"{BASE_URL}/auth/register", json=signup_data)
                    if response.status_code == 201:
                        st.success("Account created! You can now login.")
                        st.stop()
                    else:
                        error_detail = response.json().get("detail", "Registration failed")
                        st.error(f"Registration failed: {error_detail}")
                except requests.ConnectionError:
                    st.error(f"Cannot connect to backend at {BASE_URL}")
    else:
        st.info("Enter your email and password above")

def upload_page():
    st.title("📸 Share Something")
    uploaded_file = st.file_uploader(
        "Choose media",
        type=['png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov', 'mkv', 'webm']
    )
    caption = st.text_area("Caption:", placeholder="What's on your mind?")

    if uploaded_file and st.button("Share", type="primary"):
        with st.spinner("Uploading..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"caption": caption}
                response = requests.post(f"{BASE_URL}/upload", files=files, data=data, headers=get_headers())

                if response.status_code == 200:
                    st.success("Posted!")
                    st.session_state.refresh_feed = True
                    st.stop()
                else:
                    st.error("Upload failed!")
            except requests.ConnectionError:
                st.error(f"Cannot connect to backend at {BASE_URL}")

def feed_page():
    st.title("🏠 Feed")

    try:
        response = requests.get(f"{BASE_URL}/feed", headers=get_headers())
        if response.status_code == 200:
            posts = response.json()["posts"]
        else:
            st.error("Failed to load feed")
            return
    except requests.ConnectionError:
        st.error(f"Cannot connect to backend at {BASE_URL}")
        return

    if not posts:
        st.info("No posts yet! Be the first to share something.")
        return

    for post in posts:
        st.markdown("---")
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{post['email']}** • {post['created_at'][:10]}")
        with col2:
            if post.get('is_owner', False):
                if st.button("🗑️", key=f"delete_{post['id']}", help="Delete post"):
                    try:
                        resp = requests.delete(f"{BASE_URL}/posts/{post['id']}", headers=get_headers())
                        if resp.status_code == 200:
                            st.success("Post deleted!")
                            st.session_state.refresh_feed = True
                            st.stop()
                        else:
                            st.error("Failed to delete post!")
                    except requests.ConnectionError:
                        st.error(f"Cannot connect to backend at {BASE_URL}")

        caption = post.get('caption', '')
        if post['file_type'] == 'image':
            st.image(create_transformed_url(post['url'], "", caption), width=300)
        else:
            st.video(create_transformed_url(post['url'], "w-400,h-200,cm-pad_resize,bg-blurred"), width=300)
            st.caption(caption)
        st.markdown("")

# ----------------- Main App -----------------
if st.session_state.user is None:
    login_page()
else:
    st.sidebar.title(f"👋 Hi {st.session_state.user['email']}!")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.token = None
        st.session_state.refresh_feed = True
        st.stop()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate:", ["🏠 Feed", "📸 Upload"])
    if page == "🏠 Feed":
        feed_page()
    else:
        upload_page()
