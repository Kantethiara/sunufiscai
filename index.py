import os
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
import json

# Chargement des variables d'environnement
load_dotenv()

# Configuration Elasticsearch
es = Elasticsearch("http://localhost:9200", request_timeout=30)


def check_connection():
    if not es.ping():
        raise ConnectionError("❌ Connexion Elasticsearch échouée")
    print("✅ Connecté à Elasticsearch")

# Définition du mapping (tu peux adapter selon ta structure)
mapping = {
    "mappings": {
        "properties": {
            "question": {"type": "text"},
            "reponse": {"type": "text"},
            "date_creation": {"type": "date"},
            "tags": {"type": "keyword"}
        }
    }
}

# Création de l'index
es.indices.create(index="assistant_fiscal_v2", body=mapping)
print("✅ Index 'assistant_fiscal_v2' créé avec succès")

def prepare_document(doc):
    """Transforme votre structure JSON en document Elasticsearch"""
    if "messages" in doc:  # Ancien format conversation
        return prepare_conversation_doc(doc)
    else:  # Nouveau format déjà optimisé
        return {
            "_index": "assistant_fiscal_v2",
            "_source": {
                "type": doc.get("type", "qa_technique"),
                "question": doc["question"],
                "reponse": doc["reponse"],
                "tags": doc.get("tags", []),
                "language": doc.get("language", "fr"),
                "metadata": {
                    "certifie_par": doc.get("certifie_par", "DGI Sénégal"),
                    "reference_legale": doc.get("references", []),
                    "source": doc.get("source", "base_interne")
                }
            }
        }

def prepare_conversation_doc(doc):
    """Convertit les conversations en paires Q/R"""
    actions = []
    messages = doc["messages"]
    current_question = None
    
    for msg in messages:
        if msg["role"] == "user":
            current_question = msg["content"]
        elif msg["role"] == "assistant" and current_question:
            action = {
                "_index": "assistant_fiscal_v2",
                "_source": {
                    "type": "qa_technique",
                    "question": current_question,
                    "reponse": msg["content"],
                    "tags": detect_tags(current_question, msg["content"]),
                    "language": "fr",
                    "metadata": {
                        "certifie_par": "DGI Sénégal",
                        "reference_legale": [],
                        "source": "historique_conversations"
                    }
                }
            }
            actions.append(action)
            current_question = None
    return actions

def detect_tags(question, reponse):
    """Détection automatique des tags fiscaux"""
    content = question.lower() + " " + reponse.lower()
    tags = []
    
    fiscal_terms = {
        "impôt": ["impôt", "fiscal", "taxe"],
        "TVA": ["tva", "taxe sur la valeur"],
        "IR": ["impôt sur le revenu", "irpp"],
        "IS": ["impôt sur les sociétés", "is"],
        "délai": ["délai", "délais", "durée"],
        "document": ["document", "pièce", "justificatif"]
    }
    
    for tag, keywords in fiscal_terms.items():
        if any(keyword in content for keyword in keywords):
            tags.append(tag)
    
    return tags if tags else ["fiscalité"]

def index_documents(file_path):
    """Indexe les documents par lots"""
    with open(file_path) as f:
        data = json.load(f)
    
    actions = []
    for doc in data:
        prepared = prepare_document(doc)
        if isinstance(prepared, list):  # Cas des conversations
            actions.extend(prepared)
        else:  # Document unique
            actions.append(prepared)
    
    success, errors = helpers.bulk(es, actions, stats_only=True)
    print(f"\n📊 Résultat de l'indexation :")
    print(f"- Documents indexés : {success}")
    if errors:
        print(f"- Erreurs : {errors}")
    
    # Rafraîchissement pour rendre les documents disponibles
    es.indices.refresh(index="assistant_fiscal_v2")
    print("✔ Index rafraîchi")

if __name__ == "__main__":
    try:
        check_connection()
        
        # Vérification que l'index existe
        if not es.indices.exists(index="assistant_fiscal_v2"):
            raise Exception("L'index 'assistant_fiscal_v2' n'existe pas. Créez-le d'abord.")
        
        # Chemin vers votre fichier JSON
        data_file = "/Users/thiarakante/Documents/project/data/qa_format_optimise.json"
        index_documents(data_file)
        
    except Exception as e:
        print(f"❌ Erreur : {str(e)}")