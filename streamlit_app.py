
import streamlit as st

st.set_page_config(
    page_title="Studio AI | Creative Workspace",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# SESSION STATE
# =========================
if "active_menu" not in st.session_state:
    st.session_state.active_menu = "Dashboard"

if "total_foto" not in st.session_state:
    st.session_state.total_foto = 0

if "total_video" not in st.session_state:
    st.session_state.total_video = 0

# =========================
# CSS DASHBOARD
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

.stApp {
    background: #080b16;
    color: #f8fafc;
    font-family: 'Inter', sans-serif;
}

[data-testid="stHeader"] {
    background: rgba(8,11,22,0.9);
}

.block-container {
    max-width: 1450px;
    padding-top: 1.8rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#10152b 0%,#0b1020 100%);
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #e2e8f0;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
    font-size: 1.65rem;
    font-weight: 900;
}

div[data-testid="stMetric"] {
    background: linear-gradient(145deg,#171e35,#101527);
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 18px;
    padding: 20px;
}

div[data-testid="stMetricLabel"] {
    color: #a5b4fc;
}

div[data-testid="stMetricValue"] {
    color: #ffffff;
    font-weight: 800;
}

.stButton > button {
    width: 100%;
    min-height: 45px;
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 12px;
    color: white;
    font-weight: 700;
    background: linear-gradient(100deg,#7048ff,#4169f5);
    transition: .2s;
}

.stButton > button:hover {
    border-color: #a5b4fc;
    color: white;
    filter: brightness(1.16);
}

.hero {
    padding: 35px;
    border-radius: 25px;
    background:
        radial-gradient(ellipse at 90% 10%,rgba(0,225,255,.22),transparent 32%),
        radial-gradient(ellipse at 5% 100%,rgba(139,92,246,.4),transparent 48%),
        linear-gradient(120deg,#171735,#17213d 65%,#172b40);
    border: 1px solid rgba(255,255,255,.13);
    margin-bottom: 27px;
    position: relative;
    overflow: hidden;
}

.hero-label {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 30px;
    background: rgba(139,92,246,.2);
    border: 1px solid rgba(167,139,250,.35);
    color: #c4b5fd;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
}

.hero h1 {
    font-size: clamp(31px,4vw,52px);
    line-height: 1.13;
    font-weight: 900;
    letter-spacing: -1.8px;
    margin: 20px 0 14px;
    color: #fff;
}

.hero p {
    max-width: 650px;
    line-height: 1.8;
    color: #cbd5e1;
    font-size: 15px;
}

.section-title {
    font-size: 22px;
    font-weight: 800;
    margin-top: 20px;
    margin-bottom: 5px;
    color: #fff;
}

.section-subtitle {
    font-size: 13px;
    color: #94a3b8;
    margin-bottom: 20px;
}

.feature-card {
    padding: 23px;
    border-radius: 20px;
    min-height: 225px;
    border: 1px solid rgba(255,255,255,.1);
    background: linear-gradient(145deg,#171c32,#111629);
    margin-bottom: 12px;
}

.feature-icon {
    width: 54px;
    height: 54px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    font-size: 27px;
    margin-bottom: 19px;
}

.feature-card h3 {
    color: white;
    font-size: 20px;
    font-weight: 800;
    margin-bottom: 9px;
}

.feature-card p {
    color: #aab6cb;
    font-size: 13px;
    line-height: 1.75;
}

.purple {
    background: linear-gradient(135deg,rgba(139,92,246,.3),rgba(91,33,182,.12));
}

.cyan {
    background: linear-gradient(135deg,rgba(6,182,212,.25),rgba(8,145,178,.10));
}

.pink {
    background: linear-gradient(135deg,rgba(236,72,153,.23),rgba(190,24,93,.10));
}

.orange {
    background: linear-gradient(135deg,rgba(249,115,22,.23),rgba(194,65,12,.10));
}

.workflow {
    padding: 21px;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 17px;
    background: rgba(255,255,255,.025);
    min-height: 135px;
}

.workflow b {
    color: #e0e7ff;
    font-size: 14px;
}

.workflow p {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.7;
}

.status-dot {
    color: #34d399;
    font-size: 13px;
    font-weight: 700;
}

.footer {
    text-align: center;
    padding: 25px 5px 5px;
    color: #64748b;
    font-size: 12px;
}

div[data-testid="stExpander"] {
    border-color: rgba(255,255,255,.1);
    border-radius: 14px;
}

@media (max-width: 768px) {
    .hero {
        padding: 24px 20px;
    }
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("# 🎨 Studio AI")
    st.caption("YOUR PERSONAL CREATIVE STUDIO")
    st.divider()

    st.markdown("**WORKSPACE**")

    menu = st.radio(
        "Navigasi",
        [
            "Dashboard",
            "Foto AI",
            "Video AI",
            "Galeri",
            "Pengaturan",
        ],
        label_visibility="collapsed",
        key="navigation",
    )

    st.session_state.active_menu = menu

    st.divider()
    st.markdown("**AI WORKSPACE**")
    st.markdown(
        '<div style="padding:13px;border-radius:13px;'
        'background:rgba(139,92,246,.12);'
        'border:1px solid rgba(139,92,246,.2);">'
        '<span style="color:#c4b5fd;font-size:12px;">'
        '✦ CREATIVE MODE</span><br>'
        '<span style="font-size:12px;color:#cbd5e1;">'
        'Foto & Video AI Studio</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Studio AI • Creative Workspace")

# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":

    st.markdown("""
    <div class="hero">
        <span class="hero-label">✦ AI CREATIVE WORKSPACE</span>
        <h1>Ubah Imajinasi<br>Menjadi Karya.</h1>
        <p>
        Selamat datang di Studio AI. Buat foto yang menakjubkan,
        ciptakan video sinematik, dan wujudkan ide kreatif kamu
        hanya dengan menuliskan deskripsi.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # METRICS
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("🖼️ Foto AI", st.session_state.total_foto)

    with m2:
        st.metric("🎬 Video AI", st.session_state.total_video)

    with m3:
        st.metric(
            "✨ Total Karya",
            st.session_state.total_foto + st.session_state.total_video,
        )

    with m4:
        st.metric("⚡ Workspace", "Aktif")

    st.markdown(
        '<div class="section-title">Mulai Berkarya</div>'
        '<div class="section-subtitle">'
        'Pilih studio yang ingin kamu gunakan untuk memulai kreasi.'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon purple">🖼️</div>
            <h3>AI Image Generator</h3>
            <p>
            Ubah teks menjadi gambar. Buat foto produk, poster promosi,
            potret profesional, ilustrasi, dan visual sinematik
            sesuai imajinasi kamu.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✨ Buka Studio Foto AI", key="open_image"):
            st.session_state.navigation = "Foto AI"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon cyan">🎬</div>
            <h3>AI Video Generator</h3>
            <p>
            Wujudkan ide menjadi video bergerak. Rancang adegan,
            gerakan kamera, suasana, dan video promosi kreatif
            melalui deskripsi teks.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 Buka Studio Video AI", key="open_video"):
            st.session_state.navigation = "Video AI"
            st.rerun()

    st.markdown(
        '<div class="section-title">Alur Kreatif</div>'
        '<div class="section-subtitle">'
        'Dari ide sederhana hingga menjadi karya visual.'
        '</div>',
        unsafe_allow_html=True,
    )

    w1, w2, w3 = st.columns(3, gap="medium")

    with w1:
        st.markdown("""
        <div class="workflow">
            <div style="font-size:25px;margin-bottom:12px;">💡</div>
            <b>01 · Tulis Ide</b>
            <p>Deskripsikan visual, subjek, suasana, dan hasil yang kamu inginkan.</p>
        </div>
        """, unsafe_allow_html=True)

    with w2:
        st.markdown("""
        <div class="workflow">
            <div style="font-size:25px;margin-bottom:12px;">🤖</div>
            <b>02 · Generate AI</b>
            <p>Model AI mengolah deskripsi menjadi gambar atau video sesuai dukungan layanan.</p>
        </div>
        """, unsafe_allow_html=True)

    with w3:
        st.markdown("""
        <div class="workflow">
            <div style="font-size:25px;margin-bottom:12px;">📥</div>
            <b>03 · Simpan Karya</b>
            <p>Lihat hasilnya dan unduh file untuk kebutuhan kreatif atau promosi.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Creative Center</div>'
        '<div class="section-subtitle">'
        'Akses cepat ke ruang kerja Studio AI.'
        '</div>',
        unsafe_allow_html=True,
    )

    q1, q2, q3 = st.columns(3)

    with q1:
        if st.button("🎨 Buat Gambar Baru"):
            st.session_state.navigation = "Foto AI"
            st.rerun()

    with q2:
        if st.button("🎞️ Buat Video Baru"):
            st.session_state.navigation = "Video AI"
            st.rerun()

    with q3:
        if st.button("🗂️ Lihat Galeri"):
            st.session_state.navigation = "Galeri"
            st.rerun()

    st.markdown("""
    <div class="footer">
        STUDIO AI · CREATIVE WORKSPACE<br>
        Transform your imagination into visual art.
    </div>
    """, unsafe_allow_html=True)

# =========================
# HALAMAN SEMENTARA
# =========================
elif menu == "Foto AI":
    st.markdown("## 🖼️ Studio Foto AI")
    st.info(
        "Dashboard Foto AI sudah disiapkan. "
        "Modul generasi gambar dan koneksi API akan ditambahkan pada tahap berikutnya."
    )
    prompt = st.text_area(
        "Deskripsikan foto yang ingin kamu buat",
        placeholder="Contoh: Foto produk kopi premium dengan pencahayaan studio...",
        height=150,
    )
    st.selectbox(
        "Gaya visual",
        ["Realistis", "Sinematik", "Iklan Produk", "Ilustrasi", "Anime"],
    )
    st.button("✨ Generate Foto", disabled=True)
    st.caption("Tombol generasi diaktifkan setelah integrasi model AI.")

elif menu == "Video AI":
    st.markdown("## 🎬 Studio Video AI")
    st.info(
        "Ruang kerja Video AI sudah disiapkan. "
        "Koneksi model video akan ditambahkan pada tahap berikutnya."
    )
    st.text_area(
        "Deskripsikan video yang ingin kamu buat",
        placeholder="Contoh: Kamera bergerak perlahan mendekati produk...",
        height=150,
    )
    st.selectbox(
        "Gaya video",
        ["Realistis", "Sinematik", "Iklan Produk", "Fantasi"],
    )
    st.button("🎬 Generate Video", disabled=True)
    st.caption("Tombol generasi diaktifkan setelah integrasi model AI.")

elif menu == "Galeri":
    st.markdown("## 🗂️ Galeri Karya")
    st.info(
        "Galeri akan menampilkan hasil foto dan video yang berhasil "
        "dibuat setelah modul AI diintegrasikan."
    )
    st.markdown("### Koleksi Studio")
    st.write("Belum ada karya. Mulai berkarya dari menu Foto AI atau Video AI.")

elif menu == "Pengaturan":
    st.markdown("## ⚙️ Pengaturan Studio AI")
    st.markdown("### Workspace")
    st.write("Nama aplikasi: Studio AI")
    st.write("Platform: Streamlit Cloud")
    st.write("Mode: AI Creative Workspace")

    st.markdown("### Integrasi AI")
    st.warning(
        "API belum dihubungkan. Token akan disimpan secara aman "
        "menggunakan Streamlit Secrets saat tahap integrasi."
    )

    st.link_button(
        "Buka Hugging Face",
        "https://huggingface.co/",
        use_container_width=True,
    )

    st.link_button(
        "Buka Streamlit Cloud",
        "https://share.streamlit.io/",
        use_container_width=True,
    )
