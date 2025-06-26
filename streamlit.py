import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from typing import Tuple, List
import base64
import os



# Configuration de la page
st.set_page_config(
    page_title="Assistant Fiscal Sénégalais",
    page_icon="💼",
    layout="centered"
)

# Constantes
API_URL = "https://sunufiscai-henb.onrender.com/api/ask"  # Correspond à l'endpoint @app.post("/api/ask")
SALUTATIONS = ["bonjour", "salut", "hello", "hi", "coucou", "yo", "salam"]

def clean_response(text: str) -> str:
    """Nettoie et formate la réponse de l'API"""
    if not text:
        return ""
    
    # Suppression HTML
    soup = BeautifulSoup(text, "html.parser")
    clean_text = soup.get_text(separator=" ")
    
    # Formatage Markdown amélioré
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', clean_text)
    clean_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', clean_text)
    clean_text = re.sub(r'📌', '📌 ', clean_text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Réduit les sauts de ligne multiples
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def call_api(question: str) -> Tuple[bool, str]:
    """
    Interroge l'API fiscale et retourne un tuple (succès, réponse)
    """
    try:
        if not question or len(question.strip()) < 3:
            return False, "❌ La question doit contenir au moins 3 caractères"

        question = question.strip()
        
        # Détection des salutations simples
        if any(salut in question.lower() for salut in SALUTATIONS if len(question.split()) <= 3):
            return True, "👋 Bonjour ! Je suis votre assistant fiscal. Posez-moi votre question sur les impôts, taxes ou réglementations fiscales sénégalaises."

        # Création du payload selon le modèle QuestionRequest de l'API
        payload = {
            "question": question,
            "user_id": "streamlit_user"  # Optionnel mais conforme au modèle
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        with requests.Session() as session:
            # Changement crucial: utilisation de POST au lieu de GET
            response = session.post(
                API_URL,
                json=payload,  # Envoi des données en JSON
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                return False, f"⚠️ Format de réponse inattendu: {str(data)}"
            
            # Adaptation à la structure de QAItem
            if "answer" in data:
                return True, data["answer"]
            elif "output" in data:  # Alternative selon la réponse de l'API
                return True, data["output"]
            else:
                return False, f"⚠️ Réponse API incomplète: {str(data)}"

    except requests.exceptions.RequestException as e:
        return False, f"🔌 Erreur de connexion à l'API: {str(e)}"
    except Exception as e:
        return False, f"⚠️ Erreur inattendue: {str(e)}"

# Initialisation de l'historique
def init_history() -> List[Tuple[str, str]]:
    return [
        ("SunuFiscAI", 
         "\n\n"
         "💼 Bonjour ! Je suis votre assistant spécialisé dans la fiscalité sénégalaise. "
         "Posez-moi vos questions sur la fiscalité sénégalaise")
    ]

if 'history' not in st.session_state:
    st.session_state.history = init_history()

# Style CSS personnalisé
st.markdown("""
<style>
    
    .header {
        background-color: #2c3e50;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
        color: white;
    }
    .chat-container {
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        max-height: 60vh;
        overflow-y: auto;
        background-color: #1E1E1E;
    }
    .user-message {
        padding: 1rem;
        border-radius: 10px 10px 0 10px;
        margin-bottom: 1rem;
        margin-left: 15%;
        background-color: #3B3B3B;
        color: white;
    }
    .assistant-message {
        padding: 1rem;
        border-radius: 10px 10px 10px 0;
        margin-bottom: 1rem;
        margin-right: 15%;
        border-left: 4px solid #3498db;
        background-color: #2B2B2B;
        color: white;
    }
    .markdown-content {
        font-family: Arial, sans-serif;
        line-height: 1.6;
    }
    .stTextInput>div>div>input {
        border-radius: 20px;
        padding: 10px 15px;
        background-color: #3B3B3B;
        color: white;
        border: 1px solid #555;
    }
    .stButton>button {
        border-radius: 20px;
        padding: 10px 24px;
        background-color: #3498db;
        color: white;
        border: none;
    }
    .stButton>button:hover {
        background-color: #2980b9;
    }
    .error-message {
        color: #e74c3c;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# En-tête
st.markdown("""
<div class="header">
    <h1>💼 Assistant Fiscal Sénégalais</h1>
    <p>Direction Générale des Impôts et Domaines</p>
</div>
""", unsafe_allow_html=True)

# Affichage du chat
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for role, message in st.session_state.history:
    if role == "user":
        st.markdown(f'''
        <div class="user-message">
            <strong>Vous :</strong><br>{message}
        </div>
        ''', unsafe_allow_html=True)
    else:
        cleaned_message = clean_response(message)
        st.markdown(f'''
        <div class="SunuFiscAI-message">
            <div class="markdown-content">
                <strong>SunuFiscAI :</strong><br>{cleaned_message}
            </div>
        </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Saisie utilisateur
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Votre question fiscale",
        placeholder="Ex: Quelles sont les taxes applicables aux entreprises?",
        key="user_input",
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns([1, 6])
    with col1:
        submitted = st.form_submit_button("Envoyer")
    with col2:
        if st.form_submit_button("Nouvelle discussion"):
            st.session_state.history = init_history()
            st.rerun()

    if submitted and user_input:
        user_input = user_input.strip()
        st.session_state.history.append(("user", user_input))
        
        # Commandes spéciales
        if user_input.lower() in ['au revoir', 'bye', 'quit', 'q', 'exit']:
            st.session_state.history.append(("assistant", "Merci pour votre confiance. À bientôt pour vos questions fiscales !"))
        else:
            with st.spinner("Recherche dans la base fiscale..."):
                success, api_response = call_api(user_input)
                
                if not success:
                    st.error(api_response)
                
                st.session_state.history.append(("assistant", api_response))
        
        st.rerun()


# Chemin absolu vers votre logo (à adapter)
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")

# Fonction pour créer un background avec logo
def sidebar_with_bg(LOGO_PATH, opacity=0.2):
    # Convertir l'image en base64
    with open(LOGO_PATH, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    
    # CSS personnalisé    import os
    
    # Chemin relatif vers le logo
    sidebar_css = f"""
    <style>
        [data-testid="stSidebar"] {{
            position: relative;
        }}
        [data-testid="stSidebar"]::before {{
            content: "";
            background-image: url("data:image/png;base64,{encoded_string}");
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            opacity: {opacity};
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            z-index: -1;
        }}
        .sidebar-content {{
            position: relative;
            z-index: 1;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 20px;
            border-radius: 10px;
            margin: 10px;
        }}
    </style>
    """
    st.markdown(sidebar_css, unsafe_allow_html=True)

# Configuration de la sidebar
with st.sidebar:
    sidebar_with_bg(LOGO_PATH, opacity=0.15)  # Ajustez l'opacité
    
    # # Contenu dans une div pour le z-index
    # st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    
    # # Logo principal (visible)
    # st.image(LOGO_PATH, width=200)
    
    # Vos informations
    st.header("ℹ️ Informations")
    st.markdown("""
    **Domaines couverts:**
    - Impôts et taxes
    - Procédures fiscales DGID
    - Textes de loi fiscale
    - Calculs d'imposition
    - Déclarations fiscales
    """)
    
    st.markdown("""
    **Support technique:**
    📞 **00221772509700**  
    ✉️ **33 889 20 02**  
    🌐 **[www.dgid.sn](https://www.dgid.sn)**
    """)
    
    st.markdown("---")
    st.caption("Version 1.0 - Mai 2025")
    
    st.markdown('</div>', unsafe_allow_html=True)