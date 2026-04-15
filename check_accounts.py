import os
import requests
from dotenv import load_dotenv

load_dotenv()
headers = {"Authorization": f"{os.getenv('QONTO_LOGIN_ID')}:{os.getenv('QONTO_SECRET_KEY')}"}

# On récupère les infos de l'organisation
res = requests.get("https://thirdparty.qonto.com/v2/organization", headers=headers)
data = res.json()

print("--- VOS COMPTES DISPONIBLES ---")
for account in data['organization']['bank_accounts']:
    print(f"IBAN: {account['iban']}")
    print(f"ID à utiliser (slug): {account['slug']}") # C'est souvent ce 'slug' qu'il faut
    print("-" * 30)