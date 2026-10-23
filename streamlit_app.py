
import streamlit as st
import os
import io
import time
from datetime import datetime

from huggingface_hub import InferenceClient

st.set_page_config(
    page_title="Studio AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================
# CONFIGURATION
# =====================================================
CHAT_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
VIDEO_MODEL = "Wan-AI/Wan2.2-TI2V-5B"

MAX_CHAT_MESSAGES = 30
MAX_IMAGES_PER_SESSION = 3
MAX_VIDEOS_PER_SESSION = 1

def get_token():
    token = os.environ.get("HF_TOKEN", "")
    try:
        token = st.secrets.get("HF_TOKEN", token)
    except Exception:
        pass
    return str(token).strip()

def get_client():
    token = get_token()
    if not token:
        raise RuntimeError(
            "API belum dikonfigurasi oleh pemilik aplikasi."
        )
    return InferenceClient(api_key=token, timeout=180)

def init_state():
    defaults = {
        "messages": [],
        "conversations": [],
        "gallery": [],
        "image_count": 0,
        "video_count": 0,
        "chat_count": 0,
        "current_chat": "Percakapan baru",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# =====================================================
# DESIGN
# =====================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp {
    background: #212121;
    color: #ececec;
    font-family: Inter, sans-serif;
}
[data-testid="stHeader"] {
    background: rgba(33,33,33,.95);
}
.block-container {
    max-width: 1050px;
    padding-top: 1.4rem;
    padding-bottom: 5rem;
}
[data-testid="stSidebar"] {
    background: #171717;
    border-right: 1px solid #303030;
}
[data-testid="stSidebar"] * {
    color: #ececec;
}
.stButton > button {
    border-radius: 12px;
    min-height: 42px;
    border: 1px solid #414141;
    background: #2c2c2c;
    color: #f5f5f5;
    font-weight: 600;
}
.stButton > button:hover {
    border-color: #8b8b8b;
    color: white;
    background: #383838;
}
div[data-testid="stChatMessage"] {
    border-radius: 15px;
    border: 0;
    padding: 14px 17px;
}
div[data-testid="stChatInput"] {
    border-color: #555;
}
div[data-testid="stChatInput"] textarea {
    color: #fff;
}
.hero {
    text-align: center;
    padding: 55px 10px 25px;
}
.hero h1 {
    font-size: clamp(30px,4vw,43px);
    font-weight: 800;
    letter-spacing: -1.4px;
    color: #fff;
}
.hero p {
    color: #a3a3a3;
    line-height: 1.8;
}
.pill {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 30px;
    background: #303030;
    border: 1px solid #454545;
    color: #d4d4d4;
    font-size: 12px;
}
.section-card {
    background: #292929;
    border: 1px solid #414141;
    border-radius: 16px;
    padding: 20px;
    min-height: 135px;
    margin-bottom: 10px;
}
.section-card h3 {
    font-size: 17px;
    color: white;
}
.section-card p {
    color: #b3b3b3;
    font-size: 13px;
    line-height: 1.7;
}
.footer {
    text-align: center;
    color: #777;
    font-size: 11px;
    padding: 25px 0;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.markdown("## ✨ Studio AI")
    st.caption("AI CREATIVE WORKSPACE")
    st.divider()

    if st.button("＋ Percakapan Baru", use_container_width=True):
        if st.session_state.messages:
            st.session_state.conversations.insert(
                0,
                {
                    "title": st.session_state.messages[0]["content"][:45],
                    "messages": st.session_state.messages.copy(),
                },
            )
        st.session_state.messages = []
        st.session_state.current_chat = "Percakapan baru"
        st.rerun()

    mode = st.radio(
        "Pilih mode",
        ["💬 Chat AI", "🖼️ Foto AI", "🎬 Video AI", "🗂️ Galeri"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("RIWAYAT CHAT")

    if st.session_state.conversations:
        for i, conv in enumerate(st.session_state.conversations[:8]):
            if st.button(
                "💬 " + conv["title"],
                key=f"history_{i}",
                use_container_width=True,
            ):
                st.session_state.messages = conv["messages"].copy()
                st.session_state.current_chat = conv["title"]
                st.rerun()
    else:
        st.caption("Percakapan akan muncul di sini.")

    st.divider()
    st.caption("Studio AI · Publik")
    st.caption("Setiap pengguna memiliki sesi tersendiri.")

# =====================================================
# CHAT AI
# =====================================================
if mode == "💬 Chat AI":

    if not st.session_state.messages:
        st.markdown("""
        <div class="hero">
            <span class="pill">✦ AI ASSISTANT</span>
            <h1>Apa yang ingin kamu buat?</h1>
            <p>
            Tanyakan apa saja, kembangkan ide, tulis konten,
            atau minta bantuan untuk proyek kreatif kamu.
            </p>
        </div>
        """, unsafe_allow_html=True)

        a, b, c = st.columns(3)
        with a:
            st.markdown("""
            <div class="section-card">
            <h3>💡 Ide Kreatif</h3>
            <p>Buat konsep iklan, cerita, slogan, dan ide konten.</p>
            </div>
            """, unsafe_allow_html=True)
        with b:
            st.markdown("""
            <div class="section-card">
            <h3>✍️ Asisten Menulis</h3>
            <p>Bantu menyusun teks, merangkum, dan memperbaiki tulisan.</p>
            </div>
            """, unsafe_allow_html=True)
        with c:
            st.markdown("""
            <div class="section-card">
            <h3>🎨 Studio Visual</h3>
            <p>Kembangkan prompt untuk gambar dan video AI.</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("### ✨ Studio AI")
        st.caption("Percakapan dengan AI")

    # Render history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "Tanyakan sesuatu kepada Studio AI...",
        max_chars=4000,
    )

    if prompt:
        if len(st.session_state.messages) >= MAX_CHAT_MESSAGES:
            st.warning(
                "Batas percakapan sesi ini tercapai. "
                "Mulai percakapan baru untuk melanjutkan."
            )
        else:
            st.session_state.messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                try:
                    client = get_client()

                    api_messages = [
                        {
                            "role": "system",
                            "content": (
                                "Kamu adalah Studio AI, asisten kreatif "
                                "yang ramah dan membantu. Jawab dalam "
                                "bahasa yang digunakan pengguna. "
                                "Berikan jawaban jelas, terstruktur, "
                                "dan jujur tentang keterbatasanmu."
                            ),
                        }
                    ]

                    api_messages.extend(
                        st.session_state.messages[-12:]
                    )

                    response = client.chat.completions.create(
                        model=CHAT_MODEL,
                        messages=api_messages,
                        max_tokens=1000,
                    )

                    answer = (
                        response.choices[0].message.content
                        or "Maaf, AI tidak menghasilkan jawaban."
                    )

                    st.markdown(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )
                    st.session_state.chat_count += 1

                    if st.session_state.current_chat == "Percakapan baru":
                        st.session_state.current_chat = prompt[:45]

                except Exception as e:
                    error = (
                        "Maaf, Chat AI belum dapat menjawab. "
                        "Periksa token, akses model, saldo API, "
                        "atau coba beberapa saat lagi.\n\n"
                        f"Detail: {str(e)[:500]}"
                    )
                    st.error(error)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error}
                    )

            st.rerun()

# =====================================================
# FOTO AI
# =====================================================
elif mode == "🖼️ Foto AI":
    st.markdown("## 🖼️ Buat Foto dengan AI")
    st.caption("Tuliskan ide kamu, lalu biarkan AI membuat gambarnya.")

    with st.form("image_generator"):
        prompt = st.text_area(
            "Deskripsi gambar",
            placeholder=(
                "Contoh: Foto produk kopi premium, gelas berembun, "
                "pencahayaan studio, latar elegan dan realistis..."
            ),
            height=140,
        )

        style = st.selectbox(
            "Gaya visual",
            [
                "Fotografi realistis",
                "Sinematik",
                "Iklan produk",
                "Ilustrasi digital",
                "Anime",
                "Fantasi",
            ],
        )

        ratio = st.selectbox(
            "Ukuran gambar",
            ["Persegi", "Portrait", "Landscape"],
        )

        generate = st.form_submit_button(
            "✨ Generate Foto",
            use_container_width=True,
        )

    if generate:
        if not get_token():
            st.error("API belum dikonfigurasi oleh pemilik aplikasi.")
        elif not prompt.strip():
            st.warning("Masukkan deskripsi gambar.")
        elif st.session_state.image_count >= MAX_IMAGES_PER_SESSION:
            st.warning(
                "Batas foto per sesi tercapai. "
                "Silakan coba lagi nanti."
            )
        else:
            style_prompts = {
                "Fotografi realistis": "photorealistic photography",
                "Sinematik": "cinematic lighting, film composition",
                "Iklan produk": "professional commercial product photography",
                "Ilustrasi digital": "high quality digital illustration",
                "Anime": "detailed high quality anime art",
                "Fantasi": "beautiful detailed fantasy art",
            }

            sizes = {
                "Persegi": (1024, 1024),
                "Portrait": (768, 1024),
                "Landscape": (1024, 768),
            }

            width, height = sizes[ratio]
            full_prompt = (
                f"{prompt}. {style_prompts[style]}. "
                "High quality, well composed."
            )

            with st.spinner("AI sedang membuat gambar..."):
                try:
                    client = get_client()
                    image = client.text_to_image(
                        full_prompt,
                        model=IMAGE_MODEL,
                        width=width,
                        height=height,
                    )

                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    data = output.getvalue()

                    st.image(data, use_container_width=True)
                    st.download_button(
                        "⬇️ Download PNG",
                        data=data,
                        file_name=f"studio_ai_{int(time.time())}.png",
                        mime="image/png",
                        use_container_width=True,
                    )

                    st.session_state.gallery.insert(0, {
                        "type": "Foto AI",
                        "prompt": prompt,
                        "data": data,
                        "mime": "image/png",
                        "filename": f"studio_ai_{int(time.time())}.png",
                    })
                    st.session_state.image_count += 1
                    st.success("Foto berhasil dibuat.")

                except Exception as e:
                    st.error(
                        "Generasi foto gagal. Periksa ketersediaan model, "
                        "provider, token, dan saldo API."
                    )
                    st.caption(str(e)[:700])

# =====================================================
# VIDEO AI
# =====================================================
elif mode == "🎬 Video AI":
    st.markdown("## 🎬 Buat Video dengan AI")
    st.caption("Buat adegan bergerak dari deskripsi teks.")

    with st.form("video_generator"):
        prompt = st.text_area(
            "Deskripsi video",
            placeholder=(
                "Contoh: Video iklan kopi, kamera perlahan mendekat, "
                "cahaya sore, embun di gelas, gaya sinematik."
            ),
            height=150,
        )

        camera = st.selectbox(
            "Gerakan kamera",
            [
                "Natural",
                "Perlahan mendekat",
                "Menjauh",
                "Bergerak menyamping",
                "Sinematik",
            ],
        )

        generate = st.form_submit_button(
            "🎬 Generate Video",
            use_container_width=True,
        )

    if generate:
        if not get_token():
            st.error("API belum dikonfigurasi oleh pemilik aplikasi.")
        elif not prompt.strip():
            st.warning("Masukkan deskripsi video.")
        elif st.session_state.video_count >= MAX_VIDEOS_PER_SESSION:
            st.warning(
                "Batas video per sesi tercapai. "
                "Silakan coba lagi nanti."
            )
        else:
            full_prompt = (
                f"{prompt}. Camera movement: {camera}. "
                "Smooth motion, coherent scene, high visual quality."
            )

            with st.spinner(
                "Video sedang diproses. Proses dapat memerlukan "
                "beberapa menit."
            ):
                try:
                    client = InferenceClient(
                        provider="fal-ai",
                        api_key=get_token(),
                        timeout=600,
                    )

                    result = client.text_to_video(
                        full_prompt,
                        model=VIDEO_MODEL,
                    )

                    if hasattr(result, "read"):
                        video_data = result.read()
                    elif isinstance(result, bytes):
                        video_data = result
                    else:
                        video_data = bytes(result)

                    if not video_data:
                        raise ValueError("Video kosong.")

                    filename = f"studio_video_{int(time.time())}.mp4"
                    st.video(video_data)

                    st.download_button(
                        "⬇️ Download MP4",
                        data=video_data,
                        file_name=filename,
                        mime="video/mp4",
                        use_container_width=True,
                    )

                    st.session_state.gallery.insert(0, {
                        "type": "Video AI",
                        "prompt": prompt,
                        "data": video_data,
                        "mime": "video/mp4",
                        "filename": filename,
                    })
                    st.session_state.video_count += 1
                    st.success("Video berhasil dibuat.")

                except Exception as e:
                    st.error(
                        "Generasi video gagal. Periksa akses fal-ai, "
                        "model, saldo, dan batas waktu provider."
                    )
                    st.caption(str(e)[:700])

# =====================================================
# GALERI
# =====================================================
elif mode == "🗂️ Galeri":
    st.markdown("## 🗂️ Galeri Karya")
    st.caption("Karya yang dibuat dalam sesi browser ini.")

    if not st.session_state.gallery:
        st.info("Belum ada karya. Mulai dari menu Foto AI atau Video AI.")
    else:
        for i, item in enumerate(st.session_state.gallery):
            with st.container(border=True):
                st.markdown(f"**{item['type']}**")
                st.caption(item["prompt"])

                if item["mime"].startswith("image/"):
                    st.image(item["data"], use_container_width=True)
                else:
                    st.video(item["data"])

                st.download_button(
                    "⬇️ Download",
                    data=item["data"],
                    file_name=item["filename"],
                    mime=item["mime"],
                    key=f"gallery_download_{i}",
                )

# =====================================================
# FOOTER
# =====================================================
st.markdown("""
<div class="footer">
STUDIO AI · AI CREATIVE WORKSPACE<br>
Powered by Streamlit and AI inference providers.
</div>
""", unsafe_allow_html=True)
