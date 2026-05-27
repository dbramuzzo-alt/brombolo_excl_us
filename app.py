import streamlit as st
import billboard
import pandas as pd
from github import Github, Auth
import io
import datetime

# --- 1. CONFIGURAZIONE ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"].strip()
    # Nome del file modificato per evitare conflitti con la Hot 100
    FILE_PATH = "archivio_billboard_global.csv"
except Exception as e:
    st.error("❌ Errore Secrets: Controlla GITHUB_TOKEN e REPO_NAME.")
    st.stop()

auth = Auth.Token(TOKEN)
g = Github(auth=auth)

def carica_archivio():
    """Legge il file e restituisce il DataFrame e lo SHA aggiornato"""
    try:
        repo = g.get_repo(REPO_NAME)
        file_content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df, file_content.sha
    except Exception:
        # Se il file non esiste (404) o è vuoto
        return pd.DataFrame(columns=["Data", "Tag", "Pos", "Canzone", "Artista"]), None

def salva_su_github(df_nuovo):
    """Recupera lo SHA in tempo reale e salva per evitare l'errore 422"""
    repo = g.get_repo(REPO_NAME)
    csv_content = df_nuovo.to_csv(index=False)
    
    try:
        # Proviamo a vedere se il file esiste già per prendere lo SHA fresco
        contents = repo.get_contents(FILE_PATH)
        repo.update_file(FILE_PATH, "Update Billboard Global Excl US", csv_content, contents.sha)
    except Exception:
        # Se il file non esiste, lo creiamo da zero senza SHA
        repo.create_file(FILE_PATH, "Create Billboard Global Excl US", csv_content)

def correggi_data(data_in):
    giorno = data_in.weekday()
    return data_in if giorno == 5 else data_in - datetime.timedelta(days=(giorno + 2) % 7)

# --- 2. INTERFACCIA ---
st.set_page_config(page_title="Billboard Global Archiver", layout="wide")
st.title("🌐 Billboard Global Excl. US Archiver")

df_storico, _ = carica_archivio() # Lo SHA lo recuperiamo al volo nel salvataggio

st.sidebar.header("📥 Download")
data_scelta = st.sidebar.date_input("Data (Sabato)", value=datetime.date.today())

if st.sidebar.button("Scarica Classifica"):
    data_ok = correggi_data(data_scelta)
    
    with st.spinner(f"Scaricando classifica del {data_ok}..."):
        try:
            # Endpoint modificato per puntare alla classifica Global Excl. US
            chart = billboard.ChartData('global-excl-us', date=str(data_ok))
            if not chart:
                st.error("Billboard non ha risposto.")
            else:
                # Logica controllo brani già salvati nell'archivio globale
                gia_visti = set()
                if not df_storico.empty:
                    gia_visti = set((df_storico['Canzone'].str.lower() + " - " + df_storico['Artista'].str.lower()).unique())

                nuove_righe = []
                for e in chart:
                    chiave = f"{e.title} - {e.artist}".lower().strip()
                    nuove_righe.append({
                        "Data": str(chart.date),
                        "Tag": "NEW✨" if chiave not in gia_visti else "",
                        "Pos": e.rank,
                        "Canzone": e.title,
                        "Artista": e.artist
                    })
                
                df_finale = pd.concat([df_storico, pd.DataFrame(nuove_righe)], ignore_index=True)
                
                # Salvataggio con recupero SHA dinamico
                salva_su_github(df_finale)
                
                st.success("✅ Salvato con successo!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Errore durante il processo: {e}")

# --- 3. TABELLA ---
if not df_storico.empty:
    st.subheader(f"📊 Archivio Globale ({len(df_storico)} righe)")
    df_vista = df_storico.copy()
    df_vista['Data'] = pd.to_datetime(df_vista['Data'])
    
    solo_new = st.checkbox("Mostra solo 'NEW✨'")
    if solo_new:
        df_vista = df_vista[df_vista['Tag'] == "NEW✨"]
        
    st.dataframe(
        df_vista.sort_values(by=["Data", "Pos"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("L'archivio è vuoto o il file non è ancora stato creato su GitHub.")
