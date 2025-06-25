import json

def extract_tags(question, response):
    """Extract relevant tags based on content"""
    tags = []
    fiscal_keywords = {
        "impôt": ["impôt", "taxe", "fiscal"],
        "TVA": ["tva", "taxe sur la valeur"],
        "IR": ["impôt sur le revenu", "irpp"],
        "IS": ["impôt sur les sociétés", "is"],
        "déclaration": ["déclaration", "déclarer"],
        "types": ["types", "catégories", "sortes"]
    }
    
    content = question.lower() + " " + response.lower()
    for tag, keywords in fiscal_keywords.items():
        if any(keyword in content for keyword in keywords):
            tags.append(tag)
    
    return tags if tags else ["fiscalité"]

def convert_conversation_to_qa(conversation):
    """Convert a single conversation to Q/A pairs"""
    qa_pairs = []
    messages = conversation.get("messages", [])
    
    current_question = None
    question_author = None
    
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")
        
        if role == "user":
            current_question = content
            question_author = "user"
        elif role == "assistant" and current_question:
            qa_pairs.append({
                "question": current_question,
                "reponse": content,
                "tags": extract_tags(current_question, content),
                "references": [],
                "certifie_par": "DGI Sénégal",
                "source": "Historique des conversations"
            })
            current_question = None
    
    return qa_pairs

def convert_json_structure(input_file, output_file):
    """Main conversion function"""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("Le fichier JSON doit contenir une liste de conversations")
        
        all_qa_pairs = []
        
        for conversation in data:
            qa_pairs = convert_conversation_to_qa(conversation)
            all_qa_pairs.extend(qa_pairs)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_qa_pairs, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Conversion réussie ! {len(all_qa_pairs)} questions/réponses générées.")
        print(f"📁 Fichier sauvegardé : {output_file}")
    
    except Exception as e:
        print(f"❌ Erreur lors de la conversion : {str(e)}")

if __name__ == "__main__":
    input_path = "/Users/thiarakante/Documents/projet_soutenance/test_elas/data/data.json"
    output_path = "qa_format_optimise.json"
    
    print("🔄 Conversion en cours...")
    convert_json_structure(input_path, output_path)