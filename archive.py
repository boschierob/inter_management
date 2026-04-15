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
    handlers=[
        logging.FileHandler("facturation_debug.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
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

def sync_tally_to_notion_relations():
    """
    Transforme les IDs texte (ID_Transit_Presta) envoyés par Tally en véritables Relations Notion (Prestation).
    """
    logger.info("Vérification des relations à synchroniser (Tally -> Notion)...")
    url = f"https://api.notion.com/v1/databases/{NOTION_INTERVENTIONS_DB_ID}/query"
    
    # On cherche les pages où la Relation est vide mais le texte de transit est rempli
    payload = {
        "filter": {
            "and": [
                { "property": "Lien Prestation", "relation": { "is_empty": True } },
                { "property": "ID_Transit_Presta", "rich_text": { "is_not_empty": True } }
            ]
        }
    }

    try:
        res = requests.post(url, headers=headers_notion, json=payload)
        res.raise_for_status()
        pages = res.json().get("results", [])

        if not pages:
            logger.info("Aucune relation à synchroniser.")
            return

        for page in pages:
            page_id = page["id"]
            # Récupération de l'ID brut dans la colonne texte
            transit_props = page["properties"]["ID_Transit_Presta"]["rich_text"]
            if not transit_props:
                continue
                
            presta_id = transit_props[0]["plain_text"].strip()
            
            # Mise à jour de la colonne Relation
            update_url = f"https://api.notion.com/v1/pages/{page_id}"
            update_payload = {
                "properties": {
                    "Prestation": {
                        "relation": [{"id": presta_id}]
                    }
                }
            }
            requests.patch(update_url, headers=headers_notion, json=update_payload)
            logger.info(f"   ∟ ✅ Relation liée pour l'intervention : {page_id}")
        
        # Pause de sécurité pour laisser Notion calculer les Rollups de prix
        logger.info("Attente de synchronisation des prix Notion (2s)...")
        time.sleep(2)

    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation Tally/Notion : {e}")

def update_notion_status(page_ids):
    """Bascule les pages Notion au statut 'Facturé'"""
    for page_id in page_ids:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "Status": {
                    "status": {
                        "name": "Facturé"
                    }
                }
            }
        }
        try:
            res = requests.patch(url, json=payload, headers=headers_notion)
            if res.status_code == 200:
                logger.info(f"   ∟ Notion mis à jour : Page {page_id} -> Facturé")
            else:
                logger.error(f"   ∟ ❌ Erreur mise à jour Notion {page_id}: {res.text}")
        except Exception as e:
            logger.error(f"   ∟ ⚠️ Exception lors de l'update Notion: {e}")

def get_interventions():
    logger.info("Connexion à Notion (Filtre: Status == 'A Facturer')...")
    url = f"https://api.notion.com/v1/databases/{NOTION_INTERVENTIONS_DB_ID}/query"
    
    payload = {
        "filter": {
            "property": "Status",
            "status": {
                "equals": "A facturer"
            }
        }
    }
    
    try:
        res = requests.post(url, headers=headers_notion, json=payload)
        if res.status_code != 200:
            error_detail = res.json()
            logger.error(f"Détail erreur Notion: {error_detail.get('message', 'Erreur inconnue')}")
            
            logger.info("Tentative de secours avec le filtre 'select'...")
            payload["filter"]["select"] = payload["filter"].pop("status")
            res = requests.post(url, headers=headers_notion, json=payload)

        res.raise_for_status()
        results = res.json().get("results", [])
        logger.info(f"Succès : {len(results)} interventions récupérées.")
        return results

    except requests.exceptions.HTTPError as e:
        logger.error(f"Erreur HTTP Notion : {e}")
        return []
    except Exception as e:
        logger.error(f"Erreur imprévue : {e}")
        return []

def generer_factures():
    notion_cleanup.cleanup_relation_db()
    # --- SYNCHRONISATION PRÉALABLE ---
    sync_tally_to_notion_relations()

    interventions = get_interventions()
    if not interventions:
        logger.warning("Aucune donnée 'A Facturer' trouvée. Fin du script.")
        return

    groupes = defaultdict(list)
    noms_clients = {}
    pages_par_groupe = defaultdict(list)
    lignes_ignorees = 0

    logger.info("Analyse microscopique des lignes...")

    for i, row in enumerate(interventions):
        props = row['properties']
        page_id = row['id']
        
        if i == 0:
            logger.info(f"Colonnes détectées par l'API : {list(props.keys())}")

        try:
            # --- 1. RECHERCHE DE L'ID QONTO ---
            qonto_id = None
            prop_qonto = props.get('ID Client Qonto', {})
            
            if prop_qonto.get('type') == 'rollup':
                r_qonto = prop_qonto.get('rollup', {})
                if r_qonto.get('type') == 'array' and r_qonto.get('array'):
                    item = r_qonto['array'][0]
                    inner_type = item.get('type')
                    if inner_type in item and item[inner_type]:
                        content = item[inner_type]
                        if isinstance(content, list) and len(content) > 0:
                            qonto_id = content[0].get('plain_text', "").strip()
                elif r_qonto.get('type') == 'number':
                    qonto_id = str(r_qonto.get('number'))
            
            if not qonto_id:
                logger.warning(f"Ligne {i+1} : ID Qonto vide (colonne 'ID Client Qonto'), ignorée.")
                lignes_ignorees += 1
                continue

            # --- 2. RÉCUPÉRATION DU NOM DU CLIENT ---
            prop_nom_client = props.get('Nom Client', {})
            client_name = "Client Inconnu"
            
            if prop_nom_client.get('type') == 'rich_text' and prop_nom_client['rich_text']:
                client_name = prop_nom_client['rich_text'][0]['plain_text'].strip()
            elif prop_nom_client.get('type') == 'title' and prop_nom_client['title']:
                client_name = prop_nom_client['title'][0]['plain_text'].strip()

            # --- 3. RÉCUPÉRATION DU PRIX HT ---
            prop_prix = props.get('Montant HT', {})
            prix_prestations = []

            if prop_prix.get('type') == 'rollup':
                r_data = prop_prix.get('rollup', {})
                if r_data.get('type') == 'array':
                    for item in r_data.get('array', []):
                        if item.get('type') == 'number':
                            prix_prestations.append(item.get('number', 0))
                elif r_data.get('type') == 'number':
                    prix_prestations.append(r_data.get('number', 0))

            # --- 4. RÉCUPÉRATION DES NOMS DES PRESTATIONS ---
            noms_prestations = []
            prop_presta = props.get('Lien Prestation', {}) 
            
            if prop_presta.get('type') == 'rollup':
                r_data_noms = prop_presta.get('rollup', {})
                if r_data_noms.get('type') == 'array':
                    for item in r_data_noms.get('array', []):
                        t_type = item.get('type') 
                        if t_type in item and item[t_type]:
                            content = item[t_type]
                            if isinstance(content, list) and len(content) > 0:
                                noms_prestations.append(content[0].get('plain_text', 'Prestation'))

            # --- 5. ASSEMBLAGE DES LIGNES (AVEC REGROUPEMENT QUANTITÉ) ---
            pour_cette_intervention = {} 
            for j in range(len(prix_prestations)):
                nom = noms_prestations[j] if j < len(noms_prestations) else "Prestation"
                prix = prix_prestations[j]
                
                if prix > 0:
                    cle_ligne = (nom, float(prix))
                    # On incrémente la quantité pour cette intervention précise
                    pour_cette_intervention[cle_ligne] = pour_cette_intervention.get(cle_ligne, 0) + 1

            liste_details = []
            for (nom, prix), quantite in pour_cette_intervention.items():
                liste_details.append({
                    "name": nom,
                    "price": prix,
                    "quantity": quantite
                })

            if not liste_details:
                logger.warning(f"Ligne {i+1} : Aucun montant HT trouvé pour {client_name}, ignorée.")
                continue

            # --- 6. GROUPEMENT PAR CLIENT ET ANNÉE ---
            date_data = props.get('Date Intervention', {}).get('date')
            if not date_data:
                logger.warning(f"Ligne {i+1} : Date manquante, ignorée.")
                continue
                
            date_str = date_data['start']
            annee = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y")
            
            cle = (qonto_id, annee)
            groupes[cle].extend(liste_details)
            noms_clients[qonto_id] = client_name
            pages_par_groupe[cle].append(page_id) 

            logger.info(f"✅ Ligne {i+1} validée : {client_name} | Exercice {annee}")

        except Exception as e:
            logger.error(f"❌ Erreur critique ligne {i+1} : {str(e)}")
            lignes_ignorees += 1
        
    # --- ENVOI QONTO ---
    today = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    headers_qonto = {"Authorization": f"{QONTO_LOGIN}:{QONTO_SECRET}", "Content-Type": "application/json"}

    for (q_id, annee), details_bruts in groupes.items():
        nom = noms_clients[q_id]
        
        # --- Fusion globale pour l'année entière ---
        fusion_annuelle = {}
        for d in details_bruts:
            cle_ligne = (d['name'], d['price'])
            # On additionne les quantités de toutes les interventions de l'année
            fusion_annuelle[cle_ligne] = fusion_annuelle.get(cle_ligne, 0) + d.get('quantity', 1)

        qonto_items = []
        total_ht_brouillon = 0
        
        for (nom_presta, prix), qty in fusion_annuelle.items():
            total_ht_brouillon += (prix * qty) # Le log prend en compte la quantité
            qonto_items.append({
                "title": f"{nom_presta} (Exercice {annee})",
                "quantity": str(qty),
                "unit_price": {"value": f"{prix:.2f}", "currency": "EUR"},
                "vat_rate": "0.20"
            })
            
        logger.info(f"Création Brouillon Qonto : {nom} (Exercice {annee}) -> {total_ht_brouillon:.2f}€ avec {len(qonto_items)} lignes uniques.")
        
        payload_qonto = {
            "client_id": q_id,
            "issue_date": today,
            "due_date": due_date,
            "currency": "EUR",
            "status": "draft",
            "payment_methods": { "iban": MY_IBAN },
            "items": qonto_items
        }
        
        try:
            res_q = requests.post("https://thirdparty.qonto.com/v2/client_invoices", json=payload_qonto, headers=headers_qonto)
            
            if res_q.status_code == 201:
                logger.info(f"✅ Brouillon Qonto créé pour {nom}.")
                logger.info(f"Mise à jour Notion en cours...")
                update_notion_status(pages_par_groupe[(q_id, annee)])
            else:
                logger.error(f"❌ ÉCHEC Qonto pour {nom} : {res_q.text}. Notion non modifié.")
        except Exception as e:
            logger.error(f"❌ Erreur critique lors de l'envoi à Qonto pour {nom} : {e}")

if __name__ == "__main__":
    logger.info("=== DÉMARRAGE DU SCRIPT DE FACTURATION AUTOMATIQUE ===")
    generer_factures()
    logger.info("=== FIN DU SCRIPT ===")