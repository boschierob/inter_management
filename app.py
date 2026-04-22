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
    st.stop() 

# --- INTERFACE PRINCIPALE ---
user = st.session_state.user

st.markdown(f"""<div class="user-info">👤 {user['name']} ({", ".join(user['roles'])})</div>""", unsafe_allow_html=True)
st.title("🛠 Saisie Multi-Clients")

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

            st.write("📸 **Preuves photos**")
            photos = st.file_uploader("Preuves", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

            st.write("✍️ **Signatures**")
            col_sig_a, col_sig_b = st.columns(2)
            
            with col_sig_a:
                st.caption("Signature Client")
                canvas_client = st_canvas(
                    stroke_width=2, stroke_color="#000", background_color="#F0F2F6",
                    height=100, key="sig_client", display_toolbar=False, update_streamlit=True
                )
            
            with col_sig_b:
                st.caption("Signature Intervenant")
                canvas_inter = st_canvas(
                    stroke_width=2, stroke_color="#000", background_color="#F0F2F6",
                    height=100, key="sig_inter", display_toolbar=False, update_streamlit=True
                )
            
            submitted = st.form_submit_button("Ajouter au panier")
            
            if submitted and presta_choice:
                st.session_state.multi_interventions.append({
                    "client_name": client_name,
                    "client_id": client_id,
                    "nom_presta": presta_choice,
                    "id_presta": st.session_state.cached_prestas[presta_choice],
                    "date": str(date_choice),
                    "commentaire": comment,
                    "intervenant_id": user['id'],
                    "photos": photos if photos else [],
                    "canvas_client_data": canvas_client.image_data,
                    "canvas_inter_data": canvas_inter.image_data
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
            with st.spinner(f"Envoi intervention {idx+1}/{total}..."):
                
                # 1. Traitement des Photos
                list_files_notion = []
                for p in inter.get('photos', []):
                    url = api.upload_image_to_cloud(p)
                    if url:
                        list_files_notion.append({"name": p.name, "external": {"url": url}})

                # 2. Traitement Signature Client
                url_sig_client = None
                if inter.get('canvas_client_data') is not None:
                    img_c = api.convert_canvas_to_image(inter['canvas_client_data'])
                    if img_c:
                        url_sig_client = api.upload_image_to_cloud(img_c)

                # 3. Traitement Signature Intervenant
                url_sig_inter = None
                if inter.get('canvas_inter_data') is not None:
                    img_i = api.convert_canvas_to_image(inter['canvas_inter_data'])
                    if img_i:
                        url_sig_inter = api.upload_image_to_cloud(img_i)

                # 4. Construction Dynamique des Propriétés (Sécurité Notion)
                props = {
                    "Date Intervention": {"date": {"start": inter['date']}},
                    "Client": {"relation": [{"id": inter['client_id']}]},
                    "Lien Prestation": {"relation": [{"id": inter['id_presta']}]},
                    "Commentaire": {"rich_text": [{"text": {"content": inter['commentaire']}}]},
                    "Intervenants": {"relation": [{"id": inter['intervenant_id']}]}
                }

                # On ajoute les colonnes médias SEULEMENT si elles contiennent des données
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
                
                res = api.create_intervention_page(payload)
                if res.status_code == 200 or res.status_code == 201:
                    success_count += 1
                
                progress_bar.progress((idx + 1) / total)
        
        if success_count == total:
            st.success("Toutes les interventions ont été enregistrées !")
            st.session_state.multi_interventions = []
            st.balloons()
            st.rerun()
        else:
            st.warning(f"Attention : seulement {success_count}/{total} enregistrements réussis. Vérifiez votre terminal.")
else:
    if not client_name:
        st.info("Sélectionnez un client pour commencer.")