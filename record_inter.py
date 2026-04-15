import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
DB_INTERVENTIONS = os.getenv("NOTION_INTERVENTIONS_DB_ID")
DB_PRESTATIONS = os.getenv("NOTION_PRESTATIONS_DB_ID")
DB_CLIENTS = os.getenv("NOTION_CLIENTS_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def query_notion(database_id, filter_data=None):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = filter_data if filter_data else {}
    response = requests.post(url, headers=HEADERS, json=payload)
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
    clients_data = query_notion(DB_CLIENTS)
    return {get_title(c, 'Name'): c['id'] for c in clients_data}

def get_prestations_for_client(id_client):
    filter_payload = {
        "filter": {
            "property": "Clients", 
            "relation": {"contains": id_client}
        }
    }
    prestas_data = query_notion(DB_PRESTATIONS, filter_payload)
    return {get_title(p, 'Prestation'): p['id'] for p in prestas_data}

def create_intervention_page(payload):
    url = "https://api.notion.com/v1/pages"
    return requests.post(url, headers=HEADERS, json=payload)

# --- LOGIQUE TERMINAL (Ancienne version préservée) ---
if __name__ == "__main__":
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
                    "parent": {"database_id": DB_INTERVENTIONS},
                    "properties": {
                        "Date Intervention": {"date": {"start": d}},
                        "Client": {"relation": [{"id": id_client_choisi}]},
                        "Lien Prestation": {"relation": [{"id": id_presta_choisie}]},
                        "Prestation Titre": {"rich_text": [{"text": {"content": nom_presta}}]}
                    }
                }
                res = create_intervention_page(payload)
                print(f"✅ Créé le {d}" if res.status_code == 200 else f"❌ Erreur {res.status_code}")