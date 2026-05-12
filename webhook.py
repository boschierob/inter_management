import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv('NOTION_TOKEN')

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- ROUTES FLASK (RÉCEPTION UNIQUEMENT) ---

@app.route('/')
def home():
    return "Serveur de Webhook Nickel Net : Actif", 200

@app.route('/sendgrid-webhooks', methods=['POST'])
def handle_sendgrid_webhooks():
    events = request.get_json() if request.is_json else []
    if not events:
        return jsonify({"status": "no data"}), 400

    for event in events:
        # On récupère l'ID Notion que l'engine a glissé dans l'email
        msg_id = event.get('notion_msg_id')
        status = event.get('event')
        
        if msg_id:
            # Mapping des statuts SendGrid vers Notion
            status_map = {
                'delivered': "🟢 Livré",
                'bounce': "🔴 Rejeté (Bounce)",
                'dropped': "🟠 Bloqué (Spam)",
                'open': "📖 Ouvert",
                'click': "🔗 Lien cliqué"
            }
            new_val = status_map.get(status)
            if new_val:
                print(f"Statut reçu : {status} pour le message {msg_id}")
                update_notion_status(msg_id, {"Status": {"select": {"name": new_val}}})
                
    return jsonify({"status": "received"}), 200

# --- FONCTION DE MISE À JOUR ---

def update_notion_status(page_id, properties):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        r = requests.patch(url, json={"properties": properties}, headers=headers)
        return r.status_code
    except Exception as e:
        print(f"Erreur update Notion: {e}")

if __name__ == "__main__":
    app.run(port=5000, debug=True)