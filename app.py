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
    .stCanvas {
        border: 1px solid #F0F2F6;
        border-radius: 10px;
    }
    button[title="Send to Streamlit"], button[title="Download"] {
        display: none !important;
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
if 'reset_sig_client' not in st.session_state:
    st.session_state.reset_sig_client = 0
if 'reset_sig_inter' not in st.session_state:
    st.session_state.reset_sig_inter = 0

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
        st.session_state.user = None
        st.session_state.multi_interventions = []
        st.session_state.page = "saisie"
        st.rerun()

st.divider() 
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
                p = res.get('properties', {})
                
                # 1. Date
                date_prop = p.get('Date Intervention', {}).get('date')
                date_val = date_prop.get('start', 'Date inconnue') if date_prop else "Date inconnue"
                
                # 2. Client
                client_rollup = p.get('Client Nom', {}).get('rollup', {}).get('array', [])
                client = "Client inconnu"
                if client_rollup:
                    first_item = client_rollup[0]
                    client = first_item.get('title', [{}])[0].get('plain_text', 
                             first_item.get('plain_text', "Client inconnu"))

                # 3. Prestation
                presta_rollup = p.get('Prestation Titre', {}).get('rollup', {}).get('array', [])
                prestation = "Prestation inconnue"
                if presta_rollup:
                    first_item = presta_rollup[0]
                    prestation = first_item.get('title', [{}])[0].get('plain_text', 
                                 first_item.get('plain_text', "Prestation inconnue"))

                # 4. Adresse Site
                adresse_rollup = p.get('Adresse Site', {}).get('rollup', {}).get('array', [])
                adresse = "-"
                if adresse_rollup:
                    first_addr = adresse_rollup[0]
                    addr_text_list = first_addr.get('rich_text', [])
                    if addr_text_list:
                        adresse = addr_text_list[0].get('plain_text', "-")
                    else:
                        adresse = first_addr.get('plain_text', "-")

                # 5. Commentaire
                comment_list = p.get('Commentaire', {}).get('rich_text', [])
                comment = comment_list[0].get('plain_text', "Sans commentaire") if comment_list else "Sans commentaire"
                
                # 6. Affichage
                st.markdown(f"""
                <div class="hist-card">
                    <div style="display:flex; justify-content:space-between; align-items:start;">
                        <div>
                            <span class="client-tag">{client}</span><br>
                            <strong style="font-size: 1.1em; color: #1f2937;">{prestation}</strong>
                        </div>
                        <div style="text-align: right; font-size: 0.85em; color: #6b7280;">
                            📅 {date_val}
                        </div>
                    </div>
                    <div style="margin-top: 5px; font-size: 0.85em; color: #01579b;">
                        📍 {adresse}
                    </div>
                    <hr style="margin: 10px 0; border: 0; border-top: 1px solid #eee;">
                    <div style="font-style: italic; color: #4b5563; font-size: 0.9em;">
                        💬 {comment}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# --- PAGE SAISIE ---
else:
    st.title("🛠 Saisie Interventions")
    
    all_clients = api.get_all_clients(user_data=user)
    client_name = st.selectbox("🎯 Choisir le Client", options=[""] + list(all_clients.keys()))

    if client_name:
        client_id = all_clients[client_name]
        
        if 'cached_prestas' not in st.session_state or st.session_state.get('last_selected_client') != client_name:
            with st.spinner(f"Chargement des prestations..."):
                st.session_state.cached_prestas = api.get_prestations_for_client(client_id)
                st.session_state.last_selected_client = client_name

        with st.expander(f"➕ Ajouter une intervention pour {client_name}", expanded=True):
            # Utilisation d'un container au lieu d'un st.form pour autoriser les boutons "Effacer"
            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    presta_options = list(st.session_state.cached_prestas.keys())
                    presta_choice = st.selectbox("Prestation", options=presta_options)
                with col2:
                    date_choice = st.date_input("Date", value=datetime.now())
                
                comment = st.text_area("Commentaire (optionnel)")
                photos = st.file_uploader("📸 Preuves photos", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

                st.write("✍️ **Signatures**")
                st.info("💡 Utilisez la petite corbeille en bas à gauche du cadre pour effacer.")
                col_sig_a, col_sig_b = st.columns(2)
                
                with col_sig_a:
                    st.caption("Signature Client")
                    canvas_client = st_canvas(
                        stroke_width=2, 
                        stroke_color="#000", 
                        background_color="#F0F2F6", 
                        height=120, 
                        key=f"sig_c_{st.session_state.canvas_key}", # Clé simplifiée
                        display_toolbar=True,
                        update_streamlit=False
                    )
    
                        
                with col_sig_b:
                    st.caption("Signature Intervenant")
                    canvas_inter = st_canvas(
                        stroke_width=2, 
                        stroke_color="#000", 
                        background_color="#F0F2F6", 
                        height=120, 
                        key=f"sig_i_{st.session_state.canvas_key}", # Clé simplifiée
                        display_toolbar=True, # LE SECRET EST LÀ !
                        update_streamlit=True
                    )
                    # Plus besoin de bouton d'effacement Python !
                # Bouton d'ajout au panier
                if st.button("Ajouter au panier", type="primary"):
                    if presta_choice:
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
                    else:
                        st.warning("Veuillez sélectionner une prestation.")

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

        if st.button("🚀 ENREGISTRER TOUT DANS NOTION", type="primary", use_container_width=True):
            config = api.get_notion_config()
            success_count = 0
            total = len(st.session_state.multi_interventions)
            progress_bar = st.progress(0)
            
            for idx, inter in enumerate(st.session_state.multi_interventions):
                with st.spinner(f"Envoi {idx+1}/{total}..."):
                    
                    # 1. Photos
                    list_files_notion = []
                    for p in inter.get('photos', []):
                        url = api.upload_image_to_cloud(p)
                        if url:
                            list_files_notion.append({"name": p.name, "external": {"url": url}})

                    # 2. Signatures
                    url_sig_client = None
                    if inter.get('canvas_client_data') is not None:
                        img_c = api.convert_canvas_to_image(inter['canvas_client_data'])
                        if img_c:
                            url_sig_client = api.upload_image_to_cloud(img_c)

                    url_sig_inter = None
                    if inter.get('canvas_inter_data') is not None:
                        img_i = api.convert_canvas_to_image(inter['canvas_inter_data'])
                        if img_i:
                            url_sig_inter = api.upload_image_to_cloud(img_i)

                    # 3. Payload
                    props = {
                        "Date Intervention": {"date": {"start": inter['date']}},
                        "Client": {"relation": [{"id": inter['client_id']}]},
                        "Lien Prestation": {"relation": [{"id": inter['id_presta']}]},
                        "Commentaire": {"rich_text": [{"text": {"content": inter['commentaire']}}]},
                        "Intervenants": {"relation": [{"id": inter['intervenant_id']}]}
                    }

                    if list_files_notion:
                        props["Preuves"] = {"files": list_files_notion}
                    if url_sig_client:
                        props["Signature Client"] = {"files": [{"name": "sig_client.png", "external": {"url": url_sig_client}}]}
                    if url_sig_inter:
                        props["Signature Intervenant"] = {"files": [{"name": "sig_inter.png", "external": {"url": url_sig_inter}}]}

                    payload = {
                        "parent": {"database_id": config['db_interventions']},
                        "properties": props
                    }
                    
                    # 4. Envoi
                    res = api.create_intervention_page(payload)
                    
                    if res.status_code in [200, 201]:
                        success_count += 1
                    else:
                        st.error(f"Erreur sur l'item {idx+1}: {res.text}")
                
                progress_bar.progress((idx + 1) / total)
            
            if success_count == total and total > 0:
                st.session_state.multi_interventions = []
                show_success_modal(success_count)