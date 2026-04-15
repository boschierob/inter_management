import os
import requests
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def migrate():
    int_db_id = os.getenv("NOTION_DB_ID")
    prest_db_id = os.getenv("NOTION_PRESTATIONS_DB_ID")

    # --- ÉTAPE 1 : RÉCUPÉRER LES PRESTATIONS ---
    # On vide le payload pour tout récupérer sans filtre
    res_p = requests.post(f"https://api.notion.com/v1/databases/{prest_db_id}/query", 
                         headers=headers, json={})
    prest_rows = res_p.json().get("results", [])
    
    mapping = {}
    for p in prest_rows:
        try:
            # On essaie de trouver la colonne titre (peu importe son nom)
            properties = p['properties']
            title_key = [k for k, v in properties.items() if v['type'] == 'title'][0]
            name = properties[title_key]['title'][0]['plain_text']
            mapping[name.strip().lower()] = p['id']
            print(f"📍 Prestation trouvée : '{name}'")
        except: continue

    # --- ÉTAPE 2 : RÉCUPÉRER LES INTERVENTIONS ---
    res_i = requests.post(f"https://api.notion.com/v1/databases/{int_db_id}/query", 
                         headers=headers, json={})
    interventions = res_i.json().get("results", [])
    print(f"\n🔍 {len(interventions)} interventions trouvées au total.")

    # --- ÉTAPE 3 : MIGRATION ---
    for row in interventions:
        try:
            # Récupération du texte dans la colonne 'Prestation'
            # On cherche une colonne de type 'rich_text' qui s'appelle 'Prestation'
            text_field = row['properties'].get('Prestation', {}).get('rich_text', [])
            if not text_field: continue
            
            old_text = text_field[0]['plain_text'].strip()
            
            if old_text.lower() in mapping:
                target_id = mapping[old_text.lower()]
                update_url = f"https://api.notion.com/v1/pages/{row['id']}"
                payload = {
                    "properties": {
                        "Prestation (Relation)": { "relation": [{"id": target_id}] }
                    }
                }
                requests.patch(update_url, headers=headers, json=payload)
                print(f"✅ Lié : {old_text}")
        except Exception as e:
            print(f"⚠️ Erreur sur une ligne : {e}")

if __name__ == "__main__":
    migrate()
