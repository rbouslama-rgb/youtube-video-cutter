import streamlit as st
import pandas as pd
import os
import re
import time
import random
import shutil
import tempfile
from io import BytesIO
import zipfile
import subprocess
from pytube import YouTube

st.set_page_config(page_title="YouTube Video Cutter", page_icon="✂️", layout="wide")

st.markdown("""
<style>
.main-header {font-size: 3rem; color: #FF4B4B; text-align: center; margin-bottom: 2rem;}
.stats-box {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin: 10px;}
.success-box {background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;}
.error-box {background: linear-gradient(135deg, #f44336 0%, #e53935 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">✂️ YouTube Video Cutter</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Upload CSV → Get Cut Videos in ZIP</p>', unsafe_allow_html=True)

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80].strip('_')

def download_youtube_video(url, output_path, status_placeholder):
    try:
        status_placeholder.text("📡 Connexion YouTube...")
        yt = YouTube(url)
        status_placeholder.text("📡 Sélection qualité...")
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if not stream:
            stream = yt.streams.filter(file_extension='mp4').first()
        if not stream:
            return False
        status_placeholder.text("⬇️ Téléchargement...")
        stream.download(output_path=os.path.dirname(output_path), filename=os.path.basename(output_path))
        return os.path.exists(output_path)
    except Exception as e:
        status_placeholder.text(f"❌ {str(e)[:50]}")
        return False

def cut_video_ffmpeg(input_path, start, end, output_path, status_placeholder):
    try:
        status_placeholder.text("✂️ Découpage...")
        cmd = ['ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end), '-c', 'copy', '-y', output_path, '-loglevel', 'error']
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        cmd = ['ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end), '-c:v', 'libx264', '-c:a', 'aac', '-b:v', '400k', '-preset', 'ultrafast', '-y', output_path, '-loglevel', 'error']
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        status_placeholder.text(f"❌ {str(e)[:30]}")
        return False

def process_videos(df, temp_dir, progress_bar, status_text):
    output_dir = os.path.join(temp_dir, 'videos_decoupees')
    temp_download_dir = os.path.join(temp_dir, 'temp')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_download_dir, exist_ok=True)
    total = len(df)
    success = 0
    errors = []
    detail_status = st.empty()
    for index, row in df.iterrows():
        try:
            progress = (index + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"🔄 Vidéo {index+1}/{total}")
            url = str(row['videoUrl']).strip()
            start = int(row['startTime'])
            end = int(row['endTime'])
            question = str(row['questionText']).strip()
            if not url.startswith('http') or start >= end:
                errors.append(f"Ligne {index+1}: Données invalides")
                continue
            filename_base = sanitize_filename(question)
            if len(filename_base) < 3:
                filename_base = f"video_{index+1}"
            filename = f"{filename_base}_{start}_{end}.mp4"
            temp_file = os.path.join(temp_download_dir, f'temp_{index}.mp4')
            output_file = os.path.join(output_dir, filename)
            if not download_youtube_video(url, temp_file, detail_status):
                errors.append(f"Ligne {index+1}: Téléchargement échoué")
                continue
            if cut_video_ffmpeg(temp_file, start, end, output_file, detail_status):
                success += 1
                detail_status.text(f"✅ Vidéo {index+1} OK!")
            else:
                errors.append(f"Ligne {index+1}: Découpage échoué")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            errors.append(f"Ligne {index+1}: {str(e)[:50]}")
    return success, errors, output_dir

def create_zip(source_dir):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("---")
    uploaded_file = st.file_uploader("📤 Upload CSV", type=['csv'])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        required = ['videoUrl', 'startTime', 'endTime', 'questionText']
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"❌ Colonnes manquantes: {', '.join(missing)}")
        else:
            st.success(f"✅ {len(df)} lignes")
            with st.expander("📋 Aperçu"):
                st.dataframe(df.head())
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="stats-box"><h3>📝</h3><h2>{len(df)}</h2></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="stats-box"><h3>🎬</h3><h2>{df["videoUrl"].nunique()}</h2></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="stats-box"><h3>⏱️</h3><h2>{int((df["endTime"]-df["startTime"]).mean())}s</h2></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="stats-box"><h3>🎞️</h3><h2>{int((df["endTime"]-df["startTime"]).sum()/60)}m</h2></div>', unsafe_allow_html=True)
            st.markdown("---")
            if st.button("🚀 LANCER", type="primary", use_container_width=True):
                with tempfile.TemporaryDirectory() as td:
                    st.markdown("### 🔄 Traitement...")
                    pb = st.progress(0)
                    st_text = st.empty()
                    s, e, od = process_videos(df, td, pb, st_text)
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f'<div class="success-box"><h3>✅</h3><h2>{s}/{len(df)}</h2><p>{s/len(df)*100:.1f}%</p></div>', unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'<div class="error-box"><h3>❌</h3><h2>{len(e)}/{len(df)}</h2><p>{len(e)/len(df)*100:.1f}%</p></div>', unsafe_allow_html=True)
                    if e:
                        with st.expander(f"⚠️ {len(e)} échecs"):
                            for err in e[:20]:
                                st.text(err)
                    if s > 0:
                        zb = create_zip(od)
                        st.download_button("⬇️ ZIP", zb, "videos.zip", "application/zip", type="primary")
                        st.balloons()
    except Exception as ex:
        st.error(f"❌ {ex}")
else:
    st.info("📤 Uploadez CSV: videoUrl, startTime, endTime, questionText")

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Made for Lyra</p>", unsafe_allow_html=True)
