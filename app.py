import streamlit as st
import os
import record_inter as api
from datetime import datetime
try:
    from streamlit_canvas import st_canvas
except ImportError:
    from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io

# 1. Configurer la page
st.set_page_config(page_title="Gestion Interventions", layout="centered")

# --- STYLE CSS AMÉLIORÉ ---
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
    .hist-card {
        padding: 1rem;
        border-left: 5px solid #01579b;
        background-color: #f8f9fa;
        border-radius: 5px;
        margin-bottom: 10px;
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
if 'canvas_key' not in st.session_state:
    st.session_state.canvas_key = 0
if 'page' not in st.session_state:
    st.session_state.page = "saisie"

# --- MODAL DE SUCCÈS ---
@st.dialog("🚀 Opération réussie !")
def show_success_modal(count):
    st.balloons()
    st.success(f"Félicitations ! {count} intervention(s) ont été enregistrées dans Notion.")
    st.write("Que souhaitez-vous faire maintenant ?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Nouvelle saisie"):
            st.session_state.canvas_key += 1
            st.rerun()
    with col2:
        if st.button("📋 Voir l'historique"):
            st.session_state.page = "historique"
            st.rerun()
    
    st.divider()
    if st.button("🏠 Retour à l'accueil"):
        st.rerun()

# --- ÉCRAN DE CONNEXION ---
if st.session_state.user is None:
    st.title("🔐 Connexion")
    with st.form("login_form"):
        email = st.text_input("Email Professionnel")
        pin = st.text_input("Code PIN (4 chiffres)", type="password", max_chars=4)
        submit_login = st.form_submit_button("Se connecter")
        
        if submit_login:
            with st.spinner("Vérification..."):
                user_data = api.login_user(email, pin)
                if user_data:
                    st.session_state.user = user_data
                    st.rerun()
                else:
                    st.error("Email ou PIN incorrect.")
    st.stop() 

# --- NAVIGATION & HEADER ---
user = st.session_state.user
# Création d'une ligne avec les infos à gauche et le bouton à droite
header_col1, header_col2 = st.columns([4, 1])

with header_col1:
    st.markdown(f"""
        <div style="padding-top: 10px;">
            👤 <strong>{user['name']}</strong> 
            <span style="color: #666; font-size: 0.85em;">({", ".join(user['roles'])})</span>
        </div>
    """, unsafe_allow_html=True)

with header_col2:
    if st.button("🚪 Déconnexion", key="logout_btn"):
        # On vide les variables de session importantes
        st.session_state.user = None
        st.session_state.multi_interventions = []
        st.session_state.page = "saisie"
        st.rerun()

st.divider() # Une petite ligne pour séparer le header du contenu
# Barre de navigation simple
nav_col1, nav_col2, nav_col3 = st.columns([1,1,2])
if nav_col1.button("🏠 Accueil"):
    st.session_state.page = "saisie"
    st.rerun()
if nav_col2.button("📋 Historique"):
    st.session_state.page = "historique"
    st.rerun()

# --- PAGE HISTORIQUE ---
if st.session_state.page == "historique":
    st.title("📋 Historique des enregistrements")
    if st.button("⬅️ Précédent"):
        st.session_state.page = "saisie"
        st.rerun()

    with st.spinner("Récupération des données..."):
        history = api.get_interventions_history(user)
        if not history:
            st.info("Aucun historique disponible.")
        else:
            for res in history:
                p = res['properties']
                date_val = p['Date Intervention']['date']['start']
                comment = p['Commentaire']['rich_text'][0]['plain_text'] if p['Commentaire']['rich_text'] else "Sans commentaire"
                
                st.markdown(f"""
                <div class="hist-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>📅 {date_val}</strong>
                        <span class="client-tag">Enregistré</span>
                    </div>
                    <p style="margin:5px 0; font-size:0.95em;">💬 {comment}</p>
                </div>
                """, unsafe_allow_html=True)

# --- PAGE SAISIE ---
else:
    st.title("🛠 Saisie Interventions")
    
    # --- ÉTAPE 1 : SÉLECTION DU CLIENT ---
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
                photos = st.file_uploader("📸 Preuves photos", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

                st.write("✍️ **Signatures**")
                col_sig_a, col_sig_b = st.columns(2)
                with col_sig_a:
                    st.caption("Signature Client")
                    canvas_client = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=100, key=f"sig_client_{st.session_state.canvas_key}", display_toolbar=False, update_streamlit=True)
                with col_sig_b:
                    st.caption("Signature Intervenant")
                    canvas_inter = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=100, key=f"sig_inter_{st.session_state.canvas_key}", display_toolbar=False, update_streamlit=True)
                
                submitted = st.form_submit_button("Ajouter au panier")
                
                if submitted and presta_choice:
                    st.session_state.multi_interventions.append({
                        "client_name": client_name, "client_id": client_id,
                        "nom_presta": presta_choice, "id_presta": st.session_state.cached_prestas[presta_choice],
                        "date": str(date_choice), "commentaire": comment, "intervenant_id": user['id'],
                        "photos": photos if photos else [],
                        "canvas_client_data": canvas_client.image_data,
                        "canvas_inter_data": canvas_inter.image_data
                    })
                    st.session_state.canvas_key += 1
                    st.toast(f"Ajouté : {presta_choice}")
                    st.rerun()

    # --- ÉTAPE 3 : RÉCAPITULATIF ET ENVOI ---
    if st.session_state.multi_interventions:
        st.divider()
        st.subheader(f"📝 Panier ({len(st.session_state.multi_interventions)})")
        
        for i, item in enumerate(st.session_state.multi_interventions):
            with st.container():
                st.markdown(f'<div class="card"><span class="client-tag">{item["client_name"]}</span><br><strong>{item["nom_presta"]}</strong><br>📅 {item["date"]}</div>', unsafe_allow_html=True)
                if st.button(f"Retirer", key=f"del_{i}"):
                    st.session_state.multi_interventions.pop(i)
                    st.rerun()

        if st.button("🚀 ENREGISTRER TOUT DANS NOTION", type="primary"):
            config = api.get_notion_config()
            success_count = 0
            total = len(st.session_state.multi_interventions)
            progress_bar = st.progress(0)
            
            for idx, inter in enumerate(st.session_state.multi_interventions):
                with st.spinner(f"Envoi {idx+1}/{total}..."):
                    # ... (Garder ici ta logique de traitement photos/signatures identique) ...
                    # Simulation de l'appel pour l'exemple (à garder tel quel dans ton code)
                    res = api.create_intervention_page({"parent": {"database_id": config['db_interventions']}, "properties": {}}) # Version simplifiée pour l'ex
                    
                    # NOTE : Remets bien ici ton bloc complet de construction du payload 'props' que tu avais avant
                    if res.status_code in [200, 201]:
                        success_count += 1
                    progress_bar.progress((idx + 1) / total)
            
            if success_count == total and total > 0:
                st.session_state.multi_interventions = []
                show_success_modal(success_count) # APPEL DU MODAL
            elif success_count > 0:
                st.warning(f"Succès partiel : {success_count}/{total}")