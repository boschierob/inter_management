import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DB_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}
print(f"Mon token commence par : {os.getenv('NOTION_TOKEN')[:10]}...")
def check_connection():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    # Filtre pour récupérer uniquement "A facturer"
    payload = {
        "filter": {
            "property": "Status",
            "status": {
                "equals": "A facturer"
            }
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        nb_resultats = len(data.get("results", []))
        print(f"✅ Connexion réussie ! {nb_resultats} interventions trouvées à facturer.")
        return data["results"]
    else:
        print(f"❌ Erreur {response.status_code}: {response.text}")
        return None

if __name__ == "__main__":
    check_connection()