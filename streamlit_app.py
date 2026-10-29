import os
import io
import json
import re
import base64
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

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
PAGES = ["🏠 Dashboard", "💬 Chat AI", "🖼️ Foto AI", "🎬 Video AI", "🗂️ Galeri"]
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
IMAGE_MODEL_DEFAULT = "gemini-nano-banana-2.1"
VIDEO_MODEL_DEFAULT = "gemini-omni-1.1-flash"

# =========================================================
# DESAIN
# =========================================================
st.markdown("""
<style>
.stApp {background: radial-gradient(circle at 0% 0%, #d9f5ef 0%, transparent 28%), radial-gradient(circle at 100% 0%, #dbeafe 0%, transparent 30%), #f6f9fc;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #073b4c, #075985, #0f766e);}
[data-testid="stSidebar"] * {color: white;}
.hero {background: linear-gradient(120deg, #075985, #0f766e); padding: 28px; border-radius: 20px; color: white; margin-bottom: 22px; box-shadow: 0 8px 24px rgba(7,89,133,.16);}
.hero h1 {color: white; margin-bottom: 8px;}
.hero p {color: #e0f2fe; font-size: 16px; margin-bottom: 0;}
.feature-card {background: white; border: 1px solid #dbeafe; border-radius: 17px; padding: 20px; min-height: 145px; box-shadow: 0 5px 18px rgba(15,23,42,.06);}
.feature-card h3 {color: #075985;}
.stButton > button {border-radius: 11px; font-weight: 600; min-height: 42px;}
h1, h2, h3 {color: #123047;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = os.getenv(name, default)
    return str(value or "").strip()


def get_ai_status():
    return {"Gemini": bool(get_secret("GEMINI_API_KEY")), "Groq": bool(get_secret("GROQ_API_KEY"))}


def get_gemini_client():
    """Membuat klien Gemini dengan timeout eksplisit agar request tidak menggantung."""
    api_key = get_secret("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY belum dipasang di Streamlit Secrets. "
            "Buka App settings → Secrets dan tambahkan API key Gemini."
        )

    if genai is None:
        raise RuntimeError(
            "Paket google-genai belum terpasang. "
            "Pastikan google-genai tercantum di requirements.txt lalu redeploy."
        )

    try:
        from google.genai import types
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )
    except ImportError as exc:
        raise RuntimeError(
            "SDK google-genai tidak menyediakan konfigurasi HttpOptions. "
            "Perbarui versi google-genai di requirements.txt lalu redeploy."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "Klien Gemini gagal dibuat. Periksa versi paket google-genai dan konfigurasi API key. "
            f"Detail: {str(exc)[:500]}"
        ) from exc


def extract_image_bytes(interaction):
    block = getattr(interaction, "output_image", None)
    data = getattr(block, "data", None) if block else None
    if data:
        return base64.b64decode(data)
    for step in getattr(interaction, "steps", []) or []:
        if getattr(step, "type", "") == "model_output":
            for content in getattr(step, "content", []) or []:
                if getattr(content, "type", "") == "image":
                    data = getattr(content, "data", None)
                    if data:
                        return base64.b64decode(data)
    raise RuntimeError("Model tidak mengembalikan gambar. Periksa nama model, kuota, atau coba prompt lebih sederhana.")


def extract_video_bytes(interaction):
    block = getattr(interaction, "output_video", None)
    data = getattr(block, "data", None) if block else None
    if data:
        return base64.b64decode(data)
    for step in getattr(interaction, "steps", []) or []:
        if getattr(step, "type", "") == "model_output":
            for content in getattr(step, "content", []) or []:
                if getattr(content, "type", "") == "video":
                    data = getattr(content, "data", None)
                    if data:
                        return base64.b64decode(data)
    raise RuntimeError("Model tidak mengembalikan video. Periksa akses model video, kuota, atau coba prompt lebih sederhana.")

# =========================================================
# CHAT AI
# =========================================================
SYSTEM_PROMPT = """
Kamu adalah asisten AI serbaguna di Studio Promkes AI. Bantu pengguna seperti asisten percakapan modern untuk beragam tugas, bukan hanya promosi kesehatan.

BAHASA DAN GAYA
- Balas dalam bahasa yang digunakan pengguna; utamakan Bahasa Indonesia yang alami, jelas, ramah, dan tidak bertele-tele.
- Pahami instruksi sehari-hari meskipun singkat atau tidak formal. Jangan meminta pengguna menyusun prompt teknis.
- Jika maksudnya jelas, langsung kerjakan. Jika detail kecil tidak disebutkan, pilih asumsi wajar dan lanjutkan.
- Sesuaikan format dengan tugas: daftar, tabel, langkah, contoh, kode, naskah, atau hasil jadi.

KEMAMPUAN
- Menjawab pertanyaan umum, menjelaskan konsep, belajar, matematika, brainstorming, dan pemecahan masalah.
- Menulis, menyunting, menerjemahkan, meringkas, membuat surat, laporan, proposal, makalah, presentasi, caption, dan naskah.
- Membantu coding, membaca error, memperbaiki kode, dan menjelaskan implementasi.
- Menyusun ide kampanye, materi edukasi, konsep poster, arahan visual, skrip video, dan konten media sosial.
- Untuk permintaan pembuatan konten, berikan hasil yang siap digunakan, bukan hanya saran.

KETELITIAN
- Jangan mengarang fakta, kutipan, sumber, hasil pengujian, akses internet, atau tindakan yang belum dilakukan.
- Jika tidak memiliki akses ke file, internet, atau layanan eksternal, jelaskan batasannya dengan jujur.
- Untuk kode, prioritaskan kode konsisten dan dapat dijalankan; sebutkan dependensi dan konfigurasi yang diperlukan.
- Bedakan fakta dari perkiraan dan opini.

KESEHATAN
- Materi kesehatan harus edukatif, mudah dipahami, dan tidak menakut-nakuti.
- Jangan memberikan diagnosis pasti, menjanjikan kesembuhan, atau membuat klaim medis tanpa dasar.
- Untuk kondisi gawat darurat, sarankan segera mencari bantuan medis.

TUJUAN
Pahami kebutuhan pengguna, tentukan pendekatan paling sesuai secara otomatis, lalu berikan hasil paling berguna tanpa membebani pengguna dengan pertanyaan yang tidak perlu.
"""


def ask_gemini(history, prompt):
    client = get_gemini_client()
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
            messages.append({"role": item["role"], "content": item["content"]})
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
        return None, None, ["API key belum dipasang di Streamlit Secrets."]
    errors = []
    for name, function in providers:
        try:
            return function(history, prompt), name, errors
        except Exception as exc:
            error_text = str(exc).lower()
            if any(word in error_text for word in ["quota", "429", "rate limit", "resource_exhausted", "too many requests"]):
                errors.append(f"{name}: kuota atau batas permintaan tercapai.")
            else:
                errors.append(f"{name}: layanan gagal merespons. Periksa API key, model, dan log aplikasi.")
    return None, None, errors


def create_poster_copy(topic):
    """Buat salinan poster ringkas; gunakan AI lalu template lokal bila layanan teks gagal."""
    topic = (topic or "").strip() or "perilaku hidup bersih dan sehat"
    low = topic.lower()
    templates = [
        (("dbd", "demam berdarah", "nyamuk"), ("CEGAH DBD MULAI HARI INI", "Kuras tempat penampungan air, tutup rapat, dan daur ulang barang bekas. Cegah nyamuk berkembang biak di sekitar rumah.", "Ayo lakukan 3M Plus!")),
        (("cuci tangan", "kebersihan tangan"), ("BIASAKAN CUCI TANGAN", "Cuci tangan pakai sabun dan air mengalir sebelum makan dan setelah dari toilet.", "Lakukan setiap hari!")),
        (("rokok", "merokok", "tembakau"), ("HIDUP SEHAT TANPA ROKOK", "Asap rokok membahayakan kesehatan. Jaga rumah dan lingkungan bebas asap rokok.", "Lindungi diri dan keluarga!")),
        (("diabetes", "gula darah"), ("CEGAH DIABETES DENGAN HIDUP SEHAT", "Pilih makanan bergizi seimbang, aktif bergerak, dan periksa kesehatan secara berkala.", "Mulai kebiasaan sehat hari ini!")),
        (("hipertensi", "tekanan darah"), ("KENDALIKAN TEKANAN DARAH", "Batasi konsumsi garam, rutin bergerak, dan periksa tekanan darah secara berkala.", "Jaga kesehatan jantung!")),
        (("stunting", "gizi anak", "gizi ibu"), ("DUKUNG ANAK TUMBUH SEHAT", "Penuhi gizi ibu dan anak, pantau tumbuh kembang, dan konsultasikan kebutuhan gizi ke tenaga kesehatan.", "Mulai dari keluarga!")),
        (("imunisasi", "vaksin"), ("IMUNISASI LINDUNGI KITA", "Ikuti jadwal imunisasi sesuai anjuran tenaga kesehatan untuk membantu melindungi anak dari penyakit yang dapat dicegah.", "Cek jadwal di Puskesmas!")),
    ]
    for keywords, result in templates:
        if any(word in low for word in keywords):
            return (*result, "Template kesehatan lokal")

    prompt = (
        "Buat teks poster promosi kesehatan dalam Bahasa Indonesia tentang tema: " + topic + ". "
        "Kembalikan JSON valid saja dengan kunci title, body, cta. title maksimal 6 kata; "
        "body maksimal 18 kata dalam 1-2 kalimat; cta maksimal 6 kata. Teks konkret, alami, mudah dibaca, "
        "tidak mengulang instruksi, tanpa klaim medis berlebihan."
    )
    try:
        answer, provider, _errors = ask_ai([], prompt)
        if answer:
            match = re.search(r"\{.*?\}", answer, flags=re.S)
            if match:
                data = json.loads(match.group(0))
                title = " ".join(str(data.get("title", "")).split())
                body = " ".join(str(data.get("body", "")).split())
                cta = " ".join(str(data.get("cta", "")).split())
                title = " ".join(title.split()[:6])[:48].strip()
                body = " ".join(body.split()[:18])[:145].strip()
                cta = " ".join(cta.split()[:6])[:42].strip()
                if title and body and cta:
                    return title, body, cta, provider or "AI teks"
    except Exception:
        pass
    return ("AYO HIDUP LEBIH SEHAT",
            "Terapkan kebiasaan sehat, pilih informasi tepercaya, dan konsultasikan kesehatan kepada tenaga kesehatan.",
            "Mulai dari hari ini!", "Template otomatis")


# =========================================================
# FOTO AI: GENERATE DARI TEKS ATAU EDIT FOTO
# =========================================================
def _generate_image_gemini(instruction, image_bytes=None, mime_type="image/jpeg", aspect_ratio="3:4"):
    """Mencoba membuat/mengedit gambar melalui Gemini REST API."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum dipasang.")

    model = get_secret("GEMINI_IMAGE_MODEL", IMAGE_MODEL_DEFAULT)
    prompt = (
        "Buat ILUSTRASI/LATAR visual saja untuk poster promosi kesehatan masyarakat Indonesia. "
        "JANGAN membuat huruf, kata, angka, logo, watermark, atau tulisan apa pun di gambar. "
        "Sisakan area yang cukup bersih di bagian atas dan bawah untuk teks yang akan ditambahkan aplikasi. "
        "Hindari klaim kesehatan yang tidak didukung. Instruksi visual: " + instruction
    )
    if image_bytes is None:
        api_input = prompt
    else:
        api_input = [
            {"type": "text", "text": (
                "Edit gambar yang diberikan sesuai instruksi. Pertahankan subjek utama bila relevan. "
                "Untuk poster, gunakan Bahasa Indonesia yang benar dan teks mudah dibaca. "
                "Hindari klaim kesehatan yang tidak diminta. Instruksi: " + instruction
            )},
            {"type": "image", "data": base64.b64encode(image_bytes).decode("utf-8"),
             "mime_type": mime_type or "image/jpeg"},
        ]

    payload = {
        "model": model,
        "input": api_input,
        "response_format": {"type": "image", "mime_type": "image/jpeg",
                            "aspect_ratio": aspect_ratio, "image_size": "1K"},
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            details = json.loads(body)
            message = details.get("error", {}).get("message", body)
        except Exception:
            message = "Respons error tidak dapat dibaca."
        raise RuntimeError(f"Gemini HTTP {exc.code}: {message[:700]}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Gemini tidak dapat dihubungi/timeout: {str(reason)[:400]}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini mengirim respons yang bukan JSON valid.") from exc

    output_image = response_data.get("output_image") or {}
    image_data = output_image.get("data") if isinstance(output_image, dict) else None
    if image_data:
        return base64.b64decode(image_data)
    for step in response_data.get("steps", []) or []:
        if step.get("type") == "model_output":
            for content in step.get("content", []) or []:
                if content.get("type") == "image" and content.get("data"):
                    return base64.b64decode(content["data"])
    error = response_data.get("error")
    if error:
        message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise RuntimeError(f"Gemini gagal membuat gambar: {message[:700]}")
    raise RuntimeError("Gemini merespons tetapi tidak menyertakan gambar.")


def _generate_image_huggingface(instruction, image_bytes=None, aspect_ratio="3:4"):
    """Fallback gambar via Hugging Face Inference Providers; memerlukan HF_TOKEN."""
    token = get_secret("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN belum dipasang di Streamlit Secrets.")
    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        raise RuntimeError("Paket huggingface_hub belum terpasang. Tambahkan huggingface_hub ke requirements.txt lalu redeploy.") from exc

    prompt = (
        "Create ONLY a clean illustration/background for a public-health poster for an Indonesian audience. "
        "Do NOT draw any text, letters, numbers, logos, labels, or watermark. Leave clean space at the top and bottom for text to be added later. "
        "Use respectful imagery, no unsupported medical claims. Visual direction: " + instruction
    )
    client = InferenceClient(api_key=token, provider="auto", timeout=120)
    if image_bytes:
        # Image-to-image fallback. Model/provider availability depends on the HF account.
        result = client.image_to_image(
            image_bytes,
            prompt="Edit the provided image following this instruction: " + prompt,
            model="black-forest-labs/FLUX.2-klein-9B",
        )
    else:
        result = client.text_to_image(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-schnell",
        )
    output = io.BytesIO()
    result.convert("RGB").save(output, format="JPEG", quality=92)
    return output.getvalue()


def _generate_image_cloudflare(instruction, image_bytes=None, mime_type="image/jpeg", aspect_ratio="3:4"):
    """Fallback gambar via Cloudflare Workers AI REST API."""
    token = get_secret("CLOUDFLARE_API_TOKEN")
    account_id = get_secret("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN belum dipasang di Streamlit Secrets.")
    if not account_id or account_id.lower() == "workers ai" or not re.fullmatch(r"[a-fA-F0-9]{32}", account_id):
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID harus berupa Account ID Cloudflare 32 karakter heksadesimal, bukan nama token atau tulisan 'Workers AI'.")
    if image_bytes:
        raise RuntimeError("Fallback Cloudflare saat ini mendukung pembuatan gambar dari teks, bukan edit gambar yang diunggah. Hapus foto unggahan atau gunakan Gemini dengan kuota aktif.")

    prompt = (
        "Create ONLY a clean illustration/background for a public-health poster for an Indonesian audience. "
        "Do NOT draw any text, letters, numbers, logos, labels, or watermark. Leave clean space at the top and bottom for text to be added by the app. "
        "Use respectful imagery and avoid unsupported medical claims. Visual direction: " + instruction
    )
    model = get_secret("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    payload = {"prompt": prompt}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            errors = parsed.get("errors", [])
            message = "; ".join(str(e.get("message", e)) for e in errors) or body
        except Exception:
            message = "Respons error tidak dapat dibaca."
        raise RuntimeError(f"Cloudflare HTTP {exc.code}: {message[:700]}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Cloudflare tidak dapat dihubungi/timeout: {str(reason)[:400]}") from exc
    result = response_data.get("result") or {}
    image_b64 = result.get("image") if isinstance(result, dict) else None
    if image_b64:
        return base64.b64decode(image_b64)
    raise RuntimeError("Cloudflare merespons tetapi tidak mengembalikan gambar. Periksa model dan respons API.")


def generate_or_edit_image(instruction, image_bytes=None, mime_type="image/jpeg", aspect_ratio="3:4"):
    """Coba Gemini, lalu Hugging Face, lalu Cloudflare Workers AI."""
    errors = []
    if get_secret("GEMINI_API_KEY"):
        try:
            image = _generate_image_gemini(instruction, image_bytes, mime_type, aspect_ratio)
            st.session_state.last_image_provider = "Gemini"
            return image
        except Exception as exc:
            errors.append(("Gemini", str(exc)))
    else:
        errors.append(("Gemini", "GEMINI_API_KEY belum dipasang."))

    if get_secret("HF_TOKEN"):
        try:
            image = _generate_image_huggingface(instruction, image_bytes, aspect_ratio)
            st.session_state.last_image_provider = "Hugging Face (cadangan)"
            st.session_state.last_image_fallback_reason = errors[-1][1]
            return image
        except Exception as exc:
            errors.append(("Hugging Face", str(exc)))

    if get_secret("CLOUDFLARE_API_TOKEN") and get_secret("CLOUDFLARE_ACCOUNT_ID"):
        try:
            image = _generate_image_cloudflare(instruction, image_bytes, mime_type, aspect_ratio)
            st.session_state.last_image_provider = "Cloudflare Workers AI (cadangan)"
            st.session_state.last_image_fallback_reason = "; ".join(f"{name}: {msg[:250]}" for name, msg in errors)
            return image
        except Exception as exc:
            errors.append(("Cloudflare", str(exc)))
    else:
        errors.append(("Cloudflare", "CLOUDFLARE_API_TOKEN atau CLOUDFLARE_ACCOUNT_ID belum dipasang."))

    detail = " | ".join(f"{name}: {message[:650]}" for name, message in errors)
    raise RuntimeError("Semua penyedia gambar yang dikonfigurasi gagal. " + detail)

def _load_poster_font(size, bold=False):
    """Load font with Indonesian character support; use a safe fallback if unavailable."""
    candidates = ([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_poster_text(draw, text, font, max_width):
    """Wrap Indonesian text into lines that fit the poster width."""
    words = str(text or "").split()
    lines, line = [], ""
    for word in words:
        candidate = word if not line else line + " " + word
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            # Break a single unusually long word safely.
            if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                piece = ""
                for char in word:
                    if draw.textbbox((0, 0), piece + char, font=font)[2] > max_width and piece:
                        lines.append(piece)
                        piece = char
                    else:
                        piece += char
                line = piece
            else:
                line = word
    if line:
        lines.append(line)
    return lines


def add_indonesian_poster_text(image_bytes, title, body, call_to_action="Mulai dari diri sendiri, mulai hari ini!"):
    """Render exact text with Pillow so poster wording is not hallucinated by the image model."""
    try:
        base = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise RuntimeError("Gambar latar dari AI tidak dapat dibaca untuk penambahan teks.") from exc

    # Keep a consistent poster layout, adapted to any provider image dimensions.
    width, height = base.size
    scale = max(width / 900, height / 1200, 0.75)
    pad = max(24, int(width * 0.055))
    header_h = max(int(height * 0.20), int(170 * scale))
    footer_h = max(int(height * 0.29), int(220 * scale))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    navy = (7, 59, 76, 238)
    teal = (15, 118, 110, 232)
    draw.rounded_rectangle((pad // 2, pad // 2, width - pad // 2, header_h), radius=max(18, int(20*scale)), fill=navy)

    title_font = _load_poster_font(max(28, int(width * 0.068)), bold=True)
    body_font = _load_poster_font(max(22, int(width * 0.040)), bold=False)
    cta_font = _load_poster_font(max(22, int(width * 0.043)), bold=True)
    max_text_w = width - 2 * pad
    title_lines = _wrap_poster_text(draw, (title or "PROMOSI KESEHATAN").strip().upper(), title_font, max_text_w)
    # Limit headline lines so it never crowds the visual.
    title_lines = title_lines[:3]
    line_gap = max(5, int(7 * scale))
    title_heights = [draw.textbbox((0, 0), line, font=title_font)[3] for line in title_lines]
    total_title_h = sum(title_heights) + line_gap * max(0, len(title_lines)-1)
    y = max(pad // 2 + 8, (header_h - total_title_h) // 2)
    for line, line_h in zip(title_lines, title_heights):
        box = draw.textbbox((0, 0), line, font=title_font)
        x = (width - (box[2]-box[0])) // 2
        draw.text((x, y), line, font=title_font, fill=(255,255,255,255), stroke_width=max(0, int(scale)), stroke_fill=(0,0,0,90))
        y += line_h + line_gap

    # Bottom panel holds exact, selectable Indonesian text.
    footer_top = height - footer_h
    draw.rounded_rectangle((pad // 2, footer_top, width - pad // 2, height - pad // 2), radius=max(18, int(20*scale)), fill=teal)
    body_text = (body or "Jaga kesehatan dengan membiasakan perilaku hidup bersih dan sehat.").strip()
    body_text = " ".join(body_text.split())[:145]
    cta_text = " ".join((call_to_action or "Mulai dari hari ini!").split())[:42]
    body_lines = _wrap_poster_text(draw, body_text, body_font, max_text_w)[:4]
    cta_lines = _wrap_poster_text(draw, cta_text, cta_font, max_text_w)[:2]
    body_line_heights = [draw.textbbox((0,0), line, font=body_font)[3] for line in body_lines]
    cta_line_heights = [draw.textbbox((0,0), line, font=cta_font)[3] for line in cta_lines]
    gap = max(4, int(5*scale))
    total_h = sum(body_line_heights) + gap * max(0,len(body_lines)-1) + (int(12*scale) if cta_lines else 0) + sum(cta_line_heights) + gap * max(0,len(cta_lines)-1)
    y = footer_top + max(8, (footer_h-total_h)//2)
    for line, line_h in zip(body_lines, body_line_heights):
        box = draw.textbbox((0,0), line, font=body_font)
        draw.text(((width-(box[2]-box[0]))//2, y), line, font=body_font, fill=(255,255,255,255))
        y += line_h + gap
    if cta_lines:
        y += int(5*scale)
    for line, line_h in zip(cta_lines, cta_line_heights):
        box = draw.textbbox((0,0), line, font=cta_font)
        draw.text(((width-(box[2]-box[0]))//2, y), line, font=cta_font, fill=(255,245,180,255))
        y += line_h + gap

    composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    output = io.BytesIO()
    composed.save(output, format="JPEG", quality=94, optimize=True)
    return output.getvalue()


# =========================================================
# VIDEO AI: GENERATE DARI TEKS
# =========================================================
def generate_video_from_text(instruction, aspect_ratio="9:16"):
    client = get_gemini_client()
    model = get_secret("GEMINI_VIDEO_MODEL", VIDEO_MODEL_DEFAULT)
    prompt = (
        "Create a short, polished, realistic educational public-health video for an Indonesian audience. "
        "Use respectful, non-alarming visuals, no misleading medical claims, and no on-screen text unless it can be rendered clearly. "
        "Video concept: " + instruction
    )
    interaction = client.interactions.create(
        model=model,
        input=prompt,
        response_format={"type": "video", "aspect_ratio": aspect_ratio},
    )
    return extract_video_bytes(interaction)

# =========================================================
# VIDEO AI: EDIT VIDEO UNGGAHAN DENGAN FFMPEG
# =========================================================
def get_ffmpeg_path():
    if imageio_ffmpeg is None:
        raise RuntimeError("Paket imageio-ffmpeg belum terpasang. Tambahkan ke requirements.txt.")
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_video_edit_plan(instruction):
    prompt = f'''Ubah perintah edit video berikut menjadi JSON SAJA, tanpa markdown.
Perintah pengguna: {instruction!r}
Gunakan hanya skema ini:
{{"trim_seconds": null, "aspect": "original", "grayscale": false, "brightness": 0.0, "mute": false}}
Aturan:
- trim_seconds: angka detik jika diminta dipotong menjadi durasi tertentu (maksimal 180), selain itu null.
- aspect: original, vertical, horizontal, atau square. Vertical untuk Reels/TikTok, horizontal untuk YouTube, square untuk 1:1.
- grayscale: true hanya jika diminta hitam putih/monokrom.
- brightness: angka antara -0.15 dan 0.15.
- mute: true jika diminta menghilangkan suara.
Jangan menambahkan operasi lain. Jika tidak jelas, gunakan nilai default.'''
    answer = ask_gemini([], prompt)
    cleaned = answer.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("AI memberikan format rencana yang tidak valid. Coba perintah lebih sederhana.")
    plan = json.loads(cleaned[start:end + 1])
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
    return {"trim_seconds": trim, "aspect": aspect, "grayscale": bool(plan.get("grayscale", False)), "brightness": brightness, "mute": bool(plan.get("mute", False))}


def process_video(input_bytes, plan):
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
        command += ["-an"] if plan.get("mute") else ["-c:a", "aac", "-b:a", "128k"]
        command += ["-movflags", "+faststart", str(output_path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 or not output_path.exists():
            raise RuntimeError("Video gagal diproses. Coba video MP4 yang lebih kecil atau instruksi lebih sederhana.")
        return output_path.read_bytes()

# =========================================================
# SESSION STATE
# =========================================================
for key, default in {
    "messages": [], "gallery": [], "image_prompt": "", "video_prompt": "",
    "storyboard": [], "edited_image_bytes": None, "edited_video_bytes": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("# 🩺 Studio Promkes AI")
    st.caption("Studio kreatif promosi kesehatan")
    page = st.radio("Pilih menu", PAGES, key="selected_page")
    st.divider()
    st.markdown("### 🔁 Status AI")
    for provider, active in get_ai_status().items():
        st.write(("🟢 " if active else "⚪ ") + provider + (" tersedia" if active else " belum dikonfigurasi"))
    st.caption("Chat AI mencoba Gemini terlebih dahulu, lalu Groq jika API key keduanya tersedia.")
    st.divider()
    st.caption("Materi edukasi bukan pengganti konsultasi tenaga kesehatan.")

st.markdown("""
<div class="hero"><h1>🩺 Studio Promkes AI</h1><p>Ciptakan materi promosi kesehatan yang informatif, menarik, kreatif, dan mudah dipahami masyarakat.</p></div>
""", unsafe_allow_html=True)

# =========================================================
# DASHBOARD
# =========================================================
if page == "🏠 Dashboard":
    st.subheader("Selamat datang di Studio Promkes AI")
    st.write("Satu tempat untuk membantu menyiapkan naskah edukasi, poster, dan video promosi kesehatan.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="feature-card"><h3>💬 Chat AI</h3><p>Naskah penyuluhan, FAQ, caption, dan ide kampanye kesehatan.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="feature-card"><h3>🖼️ Foto AI</h3><p>Buat gambar/poster dari teks atau edit foto yang diunggah.</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="feature-card"><h3>🎬 Video AI</h3><p>Buat video dari teks atau edit video yang diunggah.</p></div>', unsafe_allow_html=True)
    st.markdown("### ✨ Yang bisa kamu buat")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("- Naskah penyuluhan hipertensi dan diabetes\n- Edukasi pencegahan DBD\n- Caption imunisasi dan PHBS")
    with c2:
        st.markdown("- Poster cuci tangan\n- Kampanye kesehatan masyarakat\n- Video edukasi singkat")
    st.info("Foto AI dan pembuatan video memerlukan akses model generatif Gemini. Biaya dan kuota mengikuti akun Google AI yang digunakan. Edit video unggahan menggunakan FFmpeg.")

# =========================================================
# CHAT AI
# =========================================================
elif page == "💬 Chat AI":
    st.subheader("💬 Chat AI")
    st.write("Tanyakan ide atau minta bantuan menyusun materi Promkes.")
    if not get_secret("GEMINI_API_KEY") and not get_secret("GROQ_API_KEY"):
        st.warning("API key belum dipasang. Tambahkan GEMINI_API_KEY dan/atau GROQ_API_KEY pada Settings → Secrets.")
        st.markdown("- [Google AI Studio](https://aistudio.google.com/)\n- [Groq Console](https://console.groq.com/)")
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item.get("provider"):
                st.caption("Provider: " + item["provider"])
    prompt = st.chat_input("Contoh: Buat naskah penyuluhan pencegahan DBD...")
    if prompt:
        previous_messages = list(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Menghubungkan ke AI..."):
                answer, provider, errors = ask_ai(previous_messages, prompt)
            if answer:
                st.markdown(answer)
                st.caption("Dijawab oleh " + provider)
                st.session_state.messages.append({"role": "assistant", "content": answer, "provider": provider})
            else:
                st.error("AI belum berhasil memberikan jawaban.")
                for error in errors:
                    st.write("- " + error)
                st.info("Pastikan API key benar, kuota tersedia, dan paket pada requirements.txt sudah terpasang.")
    if st.button("🧹 Hapus percakapan"):
        st.session_state.messages = []
        st.rerun()

# =========================================================
# FOTO AI
# =========================================================
elif page == "🖼️ Foto AI":
    st.subheader("🖼️ Foto AI — Poster Otomatis")
    st.write("Kamu cukup menuliskan tema jika mau. AI akan menyusun judul, isi, ajakan, dan deskripsi ilustrasi secara otomatis. Jika tema dikosongkan, aplikasi memilih tema umum perilaku hidup sehat.")
    if not get_secret("GEMINI_API_KEY") and not get_secret("HF_TOKEN") and not (get_secret("CLOUDFLARE_API_TOKEN") and get_secret("CLOUDFLARE_ACCOUNT_ID")):
        st.warning("Pasang minimal satu penyedia gambar di Streamlit Secrets. Jangan masukkan token ke kode atau GitHub.")
    uploaded_image = st.file_uploader("📤 Opsional: unggah foto untuk diedit", type=["png", "jpg", "jpeg", "webp"], key="upload_image")
    topic = st.text_input("🎯 Tema poster (opsional)", placeholder="Contoh: pencegahan DBD, gizi seimbang, kesehatan ibu dan anak", key="poster_topic")
    aspect_choice = st.selectbox("Rasio gambar", ["Poster vertikal (3:4)", "Persegi (1:1)", "Landscape (16:9)"], key="image_aspect")
    aspect_ratio = {"Poster vertikal (3:4)": "3:4", "Persegi (1:1)": "1:1", "Landscape (16:9)": "16:9"}[aspect_choice]
    if uploaded_image:
        st.info("Mode edit foto: AI akan mencoba mengedit foto yang diunggah. Teks poster otomatis hanya ditempel pada gambar baru.")
        st.image(uploaded_image.getvalue(), use_container_width=True)
    if st.button("✨ Buat Poster Otomatis" if not uploaded_image else "✨ Edit Foto", type="primary", use_container_width=True, key="run_image_edit"):
        if not get_secret("GEMINI_API_KEY") and not get_secret("HF_TOKEN") and not (get_secret("CLOUDFLARE_API_TOKEN") and get_secret("CLOUDFLARE_ACCOUNT_ID")):
            st.error("Belum ada penyedia gambar yang dikonfigurasi di Streamlit Secrets.")
        else:
            try:
                with st.spinner("AI sedang menyusun konsep dan membuat gambar. Mohon tunggu..."):
                    if uploaded_image:
                        image_bytes = uploaded_image.getvalue()
                        mime_type = uploaded_image.type or "image/jpeg"
                        image_instruction = "Edit foto ini secara profesional untuk materi promosi kesehatan. Pertahankan subjek utama dan jangan menambahkan tulisan acak. Tema: " + (topic.strip() or "promosi kesehatan masyarakat Indonesia")
                        result_bytes = generate_or_edit_image(image_instruction, image_bytes, mime_type, aspect_ratio)
                        poster_copy = None
                    else:
                        title, body, cta, copy_provider = create_poster_copy(topic)
                        effective_topic = topic.strip() or "perilaku hidup bersih dan sehat"
                        image_instruction = (
                            "Buat ilustrasi/latar poster promosi kesehatan modern untuk masyarakat Indonesia tentang: "
                            + effective_topic + ". Buat visual yang relevan, bersih, profesional, komposisi poster vertikal, "
                            "ruang visual jelas di tengah. JANGAN tampilkan huruf, kata, angka, logo, watermark, atau tulisan apa pun; "
                            "teks akan ditambahkan terpisah oleh aplikasi."
                        )
                        result_bytes = generate_or_edit_image(image_instruction, None, "image/jpeg", aspect_ratio)
                        result_bytes = add_indonesian_poster_text(result_bytes, title, body, cta)
                        poster_copy = {"title": title, "body": body, "cta": cta, "copy_provider": copy_provider}
                st.session_state.edited_image_bytes = result_bytes
                st.session_state.edited_image_prompt = topic.strip() or "perilaku hidup bersih dan sehat"
                st.session_state.edited_poster_copy = poster_copy
                provider_used = st.session_state.get("last_image_provider", "AI")
                st.success(f"Poster berhasil dibuat melalui {provider_used}!" if not uploaded_image else f"Foto berhasil diedit melalui {provider_used}!")
                if poster_copy:
                    st.caption(f"Konsep teks: {poster_copy['copy_provider']}")
                    with st.expander("Lihat teks poster yang dibuat otomatis"):
                        st.markdown(f"**{poster_copy['title']}**")
                        st.write(poster_copy['body'])
                        st.write("Ajakan: " + poster_copy['cta'])
            except Exception as exc:
                st.error("Poster belum berhasil dibuat.")
                st.error(str(exc)[:1200])
                st.info("Jika error menyebut kuota (HTTP 429), kredit habis (HTTP 402), atau akses model, penyedia gambar perlu kuota/akses aktif. Aplikasi akan mencoba penyedia cadangan yang sudah dikonfigurasi.")
    if st.session_state.get("edited_image_bytes"):
        st.markdown("### 🖼️ Hasil Foto AI")
        st.image(st.session_state.edited_image_bytes, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Unduh poster (JPG)", data=st.session_state.edited_image_bytes, file_name="studio_promkes_poster.jpg", mime="image/jpeg", use_container_width=True, key="download_edited_image")
        with col2:
            if st.button("➕ Simpan hasil ke Galeri", use_container_width=True, key="save_edited_image"):
                st.session_state.gallery.append({"kind": "image", "name": "studio_promkes_poster.jpg", "data": st.session_state.edited_image_bytes, "created": datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.success("Hasil foto disimpan ke Galeri sesi.")
    with st.expander("🔑 Pengaturan penyedia AI"):
        st.markdown("Gemini, Hugging Face, dan Cloudflare digunakan berurutan jika kredensial tersedia. Untuk menyusun teks otomatis, aplikasi mencoba Gemini lalu Groq; jika keduanya tidak tersedia, aplikasi memakai template lokal. API gambar tetap memerlukan kuota/akses model aktif. Simpan token hanya di Streamlit Secrets.")
    st.caption("Mode otomatis: cukup masukkan tema atau kosongkan agar aplikasi memilih tema umum. Teks poster ditempel sebagai teks asli supaya ejaan Bahasa Indonesia akurat.")

# =========================================================
# VIDEO AI
# =========================================================
elif page == "🎬 Video AI":
    st.subheader("🎬 Video AI — Buat Video atau Edit Video")
    st.write("Tanpa unggahan, AI mencoba membuat video baru dari teks. Jika video diunggah, aplikasi menjalankan fitur edit dasar pada video itu.")
    if not get_secret("GEMINI_API_KEY"):
        st.warning("Fitur AI memerlukan GEMINI_API_KEY di Streamlit Secrets.")
    uploaded_video = st.file_uploader("📤 Opsional: unggah video untuk diedit", type=["mp4", "mov", "webm", "m4v"], key="upload_video")
    video_mode = "Edit video yang diunggah" if uploaded_video else "Buat video baru dari teks"
    st.info("Mode aktif: " + video_mode)
    aspect_choice = st.selectbox("Format video", ["Vertikal 9:16 (Reels/TikTok)", "Horizontal 16:9 (YouTube)"], key="video_aspect")
    aspect_ratio = "9:16" if aspect_choice.startswith("Vertikal") else "16:9"
    video_instruction = st.text_area("✍️ Ide atau perintah video", placeholder="Contoh: Video edukasi 8 detik tentang cuci tangan yang benar, suasana puskesmas yang bersih, ramah, realistis, tanpa klaim medis.", height=110, key="video_edit_instruction")
    if uploaded_video:
        st.markdown("#### Video asli")
        st.video(uploaded_video.getvalue())
        st.caption(f"File: {uploaded_video.name} • {uploaded_video.size / (1024 * 1024):.1f} MB")
        st.caption("Edit video unggahan saat ini mendukung potong durasi, rasio layar, hitam-putih, kecerahan, dan menghilangkan suara.")
    else:
        st.caption("Pembuatan video dari teks memakai model video generatif. Proses mungkin lebih lama, kuota bisa terbatas, dan penggunaan dapat berbayar.")
    if st.button("🎬 Proses Video AI", type="primary", use_container_width=True, key="run_video_edit"):
        if not video_instruction.strip():
            st.warning("Tuliskan ide atau perintah video terlebih dahulu.")
        elif not get_secret("GEMINI_API_KEY"):
            st.error("API key Gemini belum dipasang. Ikuti petunjuk di menu Foto AI.")
        elif uploaded_video is None:
            try:
                with st.spinner("AI sedang membuat video. Proses bisa memerlukan beberapa menit..."):
                    video_bytes = generate_video_from_text(video_instruction.strip(), aspect_ratio)
                st.session_state.edited_video_bytes = video_bytes
                st.session_state.edited_video_plan = {"mode": "generate", "aspect_ratio": aspect_ratio}
                st.success("Video berhasil dibuat!")
            except Exception as exc:
                st.error("Video belum berhasil dibuat.")
                st.caption(str(exc))
                st.info("Jika error menyebut model tidak ditemukan atau akses ditolak, periksa akses model video pada akun API. Kamu juga bisa mengatur GEMINI_VIDEO_MODEL di Streamlit Secrets sesuai model yang tersedia untuk akunmu.")
        elif uploaded_video.size > 100 * 1024 * 1024:
            st.error("Ukuran video melebihi batas 100 MB untuk versi ini. Coba video yang lebih kecil.")
        elif imageio_ffmpeg is None:
            st.error("Paket imageio-ffmpeg belum tersedia. Tambahkan imageio-ffmpeg ke requirements.txt dan redeploy.")
        else:
            try:
                with st.spinner("AI sedang memahami perintah edit..."):
                    plan = make_video_edit_plan(video_instruction.strip())
                st.write("**Rencana edit dari AI:**")
                st.json(plan)
                with st.spinner("Sedang memproses video. Jangan tutup halaman..."):
                    video_bytes = process_video(uploaded_video.getvalue(), plan)
                st.session_state.edited_video_bytes = video_bytes
                st.session_state.edited_video_plan = plan
                st.success("Video berhasil diedit!")
            except Exception as exc:
                st.error("Video belum berhasil diproses.")
                st.caption(str(exc))
    if st.session_state.get("edited_video_bytes"):
        st.markdown("### 🎞️ Hasil Video AI")
        st.video(st.session_state.edited_video_bytes)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Unduh hasil video (MP4)", data=st.session_state.edited_video_bytes, file_name="studio_promkes_hasil.mp4", mime="video/mp4", use_container_width=True, key="download_edited_video")
        with col2:
            if st.button("➕ Simpan hasil ke Galeri", use_container_width=True, key="save_edited_video"):
                st.session_state.gallery.append({"kind": "video", "name": "studio_promkes_hasil.mp4", "data": st.session_state.edited_video_bytes, "created": datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.success("Hasil video disimpan ke Galeri sesi.")
    with st.expander("Contoh perintah edit video unggahan"):
        st.markdown("- `Potong video menjadi 15 detik.`\n- `Ubah menjadi vertikal 9:16 untuk Reels.`\n- `Buat video hitam putih.`\n- `Naikkan kecerahan sedikit.`\n- `Hilangkan suara video.`\n- `Jadikan horizontal 16:9 untuk YouTube dan potong menjadi 30 detik.`")
    st.caption("Galeri hanya menyimpan hasil di sesi aktif. Unduh hasil untuk salinan permanen.")

# =========================================================
# GALERI
# =========================================================
elif page == "🗂️ Galeri":
    st.subheader("🗂️ Galeri hasil")
    st.caption("Galeri tersimpan dalam sesi aktif. Hasil dapat hilang ketika sesi direset atau aplikasi dimulai ulang.")
    if not st.session_state.gallery:
        st.info("Galeri masih kosong. Buat gambar atau video melalui menu Foto AI atau Video AI.")
    else:
        if st.button("🗑️ Kosongkan galeri"):
            st.session_state.gallery = []
            st.rerun()
        for index, item in enumerate(st.session_state.gallery):
            st.divider()
            st.markdown("**" + item["name"] + "**")
            st.caption(item["kind"].capitalize() + " • " + item["created"])
            if item["kind"] == "image":
                st.image(item["data"], use_container_width=True)
                extension = item["name"].lower()
                mime = "image/png" if extension.endswith(".png") else ("image/webp" if extension.endswith(".webp") else "image/jpeg")
            else:
                st.video(item["data"])
                extension = item["name"].lower()
                mime = "video/quicktime" if extension.endswith(".mov") else ("video/webm" if extension.endswith(".webm") else "video/mp4")
            st.download_button("⬇️ Unduh hasil", data=item["data"], file_name=item["name"], mime=mime, key=f"download_{index}")

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption("Studio Promkes AI • Materi edukasi kesehatan masyarakat. Ketersediaan dan kuota layanan AI mengikuti penyedia masing-masing.")
