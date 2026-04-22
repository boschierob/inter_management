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
        "token": token,  # Ajouté pour create_intervention_page
        "headers": headers,
        "db_clients": db_clients,
        "db_prestations": db_prestations,
        "db_interventions": db_interventions,
        "db_intervenants": db_intervenants
    }

# --- GESTION DES IMAGES (Cloudinary) ---

def convert_canvas_to_image(canvas_data):
    """Transforme l'array du canvas en fichier PNG pour Cloudinary."""
    # Vérification : le canvas contient-il du dessin ? (Pixel alpha > 0)
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
        # Si c'est un fichier Streamlit, on remet au début
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

def get_all_clients(user_data=None):
    config = get_notion_config()
    if not user_data or any(role in ['Admin', 'Gérant'] for role in user_data['roles']):
        clients_data = query_notion(config['db_clients'])
    else:
        filter_payload = {
            "filter": {
                "property": "Intervenant(s) Responsable(s)",
                "relation": {"contains": user_data['id']}
            }
        }
        clients_data = query_notion(config['db_clients'], filter_payload)
    return {get_title(c, 'Name'): c['id'] for c in clients_data}

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

# --- ENREGISTREMENT FINAL ---

def create_intervention_page(payload):
    config = get_notion_config()
    url = "https://api.notion.com/v1/pages"
    
    # Utilisation du token récupéré via config
    headers = config['headers']

    print("\n--- DEBUG ENVOI NOTION ---")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code in [200, 201]:
        print("✅ Notion a accepté l'enregistrement !")
    else:
        print(f"❌ Erreur Notion ({response.status_code})")
        print(f"Détail : {response.text}")
        
    return response