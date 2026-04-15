import streamlit as st
import record_inter as api
from datetime import datetime

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.getenv("NOTION_TOKEN")
DB_CLIENTS = st.secrets.get("NOTION_CLIENTS_DB_ID") or os.getenv("NOTION_CLIENTS_DB_ID")

# Configurer la page pour le responsive
st.set_page_config(page_title="Saisie Multi-Clients", layout="centered")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; margin-top: 10px; }
    .card {
        padding: 1.2rem;
        border-radius: 10px;
        background-color: #ffffff;
        border: 1px solid #e6e9ef;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .client-tag {
        background-color: #e1f5fe;
        color: #01579b;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛠 Saisie Multi-Clients")

# --- INITIALISATION DE L'ÉTAT (Persistant même si on change de client) ---
if 'multi_interventions' not in st.session_state:
    st.session_state.multi_interventions = []

# --- ÉTAPE 1 : SÉLECTION DU CLIENT ---
all_clients = api.get_all_clients()
client_name = st.selectbox("🎯 Choisir le Client", options=[""] + list(all_clients.keys()))

if client_name:
    client_id = all_clients[client_name]
    
    # Charger les prestations du client sélectionné
    # On utilise un cache simple pour ne pas requêter Notion à chaque clic
    if 'cached_prestas' not in st.session_state or st.session_state.get('last_selected_client') != client_name:
        with st.spinner(f"Chargement des prestations de {client_name}..."):
            st.session_state.cached_prestas = api.get_prestations_for_client(client_id)
            st.session_state.last_selected_client = client_name

    # --- ÉTAPE 2 : FORMULAIRE D'AJOUT ---
    with st.expander(f"➕ Ajouter une intervention pour {client_name}", expanded=True):
        with st.form("form_inter", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                presta_choice = st.selectbox("Prestation", options=list(st.session_state.cached_prestas.keys()))
            with col2:
                date_choice = st.date_input("Date", value=datetime.now())
            
            comment = st.text_area("Commentaire (optionnel)")
            
            submitted = st.form_submit_button("Ajouter au panier")
            if submitted:
                # ICI : On enregistre l'ID du client AVEC l'intervention
                st.session_state.multi_interventions.append({
                    "client_name": client_name,
                    "client_id": client_id,
                    "nom_presta": presta_choice,
                    "id_presta": st.session_state.cached_prestas[presta_choice],
                    "date": str(date_choice),
                    "commentaire": comment
                })
                st.toast(f"Ajouté : {client_name} - {presta_choice}")

# --- ÉTAPE 3 : RÉCAPITULATIF GLOBAL (Indépendant du client sélectionné) ---
if st.session_state.multi_interventions:
    st.divider()
    st.subheader(f"📝 Panier d'interventions ({len(st.session_state.multi_interventions)})")
    
    for i, item in enumerate(st.session_state.multi_interventions):
        with st.container():
            st.markdown(f"""
            <div class="card">
                <span class="client-tag">{item['client_name']}</span><br>
                <strong>{item['nom_presta']}</strong><br>
                📅 {item['date']} | 💬 {item['commentaire']}
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Retirer", key=f"del_{i}"):
                st.session_state.multi_interventions.pop(i)
                st.rerun()

    st.divider()
    
    if st.button("🚀 ENREGISTRER TOUT DANS NOTION", type="primary"):
        success_count = 0
        total = len(st.session_state.multi_interventions)
        progress_bar = st.progress(0)
        
        for idx, inter in enumerate(st.session_state.multi_interventions):
            payload = {
                "parent": {"database_id": api.DB_INTERVENTIONS},
                "properties": {
                    "Date Intervention": {"date": {"start": inter['date']}},
                    "Client": {"relation": [{"id": inter['client_id']}]}, # Utilise l'ID spécifique à la ligne
                    "Lien Prestation": {"relation": [{"id": inter['id_presta']}]},
                    "Prestation Titre": {"rich_text": [{"text": {"content": inter['nom_presta']}}]},
                    "Commentaire": {"rich_text": [{"text": {"content": inter['commentaire']}}]}
                }
            }
            res = api.create_intervention_page(payload)
            if res.status_code == 200:
                success_count += 1
            
            progress_bar.progress((idx + 1) / total)
        
        if success_count == total:
            st.success(f"Terminé ! {success_count} interventions créées dans Notion.")
            st.session_state.multi_interventions = [] # On vide le panier après succès total
            st.balloons()
        else:
            st.warning(f"Attention : seulement {success_count}/{total} enregistrements réussis.")
else:
    if not client_name:
        st.info("Sélectionnez un premier client pour commencer à remplir votre panier d'interventions.")