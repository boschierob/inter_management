import streamlit as st
import os
import record_inter as api
from datetime import datetime

# 1. Configurer la page
st.set_page_config(page_title="Saisie Interventions", layout="centered")

# --- STYLE CSS ---
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
    .user-info {
        font-size: 0.9em;
        color: #666;
        text-align: right;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION DE L'ÉTAT ---
if 'multi_interventions' not in st.session_state:
    st.session_state.multi_interventions = []
if 'user' not in st.session_state:
    st.session_state.user = None

# --- ÉCRAN DE CONNEXION ---
if st.session_state.user is None:
    st.title("🔐 Connexion")
    with st.form("login_form"):
        email = st.text_input("Email Professionnel")
        # Utilisation de type="password" et max_chars=4 pour le PIN
        pin = st.text_input("Code PIN (4 chiffres)", type="password", max_chars=4)
        submit_login = st.form_submit_button("Se connecter")
        
        if submit_login:
            with st.spinner("Vérification..."):
                user_data = api.login_user(email, pin)
                if user_data:
                    st.session_state.user = user_data
                    st.success(f"Bienvenue {user_data['name']} !")
                    st.rerun()
                else:
                    st.error("Email ou PIN incorrect.")
    st.stop() # Arrête l'exécution ici si pas connecté

# --- INTERFACE PRINCIPALE (Utilisateur connecté) ---
user = st.session_state.user

# Barre d'info utilisateur
st.markdown(f"""<div class="user-info">👤 {user['name']} ({", ".join(user['roles'])}) | 
            <a href="javascript:window.location.reload();" style="color:red; text-decoration:none;">Déconnexion</a></div>""", 
            unsafe_allow_html=True)

st.title("🛠 Saisie Multi-Clients")

# --- ÉTAPE 1 : SÉLECTION DU CLIENT (Filtrée par rôle) ---
# On passe user_data à l'API pour filtrer selon les droits
all_clients = api.get_all_clients(user_data=user)
client_name = st.selectbox("🎯 Choisir le Client", options=[""] + list(all_clients.keys()))

if client_name:
    client_id = all_clients[client_name]
    
    if 'cached_prestas' not in st.session_state or st.session_state.get('last_selected_client') != client_name:
        with st.spinner(f"Chargement des prestations..."):
            st.session_state.cached_prestas = api.get_prestations_for_client(client_id)
            st.session_state.last_selected_client = client_name

    # --- ÉTAPE 2 : FORMULAIRE D'AJOUT ---
    with st.expander(f"➕ Ajouter une intervention pour {client_name}", expanded=True):
        with st.form("form_inter", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                presta_options = list(st.session_state.cached_prestas.keys())
                presta_choice = st.selectbox("Prestation", options=presta_options)
            with col2:
                date_choice = st.date_input("Date", value=datetime.now())
            
            comment = st.text_area("Commentaire (optionnel)")
            
            submitted = st.form_submit_button("Ajouter au panier")
            if submitted and presta_choice:
                st.session_state.multi_interventions.append({
                    "client_name": client_name,
                    "client_id": client_id,
                    "nom_presta": presta_choice,
                    "id_presta": st.session_state.cached_prestas[presta_choice],
                    "date": str(date_choice),
                    "commentaire": comment,
                    "intervenant_id": user['id'] # On stocke l'ID de celui qui saisit
                })
                st.toast(f"Ajouté : {presta_choice}")

# --- ÉTAPE 3 : RÉCAPITULATIF ET ENVOI ---
if st.session_state.multi_interventions:
    st.divider()
    st.subheader(f"📝 Panier ({len(st.session_state.multi_interventions)})")
    
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

    if st.button("🚀 ENREGISTRER TOUT DANS NOTION", type="primary"):
        config = api.get_notion_config()
        success_count = 0
        total = len(st.session_state.multi_interventions)
        progress_bar = st.progress(0)
        
        for idx, inter in enumerate(st.session_state.multi_interventions):
            payload = {
                "parent": {"database_id": config['db_interventions']},
                "properties": {
                    "Date Intervention": {"date": {"start": inter['date']}},
                    "Client": {"relation": [{"id": inter['client_id']}]},
                    "Lien Prestation": {"relation": [{"id": inter['id_presta']}]},
                    "Prestation Titre": {"rich_text": [{"text": {"content": inter['nom_presta']}}]},
                    "Commentaire": {"rich_text": [{"text": {"content": inter['commentaire']}}]},
                    # AJOUT : On lie l'intervention à l'intervenant pour la paie
                    "Intervenant ayant réalisé l'action": {"relation": [{"id": inter['intervenant_id']}]}
                }
            }
            res = api.create_intervention_page(payload)
            if res.status_code == 200:
                success_count += 1
            progress_bar.progress((idx + 1) / total)
        
        if success_count == total:
            st.success("Toutes les interventions ont été enregistrées !")
            st.session_state.multi_interventions = []
            st.balloons()
            st.rerun()
else:
    if not client_name:
        st.info("Sélectionnez un client pour commencer.")