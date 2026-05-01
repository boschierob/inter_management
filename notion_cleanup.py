import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_INTERVENTIONS_DB_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def extract_text(prop):
    """Extrait proprement le texte brut des structures complexes de Notion (Rollups, Relations, Text)"""
    if not prop: return ""
    p_type = prop.get('type')
    
    if p_type == 'rollup':
        r_data = prop.get('rollup', {})
        r_type = r_data.get('type')
        if r_type == 'array':
            items = r_data.get('array', [])
            if not items: return ""
            # Traitement récursif pour percer les couches du rollup
            return extract_text(items[0])
        elif r_type == 'number':
            return str(r_data.get('number', ''))
        elif r_type == 'rich_text':
            texts = r_data.get('rich_text', [])
            return "".join([t.get('plain_text', '') for t in texts]).strip()

    content = prop.get('rich_text') or prop.get('title')
    if content is None:
        inner_type = prop.get('type')
        if inner_type in prop:
            content = prop[inner_type]

    if isinstance(content, list) and len(content) > 0:
        return content[0].get('plain_text', "").strip()
    
    return str(content).strip() if content is not None else ""

def cleanup_relation_db():
    logger.info("--- 🔍 ANALYSE DES DOUBLONS (Mode Interactif) ---")
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    # On récupère uniquement ce qui n'est pas encore facturé
    payload = {"filter": {"property": "Status", "status": {"does_not_equal": "Facturé"}}}
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
    except Exception as e:
        logger.error(f"Erreur lors de la lecture Notion : {e}")
        return

    pages = res.json().get("results", [])
    seen_keys = {}
    
    for page in pages:
        pid = page['id']
        props = page['properties']

        # 1. Extraction technique pour la comparaison
        client_rel = props.get('Client', {}).get('relation', [])
        client_id = client_rel[0]['id'] if client_rel else "SANS_CLIENT"
        
        date_prop = props.get('Date Intervention', {}).get('date')
        date_val = date_prop.get('start', "SANS_DATE")[:10] if date_prop else "SANS_DATE"

        presta_rel = props.get('Lien Prestation', {}).get('relation', [])
        if presta_rel:
            presta_id = presta_rel[0]['id']
        else:
            presta_id = extract_text(props.get('ID_Transit_Presta')) or "SANS_PRESTA"

        # Clé unique : Date + Client + Prestation
        unique_key = f"{date_val}_{client_id}_{presta_id}"

        # 2. Extraction pour l'affichage humain (Rollups)
        # On utilise extract_text pour percer les rollups
        client_nom = extract_text(props.get('Client Nom')) or "Client inconnu"
        presta_nom = extract_text(props.get('Prestation Titre')) or "Prestation inconnue"

        # 3. Vérification des doublons
        if unique_key in seen_keys:
            # On ignore les lignes totalement vides de l'analyse interactive
            if client_id == "SANS_CLIENT" and date_val == "SANS_DATE":
                continue

            print("\n" + "="*60)
            print(f"⚠️  DOUBLON DÉTECTÉ")
            print(f"   • Client     : {client_nom}")
            print(f"   • Date       : {date_val}")
            print(f"   • Prestation : {presta_nom}")
            print(f"   • Raison     : Identique à une ligne déjà analysée.")
            print("="*60)
            
            choix = input(f"Voulez-vous ARCHIVER cette ligne ? [y/N] : ").lower()
            
            if choix == 'y':
                archive_url = f"https://api.notion.com/v1/pages/{pid}"
                r = requests.patch(archive_url, headers=headers, json={"archived": True})
                if r.status_code == 200:
                    print(f"✅ Archivage réussi.")
                else:
                    print(f"❌ Erreur : {r.text}")
            else:
                print(f"⏭️  Ligne conservée.")
        else:
            # On enregistre la ligne comme "vue" pour les suivantes
            # Note : on ne stocke pas les lignes vides pour ne pas bloquer les autres lignes vides
            if client_id != "SANS_CLIENT":
                seen_keys[unique_key] = pid

    print("\n--- ✅ Analyse et nettoyage terminés ---")

if __name__ == "__main__":
    cleanup_relation_db()