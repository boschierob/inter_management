import streamlit as st
import os
import requests

def get_notion_config():
    """Récupère la configuration et génère les headers dynamiquement."""
    try:
        # Tentative via Streamlit Secrets
        token = st.secrets["NOTION_TOKEN"]
        db_clients = st.secrets["NOTION_CLIENTS_DB_ID"]
        db_prestations = st.secrets["NOTION_PRESTATIONS_DB_ID"]
        db_interventions = st.secrets["NOTION_INTERVENTIONS_DB_ID"]
    except Exception:
        # Repli sur les variables d'environnement (Local)
        token = os.getenv("NOTION_TOKEN")
        db_clients = os.getenv("NOTION_CLIENTS_DB_ID")
        db_prestations = os.getenv("NOTION_PRESTATIONS_DB_ID")
        db_interventions = os.getenv("NOTION_INTERVENTIONS_DB_ID")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    return {
        "headers": headers,
        "db_clients": db_clients,
        "db_prestations": db_prestations,
        "db_interventions": db_interventions
    }

def query_notion(database_id, filter_data=None):
    config = get_notion_config() # Récupération dynamique
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = filter_data if filter_data else {}
    response = requests.post(url, headers=config['headers'], json=payload)
    return response.json().get('results', [])

def get_title(page, property_name):
    props = page['properties'].get(property_name, {})
    if 'title' in props and props['title']:
        return props['title'][0]['plain_text']
    if 'rich_text' in props and props['rich_text']:
        return props['rich_text'][0]['plain_text']
    return "Sans titre"

# --- FONCTIONS POUR L'INTERFACE ---

def get_all_clients():
    config = get_notion_config() # Récupération dynamique
    clients_data = query_notion(config['db_clients'])
    return {get_title(c, 'Name'): c['id'] for c in clients_data}

def get_prestations_for_client(id_client):
    config = get_notion_config() # Récupération dynamique
    filter_payload = {
        "filter": {
            "property": "Clients", 
            "relation": {"contains": id_client}
        }
    }
    prestas_data = query_notion(config['db_prestations'], filter_payload)
    return {get_title(p, 'Prestation'): p['id'] for p in prestas_data}

def create_intervention_page(payload):
    config = get_notion_config() # Récupération dynamique
    url = "https://api.notion.com/v1/pages"
    return requests.post(url, headers=config['headers'], json=payload)

# --- LOGIQUE TERMINAL ---
if __name__ == "__main__":
    config = get_notion_config()
    print("--- Initialisation Terminal ---")
    dict_clients = get_all_clients()
    print("\nClients disponibles :", ", ".join(dict_clients.keys()))
    nom_choisi = input("Sélectionnez un client : ")
    id_client_choisi = dict_clients.get(nom_choisi)

    if id_client_choisi:
        dict_prestas = get_prestations_for_client(id_client_choisi)
        print("\nPrestations trouvées :", ", ".join(dict_prestas.keys()))
        nom_presta = input("Quelle prestation ? ")
        id_presta_choisie = dict_prestas.get(nom_presta)
        
        if id_presta_choisie:
            dates_input = input("\nDates (YYYY-MM-DD), séparez par virgule : ")
            dates = [d.strip() for d in dates_input.split(',')]
            for d in dates:
                payload = {
                    "parent": {"database_id": config['db_interventions']},
                    "properties": {
                        "Date Intervention": {"date": {"start": d}},
                        "Client": {"relation": [{"id": id_client_choisi}]},
                        "Lien Prestation": {"relation": [{"id": id_presta_choisie}]},
                        "Prestation Titre": {"rich_text": [{"text": {"content": nom_presta}}]}
                    }
                }
                res = create_intervention_page(payload)
                print(f"✅ Créé le {d}" if res.status_code == 200 else f"❌ Erreur {res.status_code}")