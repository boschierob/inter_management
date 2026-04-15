import os
import requests
from dotenv import load_dotenv

# Chargement des variables
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

# --- LOGIQUE DE SAISIE ---

print("--- Initialisation ---")

# 1. Lister les clients
clients_data = query_notion(DB_CLIENTS)
dict_clients = {get_title(c, 'Name'): c['id'] for c in clients_data}

print("\nClients disponibles :", ", ".join(dict_clients.keys()))
nom_choisi = input("Sélectionnez un client : ")
id_client_choisi = dict_clients.get(nom_choisi)

if not id_client_choisi:
    print("❌ Client introuvable.")
    exit()

# 2. Filtrer les Prestations
filter_payload = {
    "filter": {
        "property": "Clients", 
        "relation": {
            "contains": id_client_choisi
        }
    }
}

print(f"--- Recherche des prestations liées à {nom_choisi} ---")
prestas_data = query_notion(DB_PRESTATIONS, filter_payload)
dict_prestas = {get_title(p, 'Prestation'): p['id'] for p in prestas_data}

if not dict_prestas:
    print(f"⚠️ Aucune prestation trouvée pour ce client.")
    exit()

print("\nPrestations trouvées :", ", ".join(dict_prestas.keys()))
nom_presta = input("Quelle prestation ? ")
id_presta_choisie = dict_prestas.get(nom_presta)

if not id_presta_choisie:
    print("❌ Prestation introuvable.")
    exit()

# 3. Saisie des dates
dates_input = input("\nDates (YYYY-MM-DD), séparez par virgule : ")
dates = [d.strip() for d in dates_input.split(',')]

# 4. Création dans la table Interventions (UNE SEULE REQUÊTE PAR DATE)
url_create = "https://api.notion.com/v1/pages"
for date in dates:
    # On construit un SEUL payload avec toutes les colonnes
    payload = {
        "parent": {"database_id": DB_INTERVENTIONS},
        "properties": {
            "Date Intervention": {"date": {"start": date}},
            "Client": {"relation": [{"id": id_client_choisi}]},
            
            # La Relation (Lien cliquable)
            "Lien Prestation": {"relation": [{"id": id_presta_choisie}]},
            
            # Le Texte (Nom de la prestation)
            "Prestation Titre": {
                "rich_text": [
                    {
                        "text": {
                            "content": nom_presta
                        }
                    }
                ]
            }
        }
    }
    
    # Un seul envoi ici
    res = requests.post(url_create, headers=HEADERS, json=payload)
    
    if res.status_code == 200:
        print(f"✅ Créé avec succès : {nom_choisi} - {nom_presta} le {date}")
    else:
        print(f"❌ Erreur {res.status_code} pour la date {date}")
        print(f"Détail : {res.text}")