
import os
import io
from datetime import datetime

import streamlit as st
from PIL import Image

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
        "Chat AI memerlukan API key. Foto AI dan Video AI pada versi "
        "ini membuat prompt, bukan menghasilkan gambar atau video "
        "secara langsung."
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

    st.subheader("🖼️ Foto AI — Pembuat Prompt Poster")

    st.write(
        "Buat prompt poster kesehatan yang dapat digunakan "
        "di layanan desain atau generator gambar."
    )

    with st.form("foto_form"):
        theme = st.text_input(
            "Tema poster",
            placeholder="Contoh: pencegahan demam berdarah",
        )

        audience = st.selectbox(
            "Sasaran",
            [
                "Masyarakat umum",
                "Anak sekolah",
                "Remaja",
                "Ibu dan keluarga",
                "Lansia",
                "Tenaga kesehatan",
            ],
        )

        style = st.selectbox(
            "Gaya desain",
            [
                "Infografik profesional",
                "Ilustrasi modern dan ceria",
                "Flat design",
                "Kartun edukasi",
                "Fotorealistis",
            ],
        )

        format_image = st.selectbox(
            "Format",
            [
                "Poster vertikal 4:5",
                "Instagram 1:1",
                "Story 9:16",
                "Presentasi 16:9",
            ],
        )

        colors = st.text_input(
            "Warna utama",
            value="biru, hijau, putih",
        )

        make_prompt = st.form_submit_button(
            "✨ Buat prompt gambar",
            use_container_width=True,
        )

    if make_prompt:
        if not theme.strip():
            st.warning("Isi tema poster terlebih dahulu.")
        else:
            st.session_state.image_prompt = (
                f"Buat desain {format_image} bertema "
                f"'{theme.strip()}' untuk {audience.lower()}. "
                f"Gaya desain: {style}. Warna utama: {colors}. "
                "Buat desain promosi kesehatan masyarakat Indonesia "
                "yang profesional, ramah, mudah dibaca di ponsel, "
                "memiliki judul yang jelas dan ilustrasi yang relevan. "
                "Gunakan Bahasa Indonesia yang benar. Hindari klaim "
                "medis berlebihan. Sisakan ruang untuk logo dan "
                "kontak resmi instansi."
            )

    if st.session_state.image_prompt:
        st.text_area(
            "Prompt siap disalin",
            value=st.session_state.image_prompt,
            height=190,
        )

    st.markdown("### 🌐 Buka layanan gambar")

    st.markdown(
        "- [Google Gemini](https://gemini.google.com/)\n"
        "- [Microsoft Designer](https://designer.microsoft.com/)\n"
        "- [Adobe Firefly](https://firefly.adobe.com/)\n"
        "- [Canva](https://www.canva.com/)"
    )

    uploaded_image = st.file_uploader(
        "Unggah hasil gambar ke galeri sesi",
        type=["png", "jpg", "jpeg", "webp"],
        key="upload_image",
    )

    if uploaded_image:
        try:
            image_bytes = uploaded_image.getvalue()
            Image.open(io.BytesIO(image_bytes)).verify()

            if st.button("➕ Simpan gambar ke galeri"):
                st.session_state.gallery.append({
                    "kind": "image",
                    "name": uploaded_image.name,
                    "data": image_bytes,
                    "created": datetime.now().strftime(
                        "%d-%m-%Y %H:%M"
                    ),
                })
                st.success("Gambar berhasil ditambahkan ke galeri sesi.")

        except Exception:
            st.error("File gambar tidak valid.")


# =========================================================
# VIDEO AI
# =========================================================
elif page == "🎬 Video AI":

    st.subheader("🎬 Video AI — Prompt dan Storyboard")

    with st.form("video_form"):
        theme = st.text_input(
            "Tema video",
            placeholder="Contoh: langkah cuci tangan yang benar",
        )

        duration = st.selectbox(
            "Durasi video",
            ["8 detik", "15 detik", "30 detik", "60 detik"],
        )

        style = st.selectbox(
            "Gaya video",
            [
                "Animasi edukasi",
                "Motion graphic",
                "Kartun ramah anak",
                "Cinematic realistis",
                "Dokumenter singkat",
            ],
        )

        format_video = st.selectbox(
            "Format video",
            [
                "Vertikal 9:16 untuk Reels/TikTok/Shorts",
                "Horizontal 16:9 untuk YouTube",
                "Horizontal 16:9 untuk presentasi",
            ],
        )

        narration = st.checkbox(
            "Sertakan narasi Bahasa Indonesia",
            value=True,
        )

        make_video_prompt = st.form_submit_button(
            "🎞️ Buat prompt dan storyboard",
            use_container_width=True,
        )

    if make_video_prompt:
        if not theme.strip():
            st.warning("Isi tema video terlebih dahulu.")
        else:
            narration_text = (
                "Sertakan narasi Bahasa Indonesia yang natural."
                if narration
                else "Gunakan visual dan teks singkat tanpa narasi."
            )

            st.session_state.video_prompt = (
                f"Buat video promosi kesehatan bertema "
                f"'{theme.strip()}', durasi {duration}, "
                f"gaya {style}, format {format_video}. "
                f"{narration_text} Gunakan visual yang inklusif, "
                "transisi rapi, teks yang mudah dibaca, informasi "
                "yang bertanggung jawab, dan penutup berupa ajakan "
                "mengakses sumber kesehatan resmi."
            )

            st.session_state.storyboard = [
                "Adegan 1 — Pembuka: tampilkan situasi yang relevan.",
                "Adegan 2 — Edukasi: sampaikan pesan utama.",
                "Adegan 3 — Tindakan: tunjukkan langkah yang dapat dilakukan.",
                "Adegan 4 — Penutup: ajakan bertindak dan sumber resmi.",
            ]

    if st.session_state.video_prompt:
        st.text_area(
            "Prompt video siap disalin",
            value=st.session_state.video_prompt,
            height=190,
        )

        st.markdown("### Storyboard")

        for scene in st.session_state.storyboard:
            st.markdown("- " + scene)

    st.markdown("### 🌐 Buka layanan video")

    st.markdown(
        "- [Google Flow](https://flow.google.com/)\n"
        "- [PixVerse](https://pixverse.ai/)\n"
        "- [Adobe Firefly](https://firefly.adobe.com/)\n"
        "- [Canva](https://www.canva.com/)"
    )

    uploaded_video = st.file_uploader(
        "Unggah hasil video ke galeri sesi",
        type=["mp4", "mov", "webm"],
        key="upload_video",
    )

    if uploaded_video:
        if st.button("➕ Simpan video ke galeri"):
            st.session_state.gallery.append({
                "kind": "video",
                "name": uploaded_video.name,
                "data": uploaded_video.getvalue(),
                "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
            })
            st.success("Video berhasil ditambahkan ke galeri sesi.")


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
