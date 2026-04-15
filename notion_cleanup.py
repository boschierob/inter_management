import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_INTERVENTIONS_DB_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger()

def cleanup_relation_db():
    logger.info("🔍 Nettoyage (Client = Relation)...")
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    # On récupère les lignes non facturées
    res = requests.post(url, headers=headers, json={"filter": {"property": "Status", "status": {"does_not_equal": "Facturé"}}})
    
    if res.status_code != 200:
        logger.error(f"Erreur : {res.text}")
        return

    pages = res.json().get("results", [])
    logger.info(f"Analyse de {len(pages)} lignes...")

    seen_keys = {}
    to_archive = []

    for page in pages:
        pid = page['id']
        props = page['properties']

        # 1. RÉCUPÉRATION DU CLIENT (Type Relation)
        # On extrait l'ID de la première page liée dans la relation
        client_rel = props.get('Client', {}).get('relation', [])
        if not client_rel:
            logger.info(f"🗑️ Client vide détecté (ID: {pid})")
            to_archive.append(pid)
            continue
        
        # On utilise l'ID unique du client comme référence
        client_id = client_rel[0]['id']

        # 2. RÉCUPÉRATION DE LA DATE
        date_prop = props.get('Date Intervention', {}).get('date')
        date_val = date_prop.get('start', "SANS_DATE")[:10] if date_prop else "SANS_DATE"

        # 3. CLÉ UNIQUE (Date + ID Client)
        unique_key = f"{date_val}_{client_id}"

        if unique_key in seen_keys:
            logger.warning(f"⚠️ Doublon trouvé pour le client {client_id} à la date {date_val}")
            to_archive.append(pid)
        else:
            seen_keys[unique_key] = pid

    # --- ARCHIVAGE ---
    if to_archive:
        logger.info(f"🚀 Archivage de {len(to_archive)} pages...")
        for pid in to_archive:
            archive_url = f"https://api.notion.com/v1/pages/{pid}"
            r = requests.patch(archive_url, headers=headers, json={"archived": True})
            if r.status_code == 200:
                logger.info(f"✅ Page {pid} archivée.")
            else:
                logger.error(f"❌ Erreur sur {pid}: {r.text}")
    else:
        logger.info("✅ Aucun doublon ou ligne vide trouvé.")

if __name__ == "__main__":
    cleanup_relation_db()