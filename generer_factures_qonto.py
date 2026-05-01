import os
import requests
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
import notion_cleanup

load_dotenv()

# --- CONFIGURATION DU LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("facturation_debug.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger()

# Configuration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_INTERVENTIONS_DB_ID = os.getenv("NOTION_INTERVENTIONS_DB_ID")
QONTO_LOGIN = os.getenv("QONTO_LOGIN_ID")
QONTO_SECRET = os.getenv("QONTO_SECRET_KEY")
MY_IBAN = os.getenv("MY_IBAN")

headers_notion = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def extract_text(prop):
    """
    Extrait proprement le texte brut des structures complexes de Notion (Rollups, Rich Text, Numbers).
    """
    if not prop: 
        return ""
    
    p_type = prop.get('type')
    
    if p_type == 'rollup':
        r_data = prop.get('rollup', {})
        r_type = r_data.get('type')
        
        if r_type == 'array':
            items = r_data.get('array', [])
            if not items: 
                return ""
            return extract_text(items[0])
        elif r_type == 'number':
            val = r_data.get('number')
            return str(val) if val is not None else ""
        elif r_type == 'rich_text':
            texts = r_data.get('rich_text', [])
            return "".join([t.get('plain_text', '') for t in texts]).strip()

    content = prop.get('rich_text') or prop.get('title')
    
    if content is None:
        inner_type = prop.get('type')
        if inner_type in prop:
            content = prop[inner_type]

    if isinstance(content, list):
        return "".join([t.get('plain_text', '') for t in content]).strip()
    
    return str(content).strip() if content is not None else ""

def sync_tally_to_notion_relations():
    url = f"https://api.notion.com/v1/databases/{NOTION_INTERVENTIONS_DB_ID}/query"
    payload = {"filter": {"and": [{"property": "Lien Prestation", "relation": {"is_empty": True}}, {"property": "ID_Transit_Presta", "rich_text": {"is_not_empty": True}}]}}
    try:
        res = requests.post(url, headers=headers_notion, json=payload)
        pages = res.json().get("results", [])
        for page in pages:
            transit = extract_text(page["properties"].get("ID_Transit_Presta"))
            if transit:
                requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", headers=headers_notion, json={"properties": {"Lien Prestation": {"relation": [{"id": transit}]}}})
        if pages: time.sleep(2)
    except Exception as e: 
        logger.error(f"Synchro fail: {e}")

def update_notion_status(page_ids):
    for pid in page_ids:
        requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers_notion, json={"properties": {"Status": {"status": {"name": "Facturé"}}}})

def generer_factures():
    # 1. On lance d'abord le nettoyage (Attention: nécessite une action dans le terminal si doublons trouvés)
    logger.info("Démarrage du nettoyage préalable...")
    notion_cleanup.cleanup_relation_db()
    
    # 2. On synchronise les nouvelles entrées Tally
    logger.info("Synchronisation Tally -> Notion...")
    sync_tally_to_notion_relations()
    
    # 3. Récupération des interventions à facturer
    url = f"https://api.notion.com/v1/databases/{NOTION_INTERVENTIONS_DB_ID}/query"
    res = requests.post(url, headers=headers_notion, json={"filter": {"property": "Status", "status": {"equals": "A facturer"}}})
    interventions = res.json().get("results", [])
    if not interventions: 
        return logger.info("Rien à facturer.")

    groupes = defaultdict(list)
    noms_clients = {}
    pages_par_groupe = defaultdict(list)

    for i, row in enumerate(interventions):
        props = row['properties']
        pid = row['id']

        q_id = extract_text(props.get('ID Client Qonto'))
        c_name = extract_text(props.get('Client Nom')) # CORRIGÉ ICI (Anciennement 'Nom Client')
        
        if not q_id:
            logger.warning(f"Ligne {i+1} : ID Qonto manquant pour {c_name}. Ignorée.")
            continue

        d_val = props.get('Date Intervention', {}).get('date', {}).get('start')
        if not d_val: continue
        d_obj = datetime.strptime(d_val, "%Y-%m-%d")
        
        annee = d_obj.strftime("%Y")
        mois_num = d_obj.strftime("%m")
        d_court = d_obj.strftime("%d/%m")

        rel_prestas = props.get('Lien Prestation', {}).get('relation', [])
        ids_presta = [r['id'] for r in rel_prestas]
        
        titre_list = []
        r_titre = props.get('Prestation Titre', {}).get('rollup', {}).get('array', [])
        for t in r_titre:
            titre_list.append(extract_text(t))

        # SÉCURITÉ AJOUTÉE : Gestion robuste du Rollup "Montant HT"
        prix_list = []
        montant_prop = props.get('Montant HT', {})
        if montant_prop.get('type') == 'rollup':
            r_type = montant_prop['rollup'].get('type')
            if r_type == 'array':
                for p in montant_prop['rollup']['array']:
                    if p.get('type') == 'number': prix_list.append(p['number'])
            elif r_type == 'number':
                prix_list.append(montant_prop['rollup']['number'])

        desc_list = []
        r_desc = props.get('Description', {}).get('rollup', {}).get('array', [])
        for d in r_desc:
            desc_list.append(extract_text(d))

        for j in range(len(prix_list)):
            presta_uid = ids_presta[j] if j < len(ids_presta) else "divers"
            presta_titre = titre_list[j] if j < len(titre_list) and titre_list[j] else "Prestation"
            presta_desc = desc_list[j] if j < len(desc_list) else ""
            val_prix = prix_list[j]
            
            if val_prix > 0:
                groupes[(q_id, annee)].append({
                    "uid": presta_uid,
                    "mois": mois_num, 
                    "titre": presta_titre,
                    "desc": presta_desc,
                    "price": float(val_prix),
                    "date": d_court
                })

        noms_clients[q_id] = c_name if c_name else f"ID_{q_id}"
        pages_par_groupe[(q_id, annee)].append(pid)
        logger.info(f"✅ Ligne validée : {noms_clients[q_id]} ({d_court})")

    # --- 5. ENVOI QONTO ---
    headers_q = {"Authorization": f"{QONTO_LOGIN}:{QONTO_SECRET}", "Content-Type": "application/json"}
    
    for (q_id, annee), items in groupes.items():
        fusion = {}
        for it in items:
            k = (it['uid'], it['price'], it['mois'])
            if k not in fusion: 
                fusion[k] = {"titre": it['titre'], "desc": it['desc'], "dates": set(), "qty": 0}
            fusion[k]["dates"].add(it['date'])
            fusion[k]["qty"] += 1

        q_items = []
        sorted_keys = sorted(fusion.keys(), key=lambda x: x[2])

        for k in sorted_keys:
            data = fusion[k]
            px = k[1]
            
            dates_list = list(data["dates"])
            dates_list.sort(key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
            dates_label = ", ".join(dates_list)
            
            full_description = f"{data['desc']}\nDates d'intervention : {dates_label}".strip()

            q_items.append({
                "title": data['titre'][:120],
                "description": full_description,
                "quantity": str(data["qty"]),
                "unit_price": {"value": f"{px:.2f}", "currency": "EUR"},
                "vat_rate": "0.20"
            })

        payload = {
            "client_id": q_id,
            "issue_date": datetime.now().strftime("%Y-%m-%d"),
            "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "currency": "EUR", "status": "draft",
            "payment_methods": {"iban": MY_IBAN}, "items": q_items
        }

        res = requests.post("https://thirdparty.qonto.com/v2/client_invoices", json=payload, headers=headers_q)
        if res.status_code == 201:
            logger.info(f"🚀 Brouillon créé pour {noms_clients[q_id]} (Mois facturés: {', '.join(set([k[2] for k in sorted_keys]))})")
            update_notion_status(pages_par_groupe[(q_id, annee)])
        else:
            logger.error(f"❌ Erreur Qonto pour {noms_clients[q_id]} : {res.text}")

if __name__ == "__main__":
    generer_factures()