import os
import requests
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def link_clients():
    int_db_id = os.getenv("NOTION_DB_ID")
    clients_db_id = os.getenv("NOTION_CLIENTS_DB_ID")

    # 1. On récupère les Clients
    res_c = requests.post(f"https://api.notion.com/v1/databases/{clients_db_id}/query", headers=headers).json()
    mapping = {}
    for c in res_c.get("results", []):
        try:
            # On prend le nom dans la colonne 'Name' (ou 'Nom')
            name = c['properties']['Name']['title'][0]['plain_text']
            mapping[name.strip().lower()] = c['id']
        except: continue

    # 2. On parcourt les interventions
    res_i = requests.post(f"https://api.notion.com/v1/databases/{int_db_id}/query", headers=headers).json()
    interventions = res_i.get("results", [])
    
    print(f"Traitements de {len(interventions)} lignes...")

    for row in interventions:
        try:
            # On lit le nom du client dans la colonne Titre
            props = row['properties']
            title_field = [k for k, v in props.items() if v['type'] == 'title'][0]
            nom_interv = props[title_field]['title'][0]['plain_text'].strip()
            
            if nom_interv.lower() in mapping:
                target_id = mapping[nom_interv.lower()]
                
                # --- LA CORRECTION EST ICI ---
                # Vérifiez que le nom entre guillemets est EXACTEMENT celui de Notion
                col_name = "Client (Relation)" 
                
                payload = {
                    "properties": {
                        col_name: { "relation": [{"id": target_id}] }
                    }
                }
                
                update_res = requests.patch(f"https://api.notion.com/v1/pages/{row['id']}", 
                                           headers=headers, json=payload)
                
                if update_res.status_code == 200:
                    print(f"✅ Lié : {nom_interv}")
                else:
                    print(f"❌ Erreur Notion sur '{nom_interv}': {update_res.text}")
                    
        except Exception as e:
            continue

if __name__ == "__main__":
    link_clients()