import streamlit as st
import os
import requests

def get_notion_config():
    try:
        token = st.secrets["NOTION_TOKEN"]
        db_clients = st.secrets["NOTION_CLIENTS_DB_ID"]
        db_prestations = st.secrets["NOTION_PRESTATIONS_DB_ID"]
        db_interventions = st.secrets["NOTION_INTERVENTIONS_DB_ID"]
        db_intervenants = st.secrets["NOTION_INTERVENANTS_DB_ID"] # <--- AJOUT
    except Exception:
        token = os.getenv("NOTION_TOKEN")
        db_clients = os.getenv("NOTION_CLIENTS_DB_ID")
        db_prestations = os.getenv("NOTION_PRESTATIONS_DB_ID")
        db_interventions = os.getenv("NOTION_INTERVENTIONS_DB_ID")
        db_intervenants = os.getenv("NOTION_INTERVENANTS_DB_ID") # <--- AJOUT

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    return {
        "headers": headers,
        "db_clients": db_clients,
        "db_prestations": db_prestations,
        "db_interventions": db_interventions,
        "db_intervenants": db_intervenants # <--- AJOUT
    }
def login_user(email, pin):
    config = get_notion_config()
    
    # On nettoie l'entrée (espaces invisibles avant/après)
    email = str(email).strip()
    pin = str(pin).strip()
    
    # --- LOGS TERMINAL ---
    print("\n--- DEBUG LOGIN ---")
    print(f"Tentative de connexion -> Email : '{email}' | PIN : '{pin}'")
    
    # Sécurité supplémentaire : Si le PIN n'est pas composé de 4 chiffres
    if not (len(pin) == 4 and pin.isdigit()):
        print("❌ Rejet local : Le PIN ne contient pas exactement 4 chiffres.")
        return None

    filter_payload = {
        "filter": {
            "and": [
                {"property": "Email", "email": {"equals": email}},
                # Comme c'est du Texte, on utilise rich_text
                {"property": "Code PIN", "rich_text": {"equals": pin}}
            ]
        }
    }
    
    # print(f"Payload Notion : {filter_payload}") # Décommente si tu veux voir la requête brute
    
    results = query_notion(config['db_intervenants'], filter_payload)
    
    print(f"Réponse Notion -> Nombre de résultats trouvés : {len(results)}")
    
    if results:
        user_page = results[0]
        # Extraction des rôles
        roles = [r['name'] for r in user_page['properties']['Rôles']['multi_select']]
        name = get_title(user_page, 'Name')
        
        print(f"✅ Succès : Utilisateur {name} identifié avec les rôles {roles}")
        
        return {
            "id": user_page['id'],
            "name": name,
            "roles": roles
        }
        
    print("❌ Échec : Aucun intervenant trouvé avec cet Email ET ce PIN.")
    return None
    
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
def get_all_clients(user_data=None):
    config = get_notion_config()
    
    # Si pas de user_data ou si Admin/Gérant -> On voit TOUT
    if not user_data or any(role in ['Admin', 'Gérant'] for role in user_data['roles']):
        clients_data = query_notion(config['db_clients'])
    else:
        # Pour Employé/Sous-traitant/Manager -> Filtre sur la relation bidirectionnelle
        # Notion cherche si l'ID de l'utilisateur est présent dans la colonne 'Intervenant(s) Responsable(s)'
        filter_payload = {
            "filter": {
                "property": "Intervenant(s) Responsable(s)",
                "relation": {"contains": user_data['id']}
            }
        }
        clients_data = query_notion(config['db_clients'], filter_payload)
    
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