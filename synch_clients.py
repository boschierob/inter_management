import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_INTERVENTIONS = os.getenv("NOTION_INTERVENTIONS_DB_ID")
DB_CLIENTS = os.getenv("NOTION_CLIENTS_DB_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger()

def sync_all_clients():
    logger.info("🚀 Lancement du scan intégral des interventions...")

    # 1. CHARGEMENT DU RÉFÉRENTIEL CLIENTS (Table Clients)
    client_map = {}
    res_c = requests.post(f"https://api.notion.com/v1/databases/{DB_CLIENTS}/query", headers=headers)
    if res_c.status_code == 200:
        for c in res_c.json().get("results", []):
            name_prop = c['properties'].get('Name', {}).get('title', [])
            if name_prop:
                client_map[name_prop[0]['plain_text'].strip()] = c['id']
    
    logger.info(f"📚 {len(client_map)} clients chargés depuis le référentiel.")

    # 2. RÉCUPÉRATION DE TOUTES LES INTERVENTIONS (Avec gestion de la pagination)
    interventions = []
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res_i = requests.post(f"https://api.notion.com/v1/databases/{DB_INTERVENTIONS}/query", headers=headers, json=payload)
        data = res_i.json()
        interventions.extend(data.get("results", []))
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")

    logger.info(f"🔎 Analyse de {len(interventions)} lignes dans Interventions...")

    # 3. LIAISON FORCÉE
    count = 0
    for row in interventions:
        pid = row['id']
        props = row['properties']
        
        # On vérifie si la relation est déjà remplie
        current_relation = props.get('Client', {}).get('relation', [])
        
        # On récupère le nom texte (Tally)
        tally_name = ""
        name_prop = props.get('Nom Client', {})
        for field in ['title', 'rich_text']:
            if name_prop.get(field):
                tally_name = name_prop[field][0]['plain_text'].strip()
                break

        # CONDITION : On lie si (Relation est vide) ET (Nom Tally existe dans notre map)
        if not current_relation and tally_name in client_map:
            update_data = {
                "properties": {
                    "Client": {"relation": [{"id": client_map[tally_name]}]}
                }
            }
            res_patch = requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json=update_data)
            if res_patch.status_code == 200:
                logger.info(f"✅ Lié : {tally_name}")
                count += 1
            else:
                logger.error(f"❌ Erreur sur {tally_name}: {res_patch.text}")
        elif not tally_name:
            # Optionnel : loguer les lignes vraiment vides
            pass

    logger.info(f"🏁 Terminé ! {count} nouvelles liaisons effectuées.")

if __name__ == "__main__":
    sync_all_clients()