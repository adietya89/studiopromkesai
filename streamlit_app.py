from pathlib import Path

out = Path("/mnt/data/studiopromkesai_baru")
out.mkdir(parents=True, exist_ok=True)

app_code = r'''import os
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


def get_groq_client():
    api_key = get_secret("GROQ_API_KEY")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None


def call_gemini(messages, user_prompt):
    client = get_gemini_client()
    if client is None:
        raise RuntimeError("Gemini belum dikonfigurasi: tambahkan GEMINI_API_KEY di Streamlit Secrets.")
    system_text = (
        "Kamu adalah asisten Studio Promkes AI untuk membantu promosi kesehatan masyarakat Indonesia. "
        "Gunakan Bahasa Indonesia yang jelas, ramah, akurat, dan mudah dipahami. "
        "Untuk informasi kesehatan, jangan menggantikan diagnosis dokter; sarankan layanan kesehatan "
        "profesional untuk kondisi darurat atau gejala berat. Hindari klaim medis yang tidak didukung."
    )
    history_lines = []
    for item in messages[-12:]:
        role = "Pengguna" if item.get("role") == "user" else "Asisten"
        content = str(item.get("content", "")).strip()
        if content:
            history_lines.append(f"{role}: {content}")
    full_prompt = system_text + "\n\nRiwayat percakapan:\n" + "\n".join(history_lines)
    if user_prompt and (not history_lines or not history_lines[-1].endswith(user_prompt)):
        full_prompt += "\nPengguna: " + user_prompt
    response = client.models.generate_content(
        model=get_secret("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        contents=full_prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini tidak mengembalikan teks. Coba ulangi dengan prompt yang lebih singkat.")
    return text.strip()


def call_groq(messages, user_prompt):
    client = get_groq_client()
    if client is None:
        raise RuntimeError("Groq belum dikonfigurasi: tambahkan GROQ_API_KEY di Streamlit Secrets.")
    system_text = (
        "Kamu adalah asisten Studio Promkes AI untuk promosi kesehatan masyarakat Indonesia. "
        "Jawab dalam Bahasa Indonesia yang jelas dan ramah. Jangan membuat diagnosis medis. "
        "Untuk keadaan darurat, arahkan pengguna mencari pertolongan medis segera."
    )
    chat_messages = [{"role": "system", "content": system_text}]
    for item in messages[-12:]:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            chat_messages.append({"role": role, "content": content})
    if user_prompt and (not chat_messages or chat_messages[-1].get("content") != user_prompt):
        chat_messages.append({"role": "user", "content": user_prompt})
    result = client.chat.completions.create(
        model=get_secret("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        messages=chat_messages,
        temperature=0.5,
        max_tokens=1800,
    )
    return result.choices[0].message.content.strip()


def ask_ai(messages, prompt):
    """Try configured free-tier providers in order. Never intentionally use paid providers."""
    failures = []
    providers = [
        ("Gemini", call_gemini),
        ("Groq", call_groq),
    ]
    for provider_name, provider_fn in providers:
        try:
            answer = provider_fn(messages, prompt)
            return answer, provider_name, failures
        except Exception as exc:
            msg = str(exc)
            lower = msg.lower()
            # Keep the app moving to the next configured provider. Avoid exposing secrets.
            if any(x in lower for x in ["api key", "api_key", "unauthorized", "authentication"]):
                failures.append(f"{provider_name}: API key belum benar/tersedia.")
            elif any(x in lower for x in ["quota", "rate limit", "resource_exhausted", "429", "too many requests"]):
                failures.append(f"{provider_name}: kuota atau batas permintaan tercapai.")
            else:
                failures.append(f"{provider_name}: layanan belum tersedia atau terjadi kesalahan.")
    return None, None, failures


# =========================================================
# SESSION STATE
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "gallery" not in st.session_state:
    st.session_state.gallery = []
if "last_ai_provider" not in st.session_state:
    st.session_state.last_ai_provider = ""


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("## 🩺 Studio Promkes AI")
    st.caption("Studio kreatif promosi kesehatan")
    page = st.radio(
        "Pilih menu",
        ["🏠 Dashboard", "💬 Chat AI", "🖼️ Foto AI", "🎬 Video AI", "🗂️ Galeri"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("### 🔁 Auto AI Switch")
    gemini_ready = bool(get_secret("GEMINI_API_KEY"))
    groq_ready = bool(get_secret("GROQ_API_KEY"))
    st.write(f"{'🟢' if gemini_ready else '⚪'} Gemini API")
    st.write(f"{'🟢' if groq_ready else '⚪'} Groq API")
    st.caption("Hanya mencoba layanan yang API key-nya sudah dipasang. Tidak otomatis beralih ke layanan berbayar.")
    st.divider()
    st.caption("Materi edukasi bersifat umum dan bukan pengganti saran tenaga kesehatan.")


# =========================================================
# HEADER
# =========================================================
st.markdown(
    f"""
    <div class="hero">
      <h1>🩺 {APP_NAME}</h1>
      <p>Buat materi promosi kesehatan, ide kampanye, poster, dan video edukasi dalam satu tempat.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DASHBOARD
# =========================================================
if page == "🏠 Dashboard":
    st.subheader("Selamat datang!")
    st.write("Studio ini dirancang untuk membantu menyiapkan materi Promosi Kesehatan (Promkes) dengan alur kerja yang sederhana.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="feature-card"><h3>💬 Chat AI</h3><p>Buat naskah penyuluhan, FAQ, caption, dan ide kampanye.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Chat AI", use_container_width=True):
            st.session_state["_navigate"] = "💬 Chat AI"
            st.rerun()
    with c2:
        st.markdown('<div class="feature-card"><h3>🖼️ Foto AI</h3><p>Buat prompt gambar/poster lalu lanjutkan di layanan gambar.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Foto AI", use_container_width=True):
            st.session_state["_navigate"] = "🖼️ Foto AI"
            st.rerun()
    with c3:
        st.markdown('<div class="feature-card"><h3>🎬 Video AI</h3><p>Siapkan prompt video edukasi dan buka layanan video.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Video AI", use_container_width=True):
            st.session_state["_navigate"] = "🎬 Video AI"
            st.rerun()
    st.markdown("### Cara kerja Auto AI Switch")
    st.info("Chat mencoba Gemini terlebih dahulu, lalu Groq jika Gemini gagal/kuotanya mencapai batas. Keduanya harus dikonfigurasi dengan API key masing-masing. Ini tidak menjamin selalu tersedia dan kuota gratis mengikuti aturan penyedia.")
    st.markdown("### Contoh kebutuhan Promkes")
    st.write("- Naskah penyuluhan hipertensi dan diabetes")
    st.write("- Caption media sosial untuk imunisasi dan PHBS")
    st.write("- Ide poster pencegahan DBD")
    st.write("- Storyboard video edukasi cuci tangan")
    st.caption("Catatan: menu Foto AI dan Video AI membantu menyiapkan prompt dan membuka layanan eksternal. Generator gambar/video langsung tidak dijanjikan gratis tanpa batas.")


# Allow dashboard buttons to select another page through state.
if st.session_state.get("_navigate"):
    wanted = st.session_state.pop("_navigate")
    st.info(f"Silakan pilih menu **{wanted}** pada sidebar untuk melanjutkan.")


# =========================================================
# CHAT AI
# =========================================================
elif page == "💬 Chat AI":
    st.subheader("💬 Chat AI — Auto AI Switch")
    st.caption("Urutan: Gemini → Groq. Jika provider pertama gagal atau mencapai batas kuota, aplikasi mencoba provider berikutnya.")
    if not gemini_ready if False else False:
        pass

    if not get_secret("GEMINI_API_KEY") and not get_secret("GROQ_API_KEY"):
        st.warning("API key belum dipasang. Buat API key gratis dari Google AI Studio dan/atau Groq, lalu masukkan ke Streamlit Secrets.")
        st.markdown("- [Google AI Studio](https://aistudio.google.com/)\n- [Groq Console](https://console.groq.com/)")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("provider"):
                st.caption(f"Provider: {msg['provider']}")

    prompt = st.chat_input("Tulis pertanyaan atau kebutuhan materi Promkes...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Menghubungkan ke AI gratis yang tersedia..."):
                answer, provider, failures = ask_ai(st.session_state.messages[:-1], prompt)
            if answer:
                st.markdown(answer)
                st.caption(f"Provider yang menjawab: {provider}")
                st.session_state.messages.append({"role": "assistant", "content": answer, "provider": provider})
                st.session_state.last_ai_provider = provider
            else:
                st.error("Semua AI yang sudah dikonfigurasi belum dapat menjawab.")
                for failure in failures:
                    st.write(f"- {failure}")
                st.info("Periksa API key/kuota atau coba lagi nanti. Aplikasi tidak akan berpindah ke layanan berbayar.")
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 Hapus percakapan", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("📝 Contoh prompt Promkes", use_container_width=True):
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Contoh prompt: Buat naskah penyuluhan 3 menit tentang pencegahan DBD untuk warga desa. Gunakan bahasa sederhana, sertakan 5 langkah pencegahan, ajakan bertindak, dan caption media sosial."
            })
            st.rerun()


# =========================================================
# FOTO AI
# =========================================================
elif page == "🖼️ Foto AI":
    st.subheader("🖼️ Foto AI — Pembuat Prompt Poster")
    st.write("Generator gambar langsung melalui API tidak disertakan agar aplikasi tidak diam-diam memakai layanan berbayar. Buat prompt di sini, lalu buka layanan yang menyediakan akses gratis sesuai akunmu.")
    with st.form("image_prompt_form"):
        tema = st.text_input("Tema poster", placeholder="Contoh: pencegahan demam berdarah")
        sasaran = st.selectbox("Sasaran audiens", ["Masyarakat umum", "Anak sekolah", "Remaja", "Ibu dan keluarga", "Lansia", "Tenaga kesehatan"])
        gaya = st.selectbox("Gaya visual", ["Ilustrasi modern dan ceria", "Infografik profesional", "Flat design", "Fotorealistis", "Kartun edukasi"])
        ukuran = st.selectbox("Format", ["Poster vertikal 4:5", "Instagram 1:1", "Story 9:16", "Presentasi 16:9"])
        warna = st.text_input("Warna utama (opsional)", value="biru, hijau, putih")
        buat_prompt = st.form_submit_button("✨ Buat prompt gambar", use_container_width=True)
    if buat_prompt:
        if not tema.strip():
            st.warning("Masukkan tema poster terlebih dahulu.")
        else:
            generated = (
                f"Buat desain {ukuran} bertema '{tema.strip()}' untuk {sasaran.lower()}. "
                f"Gaya visual: {gaya.lower()}. Palet warna: {warna or 'warna yang harmonis'}. "
                "Desain bersih, mudah dibaca dari ponsel, hierarki judul jelas, ilustrasi relevan, "
                "komposisi profesional untuk promosi kesehatan masyarakat Indonesia. "
                "Gunakan teks Bahasa Indonesia yang singkat dan ejaan benar. "
                "Jangan menampilkan logo instansi yang tidak diberikan, jangan membuat klaim medis tanpa dasar, "
                "sisakan ruang untuk logo dan kontak resmi. Hindari teks kecil dan elemen yang terlalu ramai."
            )
            st.session_state.generated_image_prompt = generated
    if st.session_state.get("generated_image_prompt"):
        st.text_area("Prompt gambar siap disalin", value=st.session_state.generated_image_prompt, height=180)
        st.code(st.session_state.generated_image_prompt, language="text")
        st.caption("Salin prompt lalu gunakan pada layanan gambar pilihanmu.")
    st.markdown("### Layanan gambar yang bisa dicoba")
    st.markdown("- [Google Gemini](https://gemini.google.com/)\n- [Microsoft Designer](https://designer.microsoft.com/)\n- [Adobe Firefly](https://firefly.adobe.com/)\n- [Canva](https://www.canva.com/)")
    uploaded = st.file_uploader("Unggah hasil gambar untuk disimpan di galeri sesi ini", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is not None:
        try:
            image_bytes = uploaded.getvalue()
            Image.open(io.BytesIO(image_bytes)).verify()
            if st.button("➕ Simpan gambar ke galeri", use_container_width=True):
                st.session_state.gallery.append({
                    "kind": "image",
                    "name": uploaded.name,
                    "data": image_bytes,
                    "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
                })
                st.success("Gambar disimpan di galeri sesi ini.")
        except Exception:
            st.error("File gambar tidak valid.")


# =========================================================
# VIDEO AI
# =========================================================
elif page == "🎬 Video AI":
    st.subheader("🎬 Video AI — Pembuat Prompt Video")
    st.write("Menu ini menyiapkan prompt dan storyboard. Pembuatan video dilakukan di layanan eksternal yang menyediakan kuota gratis untuk akunmu.")
    with st.form("video_prompt_form"):
        tema_video = st.text_input("Tema video", placeholder="Contoh: 5 langkah cuci tangan yang benar")
        durasi = st.selectbox("Durasi target", ["8 detik", "15 detik", "30 detik", "60 detik"])
        gaya_video = st.selectbox("Gaya video", ["Animasi edukasi", "Cinematic realistis", "Motion graphic", "Kartun ramah anak", "Dokumenter singkat"])
        platform = st.selectbox("Platform", ["TikTok/Reels/Shorts 9:16", "YouTube 16:9", "Video layar presentasi 16:9"])
        voice = st.checkbox("Sertakan narasi Bahasa Indonesia", value=True)
        buat_video_prompt = st.form_submit_button("🎞️ Buat prompt dan storyboard", use_container_width=True)
    if buat_video_prompt:
        if not tema_video.strip():
            st.warning("Masukkan tema video terlebih dahulu.")
        else:
            narration = "Sertakan narasi Bahasa Indonesia yang natural, jelas, dan sesuai durasi." if voice else "Tanpa narasi; gunakan visual dan teks singkat Bahasa Indonesia."
            vp = (
                f"Buat video promosi kesehatan tentang '{tema_video.strip()}', durasi {durasi}, "
                f"format {platform}, gaya {gaya_video.lower()}. {narration} "
                "Gunakan visual yang aman, inklusif, mudah dipahami masyarakat Indonesia, pencahayaan dan transisi rapi. "
                "Hindari klaim medis berlebihan, adegan menakutkan, teks kecil, logo palsu, dan informasi yang tidak terverifikasi. "
                "Akhiri dengan ajakan mencari informasi dari puskesmas atau sumber kesehatan resmi."
            )
            st.session_state.generated_video_prompt = vp
            st.session_state.generated_storyboard = [
                "Adegan 1 — Pembuka: tampilkan situasi sehari-hari yang relevan.",
                "Adegan 2 — Pesan utama: jelaskan inti edukasi dengan visual sederhana.",
                "Adegan 3 — Langkah tindakan: tampilkan tindakan yang dapat dilakukan penonton.",
                "Adegan 4 — Penutup: ajakan bertindak dan rujukan ke sumber resmi.",
            ]
    if st.session_state.get("generated_video_prompt"):
        st.text_area("Prompt video siap disalin", value=st.session_state.generated_video_prompt, height=180)
        st.markdown("**Storyboard awal**")
        for item in st.session_state.get("generated_storyboard", []):
            st.write(f"- {item}")
    st.markdown("### Layanan video yang bisa dicoba")
    st.markdown("- [Google Flow](https://flow.google.com/)\n- [PixVerse](https://pixverse.ai/)\n- [Adobe Firefly](https://firefly.adobe.com/)\n- [Canva](https://www.canva.com/)")
    uploaded_video = st.file_uploader("Unggah hasil video untuk disimpan di galeri sesi ini", type=["mp4", "mov", "webm"])
    if uploaded_video is not None:
        video_bytes = uploaded_video.getvalue()
        if st.button("➕ Simpan video ke galeri", use_container_width=True):
            st.session_state.gallery.append({
                "kind": "video",
                "name": uploaded_video.name,
                "data": video_bytes,
                "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
            })
            st.success("Video disimpan di galeri sesi ini.")


# =========================================================
# GALERI
# =========================================================
elif page == "🗂️ Galeri":
    st.subheader("🗂️ Galeri hasil")
    st.caption("Galeri versi ini disimpan selama sesi aplikasi berjalan. Hasil dapat hilang setelah sesi direset atau aplikasi dimulai ulang.")
    if not st.session_state.gallery:
        st.info("Belum ada hasil. Unggah hasil gambar atau video dari menu Foto AI / Video AI.")
    else:
        if st.button("🗑️ Kosongkan galeri", type="secondary"):
            st.session_state.gallery = []
            st.rerun()
        for idx, item in enumerate(reversed(st.session_state.gallery)):
            st.divider()
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item['kind'].capitalize()} • {item['created']}")
            if item["kind"] == "image":
                st.image(item["data"], use_container_width=True)
                mime = "image/png" if item["name"].lower().endswith(".png") else "image/jpeg"
            else:
                st.video(item["data"])
                mime = "video/mp4" if item["name"].lower().endswith(".mp4") else "video/webm"
            st.download_button(
                "⬇️ Unduh hasil",
                data=item["data"],
                file_name=item["name"],
                mime=mime,
                key=f"download_{idx}_{item['name']}",
            )


# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption("Studio Promkes AI • Mengutamakan layanan gratis. Tidak ada perpindahan otomatis ke layanan berbayar. Ketersediaan kuota mengikuti ketentuan penyedia AI.")
'''
# Remove an unnecessary awkward conditional in the generated script
app_code = app_code.replace('    if not gemini_ready if False else False:\n        pass\n\n', '')
(out / "streamlit_app.py").write_text(app_code, encoding="utf-8")

requirements = """streamlit>=1.39.0
google-genai>=1.0.0
groq>=0.11.0
Pillow>=10.0.0
"""
(out / "requirements.txt").write_text(requirements, encoding="utf-8")

readme = """# Studio Promkes AI — versi awal gratis

## File
- `streamlit_app.py`: aplikasi utama
- `requirements.txt`: paket yang dibutuhkan

## Deploy ke Streamlit Community Cloud
1. Buat repository GitHub baru, misalnya `studiopromkesai`.
2. Upload `streamlit_app.py` dan `requirements.txt` ke root repository.
3. Buat aplikasi di https://share.streamlit.io/ dan pilih file utama `streamlit_app.py`.
4. Di Streamlit Cloud: **App settings → Secrets**, masukkan API key yang sudah dibuat.

Contoh Secrets (ganti nilainya dengan API key milik sendiri; jangan upload API key ke GitHub):

GEMINI_API_KEY = "isi_api_key_gemini"
GROQ_API_KEY = "isi_api_key_groq"

# Opsional:
# GEMINI_MODEL = "gemini-2.5-flash"
# GROQ_MODEL = "llama-3.3-70b-versatile"

## Mendapatkan API key
- Gemini: https://aistudio.google.com/
- Groq: https://console.groq.com/

Gunakan model/kuota yang ditampilkan sebagai gratis pada akun masing-masing. Paket gratis, model, dan batas pemakaian bisa berubah. Jangan menganggap layanan selalu tersedia.

## Batasan penting
- Auto AI Switch berlaku untuk chat: mencoba Gemini, lalu Groq ketika provider pertama gagal.
- Tidak ada fallback berbayar yang dipanggil otomatis.
- Foto AI dan Video AI pada versi ini membuat prompt/storyboard dan membuka layanan eksternal; bukan generator gambar/video langsung di Streamlit.
- Galeri hanya tersimpan di session aplikasi. Untuk galeri permanen perlu storage/database tambahan.
"""
(out / "README.md").write_text(readme, encoding="utf-8")

import zipfile
zip_path = Path("/mnt/data/studiopromkesai_baru.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in out.iterdir():
        z.write(p, arcname=f"studiopromkesai_baru/{p.name}")

print("Created files:")
for p in out.iterdir():
    print(f"{p.name}: {p.stat().st_size} bytes")
print(f"ZIP: {zip_path} ({zip_path.stat().st_size} bytes)")
