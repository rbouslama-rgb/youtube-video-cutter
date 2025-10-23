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
import sys

# Installer yt-dlp
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"], check=True)
except:
    pass

st.set_page_config(page_title="YouTube Video Cutter", page_icon="✂️", layout="wide")

st.markdown("""
<style>
.main-header {font-size: 3rem; color: #FF4B4B; text-align: center; margin-bottom: 2rem;}
.stats-box {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
.success-box {background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;}
.error-box {background: linear-gradient(135deg, #f44336 0%, #e53935 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">✂️ YouTube Video Cutter</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Upload CSV → Get Cut Videos in ZIP 🚀</p>', unsafe_allow_html=True)

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80].strip('_')

def download_youtube_video(url, output_path):
    strategies = [
        ['yt-dlp', '-f', '18', '-o', output_path, '--no-playlist', '--quiet', '--no-warnings', url],
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
            progress = (index + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"🔄 Traitement vidéo {index+1}/{total}...")
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
            if not download_youtube_video(url, temp_file):
                errors.append(f"Ligne {index+1}: Téléchargement échoué")
                continue
            if cut_video_ffmpeg(temp_file, start, end, output_file):
                success += 1
            else:
                errors.append(f"Ligne {index+1}: Découpage échoué")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            time.sleep(random.uniform(0.5, 1.5))
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
    uploaded_file = st.file_uploader("📤 Upload votre fichier CSV", type=['csv'], help="Format: videoUrl, startTime, endTime, questionText")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        required_cols = ['videoUrl', 'startTime', 'endTime', 'questionText']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Colonnes manquantes: {', '.join(missing_cols)}")
        else:
            st.success(f"✅ CSV chargé: {len(df)} lignes")
            with st.expander("📋 Aperçu (5 premières lignes)"):
                st.dataframe(df.head(), use_container_width=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f'<div class="stats-box"><h3>📝</h3><p>Total</p><h2>{len(df)}</h2></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="stats-box"><h3>🎬</h3><p>URLs</p><h2>{df["videoUrl"].nunique()}</h2></div>', unsafe_allow_html=True)
            with col3:
                avg = int((df['endTime'] - df['startTime']).mean())
                st.markdown(f'<div class="stats-box"><h3>⏱️</h3><p>Moy.</p><h2>{avg}s</h2></div>', unsafe_allow_html=True)
            with col4:
                total = int((df['endTime'] - df['startTime']).sum()/60)
                st.markdown(f'<div class="stats-box"><h3>🎞️</h3><p>Total</p><h2>{total}m</h2></div>', unsafe_allow_html=True)
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("🚀 LANCER LE DÉCOUPAGE", type="primary", use_container_width=True):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        st.markdown("### 🔄 Traitement en cours...")
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        success, errors, output_dir = process_videos(df, temp_dir, progress_bar, status_text)
                        st.markdown("---")
                        st.markdown("### 📊 Résultats")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f'<div class="success-box"><h3>✅ Succès</h3><h2>{success}/{len(df)}</h2><p>{success/len(df)*100:.1f}%</p></div>', unsafe_allow_html=True)
                        with col2:
                            st.markdown(f'<div class="error-box"><h3>❌ Échecs</h3><h2>{len(errors)}/{len(df)}</h2><p>{len(errors)/len(df)*100:.1f}%</p></div>', unsafe_allow_html=True)
                        if errors:
                            with st.expander(f"⚠️ Détails des {len(errors)} échecs"):
                                for error in errors[:20]:
                                    st.text(f"• {error}")
                                if len(errors) > 20:
                                    st.text(f"... et {len(errors)-20} autres")
                        if success > 0:
                            st.markdown("---")
                            with st.spinner("📦 Création du ZIP..."):
                                zip_buffer = create_zip(output_dir)
                                zip_size = len(zip_buffer.getvalue()) / (1024 * 1024)
                                st.success(f"✅ ZIP créé: {zip_size:.1f} MB avec {success} vidéos")
                                st.download_button("⬇️ TÉLÉCHARGER LE ZIP", data=zip_buffer, file_name="videos_decoupees.zip", mime="application/zip", type="primary", use_container_width=True)
                                st.balloons()
                        else:
                            st.error("❌ Aucune vidéo créée")
    except Exception as e:
        st.error(f"❌ Erreur: {str(e)}")
else:
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📖 Instructions\n\n**1️⃣ Préparez CSV** avec colonnes: videoUrl, startTime, endTime, questionText\n\n**2️⃣ Uploadez** le fichier\n\n**3️⃣ Lancez** le traitement\n\n**4️⃣ Téléchargez** le ZIP")
    with col2:
        st.markdown("### ⚙️ Caractéristiques\n\n✅ 3 tentatives par vidéo\n\n✅ Qualité 240p-480p\n\n✅ Gestion erreurs\n\n✅ ZIP téléchargeable")
    st.markdown("---")
    st.markdown("### 📄 Exemple CSV")
    example = pd.DataFrame({'videoUrl': ['https://www.youtube.com/watch?v=abc123', 'https://youtu.be/xyz789'], 'startTime': [25, 50], 'endTime': [32, 60], 'questionText': ['Which team?', 'What score?']})
    st.dataframe(example, use_container_width=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Made with ❤️ for Lyra | v1.0</p>", unsafe_allow_html=True)
