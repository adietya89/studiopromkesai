import os
import io
import streamlit as st
from PIL import Image

app_code = r'''import os
import io
from datetime import datetime

import streamlit as st
from PIL import Image

try:
    from google import genai
except Exception:
    genai = None

try:
    from groq import Groq
except Exception:
    Groq = None

st.set_page_config(
    page_title="Studio Promkes AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "Studio Promkes AI"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
PAGES = ["🏠 Dashboard", "💬 Chat AI", "🖼️ Foto AI", "🎬 Video AI", "🗂️ Galeri"]

st.markdown("""
<style>
.stApp {
  background: radial-gradient(circle at 5% 0%, rgba(13,148,136,.10), transparent 28%),
              radial-gradient(circle at 95% 8%, rgba(59,130,246,.10), transparent 30%),
              #f7fafc;
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#073b4c 0%,#075985 55%,#0f766e 100%);
}
[data-testid="stSidebar"] * { color: white; }
.hero {
  padding: 1.5rem; border-radius: 20px;
  background: linear-gradient(120deg,#075985,#0f766e);
  color: white; margin-bottom: 1.2rem;
}
.hero h1 { color: white; margin: 0 0 .35rem 0; }
.hero p { color: #e0f2fe; margin: 0; }
.feature {
  background: white; border: 1px solid #dbeafe; border-radius: 16px;
  padding: 1rem; min-height: 140px; box-shadow: 0 4px 14px rgba(15,23,42,.05);
}
.stButton > button { border-radius: 10px; font-weight: 600; min-height: 2.5rem; }
</style>
""", unsafe_allow_html=True)

def secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or os.getenv(name, default) or "").strip()

def gemini_answer(history, prompt):
    key = secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY belum dipasang.")
    if genai is None:
        raise RuntimeError("Paket google-genai belum terpasang.")
    client = genai.Client(api_key=key)
    instructions = (
        "Kamu adalah asisten Studio Promkes AI untuk promosi kesehatan masyarakat Indonesia. "
        "Jawab dalam Bahasa Indonesia yang jelas, ramah, praktis, dan mudah dipahami. "
        "Jangan menggantikan diagnosis atau konsultasi tenaga kesehatan. Hindari klaim medis tanpa dasar. "
        "Untuk keadaan darurat, sarankan mencari pertolongan medis segera."
    )
    transcript = []
    for item in history[-10:]:
        role = "Pengguna" if item["role"] == "user" else "Asisten"
        transcript.append(f"{role}: {item['content']}")
    full_prompt = instructions + "\n\nRiwayat:\n" + "\n".join(transcript)
    full_prompt += "\nPengguna: " + prompt
    response = client.models.generate_content(
        model=secret("GEMINI_MODEL", GEMINI_DEFAULT_MODEL),
        contents=full_prompt,
    )
    answer = getattr(response, "text", None)
    if not answer:
        raise RuntimeError("Gemini tidak memberikan jawaban teks.")
    return answer.strip()

def groq_answer(history, prompt):
    key = secret("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY belum dipasang.")
    if Groq is None:
        raise RuntimeError("Paket groq belum terpasang.")
    client = Groq(api_key=key)
    messages = [{
        "role": "system",
        "content": (
            "Kamu adalah asisten Studio Promkes AI untuk promosi kesehatan masyarakat Indonesia. "
            "Gunakan Bahasa Indonesia yang jelas dan ramah. Jangan membuat diagnosis medis. "
            "Untuk keadaan darurat, arahkan pengguna mencari pertolongan medis segera."
        ),
    }]
    for item in history[-10:]:
        if item.get("role") in ("user", "assistant"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": prompt})
    result = client.chat.completions.create(
        model=secret("GROQ_MODEL", GROQ_DEFAULT_MODEL),
        messages=messages,
        temperature=0.5,
        max_tokens=1600,
    )
    answer = result.choices[0].message.content
    if not answer:
        raise RuntimeError("Groq tidak memberikan jawaban teks.")
    return answer.strip()

def ask_ai(history, prompt):
    failures = []
    # Hanya mencoba provider yang API key-nya tersedia; tidak ada layanan berbayar fallback.
    providers = []
    if secret("GEMINI_API_KEY"):
        providers.append(("Gemini", gemini_answer))
    if secret("GROQ_API_KEY"):
        providers.append(("Groq", groq_answer))
    if not providers:
        return None, None, ["Pasang GEMINI_API_KEY dan/atau GROQ_API_KEY di Streamlit Secrets."]
    for name, fn in providers:
        try:
            return fn(history, prompt), name, failures
        except Exception as exc:
            msg = str(exc).lower()
            if any(term in msg for term in ("quota", "rate limit", "429", "resource_exhausted", "too many requests")):
                failures.append(f"{name}: kuota/batas permintaan tercapai.")
            elif any(term in msg for term in ("api key", "unauthorized", "authentication", "belum dipasang")):
                failures.append(f"{name}: API key belum benar atau belum tersedia.")
            else:
                failures.append(f"{name}: layanan gagal merespons ({type(exc).__name__}).")
    return None, None, failures

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
if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

with st.sidebar:
    st.markdown("## 🩺 Studio Promkes AI")
    st.caption("Studio kreatif promosi kesehatan")
    selected_page = st.radio("Pilih menu", PAGES, key="page")
    st.divider()
    st.markdown("### 🔁 Status Auto AI Switch")
    st.write(("🟢" if secret("GEMINI_API_KEY") else "⚪") + " Gemini API")
    st.write(("🟢" if secret("GROQ_API_KEY") else "⚪") + " Groq API")
    st.caption("Gemini dicoba lebih dahulu, lalu Groq jika tersedia. Tidak beralih otomatis ke layanan berbayar.")
    st.divider()
    st.caption("Materi edukasi bersifat umum dan bukan pengganti konsultasi tenaga kesehatan.")

st.markdown(f"""
<div class="hero">
  <h1>🩺 {APP_NAME}</h1>
  <p>Buat materi promosi kesehatan, ide kampanye, poster, dan video edukasi dalam satu tempat.</p>
</div>
""", unsafe_allow_html=True)

if selected_page == "🏠 Dashboard":
    st.subheader("Selamat datang!")
    st.write("Studio ini membantu menyiapkan materi Promosi Kesehatan (Promkes) dengan alur kerja sederhana.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="feature"><h3>💬 Chat AI</h3><p>Naskah penyuluhan, FAQ, caption, dan ide kampanye.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Chat AI", use_container_width=True):
            st.session_state.page = "💬 Chat AI"
            st.rerun()
    with c2:
        st.markdown('<div class="feature"><h3>🖼️ Foto AI</h3><p>Susun prompt poster kesehatan untuk layanan gambar.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Foto AI", use_container_width=True):
            st.session_state.page = "🖼️ Foto AI"
            st.rerun()
    with c3:
        st.markdown('<div class="feature"><h3>🎬 Video AI</h3><p>Susun prompt dan storyboard video edukasi.</p></div>', unsafe_allow_html=True)
        if st.button("Buka Video AI", use_container_width=True):
            st.session_state.page = "🎬 Video AI"
            st.rerun()
    st.markdown("### Contoh kebutuhan Promkes")
    st.markdown("- Naskah penyuluhan hipertensi dan diabetes\n- Caption imunisasi dan PHBS\n- Poster pencegahan DBD\n- Storyboard video cuci tangan")
    st.info("Foto AI dan Video AI di versi ini membuat prompt; pembuatan media dilakukan pada layanan eksternal. Chat AI memerlukan API key.")

elif selected_page == "💬 Chat AI":
    st.subheader("💬 Chat AI — Auto AI Switch")
    st.caption("Urutan: Gemini → Groq. Fallback hanya ke provider yang API key-nya kamu pasang.")
    if not secret("GEMINI_API_KEY") and not secret("GROQ_API_KEY"):
        st.warning("API key belum dipasang. Tambahkan API key melalui Streamlit Cloud → Settings → Secrets.")
        st.markdown("- [Google AI Studio](https://aistudio.google.com/)\n- [Groq Console](https://console.groq.com/)")
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item.get("provider"):
                st.caption(f"Provider: {item['provider']}")
    prompt = st.chat_input("Tulis pertanyaan atau kebutuhan materi Promkes...")
    if prompt:
        prior_history = list(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Menghubungkan ke AI yang tersedia..."):
                answer, provider, failures = ask_ai(prior_history, prompt)
            if answer:
                st.markdown(answer)
                st.caption(f"Provider yang menjawab: {provider}")
                st.session_state.messages.append({"role": "assistant", "content": answer, "provider": provider})
            else:
                st.error("AI belum dapat menjawab.")
                for failure in failures:
                    st.write("- " + failure)
                st.info("Periksa API key, kuota, dan nama model di Secrets.")
        st.rerun()
    a, b = st.columns(2)
    with a:
        if st.button("🧹 Hapus percakapan", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with b:
        if st.button("📝 Masukkan contoh prompt", use_container_width=True):
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Contoh prompt: Buat naskah penyuluhan 3 menit tentang pencegahan DBD untuk warga desa. Sertakan 5 langkah pencegahan dan ajakan bertindak."
            })
            st.rerun()

elif selected_page == "🖼️ Foto AI":
    st.subheader("🖼️ Foto AI — Pembuat Prompt Poster")
    st.write("Isi tema untuk membuat prompt poster kesehatan yang bisa disalin ke layanan gambar pilihanmu.")
    with st.form("image_form"):
        theme = st.text_input("Tema poster", placeholder="Contoh: pencegahan demam berdarah")
        audience = st.selectbox("Sasaran", ["Masyarakat umum", "Anak sekolah", "Remaja", "Ibu dan keluarga", "Lansia", "Tenaga kesehatan"])
        style = st.selectbox("Gaya visual", ["Ilustrasi modern dan ceria", "Infografik profesional", "Flat design", "Fotorealistis", "Kartun edukasi"])
        format_size = st.selectbox("Format", ["Poster vertikal 4:5", "Instagram 1:1", "Story 9:16", "Presentasi 16:9"])
        colors = st.text_input("Warna utama", value="biru, hijau, putih")
        submitted = st.form_submit_button("✨ Buat prompt gambar", use_container_width=True)
    if submitted:
        if not theme.strip():
            st.warning("Masukkan tema poster terlebih dahulu.")
        else:
            st.session_state.image_prompt = (
                f"Buat desain {format_size} bertema '{theme.strip()}' untuk {audience.lower()}. "
                f"Gaya visual: {style.lower()}. Palet warna: {colors or 'warna harmonis'}. "
                "Desain bersih, mudah dibaca dari ponsel, judul jelas, ilustrasi relevan, profesional untuk promosi "
                "kesehatan masyarakat Indonesia. Gunakan Bahasa Indonesia yang benar, hindari klaim medis tanpa dasar, "
                "jangan menciptakan logo instansi, dan sisakan ruang untuk logo serta kontak resmi."
            )
    if st.session_state.image_prompt:
        st.text_area("Prompt gambar siap disalin", value=st.session_state.image_prompt, height=170)
        st.button("📋 Prompt tersedia di kotak di atas", disabled=True)
    st.markdown("### Layanan gambar")
    st.markdown("- [Google Gemini](https://gemini.google.com/)\n- [Microsoft Designer](https://designer.microsoft.com/)\n- [Adobe Firefly](https://firefly.adobe.com/)\n- [Canva](https://www.canva.com/)")
    upload = st.file_uploader("Unggah hasil gambar ke galeri sesi", type=["png", "jpg", "jpeg", "webp"], key="image_upload")
    if upload:
        raw = upload.getvalue()
        try:
            Image.open(io.BytesIO(raw)).verify()
            if st.button("➕ Simpan gambar ke galeri"):
                st.session_state.gallery.append({"kind":"image","name":upload.name,"data":raw,"created":datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.success("Gambar ditambahkan ke galeri sesi.")
        except Exception:
            st.error("File gambar tidak valid.")

elif selected_page == "🎬 Video AI":
    st.subheader("🎬 Video AI — Pembuat Prompt dan Storyboard")
    with st.form("video_form"):
        theme = st.text_input("Tema video", placeholder="Contoh: 5 langkah cuci tangan yang benar")
        duration = st.selectbox("Durasi", ["8 detik", "15 detik", "30 detik", "60 detik"])
        style = st.selectbox("Gaya video", ["Animasi edukasi", "Cinematic realistis", "Motion graphic", "Kartun ramah anak", "Dokumenter singkat"])
        platform = st.selectbox("Format", ["TikTok/Reels/Shorts 9:16", "YouTube 16:9", "Presentasi 16:9"])
        narration = st.checkbox("Sertakan narasi Bahasa Indonesia", value=True)
        submitted = st.form_submit_button("🎞️ Buat prompt dan storyboard", use_container_width=True)
    if submitted:
        if not theme.strip():
            st.warning("Masukkan tema video terlebih dahulu.")
        else:
            voice = "Sertakan narasi Bahasa Indonesia yang natural." if narration else "Tanpa narasi; gunakan visual dan teks singkat."
            st.session_state.video_prompt = (
                f"Buat video promosi kesehatan tentang '{theme.strip()}', durasi {duration}, format {platform}, "
                f"gaya {style.lower()}. {voice} Gunakan visual aman dan inklusif, transisi rapi, teks yang mudah dibaca. "
                "Hindari klaim medis berlebihan dan akhiri dengan ajakan mengakses sumber kesehatan resmi."
            )
            st.session_state.storyboard = [
                "Adegan 1 — Pembuka: situasi sehari-hari yang relevan.",
                "Adegan 2 — Pesan utama: jelaskan inti edukasi dengan visual sederhana.",
                "Adegan 3 — Tindakan: tampilkan langkah yang bisa dilakukan penonton.",
                "Adegan 4 — Penutup: ajakan bertindak dan rujukan sumber resmi.",
            ]
    if st.session_state.video_prompt:
        st.text_area("Prompt video siap disalin", value=st.session_state.video_prompt, height=170)
        st.markdown("**Storyboard**")
        for scene in st.session_state.storyboard:
            st.write("- " + scene)
    st.markdown("### Layanan video")
    st.markdown("- [Google Flow](https://flow.google.com/)\n- [PixVerse](https://pixverse.ai/)\n- [Adobe Firefly](https://firefly.adobe.com/)\n- [Canva](https://www.canva.com/)")
    upload = st.file_uploader("Unggah hasil video ke galeri sesi", type=["mp4", "mov", "webm"], key="video_upload")
    if upload and st.button("➕ Simpan video ke galeri"):
        st.session_state.gallery.append({"kind":"video","name":upload.name,"data":upload.getvalue(),"created":datetime.now().strftime("%d-%m-%Y %H:%M")})
        st.success("Video ditambahkan ke galeri sesi.")

elif selected_page == "🗂️ Galeri":
    st.subheader("🗂️ Galeri hasil")
    st.caption("Galeri ini tersimpan di sesi aktif; dapat hilang saat sesi direset atau aplikasi dimulai ulang.")
    if not st.session_state.gallery:
        st.info("Galeri masih kosong. Unggah hasil gambar/video dari menu Foto AI atau Video AI.")
    else:
        if st.button("🗑️ Kosongkan galeri"):
            st.session_state.gallery = []
            st.rerun()
        for index, item in enumerate(reversed(st.session_state.gallery)):
            st.divider()
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item['kind'].capitalize()} • {item['created']}")
            if item["kind"] == "image":
                st.image(item["data"], use_container_width=True)
                mime = "image/png" if item["name"].lower().endswith(".png") else "image/jpeg"
            else:
                st.video(item["data"])
                mime = "video/mp4" if item["name"].lower().endswith(".mp4") else "video/webm"
            st.download_button("⬇️ Unduh hasil", data=item["data"], file_name=item["name"], mime=mime, key=f"download_{index}_{item['name']}")

st.divider()
st.caption("Studio Promkes AI • Fokus pada layanan gratis. Kuota dan ketersediaan mengikuti kebijakan masing-masing penyedia AI.")
'''
req = """streamlit>=1.39.0
google-genai>=1.0.0
groq>=0.11.0
Pillow>=10.0.0
"""
readme = """# Studio Promkes AI — versi baru

## File yang dipakai
- `streamlit_app.py` — script utama
- `requirements.txt` — dependensi

## Pasang ke GitHub
1. Unduh ZIP ini lalu ekstrak.
2. Di repository GitHub `studiopromkesai` branch `main`, ganti isi `streamlit_app.py` dengan file dari ZIP.
3. Ganti `requirements.txt` dengan file dari ZIP.
4. Pastikan `streamlit_app.py` dan `requirements.txt` ada di root repository (sejajar, bukan di subfolder).
5. Jika repository punya `uv.lock` dan `pyproject.toml` lama yang tidak sesuai, hapus keduanya dari repository agar Streamlit Cloud menggunakan `requirements.txt` yang baru. Lakukan hanya jika memang file itu tidak dibutuhkan proyek lain.
6. Commit perubahan, lalu Reboot app di Streamlit Cloud.

## Secrets untuk Chat AI
Di Streamlit Cloud → app → Settings → Secrets, isi salah satu atau keduanya:

```toml
GEMINI_API_KEY = "API_KEY_GEMINI_KAMU"
GROQ_API_KEY = "API_KEY_GROQ_KAMU"
# Opsional:
# GEMINI_MODEL = "gemini-2.5-flash"
# GROQ_MODEL = "llama-3.3-70b-versatile"
```

Jangan taruh API key langsung di script atau GitHub. Tanpa API key, dashboard, Foto AI, Video AI, dan Galeri tetap dapat dibuka; Chat AI tidak dapat menjawab. Foto AI dan Video AI menyiapkan prompt, bukan membuat gambar/video secara langsung. Kuota gratis penyedia dapat berubah.
"""
(base/"streamlit_app.py").write_text(app_code, encoding="utf-8")
(base/"requirements.txt").write_text(req, encoding="utf-8")
(base/"README.md").write_text(readme, encoding="utf-8")
py_compile.compile(str(base/"streamlit_app.py"), doraise=True)
zip_path = Path("/mnt/data/studiopromkesai_script_baru.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for name in ("streamlit_app.py", "requirements.txt", "README.md"):
        z.write(base/name, arcname=f"studiopromkesai/{name}")
print("Berhasil dibuat dan lolos pemeriksaan sintaks Python.")
print(zip_path)
