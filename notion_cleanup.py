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

# On réduit le niveau de log pour que l'interface interactive soit lisible
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def get_prop_value(props, name):
    """Utilitaire pour extraire du texte proprement pour l'affichage"""
    prop = props.get(name, {})
    p_type = prop.get('type')
    if p_type == 'rich_text' and prop['rich_text']:
        return prop['rich_text'][0]['plain_text']
    if p_type == 'title' and prop['title']:
        return prop['title'][0]['plain_text']
    return "Non défini"

def cleanup_relation_db():
    logger.info("--- 🔍 ANALYSE DES DOUBLONS ---")
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    res = requests.post(url, headers=headers, json={"filter": {"property": "Status", "status": {"does_not_equal": "Facturé"}}})
    if res.status_code != 200:
        logger.error(f"Erreur API : {res.text}")
        return

    pages = res.json().get("results", [])
    seen_keys = {}
    
    for page in pages:
        pid = page['id']
        props = page['properties']

        # 1. Extraction des infos pour la clé technique
        client_rel = props.get('Client', {}).get('relation', [])
        client_id = client_rel[0]['id'] if client_rel else "SANS_CLIENT"
        
        date_prop = props.get('Date Intervention', {}).get('date')
        date_val = date_prop.get('start', "SANS_DATE")[:10] if date_prop else "SANS_DATE"

        presta_rel = props.get('Lien Prestation', {}).get('relation', [])
        if presta_rel:
            presta_id = presta_rel[0]['id']
        else:
            transit = props.get('ID_Transit_Presta', {}).get('rich_text', [])
            presta_id = transit[0].get('plain_text', "SANS_PRESTA") if transit else "SANS_PRESTA"

        # 2. Clé de comparaison
        unique_key = f"{date_val}_{client_id}_{presta_id}"

        # 3. Extraction des infos pour l'affichage humain
        client_nom = get_prop_value(props, "Nom Client")
        # On essaie de récupérer le titre de la prestation si le rollup existe déjà
        presta_nom = get_prop_value(props, "Prestation Titre") or "Prestation inconnue"

        if unique_key in seen_keys:
            # --- INTERFACE INTERACTIVE ---
            print("\n" + "="*50)
            print(f"⚠️  DOUBLON DÉTECTÉ")
            print(f"   • Client     : {client_nom}")
            print(f"   • Date       : {date_val}")
            print(f"   • Prestation : {presta_nom}")
            print(f"   • Raison     : Identique à une ligne déjà analysée.")
            print("="*50)
            
            choix = input(f"Voulez-vous ARCHIVER cette ligne (ID: {pid}) ? [y/N] : ").lower()
            
            if choix == 'y':
                archive_url = f"https://api.notion.com/v1/pages/{pid}"
                r = requests.patch(archive_url, headers=headers, json={"archived": True})
                if r.status_code == 200:
                    print(f"✅ Archivage réussi.")
                else:
                    print(f"❌ Erreur lors de l'archivage : {r.text}")
            else:
                print(f"⏭️  Ligne conservée.")
        else:
            seen_keys[unique_key] = pid

    print("\n--- ✅ Analyse terminée ---")

if __name__ == "__main__":
    cleanup_relation_db()