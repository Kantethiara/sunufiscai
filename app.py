import os
import warnings
import urllib3
from typing import List, Tuple, Optional

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

# Désactivation des avertissements
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")
load_dotenv()

class PremiumFiscalAssistant:
    def __init__(self):
        self.mots_cles_fiscaux = {
            "impôt", "impot", "taxe", "réglementations", "tva", "TVA", "CFPNB", "etax","imposable", "imposition", "dgi", "dgid", "droit fiscal",
            "cfpnb", "PV", "pv", "PME", "quitus", "PCF", "fiscalité", "déclaration", "TOEM",
            "CGU", "Patente", "récapitulatifs", "exonération", "remboursement", 
            "trop perçu", "délai", "quitus fiscal", "délai de paiement", "quittance", 
            "récépissé", "revenus", "formalisation", "contribution", "taxation", 
            "cadastre", "redevance", "contribution foncière", "taxe sur les véhicules", 
            "taxe sur les biens", "taxe sur les opérations", "taxe sur les produits", 
            "taxe sur les services", "droit d'enregistrement", "droits d'enregistrement", 
            "taxes d'enregistrement", "entreprise", "changement de statuts", 
            "taxes sur les salaires", "taxe sur les salaires", "taxe foncière", 
            "taxe professionnelle", "NINEA", "direct", "indirect", "réouverture",
            "taxe sur la valeur ajoutée", "passeport", "taxe sur les boissons", 
            "réductions", "immatriculation", "propriétaire", "compte", "duplicata", 
            "IR", "IS", "patente", "douane", "régime fiscal", "code général des impôts", 
            "procédure", "acte administratif", "exonérations", "obligation fiscale", 
            "pénalité", "penalite", "amende", "contrôle fiscal", "démarrage des activités", 
            "homologation", "acte", "titre", "SIGTAS", "imposition", "bail", 
            "foncier bâti", "foncier non bâti", "TEOM", "vérification", "versement", 
            "trésor", "TVA déductible", "TVA collectée", "TVA non récupérable", 
            "non-assujetti", "assujetti", "centre des impôts", "régularisation", 
            "déductibilité", "déclaration mensuelle", "déclaration annuelle", 
            "numéro fiscal", "avis d'imposition", "bordereau de paiement", "numéro IFU", 
            "COFI", "fiscale", "fiscaux", "fiscal", "DGID", "impotsetdomaines", "dgi", 
            "direction générale des impôts"
        }
        
        self.salutations = {"bonjour", "salut", "hello", "bonsoir", "coucou", "hi", "salam", "yo", "bjr", "allo", "good morning", "good afternoon"}
        self.salutations = {s.lower() for s in self.salutations}
        self.salutations = {s for s in self.salutations if len(s.split()) <= 3}
        
        self.es = self._init_elasticsearch()
        self.embedder = self._init_embedder()
        self.llm = self._init_llm()
        self.agent = self._init_agent()
        self.response_cache = {}
        self.last_query = None
    def _init_elasticsearch(self):
        """Initialise et retourne une connexion Elasticsearch sécurisée"""
        try:
            # Configuration avec valeurs par défaut sécurisées
            es = Elasticsearch(
                os.getenv(
                    "ELASTICSEARCH_URL", 
                    "https://my-elasticsearch-project-beb3d2.es.us-east-1.aws.elastic.cloud:443"
                ),
                api_key=os.getenv("ELASTIC_API_KEY"),
                verify_certs=True,
                ssl_show_warn=True,
                timeout=30,
                max_retries=2
)

            # Vérification immédiate de la connexion
            if not es.ping():
                raise ConnectionError("Échec de la connexion Elasticsearch")
            
            print("✅ Connexion Elasticsearch établie avec succès")
            return es

        except Exception as e:
            error_msg = f"❌ Erreur d'initialisation Elasticsearch: {str(e)}"
            
            # Suggestions spécifiques selon l'erreur
            if "SSL" in str(e):
                error_msg += "\n💡 Conseil: Vérifiez votre certificat SSL ou utilisez verify_certs=False en développement"
            elif "authentication" in str(e):
                error_msg += "\n💡 Conseil: Vérifiez votre clé API dans .env"
            
            print(error_msg)
            return None

    def _init_embedder(self):
        """Chargement du modèle d'embedding"""
        return SentenceTransformer("dangvantuan/sentence-camembert-base")

    def _init_llm(self):
        """Configuration du LLM"""
        return ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama3-70b-8192",
            temperature=0.2,
            max_tokens=1500
        )

    def _get_contextual_results(self, query: str) -> Tuple[List[str], float]:
        """Recherche optimisée dans Elasticsearch"""
        try:
            res = self.es.search(
                index="fiscality",
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["question^3", "reponse^2", "tags"],
                                        "type": "best_fields"
                                    }
                                }
                            ]
                        }
                    },
                    "size": 3
                }
            )

            hits = res.get('hits', {}).get('hits', [])
            if not hits:
                return [], 0

            best_score = hits[0]['_score']
            responses = [hit['_source']['reponse'] for hit in hits]
            
            print("\n🔍 Résultats de recherche :")
            for i, hit in enumerate(hits[:3]):
                print(f"{i+1}. Score: {hit['_score']:.2f} | Question: {hit['_source']['question']}")
            
            return responses, best_score

        except Exception as e:
            print(f"⚠️ Erreur recherche Elasticsearch: {e}")
            return [], 0

    def _gerer_salutation(self):
        """Gestion simplifiée des salutations"""
        return "💼 Bonjour ! Assistant fiscal sénégalais à votre service. Posez-moi vos questions sur les impôts et taxes."

    def _est_question_fiscale(self, query: str) -> bool:
        """Version améliorée pour mieux gérer les sigles et acronymes"""
        query_lower = query.lower()
        
        # Vérification des salutations simples
        if any(salut in query_lower for salut in self.salutations if len(query_lower.split()) <= 3):
            return False
            
        # Vérification des sigles (même seuls)
        sigles = {mot for mot in self.mots_cles_fiscaux if mot.isupper() and len(mot) >= 3}
        if any(sigle in query_lower for sigle in (s.lower() for s in sigles)):
            return True
        
        # Vérification standard des mots-clés
        return any(mot.lower() in query_lower for mot in self.mots_cles_fiscaux)

    def _generer_reponse_fiscale(self, question: str) -> str:
        """Génère une réponse fiscale via LLM avec des garde-fous"""
        prompt = f"""
        En tant qu'expert fiscal sénégalais, répondez STRICTEMENT en français à cette question:
        "{question}"

        Règles absolues:
        1. Répondez UNIQUEMENT si c'est une question fiscale
        2. Structure obligatoire:
           - 📌 Contexte fiscal clair
           - 🔢 3-5 points clés maximum
           - 📚 Référence légale exacte si disponible
           - 🔗 Lien vers DGID si pertinent
        3. Si vous n'êtes pas sûr: "Consultez un conseiller fiscal ou  "Consultez: https://www.dgid.sn/procedures-fiscales/"
        4. NE PAS INVENTER de textes de loi
        5. Si la question commence par "C'est quoi", "Qu'est-ce que", "Que signifie", considérez qu'il s'agit 
d'une demande de définition fiscale. Répondez comme à une question classique, en suivant la structure exigée.
        6. Répondez en français uniquement, jamais en anglais, wolof ou autres langues.
        7. POUR LES QUESTIONS NON FISCALES:
   "⛔ Je ne traite que les questions fiscales et il NE FAUT jamais répondre a une question non fiscal."
                """
        
        try:
            reponse = self.llm.invoke(prompt).content
            return self._valider_reponse_fiscale(reponse)
        except Exception as e:
            print(f"⚠️ Erreur LLM: {str(e)}")
            return ("ℹ️ Je rencontre des difficultés techniques. "
                    "Veuillez consulter directement: https://www.dgid.sn")

    def _valider_reponse_fiscale(self, reponse: str) -> str:
        """Valide que la réponse reste dans le domaine fiscal"""
        if not isinstance(reponse, str) or not reponse.strip():
            return "⛔ Réponse vide ou invalide"

        if not self._est_question_fiscale(reponse):
            return ("⛔ Je ne peux répondre qu'aux questions fiscales. "
                   )
                    
        return reponse

    def recherche_fiscale(self, query: str) -> str:
        """Version améliorée avec contrôle strict du domaine fiscal"""
        print(f"🎯 Appel à recherche_fiscale avec : {query}")

        # Étape 1 : Vérification de la langue
        try:
            if detect(query) != "fr":
                return "⛔ Veuillez poser votre question en français uniquement."
        except LangDetectException:
            return "⚠️ Impossible de détecter la langue de votre question."

        # Étape 2 : Filtrage des questions non fiscales
        if not self._est_question_fiscale(query):
            return (
                "⛔ Je suis strictement limité aux questions fiscales sénégalaises. "
                "Domaines couverts: impôts, taxes, déclarations, code fiscal."
            )

        # Étape 3 : Recherche dans la base de connaissances
        responses, score = self._get_contextual_results(query)
        
        # Étape 4 : Gestion des réponses
        if responses and score > 1.0:  # Seuil de pertinence
            return responses[0]
        else:
            # Fallback contrôlé vers le LLM
            return ("⚠️ Information non trouvée dans nos bases. Voici une réponse générale:\n\n"
                   f"{self._generer_reponse_fiscale(query)}\n\n"
                   "Pour confirmation: https://www.dgid.sn")

    def vider_cache(self):
        """Vide le cache des réponses"""
        self.response_cache.clear()
        print("🗑️ Cache vidé avec succès !")

    def _init_agent(self):
        """Initialisation de l'agent avec contrôle strict"""
        fiscal_tool = Tool(
            name="BaseFiscalePremium",
            func=self.recherche_fiscale,
            description=(
                "🔍 Outil STRICTEMENT limité à la fiscalité sénégalaise. "
                "Répond uniquement en français. "
            
            )
        )

        return initialize_agent(
            tools=[fiscal_tool],
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key='output'
            ),
            verbose=False,
            max_iterations=3,
            early_stopping_method="generate",
            handle_parsing_errors=True,  # <-- Ajout crucial
            agent_kwargs={
                "system_message": SystemMessage(content="""
🎓 Règles absolues :
0. Répondez COMME UN EXPERT FISCAL SENEGALAIS qui parle uniquement français
1. DOMAINE UNIQUE: Fiscalité sénégalaise seulement
2. POUR LES QUESTIONS NON FISCALES:
   "⛔ Je ne traite que les questions fiscales."
3. STRUCTURE OBLIGATOIRE:
   - 📌 Contexte fiscal clair
   - 🔢 3-5 points maximum
   - 📚 Référence légale exacte
   - 🔗 Lien DGID si pertinent
4. SI INFORMATION INCOMPLÈTE:
   "⚠️ Information non trouvée. Consultez www.dgid.sn"
5. LANGUE: Français exclusivement JAMAIS
   - Anglais, Wolof, ou autres langues
   - Pas de jargon technique
6. NE PAS:
   - Inventer des textes de loi
   - Donner d'avis personnel
   - Répondre hors domaine fiscal
7. Si la question commence par "C'est quoi", "Qu'est-ce que", "Que signifie", considérez qu'il s'agit 
d'une demande de définition fiscale. Répondez comme à une question classique, en suivant la structure exigée.
""")
            }
        )

    def run(self):
        print("\n" + "="*50)
        print("ASSISTANT FISCAL PREMIUM - SÉNÉGAL ".center(50))
        print("="*50)
        print(self._gerer_salutation())
        
        while True:
            try:
                user_input = input("\nVotre question fiscale : ").strip()
                
                # Commandes spéciales
                if user_input.lower() in ['au revoir', 'merci', 'quit', 'q']:
                    print("\nMerci pour votre confiance. À bientôt !")
                    break
                    
                if user_input.lower() in ['vider cache', 'reset']:
                    self.vider_cache()
                    print("Cache vidé avec succès !")
                    continue

                # Gestion des salutations
                if user_input.lower() in self.salutations:
                    print("\n💼 Bonjour ! Je suis votre assistant fiscal. Posez-moi vos questions sur :")
                    print("- Impôts (IR, IS, IFU)")
                    print("- Taxes (TVA, Patente)")
                    print("- Démarches fiscales")
                    print("- Code général des impôts")
                    continue

                # Vérification du domaine fiscal
                if not self._est_question_fiscale(user_input):
                    print("\n⛔ Désolé, je ne traite que les questions fiscales.")
                    print("Domaines acceptés :")
                    print(", ".join(sorted(self.mots_cles_fiscaux)[:10]) + "...")
                    print("Exemple : 'Quelles sont les démarches pour un quitus fiscal ?'")
                    continue

                # Traitement de la question fiscale
                print("\n🔍 Consultation de la base fiscale...")
                response = self.agent.invoke({"input": user_input})
                
                # Vérification que la réponse est bien fiscale
                if any(phrase in response['output'].lower() for phrase in ["hors domaine fiscal", "non fiscal"]):
                    print("\n⚠️ La réponse semble hors domaine :")
                    print(response['output'])
                    print("\nVeuillez reformuler votre question en termes fiscaux.")
                else:
                    print("\n📌 Réponse :", response['output'])
                    
            except KeyboardInterrupt:
                print("\n\nMerci d'avoir utilisé l'Assistant Fiscal Premium. Au revoir !")
                break
                
            except Exception as e:
                print(f"\n⚠️ Erreur technique : {str(e)}")
                print("Veuillez réessayer ou contacter le support.")
                self.vider_cache()

if __name__ == "__main__":
    assistant = PremiumFiscalAssistant()
    assistant.run()