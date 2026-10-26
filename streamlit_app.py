
import os
import io
import json
import base64
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

# AI providers bersifat opsional agar dashboard tetap bisa dibuka
# walaupun paket atau API key AI belum tersedia.
try:
    from google import genai
except ImportError:
    genai = None

try:
    from groq import Groq
except ImportError:
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
PAGES = [
    "🏠 Dashboard",
    "💬 Chat AI",
    "🖼️ Foto AI",
    "🎬 Video AI",
    "🗂️ Galeri",
]

GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
IMAGE_MODEL_DEFAULT = "gemini-nano-banana-2.1"


# =========================================================
# DESAIN DASHBOARD
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background:
          radial-gradient(circle at 0% 0%, #d9f5ef 0%, transparent 28%),
          radial-gradient(circle at 100% 0%, #dbeafe 0%, transparent 30%),
          #f6f9fc;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #073b4c, #075985, #0f766e);
    }

    [data-testid="stSidebar"] * {
        color: white;
    }

    .hero {
        background: linear-gradient(120deg, #075985, #0f766e);
        padding: 28px;
        border-radius: 20px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(7, 89, 133, 0.16);
    }

    .hero h1 {
        color: white;
        margin-bottom: 8px;
    }

    .hero p {
        color: #e0f2fe;
        font-size: 16px;
        margin-bottom: 0;
    }

    .feature-card {
        background: white;
        border: 1px solid #dbeafe;
        border-radius: 17px;
        padding: 20px;
        min-height: 145px;
        box-shadow: 0 5px 18px rgba(15, 23, 42, 0.06);
    }

    .feature-card h3 {
        color: #075985;
    }

    .stButton > button {
        border-radius: 11px;
        font-weight: 600;
        min-height: 42px;
    }

    h1, h2, h3 {
        color: #123047;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HELPER API KEY
# =========================================================
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = os.getenv(name, default)

    return str(value or "").strip()


def get_ai_status():
    return {
        "Gemini": bool(get_secret("GEMINI_API_KEY")),
        "Groq": bool(get_secret("GROQ_API_KEY")),
    }


# =========================================================
# FUNGSI CHAT AI
# =========================================================
SYSTEM_PROMPT = """
Kamu adalah asisten Studio Promkes AI untuk promosi kesehatan
masyarakat Indonesia.

Gunakan Bahasa Indonesia yang jelas, ramah, praktis, dan mudah
dipahami. Bantu membuat materi edukasi, naskah penyuluhan,
caption, FAQ, ide kampanye, dan ringkasan informasi kesehatan.

Jangan membuat diagnosis individual, jangan menjanjikan kesembuhan,
dan jangan membuat klaim medis tanpa dasar. Untuk kondisi darurat,
sarankan mencari pertolongan medis segera.
"""


def ask_gemini(history, prompt):
    api_key = get_secret("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("API key Gemini belum dipasang.")

    if genai is None:
        raise RuntimeError("Paket google-genai belum terpasang.")

    client = genai.Client(api_key=api_key)

    conversation = [SYSTEM_PROMPT]

    for item in history[-12:]:
        role = "Pengguna" if item["role"] == "user" else "Asisten"
        conversation.append(f"{role}: {item['content']}")

    conversation.append(f"Pengguna: {prompt}")

    result = client.models.generate_content(
        model=get_secret("GEMINI_MODEL", GEMINI_MODEL_DEFAULT),
        contents="\n\n".join(conversation),
    )

    answer = getattr(result, "text", None)

    if not answer:
        raise RuntimeError("Gemini tidak mengembalikan jawaban.")

    return answer.strip()


def ask_groq(history, prompt):
    api_key = get_secret("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("API key Groq belum dipasang.")

    if Groq is None:
        raise RuntimeError("Paket groq belum terpasang.")

    client = Groq(api_key=api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in history[-12:]:
        if item["role"] in ("user", "assistant"):
            messages.append({
                "role": item["role"],
                "content": item["content"],
            })

    messages.append({"role": "user", "content": prompt})

    result = client.chat.completions.create(
        model=get_secret("GROQ_MODEL", GROQ_MODEL_DEFAULT),
        messages=messages,
        temperature=0.5,
        max_tokens=1800,
    )

    answer = result.choices[0].message.content

    if not answer:
        raise RuntimeError("Groq tidak mengembalikan jawaban.")

    return answer.strip()


def ask_ai(history, prompt):
    providers = []

    if get_secret("GEMINI_API_KEY"):
        providers.append(("Gemini", ask_gemini))

    if get_secret("GROQ_API_KEY"):
        providers.append(("Groq", ask_groq))

    if not providers:
        return None, None, [
            "API key belum dipasang di Streamlit Secrets."
        ]

    errors = []

    # Gemini dicoba lebih dahulu, kemudian Groq jika tersedia.
    for provider_name, provider_function in providers:
        try:
            answer = provider_function(history, prompt)
            return answer, provider_name, errors

        except Exception as exc:
            # Jangan tampilkan detail error/API key kepada pengunjung.
            error_text = str(exc).lower()

            if any(word in error_text for word in [
                "quota", "429", "rate limit",
                "resource_exhausted", "too many requests"
            ]):
                errors.append(
                    f"{provider_name}: kuota atau batas permintaan tercapai."
                )
            else:
                errors.append(
                    f"{provider_name}: layanan gagal merespons. "
                    "Periksa API key, model, dan log aplikasi."
                )

    return None, None, errors


# =========================================================
# FOTO AI: EDIT GAMBAR DENGAN GEMINI
# =========================================================
def edit_image_with_gemini(image_bytes, mime_type, instruction):
    """Mengedit gambar menggunakan model Gemini yang mendukung output gambar."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum dipasang di Streamlit Secrets.")
    if genai is None:
        raise RuntimeError("Paket google-genai belum terpasang. Tambahkan ke requirements.txt.")

    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=get_secret("GEMINI_IMAGE_MODEL", IMAGE_MODEL_DEFAULT),
        input=[
            {"type": "text", "text": (
                "Edit gambar yang diberikan sesuai instruksi berikut. "
                "Pertahankan subjek utama dan jangan menambahkan klaim kesehatan yang tidak diminta. "
                "Jika membuat poster, gunakan Bahasa Indonesia yang benar dan teks yang mudah dibaca. "
                "Instruksi pengguna: " + instruction
            )},
            {"type": "image", "data": base64.b64encode(image_bytes).decode("utf-8"), "mime_type": mime_type},
        ],
    )

    # SDK dapat mengembalikan gambar melalui output_image atau steps.
    output_image = getattr(interaction, "output_image", None)
    if output_image and getattr(output_image, "data", None):
        return base64.b64decode(output_image.data)

    for step in getattr(interaction, "steps", []) or []:
        if getattr(step, "type", "") == "model_output":
            for block in getattr(step, "content", []) or []:
                if getattr(block, "type", "") == "image":
                    data = getattr(block, "data", None)
                    if data:
                        return base64.b64decode(data)
    raise RuntimeError("Gemini tidak mengembalikan gambar. Coba perintah yang lebih sederhana atau periksa model/API.")


def get_ffmpeg_path():
    if imageio_ffmpeg is None:
        raise RuntimeError("Paket imageio-ffmpeg belum terpasang. Tambahkan ke requirements.txt.")
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_video_edit_plan(instruction):
    """Minta Gemini menerjemahkan perintah pengguna menjadi operasi video sederhana."""
    prompt = f"""Ubah perintah edit video berikut menjadi JSON SAJA, tanpa markdown.
Perintah pengguna: {instruction!r}
Gunakan hanya skema ini:
{{"trim_seconds": null, "aspect": "original", "grayscale": false, "brightness": 0.0, "mute": false}}
Aturan:
- trim_seconds: angka detik jika pengguna meminta video dipotong menjadi durasi tertentu (maksimal 180), selain itu null.
- aspect: salah satu dari original, vertical, horizontal, square. Pilih vertical untuk Reels/TikTok, horizontal untuk YouTube, square untuk 1:1.
- grayscale: true hanya jika diminta hitam putih/monokrom.
- brightness: angka antara -0.15 dan 0.15, selain itu 0.0.
- mute: true jika diminta menghilangkan suara, selain itu false.
Jangan menambahkan operasi lain. Jika instruksi tidak jelas, gunakan nilai default."""
    answer = ask_gemini([], prompt)
    if not answer:
        raise RuntimeError("Gemini belum dapat membuat rencana edit video. Pastikan GEMINI_API_KEY aktif.")
    cleaned = answer.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("AI memberikan format rencana yang tidak valid. Coba tulis perintah lebih sederhana.")
    plan = json.loads(cleaned[start:end + 1])
    # Validasi nilai untuk mencegah perintah eksternal masuk ke FFmpeg.
    aspect = plan.get("aspect", "original")
    if aspect not in {"original", "vertical", "horizontal", "square"}:
        aspect = "original"
    try:
        trim = float(plan.get("trim_seconds")) if plan.get("trim_seconds") is not None else None
    except (TypeError, ValueError):
        trim = None
    if trim is not None:
        trim = max(1.0, min(trim, 180.0))
    try:
        brightness = max(-0.15, min(0.15, float(plan.get("brightness", 0.0))))
    except (TypeError, ValueError):
        brightness = 0.0
    return {
        "trim_seconds": trim,
        "aspect": aspect,
        "grayscale": bool(plan.get("grayscale", False)),
        "brightness": brightness,
        "mute": bool(plan.get("mute", False)),
    }


def process_video(input_bytes, plan):
    """Menerapkan edit dasar dengan FFmpeg; bukan generasi ulang video."""
    ffmpeg = get_ffmpeg_path()
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "input_video"
        output_path = Path(temp_dir) / "hasil_edit.mp4"
        input_path.write_bytes(input_bytes)
        command = [ffmpeg, "-y", "-i", str(input_path)]
        if plan.get("trim_seconds"):
            command += ["-t", str(plan["trim_seconds"])]

        filters = []
        aspect = plan.get("aspect", "original")
        if aspect == "vertical":
            filters.append("scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280")
        elif aspect == "horizontal":
            filters.append("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720")
        elif aspect == "square":
            filters.append("scale=720:720:force_original_aspect_ratio=increase,crop=720:720")
        if plan.get("grayscale"):
            filters.append("hue=s=0")
        brightness = float(plan.get("brightness", 0.0))
        if abs(brightness) > 0.001:
            filters.append(f"eq=brightness={brightness:.3f}")
        if filters:
            command += ["-vf", ",".join(filters)]
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
        if plan.get("mute"):
            command += ["-an"]
        else:
            command += ["-c:a", "aac", "-b:a", "128k"]
        command += ["-movflags", "+faststart", str(output_path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 or not output_path.exists():
            # Jangan memunculkan log FFmpeg yang sangat panjang ke layar.
            raise RuntimeError("Video gagal diproses. Coba video MP4 yang lebih kecil atau instruksi lebih sederhana.")
        return output_path.read_bytes()


# =========================================================
# SESSION STATE
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "gallery" not in st.session_state:
    st.session_state.gallery = []

if "image_prompt" not in st.session_state:
    st.session_state.image_prompt = ""

if "video_prompt" not in st.session_state:
    st.session_state.video_prompt = ""

if "storyboard" not in st.session_state:
    st.session_state.storyboard = []

if "edited_image_bytes" not in st.session_state:
    st.session_state.edited_image_bytes = None

if "edited_video_bytes" not in st.session_state:
    st.session_state.edited_video_bytes = None


# =========================================================
# SIDEBAR MENU
# =========================================================
with st.sidebar:
    st.markdown("# 🩺 Studio Promkes AI")
    st.caption("Studio kreatif promosi kesehatan")

    page = st.radio(
        "Pilih menu",
        PAGES,
        key="selected_page",
    )

    st.divider()
    st.markdown("### 🔁 Status AI")

    statuses = get_ai_status()

    for provider, active in statuses.items():
        st.write(
            ("🟢 " if active else "⚪ ")
            + provider
            + (" tersedia" if active else " belum dikonfigurasi")
        )

    st.caption(
        "Chat AI mencoba Gemini terlebih dahulu, lalu Groq "
        "jika API key keduanya tersedia."
    )

    st.divider()
    st.caption("Materi edukasi bukan pengganti konsultasi tenaga kesehatan.")


# =========================================================
# HEADER
# =========================================================
st.markdown(
    """
    <div class="hero">
      <h1>🩺 Studio Promkes AI</h1>
      <p>
        Ciptakan materi promosi kesehatan yang informatif,
        menarik, kreatif, dan mudah dipahami masyarakat.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DASHBOARD
# =========================================================
if page == "🏠 Dashboard":

    st.subheader("Selamat datang di Studio Promkes AI")

    st.write(
        "Satu tempat untuk membantu menyiapkan naskah edukasi, "
        "konsep poster, dan storyboard video promosi kesehatan."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <h3>💬 Chat AI</h3>
                <p>Bantu susun naskah penyuluhan, FAQ, caption,
                dan ide kampanye kesehatan.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🖼️ Foto AI</h3>
                <p>Rancang prompt poster dan infografik
                kesehatan untuk layanan gambar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🎬 Video AI</h3>
                <p>Susun konsep, prompt, dan storyboard
                video edukasi kesehatan.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### ✨ Yang bisa kamu buat")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(
            "- Naskah penyuluhan hipertensi dan diabetes\n"
            "- Edukasi pencegahan DBD\n"
            "- Caption imunisasi dan PHBS"
        )

    with c2:
        st.markdown(
            "- Poster cuci tangan\n"
            "- Ide kampanye kesehatan masyarakat\n"
            "- Storyboard video edukasi"
        )

    st.info(
        "Chat AI, edit foto, dan perintah edit video memerlukan GEMINI_API_KEY. "
        "Edit foto memakai model gambar Gemini; edit video saat ini menerapkan "
        "operasi dasar pada video yang diunggah."
    )


# =========================================================
# CHAT AI
# =========================================================
elif page == "💬 Chat AI":

    st.subheader("💬 Chat AI")
    st.write("Tanyakan ide atau minta bantuan menyusun materi Promkes.")

    if not get_secret("GEMINI_API_KEY") and not get_secret("GROQ_API_KEY"):
        st.warning(
            "API key belum dipasang. Tambahkan GEMINI_API_KEY "
            "dan/atau GROQ_API_KEY pada Settings → Secrets."
        )

        st.markdown(
            "- [Google AI Studio](https://aistudio.google.com/)\n"
            "- [Groq Console](https://console.groq.com/)"
        )

    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

            if item.get("provider"):
                st.caption("Provider: " + item["provider"])

    prompt = st.chat_input(
        "Contoh: Buat naskah penyuluhan pencegahan DBD..."
    )

    if prompt:
        previous_messages = list(st.session_state.messages)

        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Menghubungkan ke AI..."):
                answer, provider, errors = ask_ai(
                    previous_messages,
                    prompt,
                )

            if answer:
                st.markdown(answer)
                st.caption("Dijawab oleh " + provider)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "provider": provider,
                })

            else:
                st.error("AI belum berhasil memberikan jawaban.")

                for error in errors:
                    st.write("- " + error)

                st.info(
                    "Pastikan API key benar, kuota tersedia, "
                    "dan paket pada requirements.txt sudah terpasang."
                )

    if st.button("🧹 Hapus percakapan"):
        st.session_state.messages = []
        st.rerun()


# =========================================================
# FOTO AI
# =========================================================
elif page == "🖼️ Foto AI":
    st.subheader("🖼️ Foto AI — Edit Foto dengan Perintah AI")
    st.write("Unggah foto atau poster, tulis perubahan yang kamu inginkan, lalu minta Gemini mengedit gambar tersebut.")

    if not get_secret("GEMINI_API_KEY"):
        st.warning("Fitur edit foto memerlukan GEMINI_API_KEY. Tambahkan dahulu melalui Settings → Secrets di Streamlit Community Cloud. Jangan menaruh API key langsung di kode.")

    uploaded_image = st.file_uploader(
        "📤 Unggah foto yang ingin diedit",
        type=["png", "jpg", "jpeg", "webp"],
        key="upload_image",
    )
    image_instruction = st.text_area(
        "✍️ Perintah edit foto",
        placeholder="Contoh: Ubah foto ini menjadi poster edukasi pencegahan DBD, tambahkan judul 'Cegah DBD', warna biru-hijau, dan ajakan 3M Plus.",
        height=110,
        key="image_edit_instruction",
    )

    if uploaded_image:
        st.markdown("#### Foto asli")
        st.image(uploaded_image.getvalue(), use_container_width=True)

    if st.button("✨ Proses Edit Foto dengan AI", type="primary", use_container_width=True, key="run_image_edit"):
        if not uploaded_image:
            st.warning("Unggah foto terlebih dahulu.")
        elif not image_instruction.strip():
            st.warning("Tuliskan perintah edit terlebih dahulu.")
        elif not get_secret("GEMINI_API_KEY"):
            st.error("API key Gemini belum dipasang. Lihat petunjuk di bawah.")
        else:
            try:
                mime_type = uploaded_image.type or "image/jpeg"
                with st.spinner("Gemini sedang mengedit gambar. Proses dapat memerlukan waktu dan kuota API..."):
                    edited_bytes = edit_image_with_gemini(uploaded_image.getvalue(), mime_type, image_instruction.strip())
                st.session_state.edited_image_bytes = edited_bytes
                st.session_state.edited_image_prompt = image_instruction.strip()
                st.success("Foto berhasil diproses!")
            except Exception as exc:
                st.error("Foto belum berhasil diedit.")
                st.caption(str(exc))

    if st.session_state.get("edited_image_bytes"):
        st.markdown("### 🖼️ Hasil edit")
        st.image(st.session_state.edited_image_bytes, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Unduh hasil foto (PNG)",
                data=st.session_state.edited_image_bytes,
                file_name="studio_promkes_hasil_edit.png",
                mime="image/png",
                use_container_width=True,
                key="download_edited_image",
            )
        with col2:
            if st.button("➕ Simpan hasil ke Galeri", use_container_width=True, key="save_edited_image"):
                st.session_state.gallery.append({
                    "kind": "image",
                    "name": "studio_promkes_hasil_edit.png",
                    "data": st.session_state.edited_image_bytes,
                    "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
                })
                st.success("Hasil foto disimpan ke Galeri sesi.")

    with st.expander("🔑 Cara memasang GEMINI_API_KEY"):
        st.markdown(
            "1. Buka [Google AI Studio](https://aistudio.google.com/) dan buat API key.\n"
            "2. Buka aplikasi Studio Promkes AI di Streamlit Community Cloud.\n"
            "3. Buka **App settings → Secrets**.\n"
            "4. Tambahkan baris berikut, ganti teks contoh dengan API key milikmu:\n"
            "```toml\nGEMINI_API_KEY = \"TEMPEL_API_KEY_DI_SINI\"\n```\n"
            "5. Simpan, lalu restart aplikasi bila diminta. Jangan kirim API key ke chat atau memasukkannya ke GitHub."
        )
    st.caption("Pengeditan gambar memerlukan model Gemini yang mendukung input gambar dan output gambar. Penggunaan API dapat memiliki biaya atau batas kuota.")


# =========================================================
# VIDEO AI
# =========================================================
elif page == "🎬 Video AI":
    st.subheader("🎬 Video AI — Edit Video dengan Perintah AI")
    st.write("Unggah video dan tulis perintah. Gemini menerjemahkan perintah menjadi langkah edit dasar, lalu FFmpeg memproses videonya.")
    st.info("Versi ini dapat memotong durasi, mengubah format layar, membuat video hitam-putih, menyesuaikan kecerahan, dan menghilangkan suara. Ini bukan generator video baru dan belum membuat adegan baru atau menambahkan narasi otomatis.")

    if not get_secret("GEMINI_API_KEY"):
        st.warning("Perintah bahasa alami membutuhkan GEMINI_API_KEY. Panduan pemasangan tersedia di menu Foto AI → Cara memasang GEMINI_API_KEY.")
    if imageio_ffmpeg is None:
        st.warning("Paket imageio-ffmpeg belum terpasang. Tambahkan `imageio-ffmpeg` ke requirements.txt lalu redeploy aplikasi.")

    uploaded_video = st.file_uploader(
        "📤 Unggah video yang ingin diedit",
        type=["mp4", "mov", "webm", "m4v"],
        key="upload_video",
    )
    video_instruction = st.text_area(
        "✍️ Perintah edit video",
        placeholder="Contoh: Jadikan video vertikal 9:16 untuk Reels, potong menjadi 15 detik, dan naikkan sedikit kecerahannya.",
        height=100,
        key="video_edit_instruction",
    )
    if uploaded_video:
        st.markdown("#### Video asli")
        st.video(uploaded_video.getvalue())
        st.caption(f"File: {uploaded_video.name} • {uploaded_video.size / (1024 * 1024):.1f} MB")

    if st.button("🎬 Proses Edit Video dengan AI", type="primary", use_container_width=True, key="run_video_edit"):
        if not uploaded_video:
            st.warning("Unggah video terlebih dahulu.")
        elif not video_instruction.strip():
            st.warning("Tuliskan perintah edit terlebih dahulu.")
        elif not get_secret("GEMINI_API_KEY"):
            st.error("API key Gemini belum dipasang. Ikuti petunjuk di menu Foto AI.")
        elif imageio_ffmpeg is None:
            st.error("Paket imageio-ffmpeg belum tersedia. Tambahkan ke requirements.txt dan redeploy.")
        elif uploaded_video.size > 100 * 1024 * 1024:
            st.error("Ukuran video melebihi batas 100 MB untuk versi ini. Coba video yang lebih kecil.")
        else:
            try:
                with st.spinner("AI sedang memahami perintah edit..."):
                    plan = make_video_edit_plan(video_instruction.strip())
                st.write("**Rencana edit dari AI:**")
                st.json(plan)
                with st.spinner("Sedang memproses video. Jangan tutup halaman..."):
                    edited_video_bytes = process_video(uploaded_video.getvalue(), plan)
                st.session_state.edited_video_bytes = edited_video_bytes
                st.session_state.edited_video_plan = plan
                st.success("Video berhasil diedit!")
            except Exception as exc:
                st.error("Video belum berhasil diproses.")
                st.caption(str(exc))

    if st.session_state.get("edited_video_bytes"):
        st.markdown("### 🎞️ Hasil edit video")
        st.video(st.session_state.edited_video_bytes)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Unduh hasil video (MP4)",
                data=st.session_state.edited_video_bytes,
                file_name="studio_promkes_hasil_edit.mp4",
                mime="video/mp4",
                use_container_width=True,
                key="download_edited_video",
            )
        with col2:
            if st.button("➕ Simpan hasil ke Galeri", use_container_width=True, key="save_edited_video"):
                st.session_state.gallery.append({
                    "kind": "video",
                    "name": "studio_promkes_hasil_edit.mp4",
                    "data": st.session_state.edited_video_bytes,
                    "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
                })
                st.success("Hasil video disimpan ke Galeri sesi.")

    with st.expander("Contoh perintah yang didukung"):
        st.markdown(
            "- `Potong video menjadi 15 detik.`\n"
            "- `Ubah menjadi vertikal 9:16 untuk Reels.`\n"
            "- `Buat video hitam putih.`\n"
            "- `Naikkan kecerahan sedikit.`\n"
            "- `Hilangkan suara video.`\n"
            "- `Jadikan horizontal 16:9 untuk YouTube dan potong menjadi 30 detik.`"
        )
    st.caption("Hasil tersimpan di Galeri sesi aktif dan dapat hilang saat sesi direset atau aplikasi dimulai ulang. Unduh hasil untuk menyimpan salinan permanen.")


# =========================================================
# GALERI
# =========================================================
elif page == "🗂️ Galeri":

    st.subheader("🗂️ Galeri hasil")

    st.caption(
        "Galeri tersimpan dalam sesi aktif. Hasil dapat hilang "
        "ketika sesi direset atau aplikasi dimulai ulang."
    )

    if not st.session_state.gallery:
        st.info(
            "Galeri masih kosong. Unggah gambar atau video "
            "melalui menu Foto AI atau Video AI."
        )

    else:
        if st.button("🗑️ Kosongkan galeri"):
            st.session_state.gallery = []
            st.rerun()

        for index, item in enumerate(st.session_state.gallery):
            st.divider()
            st.markdown("**" + item["name"] + "**")
            st.caption(
                item["kind"].capitalize()
                + " • "
                + item["created"]
            )

            if item["kind"] == "image":
                st.image(item["data"], use_container_width=True)

                extension = item["name"].lower()

                if extension.endswith(".png"):
                    mime = "image/png"
                elif extension.endswith(".webp"):
                    mime = "image/webp"
                else:
                    mime = "image/jpeg"

            else:
                st.video(item["data"])
                extension = item["name"].lower()

                if extension.endswith(".mov"):
                    mime = "video/quicktime"
                elif extension.endswith(".webm"):
                    mime = "video/webm"
                else:
                    mime = "video/mp4"

            st.download_button(
                "⬇️ Unduh hasil",
                data=item["data"],
                file_name=item["name"],
                mime=mime,
                key=f"download_{index}",
            )


# =========================================================
# FOOTER
# =========================================================
st.divider()

st.caption(
    "Studio Promkes AI • Materi edukasi kesehatan masyarakat. "
    "Ketersediaan dan kuota layanan AI mengikuti penyedia masing-masing."
)
