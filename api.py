from fastapi import FastAPI, Query
from app import PremiumFiscalAssistant

app = FastAPI()

# Initialisation de l'assistant fiscal
assistant = PremiumFiscalAssistant()

@app.get("/fiscalite")
def get_fiscalite(question: str = Query(..., description="Posez une question sur la fiscalité")):
    """
    Endpoint pour répondre aux questions fiscales.
    """
    # Utilisation de l'assistant pour traiter la question
    response = assistant.recherche_fiscale(question)
    return {"message": response}




# import uvicorn
# uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# # Pour lancer l'API, exécute :
# # uvicorn api:app --host 0.0.0.0 --port 8000 --reload
