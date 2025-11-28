from imagekitio import ImageKit
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

PUBLIC_KEY = os.getenv("IMAGEKIT_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("IMAGEKIT_PRIVATE_KEY")
URL_ENDPOINT = os.getenv("IMAGEKIT_URL_ENDPOINT")  # Make sure your .env has this exact name

imagekit = ImageKit(
    public_key=PUBLIC_KEY,
    private_key=PRIVATE_KEY,
    url_endpoint=URL_ENDPOINT
)
