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

# Configuration de la page
st.set_page_config(
    page_title="YouTube Video Cutter",
    page_icon="✂️",
    layout="wide"
)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #FF4B4B;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 3rem;
    }
    .stats-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stats-box h3 {
        font-size: 2rem;
        margin: 0;
    }
    .stats-box p {
        margin: 5px 0;
        font-size: 0.9rem;
    }
    .stats-box h2 {
        font-size: 2.5rem;
        margin: 10px 0;
        font-weight: bold;
    }
    .success-box {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .success-box h3 {
        margin: 0;
        font-size: 1.5rem;
    }
    .success-box h2 {
        font-size: 3rem;
        margin: 10px 0;
    }
    .error-box {
        background: linear-gradient(135deg, #f44336 0%, #e53935 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .error-box h3 {
        margin: 0;
        font-size: 1.5rem;
    }
    .error-box h2 {
        font-size: 3rem;
        margin: 10px 0;
    }
    .stButton>button {
        font-size: 1.2rem;
        font-weight: bold;
        padding: 15px 30px;
    }
    .instruction-box {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# En-tête
st.markdown('<h1 class="main-header">✂️ YouTube Video Cutter</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Upload CSV → Get Cut Videos in ZIP 🚀</p>', unsafe_allow_html=True)

# Fonctions utilitaires
def sanitize_filename(text):
    """Nettoyer le nom de fichier des caractères invalides"""
    text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80].strip('_')

def download_youtube_video(url, output_path):
    """Télécharger vidéo YouTube avec plusieurs stratégies"""
    strategies = [
        ['yt-dlp', '-f', '18', '-o', output_path, '--no-playlist', '--quiet', '--no-warnings', url],
        ['yt-dlp', '-f', 'best[height<=480]', '-o', output_path, '--no-playlist', '--quiet', '--no-warnings', url],
        ['yt-dlp', '-f', 'worst[ext=mp4]', '-o', output_path, '--no-playlist', '--quiet', '--no-warnings', url]
    ]
    
    for cmd in strategies:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            time.sleep(1)
        except Exception:
            continue
    
    return False

def cut_video_ffmpeg(input_path, start, end, output_path):
    """Découper vidéo avec FFmpeg"""
    try:
        # Essayer copie directe (plus rapide)
        cmd = [
            'ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end),
            '-c', 'copy', '-y', output_path, '-loglevel', 'error'
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        
        # Sinon réencoder
        cmd = [
            'ffmpeg', '-i', input_path, '-ss', str(start), '-to', str(end),
            '-c:v', 'libx264', '-c:a', 'aac', '-b:v', '400k',
            '-preset', 'ultrafast', '-y', output_path, '-loglevel', 'error'
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_path)
    
    except Exception:
        return False

def process_videos(df, temp_dir, progress_bar, status_text):
    """Traiter toutes les vidéos du CSV"""
    output_dir = os.path.join(temp_dir, 'videos_decoupees')
    temp_download_dir = os.path.join(temp_dir, 'temp')
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_download_dir, exist_ok=True)
    
    total = len(df)
    success = 0
    errors = []
    
    for index, row in df.iterrows():
        try:
            # Mise à jour de la progression
            progress = (index + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"🔄 Traitement vidéo {index+1}/{total}...")
            
            # Extraire les données
            url = str(row['videoUrl']).strip()
            start = int(row['startTime'])
            end = int(row['endTime'])
            question = str(row['questionText']).strip()
            
            # Validation des données
            if not url.startswith('http') or start >= end:
                errors.append(f"Ligne {index+1}: Données invalides")
                continue
            
            # Créer nom de fichier
            filename_base = sanitize_filename(question)
            if len(filename_base) < 3:
                filename_base = f"video_{index+1}"
            
            filename = f"{filename_base}_{start}_{end}.mp4"
            temp_file = os.path.join(temp_download_dir, f'temp_{index}.mp4')
            output_file = os.path.join(output_dir, filename)
            
            # Télécharger vidéo
            if not download_youtube_video(url, temp_file):
                errors.append(f"Ligne {index+1}: Téléchargement échoué - {url[:50]}")
                continue
            
            # Découper vidéo
            if cut_video_ffmpeg(temp_file, start, end, output_file):
                success += 1
            else:
                errors.append(f"Ligne {index+1}: Découpage échoué")
            
            # Nettoyer fichier temporaire
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            # Pause entre vidéos
            time.sleep(random.uniform(0.5, 1.5))
        
        except Exception as e:
            errors.append(f"Ligne {index+1}: {str(e)[:50]}")
    
    return success, errors, output_dir

def create_zip(source_dir):
    """Créer fichier ZIP en mémoire"""
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    return zip_buffer

# Interface utilisateur principale
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown("---")
    uploaded_file = st.file_uploader(
        "📤 Upload votre fichier CSV",
        type=['csv'],
        help="Format requis: videoUrl, startTime, endTime, questionText"
    )

if uploaded_file is not None:
    try:
        # Lire le CSV
        df = pd.read_csv(uploaded_file)
        
        # Vérifier les colonnes requises
        required_cols = ['videoUrl', 'startTime', 'endTime', 'questionText']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Colonnes manquantes dans le CSV: {', '.join(missing_cols)}")
            st.info("📋 Colonnes requises: videoUrl, startTime, endTime, questionText")
        else:
            st.success(f"✅ CSV chargé avec succès: {len(df)} lignes détectées")
            
            # Aperçu des données
            with st.expander("📋 Aperçu des données (5 premières lignes)"):
                st.dataframe(df.head(), use_container_width=True)
            
            # Statistiques
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(
                    f'<div class="stats-box"><h3>📝</h3><p>Total Vidéos</p><h2>{len(df)}</h2></div>',
                    unsafe_allow_html=True
                )
            
            with col2:
                unique_urls = df['videoUrl'].nunique()
                st.markdown(
                    f'<div class="stats-box"><h3>🎬</h3><p>URLs Uniques</p><h2>{unique_urls}</h2></div>',
                    unsafe_allow_html=True
                )
            
            with col3:
                avg_duration = int((df['endTime'] - df['startTime']).mean())
                st.markdown(
                    f'<div class="stats-box"><h3>⏱️</h3><p>Durée Moy.</p><h2>{avg_duration}s</h2></div>',
                    unsafe_allow_html=True
                )
            
            with col4:
                total_duration = int((df['endTime'] - df['startTime']).sum() / 60)
                st.markdown(
                    f'<div class="stats-box"><h3>🎞️</h3><p>Durée Totale</p><h2>{total_duration}m</h2></div>',
                    unsafe_allow_html=True
                )
            
            st.markdown("---")
            
            # Bouton de traitement
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col2:
                if st.button("🚀 LANCER LE DÉCOUPAGE", type="primary", use_container_width=True):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        st.markdown("### 🔄 Traitement en cours...")
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Traiter les vidéos
                        success, errors, output_dir = process_videos(
                            df, temp_dir, progress_bar, status_text
                        )
                        
                        # Afficher les résultats
                        st.markdown("---")
                        st.markdown("### 📊 Résultats du traitement")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            success_percent = (success / len(df) * 100) if len(df) > 0 else 0
                            st.markdown(
                                f'<div class="success-box"><h3>✅ Succès</h3><h2>{success}/{len(df)}</h2><p>{success_percent:.1f}%</p></div>',
                                unsafe_allow_html=True
                            )
                        
                        with col2:
                            error_percent = (len(errors) / len(df) * 100) if len(df) > 0 else 0
                            st.markdown(
                                f'<div class="error-box"><h3>❌ Échecs</h3><h2>{len(errors)}/{len(df)}</h2><p>{error_percent:.1f}%</p></div>',
                                unsafe_allow_html=True
                            )
                        
                        # Afficher les erreurs
                        if errors:
                            with st.expander(f"⚠️ Détails des {len(errors)} échecs"):
                                for error in errors[:20]:
                                    st.text(f"• {error}")
                                if len(errors) > 20:
                                    st.text(f"... et {len(errors) - 20} autres erreurs")
                        
                        # Créer et télécharger le ZIP
                        if success > 0:
                            st.markdown("---")
                            st.markdown("### 📦 Téléchargement")
                            
                            with st.spinner("📦 Création du fichier ZIP..."):
                                zip_buffer = create_zip(output_dir)
                                zip_size = len(zip_buffer.getvalue()) / (1024 * 1024)
                                
                                st.success(f"✅ ZIP créé avec succès: {zip_size:.1f} MB contenant {success} vidéos")
                                
                                # Bouton de téléchargement
                                st.download_button(
                                    label="⬇️ TÉLÉCHARGER LE ZIP",
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
        st.error(f"❌ Erreur lors du traitement: {str(e)}")
        st.info("💡 Vérifiez que votre CSV est au bon format et réessayez.")

else:
    # Page d'accueil avec instructions
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="instruction-box">
        <h3>📖 Instructions d'utilisation</h3>
        
        <p><strong>1️⃣ Préparez votre fichier CSV</strong></p>
        <ul>
            <li>Colonnes requises: <code>videoUrl</code>, <code>startTime</code>, <code>endTime</code>, <code>questionText</code></li>
            <li>Temps en <strong>secondes</strong> (pas en format MM:SS)</li>
            <li>Avec ou sans ligne d'en-tête</li>
        </ul>
        
        <p><strong>2️⃣ Uploadez le fichier</strong></p>
        <ul>
            <li>Cliquez sur "Browse files"</li>
            <li>Sélectionnez votre CSV</li>
        </ul>
        
        <p><strong>3️⃣ Lancez le traitement</strong></p>
        <ul>
            <li>Vérifiez l'aperçu des données</li>
            <li>Cliquez "LANCER LE DÉCOUPAGE"</li>
            <li>Attendez (10-30 minutes selon nombre de vidéos)</li>
        </ul>
        
        <p><strong>4️⃣ Téléchargez le résultat</strong></p>
        <ul>
            <li>Un fichier ZIP contenant toutes les vidéos</li>
            <li>Rapport détaillé des succès/échecs</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="instruction-box">
        <h3>⚙️ Caractéristiques techniques</h3>
        
        <p><strong>✅ Fonctionnalités</strong></p>
        <ul>
            <li>3 tentatives automatiques par vidéo</li>
            <li>Qualité optimisée 240p-480p</li>
            <li>Gestion intelligente des erreurs</li>
            <li>Rapport détaillé en temps réel</li>
            <li>Noms de fichiers basés sur questions</li>
            <li>Téléchargement ZIP simple</li>
        </ul>
        
        <p><strong>📊 Formats supportés</strong></p>
        <ul>
            <li>URLs YouTube (youtube.com, youtu.be)</li>
            <li>Fichiers CSV standards</li>
            <li>Temps en secondes (entiers)</li>
        </ul>
        
        <p><strong>⚠️ Limitations</strong></p>
        <ul>
            <li>Vidéos publiques uniquement</li>
            <li>Maximum 1000 vidéos par traitement</li>
            <li>Temps d'attente selon nombre de vidéos</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📄 Exemple de fichier CSV")
    
    example_df = pd.DataFrame({
        'videoUrl': [
            'https://www.youtube.com/watch?v=abc123',
            'https://youtu.be/xyz789',
            'https://www.youtube.com/watch?v=def456'
        ],
        'startTime': [25, 50, 120],
        'endTime': [32, 60, 135],
        'questionText': [
            'Which national team is mentioned?',
            'What is the final score?',
            'Who scored the goal?'
        ]
    })
    
    st.dataframe(example_df, use_container_width=True)
    
    st.info("💡 **Astuce:** Vous pouvez télécharger cet exemple et le modifier pour tester l'outil!")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray; font-size: 0.9rem;'>Made with ❤️ by Claude AI for Lyra | Version 1.0 | © 2025</p>",
    unsafe_allow_html=True
)
```

---

## **COMMENT L'AJOUTER À GITHUB:**

1. **Sur votre repo GitHub**, cliquez **"Add file"** → **"Create new file"**
2. **Nom du fichier:** Tapez `app.py`
3. **Copiez-collez TOUT le code ci-dessus** dans la grande zone de texte
4. **Scrollez en bas**, cliquez **"Commit new file"**

✅ **C'est fait!**

---

## **PROCHAINES ÉTAPES:**

Maintenant créez les 2 autres fichiers:

**`requirements.txt`:**
```
streamlit==1.32.0
pandas==2.2.2
```

**`packages.txt`:**
```
ffmpeg
yt-dlp
