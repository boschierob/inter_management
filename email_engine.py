import os
import base64
import requests
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, Bcc

load_dotenv()

# Config
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
MESSAGERIE_DB_ID = os.getenv("NOTION_MESSAGERIE_DB_ID") # Base "Messagerie"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def update_notion_status(page_id, properties):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(url, json={"properties": properties}, headers=headers)

def run_real_delivery():
    print("🚀 DÉMARRAGE DE L'ENVOI (SOURCE: MESSAGERIE NOTION)")

    # 1. On cherche les messages "À envoyer" dans la base Messagerie
    url = f"https://api.notion.com/v1/databases/{MESSAGERIE_DB_ID}/query"
    payload = {
        "filter": {
            "property": "Status", 
            "select": {"equals": "À envoyer"}
        }
    }

    res = requests.post(url, json=payload, headers=headers)
    if res.status_code != 200:
        print(f"❌ Erreur Notion Messagerie: {res.text}")
        return

    messages = res.json().get("results", [])
    if not messages:
        print("✅ Aucun message en attente d'envoi.")
        return

    sg = SendGridAPIClient(SENDGRID_API_KEY)

    for msg in messages:
        props = msg["properties"]
        msg_id = msg["id"]
        
        # Récupération Destinataire (vérifie si c'est une colonne Email ou Texte)
        dest_prop = props.get("Destinataire", {})
        destinataire = dest_prop.get("email") or (dest_prop.get("rich_text", [{}])[0].get("plain_text") if dest_prop.get("rich_text") else None)
        
        # Récupération Sujet
        sujet_data = props.get("Sujet", {}).get("title", [])
        sujet = "".join([t["plain_text"] for t in sujet_data]) if sujet_data else "Votre facture"

        if not destinataire:
            print(f"⚠️ Email manquant pour le message {msg_id}")
            continue

        # 2. On récupère les factures liées (Relation)
        # Assure-toi que la relation s'appelle bien "Facture" ou "Factures"
        facture_relations = props.get("Facture", {}).get("relation", [])
        
        mail = Mail(
            from_email=FROM_EMAIL,
            to_emails=destinataire,
            subject=sujet,
            plain_text_content="Bonjour,\n\nVeuillez trouver ci-joint votre facture nettoyage.\n\nCordialement."
        )

        mail.add_bcc(Bcc("contact.nickelnet@gmail.com"))

        has_attachment = False

        for rel in facture_relations:
            f_id = rel["id"]
            
            # On va chercher les infos de la facture dans la table Factures
            f_res = requests.get(f"https://api.notion.com/v1/pages/{f_id}", headers=headers).json()
            f_props = f_res.get("properties", {})

            # On récupère le lien Supabase et le Numéro de facture
            supabase_url = f_props.get("Lien PDF", {}).get("url")
            num_data = f_props.get("Numéro", {}).get("rich_text", [])
            num = num_data[0]["plain_text"] if num_data else "Facture"

            # On vérifie aussi le status de la facture (unpaid) si tu veux être prudent
            status_facture = f_props.get("Status", {}).get("select", {}).get("name")

            if supabase_url and status_facture == "unpaid":
                try:
                    print(f"📥 Récupération PDF {num} depuis Supabase...")
                    pdf_content = requests.get(supabase_url).content
                    
                    encoded = base64.b64encode(pdf_content).decode()
                    attachment = Attachment(
                        FileContent(encoded),
                        FileName(f"{num}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment")
                    )
                    mail.add_attachment(attachment)
                    has_attachment = True
                except Exception as e:
                    print(f"❌ Erreur PDF {num}: {e}")

        # 3. Envoi si on a au moins une pièce jointe
        if has_attachment:
            try:
                sg.send(mail)
                print(f"🟡 Envoi en cours à {destinataire}")
                # On met à jour le statut dans la base Messagerie
                update_notion_status(msg_id, {"Status": {"select": {"name": "🟡 Envoi en cours"}}})
            except Exception as e:
                print(f"❌ Erreur SendGrid: {e}")
        else:
            print(f"⚠️ Message {msg_id} ignoré (aucune facture unpaid avec lien Supabase trouvée)")

if __name__ == "__main__":
    run_real_delivery()