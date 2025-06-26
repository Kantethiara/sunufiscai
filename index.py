import os
from elasticsearch import Elasticsearch, helpers, NotFoundError
from dotenv import load_dotenv
import json

# Chargement des variables d'environnement
load_dotenv()

# Configuration sécurisée Elasticsearch
es = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL", "https://my-elasticsearch-project-beb3d2.es.us-east-1.aws.elastic.cloud:443"),
    api_key=os.getenv("ELASTIC_API_KEY"),
    request_timeout=30,
    verify_certs=True
)

def check_connection():
    """Vérifie la connexion à Elasticsearch"""
    try:
        if not es.ping():
            raise ConnectionError("Connexion échouée")
        print("✅ Connecté à Elasticsearch")
        return True
    except Exception as e:
        print(f"❌ Erreur de connexion: {str(e)}")
        return False

# Configuration optimisée du mapping
FISCALITY_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "french_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "french_stemmer",
                        "asciifolding"
                    ]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "question": {
                "type": "text",
                "analyzer": "french_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "reponse": {"type": "text", "analyzer": "french_analyzer"},
            "date_creation": {"type": "date"},
            "tags": {"type": "keyword"},
            "language": {"type": "keyword"},
            "metadata": {
                "properties": {
                    "certifie_par": {"type": "keyword"},
                    "reference_legale": {"type": "keyword"},
                    "source": {"type": "keyword"}
                }
            }
        }
    }
}

def init_index():
    """Initialise l'index avec gestion des erreurs"""
    try:
        # Suppression si l'index existe déjà
        if es.indices.exists(index="fiscality"):
            es.indices.delete(index="fiscality")
            print("♻️ Ancien index supprimé")
        
        # Création du nouvel index
        es.indices.create(
            index="fiscality",
            body=FISCALITY_MAPPING,
            ignore=400  # Ignore l'erreur si l'index existe déjà
        )
        print("✅ Index 'fiscality' créé avec succès")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de l'index: {str(e)}")
        return False

def prepare_document(doc):
    """Transforme la structure JSON en document Elasticsearch"""
    doc_source = {
        "type": doc.get("type", "qa_technique"),
        "question": doc["question"],
        "reponse": doc["reponse"],
        "tags": doc.get("tags", []),
        "language": doc.get("language", "fr"),
        "date_creation": doc.get("date_creation", "now"),
        "metadata": {
            "certifie_par": doc.get("certifie_par", "DGI Sénégal"),
            "reference_legale": doc.get("references", []),
            "source": doc.get("source", "base_interne")
        }
    }
    
    # Nettoyage des champs vides
    return {k: v for k, v in {
        "_index": "fiscality",
        "_source": doc_source
    }.items() if v is not None}
def validate_document(doc):
    """Validation robuste des documents"""
    if not isinstance(doc, dict):
        raise ValueError("Le document doit être un dictionnaire")
    
    # Format Q/R direct
    if "question" in doc and "reponse" in doc:
        return {
            "_index": "fiscality",
            "_source": {
                "question": str(doc["question"]),
                "reponse": str(doc["reponse"]),
                "tags": doc.get("tags", []),
                # "date_creation": doc.get("date_creation", datetime.now().isoformat()),
                "metadata": {
                    "certifie_par": doc.get("certifie_par", "DGI Sénégal"),
                    "reference_legale": doc.get("references", []),
                    "source": doc.get("source", "base_interne")
                }
            }
        }
    
    # Format conversationnel
    elif "messages" in doc:
        # Implémentez votre logique pour les messages ici
        pass
    
    raise ValueError(f"Format de document non reconnu: {json.dumps(doc, indent=2)}")

def index_documents():
    """Indexation avec validation améliorée"""
    data_file = "/Users/thiarakante/Documents/project copie/data/qa_format_optimise.json"
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("Le fichier doit contenir une liste de documents")
        
        actions = []
        error_count = 0
        
        for doc in data:
            try:
                actions.append(validate_document(doc))
            except ValueError as e:
                print(f"⚠️ Document ignoré: {str(e)}")
                error_count += 1
            except Exception as e:
                print(f"⚠️ Erreur inattendue: {str(e)}")
                error_count += 1
        
        if not actions:
            raise ValueError("Aucun document valide à indexer")
        
        success, _ = helpers.bulk(es, actions)
        es.indices.refresh(index="fiscality")
        
        print(f"\n📊 Résultats:")
        print(f"- Documents indexés: {success}")
        print(f"- Erreurs: {error_count}")
        
    except Exception as e:
        print(f"❌ Erreur majeure: {str(e)}")

if __name__ == "__main__":
    try:
        # Vérification connexion
        if not es.ping():
            raise ConnectionError("Échec de connexion Elasticsearch")
        print("✅ Connecté à Elasticsearch")
        
        # Initialisation
        init_index()
        
        # Indexation
        index_documents()
        
    except Exception as e:
        print(f"🔥 Erreur critique: {str(e)}")