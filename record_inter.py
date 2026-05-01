import streamlit as st
import os
import requests
import cloudinary
import cloudinary.uploader
import numpy as np           
from PIL import Image       
import io

# --- CONFIGURATION ---

def get_notion_config():
    """Récupère la configuration Notion depuis secrets ou environnement."""
    try:
        token = st.secrets["NOTION_TOKEN"]
        db_clients = st.secrets["NOTION_CLIENTS_DB_ID"]
        db_prestations = st.secrets["NOTION_PRESTATIONS_DB_ID"]
        db_interventions = st.secrets["NOTION_INTERVENTIONS_DB_ID"]
        db_intervenants = st.secrets["NOTION_INTERVENANTS_DB_ID"]
    except Exception:
        token = os.getenv("NOTION_TOKEN")
        db_clients = os.getenv("NOTION_CLIENTS_DB_ID")
        db_prestations = os.getenv("NOTION_PRESTATIONS_DB_ID")
        db_interventions = os.getenv("NOTION_INTERVENTIONS_DB_ID")
        db_intervenants = os.getenv("NOTION_INTERVENANTS_DB_ID")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    return {
        "token": token,
        "headers": headers,
        "db_clients": db_clients,
        "db_prestations": db_prestations,
        "db_interventions": db_interventions,
        "db_intervenants": db_intervenants
    }

# --- GESTION DES IMAGES (Cloudinary) ---

def convert_canvas_to_image(canvas_data):
    """Transforme l'array du canvas en fichier PNG pour Cloudinary."""
    if canvas_data is not None and np.any(canvas_data[:, :, 3] > 0):
        img = Image.fromarray(canvas_data.astype('uint8'), 'RGBA')
        byte_io = io.BytesIO()
        img.save(byte_io, format='PNG')
        byte_io.seek(0) 
        return byte_io
    return None

def upload_image_to_cloud(image_file):
    """Envoie une image sur Cloudinary et retourne l'URL publique."""
    if image_file is None:
        return None
        
    cloudinary.config(
        cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key = st.secrets["CLOUDINARY_API_KEY"],
        api_secret = st.secrets["CLOUDINARY_API_SECRET"]
    )
    
    try:
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
            
        response = cloudinary.uploader.upload(image_file)
        return response.get("secure_url")
    except Exception as e:
        st.error(f"Erreur Upload Cloudinary : {e}")
        return None

# --- FONCTIONS NOTION CORE ---

def query_notion(database_id, filter_data=None):
    config = get_notion_config()
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

# --- LOGIN ---

def login_user(email_saisi, pin_saisi):
    config = get_notion_config()
    email_saisi = str(email_saisi).strip().lower()
    pin_saisi = str(pin_saisi).strip()
    
    results = query_notion(config['db_intervenants'])

    for page in results:
        props = page['properties']
        
        email_notion = ""
        if 'Email' in props:
            if props['Email']['type'] == 'email' and props['Email']['email']:
                email_notion = props['Email']['email'].lower()
            elif props['Email']['type'] == 'rich_text' and props['Email']['rich_text']:
                email_notion = props['Email']['rich_text'][0]['plain_text'].lower()

        pin_notion = ""
        if 'Code PIN' in props:
            if props['Code PIN']['type'] == 'rich_text' and props['Code PIN']['rich_text']:
                pin_notion = props['Code PIN']['rich_text'][0]['plain_text']
            elif props['Code PIN']['type'] == 'number' and props['Code PIN']['number'] is not None:
                pin_notion = f"{int(props['Code PIN']['number']):04d}"

        if email_notion == email_saisi and pin_notion == pin_saisi:
            roles = []
            if 'Rôles' in props and props['Rôles']['type'] == 'multi_select':
                roles = [r['name'] for r in props['Rôles']['multi_select']]
            
            name = get_title(page, 'Name')
            return {"id": page['id'], "name": name, "roles": roles}
    return None

# --- FETCH DONNÉES INTERFACE ---

@st.cache_data(ttl=600)  # Supprime les lenteurs en gardant la liste en mémoire 10 min
def get_all_clients(user_data=None):
    config = get_notion_config()
    
    # 1. Sécurité : si pas d'utilisateur, on ne renvoie rien
    if not user_data:
        return {}

    # 2. Définition des rôles avec accès total
    roles_admin = ['Admin', 'Gérant']
    user_roles = user_data.get('roles', [])
    
    # Vérification : est-ce que l'utilisateur a au moins un rôle d'admin ?
    is_admin = any(role in roles_admin for role in user_roles)

    if is_admin:
        # ACCÈS TOTAL : Pas de filtre
        clients_data = query_notion(config['db_clients'])
    else:
        # ACCÈS RESTREINT (Employé ou Sous-traitant)
        # On filtre par la relation "Intervenants" dans la base Clients
        filter_payload = {
            "filter": {
                "property": "Intervenants", # Nom exact de la colonne dans Notion
                "relation": {
                    "contains": user_data['id'] # ID de l'intervenant connecté
                }
            }
        }
        clients_data = query_notion(config['db_clients'], filter_payload)

    # 3. Formatage pour le selectbox de Streamlit { "Nom du Client": "ID_Notion" }
    clients_dict = {}
    for c in clients_data:
        # get_title est ta fonction qui extrait le texte de la propriété 'Name'
        name = get_title(c, 'Name') 
        if name:
            clients_dict[name] = c['id']
            
    return clients_dict

def get_prestations_for_client(id_client):
    config = get_notion_config()
    filter_payload = {
        "filter": {
            "property": "Clients", 
            "relation": {"contains": id_client}
        }
    }
    prestas_data = query_notion(config['db_prestations'], filter_payload)
    return {get_title(p, 'Prestation'): p['id'] for p in prestas_data}

def get_interventions_history(user_data):
    config = get_notion_config()
    headers = config["headers"]
    db_id = config["db_interventions"]
    
    is_admin = any(role in ["Gérant", "Manager", "Admin"] for role in user_data['roles'])
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    
    payload = {
        "sorts": [{"property": "Date Intervention", "direction": "descending"}]
    }
    
    if not is_admin:
        payload["filter"] = {
            "property": "Intervenants",
            "relation": {"contains": user_data['id']}
        }
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        return res.json().get('results', [])
    return []

# --- ENREGISTREMENT FINAL ---

def create_intervention_page(payload):
    config = get_notion_config()
    url = "https://api.notion.com/v1/pages"
    headers = config['headers']

    response = requests.post(url, json=payload, headers=headers)
    return response

# --- NOUVELLES FONCTIONS : MODIFICATION ET SUPPRESSION ---

def delete_intervention(page_id):
    """Archive une page Notion (équivalent à la suppression)."""
    config = get_notion_config()
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    # Dans Notion, on ne supprime pas physiquement, on archive.
    payload = {"archived": True}
    
    response = requests.patch(url, json=payload, headers=config['headers'])
    
    if response.status_code == 200:
        return True
    else:
        print(f"Erreur Suppression Notion : {response.text}")
        return False

def update_intervention(page_id, properties_payload):
    """Met à jour les propriétés d'une page Notion existante."""
    config = get_notion_config()
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    payload = {"properties": properties_payload}
    
    response = requests.patch(url, json=payload, headers=config['headers'])
    
    if response.status_code == 200:
        return True
    else:
        print(f"Erreur Mise à jour Notion : {response.text}")
        return False