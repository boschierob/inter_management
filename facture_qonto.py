import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Configuration Qonto
QONTO_LOGIN = os.getenv("QONTO_LOGIN_ID")
QONTO_SECRET = os.getenv("QONTO_SECRET_KEY")
QONTO_API_URL = "https://thirdparty.qonto.com/v2/client_invoices"
MY_IBAN = os.getenv("MY_IBAN")

headers = {
    "Authorization": f"{QONTO_LOGIN}:{QONTO_SECRET}",
    "Content-Type": "application/json"
}

res = requests.get("https://thirdparty.qonto.com/v2/organization", headers=headers)
print(res.json())

def create_draft_invoice(customer_id, title, amount_cents):
    """
    Crée une facture en mode DRAFT (Brouillon) dans Qonto
    amount_cents: montant en centimes (ex: 100.00€ = 10000)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    payload = {
        "client_id": customer_id,
        "issue_date": today,
        "due_date": due_date,
        "currency": "EUR",
        "status": "draft",
        "payment_methods": { 
            "iban": MY_IBAN  # <-- La correction est ici (objet imbriqué)
        },
        "items": [
            {
                "title": title,
                "quantity": "1",
                "unit_price": {
                    "value": str(amount_cents),
                    "currency": "EUR"
                },
                "vat_rate": "0.20", # 20% s'écrit 0.20 dans cette version de l'API
                "description": "Prestation effectuée et enregistrée via Notion"
            }
        ]
    }

    response = requests.post(QONTO_API_URL, headers=headers, json=payload)
    
    if response.status_code == 201:
        print(f"✅ Brouillon créé avec succès pour {title} !")
        print(f"🔗 Allez voir dans votre interface Qonto > Facturation")
    else:
        print(f"❌ Erreur Qonto : {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    # TEST : Remplacez par un vrai ID client Qonto de votre Notion
    TEST_CUSTOMER_ID = "019d8c99-7bb5-7386-8f5c-5a314e697ddc"
    create_draft_invoice(TEST_CUSTOMER_ID, "Test Facturation Automatique", 50.0) # 50.00€