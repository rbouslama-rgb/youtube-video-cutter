import streamlit as st
import pandas as pd
import subprocess
import os
import re
import time
import random
import shutil
import tempfile
from io import BytesIO
import zipfile

st.set_page_config(page_title="YouTube Video Cutter", page_icon="✂️", layout="wide")

st.markdown("""
<style>
.main-header {font-size: 3rem; color: #FF4B4B; text-align: center; margin-bottom: 2rem;}
.stats-box {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin: 10px;}
.success-box {background: #4CAF50; padding: 20px; border-radius: 10px; color: white; text-align: center;}
.error-box {background: #f44336; padding: 20px; border-radius: 10px; color: white; text-align: center;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">✂️ YouTube Video Cutter</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem;">Upload CSV → Get Cut Videos 🚀</p>', unsafe_allow_html=True)

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80].strip('_')

def download_youtube_video(url, output_path):
    strategies = [
        ['yt-dlp', '-f', '18', '-o', output_path, '--no-playlist', '--quiet', url],
        ['yt-dlp', '-f', 'best[height<=480]', '-o', output_path, '--no-playlist', '--quiet', url],
        ['yt-dlp', '-f', 'worst[ext=mp4]', '-o', output_path, '--no-playlist', '--quiet', url]
    ]
    for cmd in strategies:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            time.sleep(1)
        except:
            continue
    return False

def cut_video_ffmpeg(input_path, start, end, output_path):
    try:
        cmd = ['ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end), '-c', 'copy', '-y', output_path, '-loglevel', 'error']
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        cmd = ['ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end), '-c:v', 'libx264', '-c:a', 'aac', '-b:v', '400k', '-preset', 'ultrafast', '-y', output_path, '-loglevel', 'error']
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_path)
    except:
        return False

def process_videos(df, temp_dir, progress_bar, status_text):
    output_dir = os.path.join(temp_dir, 'videos_decoupees')
    temp_download_dir = os.path.join(temp_dir, 'temp')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_download_dir, exist_ok=True)
    
    total = len(df)
    success = 0
    errors = []
    
    for index, row in df.iterrows():
        try:
            progress_bar.progress((index + 1) / total)
            status_text.text(f"🔄 Traitement {index+1}/{total}...")
            
            url = str(row['videoUrl']).strip()
            start = int(row['startTime'])
            end = int(row['endTime'])
            question = str(row['questionText']).strip()
            
            if not url.startswith('http') or start >= end:
                errors.append(f"Ligne {index+1}: Invalide")
                continue
            
            filename_base = sanitize_filename(question) if len(sanitize_filename(question)) >= 3 else f"video_{index+1}"
            filename = f"{filename_base}_{start}_{end}.mp4"
            temp_file = os.path.join(temp_download_dir, f'temp_{index}.mp4')
            output_file = os.path.join(output_dir, filename)
            
            if not download_youtube_video(url, temp_file):
                errors.append(f"Ligne {index+1}: Téléchargement")
                continue
            
            if cut_video_ffmpeg(temp_file, start, end, output_file):
                success += 1
            else:
                errors.append(f"Ligne {index+1}: Découpage")
            
            if os.path.exists(temp_file):
                os.remove(temp_file)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            errors.append(f"Ligne {index+1}: Erreur")
    
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
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f'<div class="stats-box"><h3>📝</h3><p>Total</p><h2>{len(df)}</h2></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="stats-box"><h3>🎬</h3><p>URLs</p><h2>{df["videoUrl"].nunique()}</h2></div>', unsafe_allow_html=True)
            with col3:
                avg = int((df['endTime'] - df['startTime']).mean())
                st.markdown(f'<div class="stats-box"><h3>⏱️</h3><p>Moy</p><h2>{avg}s</h2></div>', unsafe_allow_html=True)
            with col4:
                total = int((df['endTime'] - df['startTime']).sum()/60)
                st.markdown(f'<div class="stats-box"><h3>🎞️</h3><p>Total</p><h2>{total}m</h2></div>', unsafe_allow_html=True)
            
            if st.button("🚀 LANCER", type="primary"):
                with tempfile.TemporaryDirectory() as temp_dir:
                    st.markdown("### 🔄 En cours...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success, errors, output_dir = process_videos(df, temp_dir, progress_bar, status_text)
                    
                    col1, col2 = st.columns(2)
                    with col1:
