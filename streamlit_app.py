import os, io, json, re, base64, subprocess, tempfile, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai, types = None, None
try:
    from groq import Groq
except ImportError:
    Groq = None
try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

# =========================================================
# KONFIGURASI DAN TAMPILAN — menu utama tetap dipertahankan
# =========================================================
st.set_page_config(page_title="Studio Promkes AI", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")
PAGES = ["🏠 Dashboard", "💬 Chat AI", "🖼️ Foto AI", "🎬 Video AI", "🗂️ Galeri"]

st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 0% 0%,#d9f5ef 0%,transparent 28%),radial-gradient(circle at 100% 0%,#dbeafe 0%,transparent 30%),#f6f9fc}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#073b4c,#075985,#0f766e)}
[data-testid="stSidebar"] *{color:white}
.hero{background:linear-gradient(120deg,#075985,#0f766e);padding:28px;border-radius:20px;color:white;margin-bottom:22px;box-shadow:0 8px 24px #07598522}
.hero h1{color:white;margin-bottom:8px}.hero p{color:#e0f2fe;font-size:16px;margin:0}
.feature-card{background:white;border:1px solid #dbeafe;border-radius:17px;padding:20px;min-height:145px;box-shadow:0 5px 18px #0f172a0f}
.feature-card h3{color:#075985}.stButton>button{border-radius:11px;font-weight:600;min-height:42px}h1,h2,h3{color:#123047}
</style>
""", unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return str(st.secrets.get(name, default) or "").strip()
    except Exception:
        return str(os.getenv(name, default) or "").strip()


SYSTEM_PROMPT = """Kamu asisten AI serbaguna yang ramah dan praktis. Jawab dengan Bahasa Indonesia alami jika pengguna memakai Bahasa Indonesia. Pahami instruksi sehari-hari dan langsung kerjakan jika jelas. Bantu pertanyaan umum, menulis, merangkum, menerjemahkan, coding, ide kampanye, naskah edukasi, caption, poster, dan video. Jangan mengarang sumber atau hasil tindakan. Untuk kesehatan, gunakan bahasa edukatif, hindari diagnosis pasti dan klaim berlebihan."""


def gemini_client():
    if not secret("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY belum dipasang pada Streamlit Secrets.")
    if genai is None:
        raise RuntimeError("Paket google-genai belum ada di requirements.txt.")
    try:
        opts = types.HttpOptions(timeout=120_000) if types else None
        return genai.Client(api_key=secret("GEMINI_API_KEY"), http_options=opts) if opts else genai.Client(api_key=secret("GEMINI_API_KEY"))
    except Exception as e:
        raise RuntimeError(f"Gagal menyiapkan Gemini: {e}") from e


def ask_gemini(history, prompt):
    conversation = [SYSTEM_PROMPT]
    for m in history[-12:]:
        conversation.append(("Pengguna: " if m["role"] == "user" else "Asisten: ") + m["content"])
    conversation.append("Pengguna: " + prompt)
    result = gemini_client().models.generate_content(
        model=secret("GEMINI_MODEL", "gemini-2.5-flash"),
        contents="\n\n".join(conversation))
    if not getattr(result, "text", None):
        raise RuntimeError("Gemini tidak mengembalikan jawaban.")
    return result.text.strip()


def ask_groq(history, prompt):
    if not secret("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY belum dipasang.")
    if Groq is None:
        raise RuntimeError("Paket groq belum ada di requirements.txt.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-12:] if m["role"] in ("user", "assistant")]
    messages.append({"role": "user", "content": prompt})
    result = Groq(api_key=secret("GROQ_API_KEY")).chat.completions.create(
        model=secret("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=messages, temperature=0.5, max_tokens=2000)
    answer = result.choices[0].message.content
    if not answer:
        raise RuntimeError("Groq tidak mengembalikan jawaban.")
    return answer.strip()


def ask_ai(history, prompt):
    providers = []
    if secret("GEMINI_API_KEY"): providers.append(("Gemini", ask_gemini))
    if secret("GROQ_API_KEY"): providers.append(("Groq", ask_groq))
    if not providers: return None, None, ["Pasang GEMINI_API_KEY dan/atau GROQ_API_KEY di Streamlit Secrets."]
    errors = []
    for name, fn in providers:
        try: return fn(history, prompt), name, errors
        except Exception as e: errors.append(f"{name}: {str(e)[:500]}")
    return None, None, errors


# =========================================================
# TEKS POSTER: template akurat + AI untuk tema yang belum ada
# =========================================================
TEMPLATES = [
    (("dbd", "demam berdarah", "nyamuk"), ("CEGAH DBD DARI RUMAH", "Kuras penampungan air, tutup rapat, dan daur ulang barang bekas. Periksa lingkungan setiap minggu.", "Ayo lakukan 3M Plus!")),
    (("cuci tangan", "kebersihan tangan"), ("CUCI TANGAN PAKAI SABUN", "Gunakan sabun dan air mengalir sebelum makan, setelah dari toilet, dan saat tangan kotor.", "Biasakan setiap hari!")),
    (("rokok", "merokok", "asap rokok"), ("RUMAH BEBAS ASAP ROKOK", "Asap rokok membahayakan perokok dan orang di sekitarnya. Jangan merokok di rumah atau dekat anak.", "Lindungi keluarga kita!")),
    (("diabetes", "gula darah"), ("CEGAH DIABETES SEJAK DINI", "Pilih makanan bergizi seimbang, aktif bergerak, dan periksa kesehatan secara berkala.", "Mulai kebiasaan sehat!")),
    (("hipertensi", "tekanan darah"), ("JAGA TEKANAN DARAH", "Batasi garam, rutin bergerak, hindari rokok, dan periksa tekanan darah sesuai anjuran tenaga kesehatan.", "Jaga jantung tetap sehat!")),
    (("stunting", "gizi anak", "gizi ibu"), ("DUKUNG TUMBUH KEMBANG ANAK", "Penuhi kebutuhan gizi ibu dan anak, pantau pertumbuhan, dan konsultasikan ke tenaga kesehatan.", "Pantau tumbuh kembang rutin!")),
    (("imunisasi", "vaksin"), ("IMUNISASI MELINDUNGI ANAK", "Ikuti jadwal imunisasi sesuai rekomendasi tenaga kesehatan dan simpan catatan imunisasi anak.", "Tanyakan jadwal ke Puskesmas!")),
    (("gizi seimbang", "makanan sehat"), ("ISI PIRINGKU, GIZI SEIMBANG", "Variasikan makanan pokok, lauk berprotein, sayur, dan buah. Minum air putih serta batasi gula, garam, dan lemak.", "Pilih makan beragam!")),
    (("olahraga", "aktivitas fisik", "bergerak"), ("AYO AKTIF BERGERAK", "Luangkan waktu untuk berjalan kaki, bersepeda, atau aktivitas fisik sesuai kemampuan setiap hari.", "Gerak rutin, tubuh bugar!")),
    (("kesehatan mental", "stres", "kesehatan jiwa"), ("RAWAT KESEHATAN MENTAL", "Istirahat cukup, terhubung dengan orang tepercaya, dan cari bantuan profesional saat merasa kewalahan.", "Tidak apa-apa minta bantuan!")),
]


def poster_copy(topic):
    topic = topic.strip() or "perilaku hidup bersih dan sehat"
    low = topic.lower()
    for words, result in TEMPLATES:
        if any(w in low for w in words):
            return (*result, "Template edukasi")
    prompt = ("Buat teks poster edukasi kesehatan Bahasa Indonesia tentang: " + topic +
              ". Balas JSON valid saja dengan kunci title, body, cta. title maksimal 6 kata, body maksimal 24 kata, cta maksimal 6 kata. Konkret, jelas, tanpa klaim medis berlebihan.")
    answer, provider, _ = ask_ai([], prompt)
    if answer:
        try:
            match = re.search(r"\{.*\}", answer, re.S)
            data = json.loads(match.group(0)) if match else {}
            title = " ".join(str(data.get("title", "")).split())[:60]
            body = " ".join(str(data.get("body", "")).split())[:180]
            cta = " ".join(str(data.get("cta", "")).split())[:55]
            if title and body and cta: return title, body, cta, provider
        except Exception: pass
    return ("MULAI HIDUP LEBIH SEHAT",
            f"Terapkan kebiasaan sehat terkait {topic}, pilih informasi tepercaya, dan konsultasikan pertanyaan kesehatan kepada tenaga kesehatan.",
            "Mulai dari hari ini!", "Template otomatis")


# =========================================================
# GAMBAR AI — Gemini lalu Hugging Face
# =========================================================
def image_gemini(prompt):
    key = secret("GEMINI_API_KEY")
    if not key: raise RuntimeError("GEMINI_API_KEY belum dipasang.")
    model = secret("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    payload = {"contents": [{"parts": [{"text":
        "Buat ilustrasi/latar profesional untuk poster edukasi kesehatan masyarakat Indonesia. "
        "Jangan buat teks, huruf, angka, logo, atau watermark. Sisakan ruang untuk teks yang akan ditambahkan aplikasi. "
        "Visual ramah, jelas, modern, tidak menakut-nakuti. Tema: " + prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp: data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Gemini gambar HTTP {e.code}: {detail[:500]}") from e
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"): return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini tidak mengembalikan gambar. Periksa akses model dan kuota.")


def image_huggingface(prompt):
    token = secret("HF_TOKEN")
    if not token: raise RuntimeError("HF_TOKEN belum dipasang.")
    try: from huggingface_hub import InferenceClient
    except ImportError as e: raise RuntimeError("Tambahkan huggingface_hub ke requirements.txt.") from e
    client = InferenceClient(api_key=token, provider="auto", timeout=120)
    img = client.text_to_image(
        prompt="Professional illustration for an Indonesian public health poster. No text, letters, numbers, logo, watermark. Leave clear space for overlay text. " + prompt,
        model=secret("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"))
    out = io.BytesIO(); img.convert("RGB").save(out, "JPEG", quality=94)
    return out.getvalue()


def make_background(prompt):
    errors = []
    if secret("GEMINI_API_KEY"):
        try:
            img = image_gemini(prompt); st.session_state.last_image_provider = "Gemini"; return img
        except Exception as e: errors.append("Gemini: " + str(e)[:400])
    if secret("HF_TOKEN"):
        try:
            img = image_huggingface(prompt); st.session_state.last_image_provider = "Hugging Face"; return img
        except Exception as e: errors.append("Hugging Face: " + str(e)[:400])
    raise RuntimeError("Pembuatan gambar gagal. " + " | ".join(errors or ["Pasang GEMINI_API_KEY atau HF_TOKEN."]))


# =========================================================
# LAYOUT POSTER — judul, isi, ajakan ditulis Pillow, bukan oleh model gambar
# =========================================================
def font(size, bold=False):
    paths = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
             if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"])
    for path in paths:
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_width):
    lines, line = [], ""
    for word in str(text or "").split():
        trial = word if not line else line + " " + word
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width: line = trial
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines


def render_poster(image_bytes, title, body, cta, ratio="3:4"):
    try: base = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e: raise RuntimeError("Gambar latar tidak dapat dibaca.") from e
    ratios = {"3:4": 3/4, "1:1": 1, "16:9": 16/9}
    target = ratios.get(ratio, 3/4)
    w, h = base.size
    if w/h > target:
        nw = int(h*target); x = (w-nw)//2; base = base.crop((x, 0, x+nw, h))
    else:
        nh = int(w/target); y0 = (h-nh)//2; base = base.crop((0, y0, w, y0+nh))
    w, h = base.size
    scale = max(w/900, h/1200, 0.55); pad = int(w*0.055)
    head_h, foot_h = int(h*0.23), int(h*0.32)
    overlay = Image.new("RGBA", base.size, (0,0,0,0)); d = ImageDraw.Draw(overlay)
    d.rounded_rectangle((pad//2,pad//2,w-pad//2,head_h), radius=int(22*scale), fill=(7,45,65,238))
    d.rounded_rectangle((pad//2,h-foot_h,w-pad//2,h-pad//2), radius=int(22*scale), fill=(4,110,103,242))
    tf, bf, cf = font(max(22,int(w*.060)),True), font(max(17,int(w*.033))), font(max(18,int(w*.037)),True)
    maxw = w-2*pad
    titles = wrap(d, title.upper(), tf, maxw)[:3]
    th = [d.textbbox((0,0),s,font=tf)[3] for s in titles]; gap = max(3,int(5*scale))
    y = max(pad//2+8,(head_h-sum(th)-gap*max(0,len(th)-1))//2)
    for line, lh in zip(titles, th):
        box=d.textbbox((0,0),line,font=tf); d.text(((w-(box[2]-box[0]))//2,y),line,font=tf,fill="white"); y += lh+gap
    body_lines=wrap(d,body,bf,maxw)[:5]; cta_lines=wrap(d,cta,cf,maxw)[:2]
    bh=[d.textbbox((0,0),s,font=bf)[3] for s in body_lines]; ch=[d.textbbox((0,0),s,font=cf)[3] for s in cta_lines]
    gap2=max(3,int(4*scale))
    total=sum(bh)+gap2*max(0,len(bh)-1)+int(10*scale)+sum(ch)+gap2*max(0,len(ch)-1)
    y=h-foot_h+max(8,(foot_h-total)//2)
    for line,lh in zip(body_lines,bh):
        box=d.textbbox((0,0),line,font=bf); d.text(((w-(box[2]-box[0]))//2,y),line,font=bf,fill="white"); y+=lh+gap2
    y+=int(5*scale)
    for line,lh in zip(cta_lines,ch):
        box=d.textbbox((0,0),line,font=cf); d.text(((w-(box[2]-box[0]))//2,y),line,font=cf,fill=(255,245,180,255)); y+=lh+gap2
    result=Image.alpha_composite(base.convert("RGBA"),overlay).convert("RGB")
    out=io.BytesIO(); result.save(out,"JPEG",quality=94,optimize=True); return out.getvalue()


# =========================================================
# VIDEO — generator optional; uploaded video edited with FFmpeg
# =========================================================
def video_from_text(prompt, ratio):
    client = gemini_client()
    model = secret("GEMINI_VIDEO_MODEL", "veo-2.0-generate-001")
    interaction = client.interactions.create(model=model,
        input="Buat video edukasi kesehatan masyarakat Indonesia, ramah, realistis, tanpa teks layar. Ide: " + prompt,
        response_format={"type":"video","aspect_ratio":ratio})
    block = getattr(interaction,"output_video",None)
    data = getattr(block,"data",None) if block else None
    if data: return base64.b64decode(data)
    for step in getattr(interaction,"steps",[]) or []:
        for item in getattr(step,"content",[]) or []:
            if getattr(item,"type","")=="video" and getattr(item,"data",None): return base64.b64decode(item.data)
    raise RuntimeError("Model tidak mengembalikan video.")


def video_plan(instruction):
    prompt = f"""Ubah perintah edit video berikut menjadi JSON valid saja.
Perintah: {instruction!r}
Skema: {{"trim_seconds": null, "aspect": "original", "grayscale": false, "brightness": 0.0, "mute": false}}
trim_seconds angka 1-180 jika diminta durasi; aspect original, vertical, horizontal, square;
grayscale true jika diminta hitam putih; brightness -0.15 sampai 0.15; mute true jika diminta hilangkan suara.
Jika tidak jelas gunakan default."""
    answer=ask_gemini([],prompt).replace("```json","").replace("```","").strip()
    a,b=answer.find("{"),answer.rfind("}")
    if a<0 or b<a: raise RuntimeError("AI memberikan rencana edit tidak valid.")
    p=json.loads(answer[a:b+1]); aspect=p.get("aspect","original")
    if aspect not in ("original","vertical","horizontal","square"): aspect="original"
    try: trim=max(1,min(float(p["trim_seconds"]),180)) if p.get("trim_seconds") is not None else None
    except (TypeError,ValueError): trim=None
    try: bright=max(-.15,min(.15,float(p.get("brightness",0))))
    except (TypeError,ValueError): bright=0
    return {"trim_seconds":trim,"aspect":aspect,"grayscale":bool(p.get("grayscale",False)),"brightness":bright,"mute":bool(p.get("mute",False))}


def edit_video(data, plan):
    if imageio_ffmpeg is None: raise RuntimeError("Tambahkan imageio-ffmpeg ke requirements.txt.")
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        src=Path(tmp)/"input_video"; dst=Path(tmp)/"output.mp4"; src.write_bytes(data)
        cmd=[ffmpeg,"-y","-i",str(src)]
        if plan.get("trim_seconds"): cmd += ["-t",str(plan["trim_seconds"])]
        filters=[]; aspect=plan.get("aspect","original")
        if aspect=="vertical": filters.append("scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280")
        elif aspect=="horizontal": filters.append("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720")
        elif aspect=="square": filters.append("scale=720:720:force_original_aspect_ratio=increase,crop=720:720")
        if plan.get("grayscale"): filters.append("hue=s=0")
        bright=float(plan.get("brightness",0))
        if abs(bright)>.001: filters.append(f"eq=brightness={bright:.3f}")
        if filters: cmd += ["-vf",",".join(filters)]
        cmd += ["-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p"]
        cmd += ["-an"] if plan.get("mute") else ["-c:a","aac","-b:a","128k"]
        cmd += ["-movflags","+faststart",str(dst)]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
        if result.returncode or not dst.exists(): raise RuntimeError("FFmpeg gagal memproses video. Coba file MP4 lebih kecil.")
        return dst.read_bytes()


# =========================================================
# SESSION STATE
# =========================================================
for key, default in {"messages":[],"gallery":[],"edited_image_bytes":None,"edited_video_bytes":None,"poster_copy":None}.items():
    if key not in st.session_state: st.session_state[key]=default

with st.sidebar:
    st.markdown("# 🩺 Studio Promkes AI")
    st.caption("Studio kreatif promosi kesehatan")
    page=st.radio("Pilih menu",PAGES,key="selected_page")
    st.divider(); st.markdown("### 🔁 Status AI")
    for name,active in {"Gemini":bool(secret("GEMINI_API_KEY")),"Groq":bool(secret("GROQ_API_KEY"))}.items():
        st.write(("🟢 " if active else "⚪ ")+name+(" tersedia" if active else " belum dikonfigurasi"))
    st.caption("Chat mencoba Gemini, lalu Groq jika tersedia.")
    st.divider(); st.caption("Materi edukasi bukan pengganti konsultasi tenaga kesehatan.")

st.markdown('<div class="hero"><h1>🩺 Studio Promkes AI</h1><p>Ciptakan materi promosi kesehatan yang informatif, menarik, kreatif, dan mudah dipahami masyarakat.</p></div>',unsafe_allow_html=True)

if page=="🏠 Dashboard":
    st.subheader("Selamat datang di Studio Promkes AI")
    st.write("Satu tempat untuk menyiapkan naskah edukasi, poster, dan video promosi kesehatan.")
    a,b,c=st.columns(3)
    with a: st.markdown('<div class="feature-card"><h3>💬 Chat AI</h3><p>Naskah penyuluhan, FAQ, caption, dan ide kampanye kesehatan.</p></div>',unsafe_allow_html=True)
    with b: st.markdown('<div class="feature-card"><h3>🖼️ Foto AI</h3><p>Buat poster otomatis dengan teks Bahasa Indonesia yang akurat.</p></div>',unsafe_allow_html=True)
    with c: st.markdown('<div class="feature-card"><h3>🎬 Video AI</h3><p>Buat video generatif atau edit video unggahan.</p></div>',unsafe_allow_html=True)
    st.markdown("### ✨ Yang bisa kamu buat")
    l,r=st.columns(2)
    with l: st.markdown("- Naskah penyuluhan hipertensi dan diabetes\n- Edukasi pencegahan DBD\n- Caption imunisasi dan PHBS")
    with r: st.markdown("- Poster cuci tangan dan gizi seimbang\n- Kampanye kesehatan masyarakat\n- Video edukasi singkat")
    st.info("Pembuatan gambar/video bergantung pada akses model dan kuota. Edit video lokal memerlukan FFmpeg.")

elif page=="💬 Chat AI":
    st.subheader("💬 Chat AI serbaguna")
    st.write("Tulis permintaan biasa saja. AI akan mencoba memahami dan mengerjakannya otomatis.")
    if not secret("GEMINI_API_KEY") and not secret("GROQ_API_KEY"):
        st.warning("Pasang GEMINI_API_KEY dan/atau GROQ_API_KEY pada Streamlit Secrets.")
        st.markdown("- [Google AI Studio](https://aistudio.google.com/)\n- [Groq Console](https://console.groq.com/)")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("provider"): st.caption("Dijawab oleh "+m["provider"])
    prompt=st.chat_input("Contoh: Buat naskah penyuluhan pencegahan DBD...")
    if prompt:
        old=list(st.session_state.messages); st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("AI sedang berpikir..."): answer,provider,errors=ask_ai(old,prompt)
            if answer:
                st.markdown(answer); st.caption("Dijawab oleh "+provider)
                st.session_state.messages.append({"role":"assistant","content":answer,"provider":provider})
            else:
                st.error("AI belum berhasil menjawab.")
                for err in errors: st.write("- "+err)
    if st.button("🧹 Hapus percakapan"):
        st.session_state.messages=[]; st.rerun()

elif page=="🖼️ Foto AI":
    st.subheader("🖼️ Foto AI — Poster Otomatis")
    st.write("Tulis tema. Aplikasi menyusun edukasi dan menambahkan teks langsung ke gambar supaya ejaan tidak dibuat-buat oleh model gambar.")
    topic=st.text_input("🎯 Tema poster (opsional)",placeholder="Contoh: pencegahan DBD, gizi seimbang, kesehatan ibu dan anak",key="poster_topic")
    ratio_label=st.selectbox("Rasio gambar",["Poster vertikal (3:4)","Persegi (1:1)","Landscape (16:9)"],key="poster_ratio")
    ratio={"Poster vertikal (3:4)":"3:4","Persegi (1:1)":"1:1","Landscape (16:9)":"16:9"}[ratio_label]
    uploaded=st.file_uploader("Opsional: unggah foto latar",type=["png","jpg","jpeg","webp"],key="poster_upload")
    if uploaded: st.image(uploaded.getvalue(),caption="Foto latar",use_container_width=True)
    if not secret("GEMINI_API_KEY") and not secret("HF_TOKEN"):
        st.warning("Untuk membuat latar gambar AI, pasang GEMINI_API_KEY atau HF_TOKEN di Secrets. Kamu tetap bisa mengunggah foto latar.")
    if st.button("✨ Buat Poster Otomatis",type="primary",use_container_width=True,key="make_poster"):
        topic_final=topic.strip() or "perilaku hidup bersih dan sehat"
        try:
            with st.spinner("Menyusun teks dan membuat poster..."):
                title,body,cta,copy_provider=poster_copy(topic_final)
                if uploaded: background=uploaded.getvalue()
                else: background=make_background("Tema "+topic_final+". Ilustrasi modern, ramah, konteks Indonesia, komposisi rapi, tanpa tulisan.")
                result=render_poster(background,title,body,cta,ratio)
            st.session_state.edited_image_bytes=result
            st.session_state.poster_copy={"title":title,"body":body,"cta":cta,"provider":copy_provider}
            st.success("Poster selesai dibuat.")
        except Exception as e:
            st.error("Poster belum berhasil dibuat."); st.error(str(e)[:1200])
    if st.session_state.edited_image_bytes:
        st.markdown("### 🖼️ Hasil Poster")
        st.image(st.session_state.edited_image_bytes,use_container_width=True)
        cp=st.session_state.poster_copy or {}
        if cp:
            with st.expander("Lihat teks poster"):
                st.markdown("**"+cp.get("title","")+"**"); st.write(cp.get("body","")); st.write("Ajakan: "+cp.get("cta",""))
                st.caption("Teks: "+cp.get("provider","otomatis"))
        a,b=st.columns(2)
        with a:
            st.download_button("⬇️ Unduh poster JPG",st.session_state.edited_image_bytes,file_name="studio_promkes_poster.jpg",mime="image/jpeg",use_container_width=True,key="download_poster")
        with b:
            if st.button("➕ Simpan ke Galeri",use_container_width=True,key="save_poster"):
                st.session_state.gallery.append({"kind":"image","name":"studio_promkes_poster.jpg","data":st.session_state.edited_image_bytes,"created":datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.success("Poster disimpan ke Galeri sesi.")

elif page=="🎬 Video AI":
    st.subheader("🎬 Video AI — Buat atau Edit Video")
    uploaded=st.file_uploader("Opsional: unggah video untuk diedit",type=["mp4","mov","webm","m4v"],key="video_upload")
    if uploaded: st.video(uploaded.getvalue())
    ratio_label=st.selectbox("Format video",["Vertikal 9:16 (Reels/TikTok)","Horizontal 16:9 (YouTube)"],key="video_ratio")
    ratio="9:16" if ratio_label.startswith("Vertikal") else "16:9"
    instruction=st.text_area("✍️ Ide atau perintah video",placeholder="Contoh: Video edukasi cuci tangan untuk anak sekolah, suasana ceria.",height=110,key="video_instruction")
    if uploaded: st.caption("Edit video mendukung potong durasi, ubah rasio, hitam-putih, kecerahan, dan hapus suara.")
    if st.button("🎬 Proses Video",type="primary",use_container_width=True,key="process_video"):
        if not instruction.strip(): st.warning("Tuliskan ide atau perintah terlebih dahulu.")
        elif uploaded:
            if uploaded.size>100*1024*1024: st.error("Ukuran video maksimal 100 MB.")
            else:
                try:
                    with st.spinner("AI memahami perintah edit..."): plan=video_plan(instruction.strip())
                    with st.expander("Rencana edit"): st.json(plan)
                    with st.spinner("Memproses video..."): result=edit_video(uploaded.getvalue(),plan)
                    st.session_state.edited_video_bytes=result; st.success("Video berhasil diedit.")
                except Exception as e: st.error(str(e)[:1200])
        elif not secret("GEMINI_API_KEY"): st.error("Pembuatan video memerlukan GEMINI_API_KEY.")
        else:
            try:
                with st.spinner("AI sedang membuat video..."): result=video_from_text(instruction.strip(),ratio)
                st.session_state.edited_video_bytes=result; st.success("Video selesai dibuat.")
            except Exception as e: st.error("Video belum berhasil dibuat: "+str(e)[:1000])
    if st.session_state.edited_video_bytes:
        st.markdown("### 🎞️ Hasil Video"); st.video(st.session_state.edited_video_bytes)
        a,b=st.columns(2)
        with a: st.download_button("⬇️ Unduh MP4",st.session_state.edited_video_bytes,file_name="studio_promkes_hasil.mp4",mime="video/mp4",use_container_width=True,key="download_video")
        with b:
            if st.button("➕ Simpan ke Galeri",use_container_width=True,key="save_video"):
                st.session_state.gallery.append({"kind":"video","name":"studio_promkes_hasil.mp4","data":st.session_state.edited_video_bytes,"created":datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.success("Video disimpan ke Galeri sesi.")
    with st.expander("Contoh perintah edit"):
        st.markdown("- Potong video menjadi 15 detik.\n- Ubah menjadi vertikal 9:16.\n- Buat video hitam putih.\n- Naikkan kecerahan sedikit.\n- Hilangkan suara video.")

elif page=="🗂️ Galeri":
    st.subheader("🗂️ Galeri hasil")
    st.caption("Galeri disimpan dalam sesi aktif. Unduh hasil untuk salinan permanen.")
    if not st.session_state.gallery: st.info("Galeri masih kosong. Buat poster atau video terlebih dahulu.")
    else:
        if st.button("🗑️ Kosongkan galeri",key="clear_gallery"):
            st.session_state.gallery=[]; st.rerun()
        for i,item in enumerate(st.session_state.gallery):
            st.divider(); st.markdown("**"+item["name"]+"**"); st.caption(item["kind"].capitalize()+" • "+item["created"])
            if item["kind"]=="image": st.image(item["data"],use_container_width=True); mime="image/jpeg"
            else: st.video(item["data"]); mime="video/mp4"
            st.download_button("⬇️ Unduh hasil",item["data"],file_name=item["name"],mime=mime,key=f"gallery_download_{i}")

st.divider()
st.caption("Studio Promkes AI • Materi edukasi kesehatan masyarakat. Ketersediaan dan kuota layanan mengikuti penyedia masing-masing.")
