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
