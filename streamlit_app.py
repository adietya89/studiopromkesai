# -*- coding: utf-8 -*-
"""Studio Promkes AI — asisten serbaguna dan pembuat poster otomatis.
Simpan semua kredensial di Streamlit Secrets, jangan hardcode API key.
"""
import base64
import io
import json
import os
import re
import textwrap
from datetime import datetime

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title="Studio Promkes AI", page_icon="🩺", layout="wide")

SYSTEM_PROMPT = """Kamu adalah asisten AI serbaguna yang membantu dengan bahasa alami dan praktis.
Balas dalam bahasa pengguna, utamakan Bahasa Indonesia yang jelas dan ramah.
Pahami instruksi singkat; jika permintaan jelas, langsung kerjakan tanpa meminta prompt teknis.
Kamu dapat membantu menjawab pertanyaan, menulis, menyunting, menerjemahkan, meringkas,
menjelaskan pelajaran, matematika, coding, ide, rencana kerja, dokumen, caption, skrip,
dan materi edukasi. Jangan mengaku telah melakukan tindakan atau memeriksa sumber jika belum.
Jangan mengarang fakta, sumber, hasil pengujian, atau kemampuan alat yang tidak tersedia.
Untuk kesehatan, berikan edukasi yang bertanggung jawab, jangan mendiagnosis secara pasti,
menjanjikan kesembuhan, atau membuat klaim berlebihan. Sarankan tenaga kesehatan bila sesuai.
Berikan hasil yang siap digunakan, sesuai konteks, dengan struktur yang mudah dibaca."""

# -------------------- Secrets and API helpers --------------------
def secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip() if isinstance(os.getenv(name, default), str) else default


def post_json(url, headers, payload, timeout=90):
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        detail = response.text[:700].replace("\n", " ")
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")
    return response


def openai_compatible_text(base_url, api_key, model, messages):
    response = post_json(
        base_url.rstrip("/") + "/chat/completions",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        {"model": model, "messages": messages, "temperature": 0.7}, timeout=75,
    )
    data = response.json()
    return data["choices"][0]["message"]["content"]


def ask_text_ai(user_prompt, history=None, system_prompt=SYSTEM_PROMPT):
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-12:]:
            role = item.get("role")
            content = item.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content[:12000]})
    messages.append({"role": "user", "content": user_prompt})
    errors = []

    gemini_key = secret("GEMINI_API_KEY")
    if gemini_key:
        model = secret("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        try:
            prompt = "SYSTEM INSTRUCTIONS:\n" + system_prompt + "\n\nCONVERSATION:\n" + "\n".join(
                f"{m['role']}: {m['content']}" for m in messages[1:]
            )
            data = post_json(url, {"Content-Type": "application/json"},
                             {"contents": [{"parts": [{"text": prompt}]}],
                              "generationConfig": {"temperature": 0.7}}, timeout=75).json()
            text = "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
            if text.strip():
                return text.strip(), f"Gemini ({model})", errors
        except Exception as exc:
            errors.append(f"Gemini: {exc}")

    groq_key = secret("GROQ_API_KEY")
    if groq_key:
        try:
            model = secret("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
            answer = openai_compatible_text("https://api.groq.com/openai/v1", groq_key, model, messages)
            if answer.strip():
                return answer.strip(), f"Groq ({model})", errors
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    openrouter_key = secret("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            model = secret("OPENROUTER_TEXT_MODEL", "openrouter/auto")
            answer = openai_compatible_text("https://openrouter.ai/api/v1", openrouter_key, model, messages)
            if answer.strip():
                return answer.strip(), f"OpenRouter ({model})", errors
        except Exception as exc:
            errors.append(f"OpenRouter: {exc}")

    raise RuntimeError("Semua penyedia AI teks gagal atau belum dikonfigurasi. " + " | ".join(errors[-3:]))

# -------------------- Poster copy generation --------------------
POSTER_TEMPLATES = [
    (("dbd", "demam berdarah", "nyamuk"), "CEGAH DBD MULAI DARI RUMAH", "Kuras tempat penampungan air, tutup rapat, dan daur ulang barang bekas. Singkirkan genangan agar nyamuk tidak mudah berkembang biak.", "Ayo lakukan 3M Plus!"),
    (("cuci tangan", "kebersihan tangan"), "CUCI TANGAN PAKAI SABUN", "Basahi tangan, gunakan sabun, gosok seluruh bagian tangan, lalu bilas dengan air mengalir. Lakukan sebelum makan dan setelah dari toilet.", "Biasakan setiap hari!"),
    (("rokok", "merokok", "tembakau"), "RUMAH BEBAS ASAP ROKOK", "Asap rokok membahayakan perokok dan orang di sekitarnya. Jangan merokok di rumah, kendaraan, atau dekat anak dan ibu hamil.", "Lindungi keluarga kita!"),
    (("diabetes", "gula darah"), "KENALI RISIKO DIABETES", "Pilih makanan bergizi seimbang, aktif bergerak, dan lakukan pemeriksaan sesuai anjuran tenaga kesehatan. Risiko tiap orang dapat berbeda.", "Mulai kebiasaan sehat hari ini!"),
    (("hipertensi", "tekanan darah"), "PANTAU TEKANAN DARAH", "Batasi garam, rutin bergerak, dan periksa tekanan darah secara berkala. Ikuti saran tenaga kesehatan jika hasil pemeriksaan tinggi.", "Periksa, catat, kendalikan!"),
    (("stunting", "gizi anak", "gizi ibu"), "DUKUNG ANAK TUMBUH OPTIMAL", "Penuhi kebutuhan gizi ibu dan anak, pantau pertumbuhan secara rutin, dan konsultasikan masalah makan atau tumbuh kembang ke tenaga kesehatan.", "Datang ke Posyandu!"),
    (("imunisasi", "vaksin"), "IMUNISASI MELINDUNGI ANAK", "Ikuti jadwal imunisasi sesuai rekomendasi tenaga kesehatan. Bawa buku KIA atau catatan imunisasi saat berkunjung ke fasilitas kesehatan.", "Cek jadwal imunisasi!"),
    (("aktivitas fisik", "olahraga", "bergerak"), "AKTIF BERGERAK SETIAP HARI", "Kurangi duduk terlalu lama. Pilih kegiatan yang sesuai kemampuan, seperti berjalan kaki, bersepeda, atau bermain aktif bersama keluarga.", "Ayo mulai bergerak!"),
    (("gizi seimbang", "makanan sehat", "isi piringku"), "ISI PIRINGKU, GIZI SEIMBANG", "Lengkapi makanan dengan sumber karbohidrat, lauk berprotein, sayur, dan buah. Variasikan pilihan pangan dan minum air putih yang cukup.", "Makan beragam setiap hari!"),
    (("tbc", "tuberkulosis", "batuk lama"), "BATUK LAMA? PERIKSA TBC", "Batuk berkepanjangan perlu diperiksa. TBC dapat diobati; periksakan diri ke Puskesmas dan ikuti pengobatan sesuai petunjuk tenaga kesehatan.", "Periksa lebih awal!"),
    (("kesehatan mental", "stres", "kesehatan jiwa"), "KESEHATAN MENTAL ITU PENTING", "Istirahat cukup, jaga hubungan dengan orang tepercaya, dan cari bantuan profesional jika tekanan terasa berat atau mengganggu aktivitas.", "Tidak apa-apa meminta bantuan."),
    (("cek kesehatan gratis", "skrining", "pemeriksaan kesehatan"), "KENALI KESEHATANMU LEBIH DINI", "Pemeriksaan kesehatan dapat membantu mengenali faktor risiko. Tanyakan jenis pemeriksaan, jadwal, dan persyaratan kepada Puskesmas atau fasilitas kesehatan setempat.", "Tanyakan layanan di Puskesmas!"),
]


def create_poster_copy(topic):
    topic = (topic or "").strip() or "Perilaku Hidup Bersih dan Sehat"
    low = topic.casefold()
    for keywords, title, body, cta in POSTER_TEMPLATES:
        if any(word in low for word in keywords):
            return {"title": title, "body": body, "cta": cta, "source": "Template edukasi lokal"}

    prompt = f"""Buat naskah poster edukasi berbahasa Indonesia tentang tema: {topic}
Balas hanya JSON valid dengan kunci title, body, cta.
Batas: title 3-7 kata; body 25-40 kata berupa informasi praktis yang jelas; cta 3-7 kata.
Jangan mengulang tema tanpa penjelasan. Hindari klaim medis yang tidak berdasar.
Jangan menulis kata-kata bahasa Inggris kecuali nama resmi yang memang diperlukan.
Jika tema menyangkut layanan lokal, jangan mengarang jadwal, biaya, alamat, atau syarat.
"""
    try:
        answer, provider, _ = ask_text_ai(prompt, system_prompt=SYSTEM_PROMPT + "\nUntuk poster, hasil harus spesifik, jelas, dan layak dibaca masyarakat.")
        match = re.search(r"\{.*\}", answer, re.S)
        if match:
            data = json.loads(match.group(0))
            title = " ".join(str(data.get("title", "")).split())[:100]
            body = " ".join(str(data.get("body", "")).split())[:320]
            cta = " ".join(str(data.get("cta", "")).split())[:100]
            if title and body and cta:
                return {"title": title, "body": body, "cta": cta, "source": provider}
    except Exception:
        pass
    return {"title": "AYO HIDUP LEBIH SEHAT", "body": "Pilih kebiasaan sehat, cari informasi dari sumber tepercaya, dan konsultasikan pertanyaan kesehatan kepada tenaga kesehatan.", "cta": "Mulai dari langkah kecil!", "source": "Template otomatis"}

# -------------------- Image generation providers --------------------
def generate_gemini_image(prompt):
    key = secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY belum diatur")
    model = secret("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    data = post_json(url, {"Content-Type": "application/json"}, payload, timeout=180).json()
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"]), f"Gemini ({model})"
    raise RuntimeError("Gemini tidak mengembalikan data gambar. Periksa model dan akses API.")


def generate_cloudflare_image(prompt):
    token, account = secret("CLOUDFLARE_API_TOKEN"), secret("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        raise RuntimeError("Token atau Account ID Cloudflare belum diatur")
    model = secret("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    data = post_json(url, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                     {"prompt": prompt}, timeout=180).json()
    result = data.get("result", {})
    if result.get("image"):
        return base64.b64decode(result["image"]), f"Cloudflare ({model})"
    raise RuntimeError("Cloudflare tidak mengembalikan gambar: " + str(data)[:400])


def generate_huggingface_image(prompt):
    token = secret("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN belum diatur")
    model = secret("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    response = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                             json={"inputs": prompt, "parameters": {"width": 1024, "height": 1024}}, timeout=180)
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    if "image" not in response.headers.get("content-type", "") and not response.content.startswith(b"\x89PNG") and not response.content.startswith(b"\xff\xd8"):
        raise RuntimeError("Hugging Face tidak mengembalikan file gambar: " + response.text[:300])
    return response.content, f"Hugging Face ({model})"


def generate_image(prompt):
    errors = []
    providers = [
        ("Gemini", generate_gemini_image),
        ("Cloudflare", generate_cloudflare_image),
        ("Hugging Face", generate_huggingface_image),
    ]
    preferred = secret("IMAGE_PROVIDER_ORDER", "Gemini,Cloudflare,Hugging Face")
    order = [x.strip().lower() for x in preferred.split(",")]
    providers.sort(key=lambda item: order.index(item[0].lower()) if item[0].lower() in order else 99)
    for name, fn in providers:
        try:
            image_bytes, label = fn(prompt)
            # Verify bytes are actually an image before reporting success.
            Image.open(io.BytesIO(image_bytes)).verify()
            return image_bytes, label, errors
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError("Semua penyedia gambar gagal. " + " | ".join(errors))

# -------------------- Indonesian text layout --------------------
def load_font(size, bold=False):
    paths = ([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ])
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = str(text or "").split()
    lines, line = [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            # Split an unusually long token to avoid clipping.
            if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                chunk = ""
                for char in word:
                    if draw.textbbox((0, 0), chunk + char, font=font)[2] <= max_width:
                        chunk += char
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = char
                line = chunk
            else:
                line = word
    if line:
        lines.append(line)
    return lines


def add_indonesian_poster_text(image_bytes, title, body, cta, topic=""):
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Preserve image composition while fitting a clean 4:5 poster canvas.
    W, H = 1080, 1350
    original.thumbnail((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (W, H), "#EAF5F1")
    x, y = (W-original.width)//2, (H-original.height)//2
    canvas.paste(original, (x, y))
    draw = ImageDraw.Draw(canvas)

    # Solid, high-contrast panels keep all copy legible and cover AI-generated gibberish at edges.
    draw.rounded_rectangle((34, 28, W-34, 330), radius=30, fill="#103F46")
    draw.rounded_rectangle((34, 965, W-34, H-28), radius=30, fill="#FFFFFF")
    draw.rounded_rectangle((70, 1000, W-70, 1009), radius=5, fill="#169B85")

    title = " ".join(str(title or "AYO HIDUP LEBIH SEHAT").split()).upper()
    body = " ".join(str(body or "Terapkan kebiasaan sehat dan cari informasi dari tenaga kesehatan.").split())
    cta = " ".join(str(cta or "Mulai dari hari ini!").split())
    max_width = W - 140

    title_size = 58
    while title_size > 36:
        tf = load_font(title_size, True)
        title_lines = wrap_text(draw, title, tf, max_width)
        if len(title_lines) <= 3:
            break
        title_size -= 3
    tf = load_font(title_size, True)
    title_lines = wrap_text(draw, title, tf, max_width)[:3]
    line_heights = [draw.textbbox((0, 0), line, font=tf)[3] for line in title_lines]
    total_h = sum(line_heights) + 10 * max(0, len(title_lines)-1)
    ty = 178 - total_h // 2
    for line, line_h in zip(title_lines, line_heights):
        box = draw.textbbox((0, 0), line, font=tf)
        draw.text(((W-(box[2]-box[0]))//2, ty), line, font=tf, fill="#FFFFFF")
        ty += line_h + 10

    # Body area sized for readable 26-32px text, max 5 lines.
    body_size = 32
    while body_size > 24:
        bf = load_font(body_size, False)
        body_lines = wrap_text(draw, body, bf, max_width)
        if len(body_lines) <= 5:
            break
        body_size -= 2
    bf = load_font(body_size, False)
    body_lines = wrap_text(draw, body, bf, max_width)[:5]
    by = 1018
    for line in body_lines:
        box = draw.textbbox((0, 0), line, font=bf)
        draw.text(((W-(box[2]-box[0]))//2, by), line, font=bf, fill="#193D3B")
        by += (box[3]-box[1]) + 9

    cta_size = 32
    cf = load_font(cta_size, True)
    cta_lines = wrap_text(draw, cta, cf, max_width)[:2]
    cta_height = sum(draw.textbbox((0,0), line, font=cf)[3] for line in cta_lines) + 5 * len(cta_lines)
    cy = min(max(by + 18, 1240), H - 35 - cta_height)
    for line in cta_lines:
        box = draw.textbbox((0, 0), line, font=cf)
        draw.text(((W-(box[2]-box[0]))//2, cy), line, font=cf, fill="#087F70")
        cy += (box[3]-box[1]) + 5

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=94, optimize=True)
    return out.getvalue()

# -------------------- UI --------------------
st.title("🩺 Studio Promkes AI")
st.caption("Asisten AI serbaguna • Materi edukasi • Poster dengan teks Bahasa Indonesia")
with st.sidebar:
    st.header("Menu")
    page = st.radio("Pilih fitur", ["Chat AI", "Buat Poster", "Pengaturan API"], label_visibility="collapsed")
    st.divider()
    st.caption("API key disimpan di Streamlit Secrets. Jangan masukkan token ke kode publik.")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "poster_result" not in st.session_state:
    st.session_state.poster_result = None

if page == "Chat AI":
    st.subheader("💬 Chat AI serbaguna")
    st.write("Tulis apa saja yang ingin kamu kerjakan. Kamu tidak perlu membuat prompt teknis.")
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    prompt = st.chat_input("Tanyakan sesuatu atau minta AI membuat sesuatu…")
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Hapus chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("AI sedang berpikir…"):
                try:
                    history = st.session_state.chat_messages[:-1]
                    answer, provider, errors = ask_text_ai(prompt, history)
                    st.markdown(answer)
                    st.caption(f"Penyedia: {provider}")
                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                except Exception as exc:
                    st.error(str(exc))
                    st.info("Tambahkan minimal satu API key teks di Streamlit Secrets, misalnya GEMINI_API_KEY, GROQ_API_KEY, atau OPENROUTER_API_KEY.")

elif page == "Buat Poster":
    st.subheader("🎨 Pembuat poster otomatis")
    st.write("Masukkan tema saja. AI akan menyusun teks edukasi dan membuat ilustrasi tanpa tulisan; aplikasi menempelkan teks yang benar setelah gambar dibuat.")
    with st.form("poster_form"):
        topic = st.text_input("Tema poster", placeholder="Contoh: pencegahan DBD, gizi seimbang, cek kesehatan gratis")
        style = st.selectbox("Gaya ilustrasi", ["Ilustrasi vektor modern", "Ilustrasi editorial profesional", "Ilustrasi ramah keluarga", "Fotografi realistis"])
        palette = st.selectbox("Warna desain", ["Hijau teal dan putih", "Biru dan putih", "Oranye hangat", "Warna cerah edukatif"])
        submitted = st.form_submit_button("✨ Buat poster otomatis", type="primary", use_container_width=True)
    if submitted:
        if not topic.strip():
            topic = "Perilaku Hidup Bersih dan Sehat"
        copy = create_poster_copy(topic)
        visual_prompt = (
            f"Create a polished {style.lower()} background illustration for a public health education poster about {topic}. "
            f"Color palette: {palette}. Indonesian community context, professional composition, clear central visual, "
            "simple uncluttered background, high-quality editorial design. Absolutely NO text, NO letters, NO words, "
            "NO numbers, NO logos, NO watermarks, NO typography. Image only; leave calm negative space for text panels."
        )
        try:
            with st.spinner("Menyusun ilustrasi poster. Penyedia gambar akan dicoba bergantian jika tersedia…"):
                image_bytes, provider, errors = generate_image(visual_prompt)
                poster_bytes = add_indonesian_poster_text(image_bytes, copy["title"], copy["body"], copy["cta"], topic)
            st.session_state.poster_result = {"bytes": poster_bytes, "copy": copy, "provider": provider, "topic": topic}
            st.success(f"Poster berhasil dibuat menggunakan {provider}.")
        except Exception as exc:
            st.error(str(exc))
            st.warning("Periksa kuota, akses model, serta API key di Streamlit Secrets. Fallback hanya bisa bekerja jika penyedia lain memiliki akses dan kuota aktif.")
    result = st.session_state.poster_result
    if result:
        st.markdown("### Hasil poster")
        st.image(result["bytes"], use_container_width=True)
        st.markdown("**Teks poster yang digunakan**")
        st.markdown(f"**{result['copy']['title']}**\n\n{result['copy']['body']}\n\n**{result['copy']['cta']}**")
        st.caption(f"Teks: {result['copy']['source']} • Gambar: {result['provider']}")
        st.download_button("⬇️ Unduh poster JPG", data=result["bytes"], file_name="poster_promkes_ai.jpg", mime="image/jpeg", use_container_width=True)

else:
    st.subheader("🔐 Pengaturan API")
    st.write("Tambahkan key di Streamlit → App settings → Secrets. Jangan menulis API key langsung di file Python atau GitHub.")
    st.code('''GEMINI_API_KEY = "isi_key_baru_di_sini"
GROQ_API_KEY = "isi_key_groq_jika_ada"
OPENROUTER_API_KEY = "isi_key_openrouter_jika_ada"
HF_TOKEN = "isi_token_huggingface_jika_ada"
CLOUDFLARE_API_TOKEN = "isi_token_cloudflare_jika_ada"
CLOUDFLARE_ACCOUNT_ID = "isi_account_id_cloudflare_jika_ada"

# Opsional, ubah hanya jika model default tidak tersedia:
# GEMINI_TEXT_MODEL = "gemini-2.5-flash"
# GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
# CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
# HF_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
''', language="toml")
    st.info("Pakai key baru yang sudah diregenerasi. Token yang pernah dibagikan di chat sebaiknya dicabut.")
    configured = {
        "Gemini": bool(secret("GEMINI_API_KEY")),
        "Groq": bool(secret("GROQ_API_KEY")),
        "OpenRouter": bool(secret("OPENROUTER_API_KEY")),
        "Cloudflare (token + account ID)": bool(secret("CLOUDFLARE_API_TOKEN") and secret("CLOUDFLARE_ACCOUNT_ID")),
        "Hugging Face": bool(secret("HF_TOKEN")),
    }
    for name, is_set in configured.items():
        st.write(("✅ " if is_set else "⚪ ") + name + (" terkonfigurasi" if is_set else " belum diatur"))

st.divider()
st.caption("Studio Promkes AI • Periksa materi kesehatan dengan sumber resmi/tenaga kesehatan sebelum publikasi.")
