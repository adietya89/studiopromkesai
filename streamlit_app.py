import os
import io
import time
from datetime import datetime

import streamlit as st
from PIL import Image

# Optional API clients are imported only when available; requirements.txt installs them.
try:
    from google import genai
except Exception:
    genai = None

try:
    from groq import Groq
except Exception:
    Groq = None


# =========================================================
# KONFIGURASI APLIKASI
# =========================================================
st.set_page_config(
    page_title="Studio Promkes AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "Studio Promkes AI"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp {
        background:
          radial-gradient(circle at 5% 0%, rgba(13, 148, 136, .10), transparent 28%),
          radial-gradient(circle at 95% 8%, rgba(59, 130, 246, .10), transparent 30%),
          #f7fafc;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #073b4c 0%, #075985 55%, #0f766e 100%);
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .hero {
        padding: 1.4rem 1.6rem;
        border-radius: 22px;
        background: linear-gradient(120deg, #075985, #0f766e);
        color: white;
        box-shadow: 0 12px 28px rgba(7, 89, 133, .16);
        margin-bottom: 1rem;
    }
    .hero h1 { color: white; margin: 0 0 .35rem 0; font-size: 2rem; }
    .hero p { color: #e0f2fe; margin: 0; font-size: 1rem; }
    .feature-card {
        padding: 1rem;
        border-radius: 16px;
        background: white;
        border: 1px solid #dbeafe;
        box-shadow: 0 4px 14px rgba(15, 23, 42, .04);
        min-height: 125px;
    }
    .small-note { color: #475569; font-size: .9rem; }
    .stButton > button {
        border-radius: 11px;
        font-weight: 650;
        min-height: 2.65rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_secret(name: str, default: str = "") -> str:
    """Read Streamlit secrets first, then environment variables."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or os.getenv(name, default) or "").strip()


def get_gemini_client():
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None
