from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict
import uuid
import csv
from contextlib import asynccontextmanager
from pathlib import Path
import os
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
# Importez votre classe existante
from app import PremiumFiscalAssistant  # Remplacez par le bon import
from elasticsearch import Elasticsearch


# Configuration de l'API
security = HTTPBearer()
app = FastAPI(title="API Assistant Fiscal Premium")


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. Chemin corrigé et isolé dans un sous-répertoire
CONVERSATION_DB = Path(__file__).parent / "conversation_data"  # Crée un sous-dossier dédié

# 2. Création sécurisée du répertoire
try:
    CONVERSATION_DB.mkdir(exist_ok=True)
except Exception as e:
    print(f"⚠️ Erreur création du dossier: {e}")
    # Solution de repli temporaire
    CONVERSATION_DB = Path("/tmp/conversation_data")
    CONVERSATION_DB.mkdir(exist_ok=True)

# 3. Vérification des permissions
if not os.access(CONVERSATION_DB, os.W_OK):
    raise RuntimeError(f"Pas d'accès en écriture à {CONVERSATION_DB}")

# Modèles Pydantic
class QuestionRequest(BaseModel):
    question: str
    user_id: Optional[str] = None  # Optionnel pour suivre les utilisateurs

class QAItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime
    conversation_id: str

class HealthCheck(BaseModel):
    status: str
    details: Dict[str, str]

# Variables globales
assistant = None
conversation_history = []


# Initialisation Elasticsearch
@app.on_event("startup")
async def startup():
    try:
        app.state.es = Elasticsearch(
            os.getenv("ELASTICSEARCH_URL"),
            api_key=os.getenv("ELASTIC_API_KEY"),
            request_timeout=10,
            verify_certs=True
        )
        if not app.state.es.ping():
            raise RuntimeError("Connexion Elasticsearch échouée")
        print("✅ Elasticsearch connecté")
    except Exception as e:
        print(f"❌ Erreur Elasticsearch: {str(e)}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'API"""
    global assistant
    # Initialisation de l'assistant
    try:
        assistant = PremiumFiscalAssistant()
        print("✅ Assistant fiscal initialisé avec succès")
    except Exception as e:
        print(f"❌ Erreur d'initialisation: {str(e)}")
        raise
    yield
    # Nettoyage
    assistant = None
    conversation_history.clear()

app.router.lifespan_context = lifespan

# Stockage des conversations (à remplacer par une base de données en production)
conversation_history = []
@app.get("/")
async def root():
    return {
        "status": "API Assistant Fiscal en service",
        "endpoints": {
            "documentation": "/docs",
            "ask": "/api/ask",
            "health": "/api/health"
        }
    }
@app.post("/api/ask", response_model=QAItem)
async def ask_question(request: QuestionRequest):
    """
    Endpoint strictement fiscal avec toutes les validations du CLI
    """
    try:
        # Initialisation et vérifications de base
        if not hasattr(app, 'assistant'):
            app.assistant = PremiumFiscalAssistant()
            
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question vide")

        # 1. Gestion PRIORITAIRE des salutations (avant la détection de langue)
        question_lower = question.lower()
        if any(salut in question_lower for salut in app.assistant.salutations):
            # Cas spécial pour les salutations simples (1-2 mots)
            if len(question.split()) <= 2:
                return create_response(
                    question,
                    "💼 Bonjour ! Assistant fiscal sénégalais à votre service. Posez-moi vos questions sur les impôts et taxes."
                )
            # Cas des salutations + question (ex: "Bonjour, comment payer la TVA ?")
            # => On continue le traitement normal

        # 2. Vérification linguistique (sauf pour les salutations simples)
        try:
            if detect(question) != "fr" :
                return create_response(
                    question,
                    "⛔ Veuillez poser votre question en français uniquement."
                )
        except LangDetectException:
            # On accepte les salutations même si la détection échoue
            if not any(salut in question_lower for salut in app.assistant.salutations):
                return create_response(
                    question,
                    "⚠️ Impossible de détecter la langue de votre question."
                )

        # Traitement par l'agent avec gestion d'erreur
        try:
            response = app.assistant.agent.invoke({"input": question})
            answer = response['output']
            
            # Validation finale de la réponse
            if should_reject_response(answer):
                answer = ("⛔ [Réponse bloquée] Cette question semble hors domaine fiscal. "
                          "Veuillez poser une question clairement liée à la fiscalité sénégalaise.")
            
                qa_item = create_response(question, answer)
                save_conversation(qa_item)
            return create_response(question, answer)
            
        except Exception as e:
            print(f"Erreur de traitement: {str(e)}")
            return create_response(question,
                "⚠️ Désolé, je rencontre une difficulté technique. "
                "Veuillez reformuler votre question ou consulter www.dgid.sn")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")

# Fonctions utilitaires
def create_response(question: str, answer: str) -> QAItem:
    """Crée une réponse standardisée avec suivi de conversation"""
    item = QAItem(
        question=question,
        answer=answer,
        timestamp=datetime.now(),
        conversation_id=str(uuid.uuid4())
    )
    conversation_history.append(item)
    return item

def save_conversation(qa_item: QAItem):
    """Sauvegarde dans un fichier CSV avec date"""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = CONVERSATION_DB / f"conversations_{today}.csv"
    
    file_exists = filepath.exists()
    
    with open(filepath, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='|')
        if not file_exists:
            writer.writerow(["timestamp", "question", "answer", "conversation_id"])
        writer.writerow([
            qa_item.timestamp.isoformat(),
            qa_item.question,
            qa_item.answer,
            qa_item.conversation_id
        ])

def is_question_fiscale_strict(question: str) -> bool:
    """Version renforcée de la validation des questions"""
    assistant = getattr(app, 'assistant', None)
    if not assistant:
        return False
    
    # Vérification standard
    if not assistant._est_question_fiscale(question):
        return False
    
    # Liste noire de sujets non fiscaux
    non_fiscal_keywords = {
        "président", "premier ministre", "ministre", "gouvernement",
        "fifa", "politique", "élection", "parti", "sport", "football",
        "biographie", "histoire", "culture", "religion","nourriture",
        "voyage", "tourisme", "santé", "médecine", "éducation",
        "loisirs", "cinéma", "musique", "art", "littérature",
        "sciences", "technologie", "informatique", "programmation",
        "environnement", "écologie", "climat", "nature", "animaux",
        "philosophie", "psychologie", "sociologie", "anthropologie",
        "carrière", "emploi", "recrutement", "formation", "stage",
        "capitale", "monnaie", "économie", "marché"
    }
    
    return not any(keyword in question.lower() for keyword in non_fiscal_keywords)

def should_reject_response(answer: str) -> bool:
    """Détecte les réponses inappropriées qui auraient pu passer"""
    rejection_phrases = {
        "je ne sais pas", "je ne connais pas", "premier ministre",
        "président de", "ministre de", "dans le domaine", "hors sujet"
    }
    
    answer_lower = answer.lower()
    return (any(phrase in answer_lower for phrase in rejection_phrases) 
            or not app.assistant._est_question_fiscale(answer))
    
@app.get("/api/conversations", response_model=List[QAItem])
async def get_conversations(limit: int = 10):
    """
    Endpoint pour récupérer l'historique des conversations
    """
    return conversation_history[-limit:]

@app.get("/api/health", response_model=HealthCheck)
async def health_check():
    """
    Endpoint de vérification de l'état de l'API
    """
    status = "healthy"
    details = {
        "elasticsearch": "connected" if assistant and assistant.es.ping() else "disconnected",
        "llm": "ready" if assistant and assistant.llm else "unavailable",
        "conversations_stored": len(conversation_history),
        "last_updated": datetime.now().isoformat()
    }
    
    if not assistant or not assistant.es.ping():
        status = "degraded"
    
    return {"status": status, "details": details}

# Fonction utilitaire pour les tests
def _get_test_client():
    from fastapi.testclient import TestClient
    return TestClient(app)