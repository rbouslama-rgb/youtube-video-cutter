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
from pytube import YouTube
from moviepy.editor import VideoFileClip

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
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Upload CSV → Get Cut Videos in ZIP 🚀</p>', unsafe_allow_html=True)

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80].strip('_')

def download_youtube_video(url, output_path, status_placeholder):
    try:
        status_placeholder.text("📡 Connexion à YouTube...")
        yt = YouTube(url)
        
        status_placeholder.text("📡 Sélection du stream...")
        # Essayer plusieurs qualités
        stream = (yt.streams.filter(progressive=True, file_extension='mp4')
                 .order_by('resolution')
                 .desc()
                 .first())
        
        if not stream:
            stream = yt.streams.filter(file_extension='mp4').first()
        
        if not stream:
            return False
        
        status_placeholder.text("⬇️ Téléchargement...")
        stream.download(output_path=os.path.dirname(output_path), 
                       filename=os.path.basename(output_path))
        
        return os.path.exists(output_path)
    except Exception as e:
        status_placeholder.text(f"❌ Erreur: {str(e)[:50]}")
        return False

def cut_video(input_path, start, end, output_path, status_placeholder):
    try:
        status_placeholder.text("✂️ Découpage vidéo...")
        video = VideoFileClip(input_path)
        
        # Ajuster temps si nécessaire
        if start >= video.duration:
            video.close()
            return False
        
        actual_end = min(end, video.duration)
        
        # Découper
        cut_clip = video.subclip(start, actual_end)
        
        # Sauvegarder
        cut_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            verbose=False,
            logger=None
        )
        
        cut_clip.close()
        video.close()
        
        return os.path.exists(output_path)
    except Exception as e:
        status_placeholder.text(f"❌ Erreur découpage: {str(e)[:50]}")
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
            
            # Télécharger
            if not download_youtube_video(url, temp_file, detail_status):
                errors.append(f"Ligne {index+1}: Téléchargement échoué")
                continue
            
            # Découper
            if cut_video(temp_file, start, end, output_file, detail_status):
                success += 1
                detail_status.text(f"✅ Vidéo {index+1} créée!")
            else:
                errors.append(f"Ligne {index+1}: Découpage échoué")
            
            # Nettoyer
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            time.sleep(random.uniform(1, 2))
        
        except Exception as e:
            errors.append(f"Ligne {index+1}: {str(e)[:50]}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
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

# Interface
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("---")
    uploaded_file = st.file_uploader("📤 Upload CSV", type=['csv'], 
                                     help="videoUrl, startTime, endTime, questionText")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        required = ['videoUrl', 'startTime', 'endTime', 'questionText']
        missing = [c for c in required if c not in df.columns]
        
        if missing:
            st.error(f"❌ Colonnes manquantes: {', '.join(missing)}")
        else:
            st.success(f"✅ CSV chargé: {len(df)} lignes")
            
            with st.expander("📋 Aperçu (5 premières lignes)"):
                st.dataframe(df.head(), use_container_width=True)
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="stats-box"><h3>📝</h3><p>Total</p><h2>{len(df)}</h2></div>', 
                           unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="stats-box"><h3>🎬</h3><p>URLs</p><h2>{df["videoUrl"].nunique()}</h2></div>', 
                           unsafe_allow_html=True)
            with c3:
                avg = int((df['endTime'] - df['startTime']).mean())
                st.markdown(f'<div class="stats-box"><h3>⏱️</h3><p>Moy.</p><h2>{avg}s</h2></div>', 
                           unsafe_allow_html=True)
            with c4:
                total_min = int((df['endTime'] - df['startTime']).sum() / 60)
                st.markdown(f'<div class="stats-box"><h3>🎞️</h3><p>Total</p><h2>{total_min}m</h2></div>', 
                           unsafe_allow_html=True)
            
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
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            success_pct = (success / len(df) * 100) if len(df) > 0 else 0
                            st.markdown(f'<div class="success-box"><h3>✅ Succès</h3><h2>{success}/{len(df)}</h2><p>{success_pct:.1f}%</p></div>', 
                                       unsafe_allow_html=True)
                        with c2:
                            error_pct = (len(errors) / len(df) * 100) if len(df) > 0 else 0
                            st.markdown(f'<div class="error-box"><h3>❌ Échecs</h3><h2>{len(errors)}/{len(df)}</h2><p>{error_pct:.1f}%</p></div>', 
                                       unsafe_allow_html=True)
                        
                        if errors:
                            with st.expander(f"⚠️ Détails des {len(errors)} échecs"):
                                for error in errors[:20]:
                                    st.text(f"• {error}")
                                if len(errors) > 20:
                                    st.text(f"... et {len(errors) - 20} autres")
                        
                        if success > 0:
                            st.markdown("---")
                            with st.spinner("📦 Création du ZIP..."):
                                zip_buffer = create_zip(output_dir)
                                zip_size = len(zip_buffer.getvalue()) / (1024 * 1024)
                                
                                st.success(f"✅ ZIP créé: {zip_size:.1f} MB avec {success} vidéos")
                                
                                st.download_button(
                                    "⬇️ TÉLÉCHARGER LE ZIP",
                                    data=zip_buffer,
                                    file_name="videos_decoupees.zip",
                                    mime="application/zip",
                                    type="primary",
                                    use_container_width=True
                                )
                                
                                st.balloons()
                        else:
                            st.error("❌ Aucune vidéo n'a pu être créée. Vérifiez les erreurs ci-dessus.")
    
    except Exception as e:
        st.error(f"❌ Erreur: {str(e)}")

else:
    st.markdown("---")
    st.info("📤 **Uploadez un fichier CSV** avec les colonnes: videoUrl, startTime, endTime, questionText")
    
    st.markdown("### 📄 Exemple de CSV")
    example = pd.DataFrame({
        'videoUrl': ['https://www.youtube.com/watch?v=dQw4w9WgXcQ'],
        'startTime': [30],
        'endTime': [45],
        'questionText': ['Example question']
    })
    st.dataframe(example, use_container_width=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Made with ❤️ for Lyra | v2.0</p>", unsafe_allow_html=True)
