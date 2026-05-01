import streamlit as st
import os
import record_inter as api
from datetime import datetime
try:
    from streamlit_canvas import st_canvas
except ImportError:
    from streamlit_drawable_canvas import st_canvas
import numpy as np
from PIL import Image
import io

# 1. Configurer la page
st.set_page_config(page_title="Gestion Interventions", layout="centered")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; margin-top: 10px; }
    .hist-card {
        padding: 1rem;
        border-left: 5px solid #01579b;
        background-color: #f8f9fa;
        border-radius: 5px;
        margin-bottom: 5px;
    }
    .client-tag {
        background-color: #e1f5fe;
        color: #01579b;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .panier-item {
        padding: 10px;
        background-color: #ffffff;
        border: 1px solid #eee;
        border-radius: 8px;
        margin-bottom: 10px;
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

# --- MODAL D'ÉDITION ---
@st.dialog("📝 Modifier l'intervention", width="large")
def edit_modal(page_id, current_date, current_comment):
    try:
        val_date = datetime.strptime(current_date, "%Y-%m-%d")
    except:
        val_date = datetime.now()
        
    new_date = st.date_input("Date Intervention", value=val_date)
    new_comment = st.text_area("Commentaire", value=current_comment)
    new_photos = st.file_uploader("📸 Remplacer les photos", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    
    st.write("✍️ **Signatures**")
    col_sig_a, col_sig_b = st.columns(2)
    with col_sig_a:
        canvas_c = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=120, key=f"edit_c_{page_id}")
    with col_sig_b:
        canvas_i = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=120, key=f"edit_i_{page_id}")

    # --- BOUTONS ACTIONS ---
    st.write("---") # Séparateur visuel
    col_btn_save, col_btn_cancel = st.columns(2)
    
    with col_btn_save:
        if st.button("🚀 Enregistrer les modifications", type="primary", use_container_width=True):
            with st.spinner("Mise à jour..."):
                props = {
                    "Date Intervention": {"date": {"start": str(new_date)}},
                    "Commentaire": {"rich_text": [{"text": {"content": new_comment}}]}
                }
                if new_photos:
                    list_files = []
                    for p in new_photos:
                        url = api.upload_image_to_cloud(p)
                        if url: list_files.append({"name": p.name, "external": {"url": url}})
                    props["Preuves"] = {"files": list_files}
                
                if canvas_c.image_data is not None and np.any(canvas_c.image_data[:, :, 3] > 0):
                    img_c = api.convert_canvas_to_image(canvas_c.image_data)
                    url_c = api.upload_image_to_cloud(img_c)
                    if url_c: props["Signature Client"] = {"files": [{"name": "sc.png", "external": {"url": url_c}}]}

                if canvas_i.image_data is not None and np.any(canvas_i.image_data[:, :, 3] > 0):
                    img_i = api.convert_canvas_to_image(canvas_i.image_data)
                    url_i = api.upload_image_to_cloud(img_i)
                    if url_i: props["Signature Intervenant"] = {"files": [{"name": "si.png", "external": {"url": url_i}}]}

                if api.update_intervention(page_id, props):
                    st.success("Modifié !")
                    st.rerun()

    with col_btn_cancel:
        # Un simple st.rerun() ferme le modal car l'état du bouton d'édition sera réinitialisé
        if st.button("❌ Annuler", use_container_width=True):
            st.rerun()

@st.dialog("🚀 Opération réussie !")
def show_success_modal(count):
    st.balloons()
    st.success(f"Félicitations ! {count} intervention(s) ont été enregistrées avec succès dans Notion.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Nouvelle saisie"):
            st.session_state.canvas_key += 1 # Reset les canvas
            st.rerun()
    with col2:
        if st.button("📋 Voir l'historique"):
            st.session_state.page = "historique"
            st.rerun()

# --- CONNEXION ---
if st.session_state.user is None:
    st.title("🔐 Connexion")
    with st.form("login"):
        email = st.text_input("Email")
        pin = st.text_input("PIN", type="password")
        if st.form_submit_button("Se connecter"):
            u = api.login_user(email, pin)
            if u: st.session_state.user = u; st.rerun()
    st.stop()

# --- NAVIGATION ---
user = st.session_state.user
c1, c2 = st.columns([4, 1])
with c1: st.write(f"👤 **{user['name']}**")
with c2: 
    if st.button("🚪"): st.session_state.user = None; st.rerun()

st.divider()
n1, n2, _ = st.columns([1,1,2])
if n1.button("🏠 Saisie"): st.session_state.page = "saisie"; st.rerun()
if n2.button("📋 Historique"): st.session_state.page = "historique"; st.rerun()

# --- PAGE HISTORIQUE ---
if st.session_state.page == "historique":
    st.title("📋 Historique")
    history = api.get_interventions_history(user)
    if not history: st.info("Vide.")
    else:
        for res in history:
            pid = res.get('id')
            p = res.get('properties', {})
            d_val = p.get('Date Intervention', {}).get('date', {}).get('start', "")
            
            # Logique originale pour les noms
            cl_r = p.get('Client Nom', {}).get('rollup', {}).get('array', [])
            cl_name = cl_r[0].get('title', [{}])[0].get('plain_text', "Client") if cl_r else "Client"
            
            pr_r = p.get('Prestation Titre', {}).get('rollup', {}).get('array', [])
            pr_name = pr_r[0].get('title', [{}])[0].get('plain_text', "Prestation") if pr_r else "Prestation"
            
            c_rich = p.get('Commentaire', {}).get('rich_text', [])
            c_val = c_rich[0].get('plain_text', "") if c_rich else ""

            st.markdown(f'<div class="hist-card"><span class="client-tag">{cl_name}</span><br><strong>{pr_name}</strong> | {d_val}</div>', unsafe_allow_html=True)
            col_e, col_d, _ = st.columns([1, 1, 2])
            if col_e.button("📝", key=f"e_{pid}"): edit_modal(pid, d_val, c_val)
            if col_d.button("🗑️", key=f"d_{pid}"): 
                if api.delete_intervention(pid): st.rerun()
            st.divider()

# --- PAGE SAISIE ---
else:
    st.title("🛠 Saisie")
    all_clients = api.get_all_clients(user_data=user)
    c_name = st.selectbox("Client", options=[""] + list(all_clients.keys()))

    if c_name:
        cl_id = all_clients[c_name]
        prestas = api.get_prestations_for_client(cl_id)
        
        with st.expander("Détails de l'intervention", expanded=True):
            p_choice = st.selectbox("Prestation", options=list(prestas.keys()))
            d_choice = st.date_input("Date", value=datetime.now())
            comment = st.text_area("Commentaire")
            files = st.file_uploader("Photos", type=['png','jpg','jpeg'], accept_multiple_files=True)
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.caption("Signature Client")
                cv_c = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=120, key=f"c_{st.session_state.canvas_key}")
            with col_b:
                st.caption("Signature Intervenant")
                cv_i = st_canvas(stroke_width=2, stroke_color="#000", background_color="#F0F2F6", height=120, key=f"i_{st.session_state.canvas_key}")

            if st.button("➕ Ajouter au panier", type="primary"):
                st.session_state.multi_interventions.append({
                    "client_name": c_name, "client_id": cl_id,
                    "nom_presta": p_choice, "id_presta": prestas[p_choice],
                    "date": str(d_choice), "commentaire": comment, "intervenant_id": user['id'],
                    "photos": files if files else [],
                    "canvas_client_data": cv_c.image_data,
                    "canvas_inter_data": cv_i.image_data
                })
                st.session_state.canvas_key += 1
                st.rerun()

    
       # --- SECTION PANIER AVEC SUPPRESSION ---
    if st.session_state.multi_interventions:
        st.divider()
        st.subheader(f"🛒 Panier ({len(st.session_state.multi_interventions)})")
        
        for index, item in enumerate(st.session_state.multi_interventions):
            # On crée un container avec une bordure légère pour chaque intervention
            with st.container(border=True):
                col_info, col_del = st.columns([5, 1])
                
                with col_info:
                    # Ligne 1 : Titre de la prestation et Client
                    st.markdown(f"### {item['nom_presta']}")
                    
                    # Ligne 2 : Badge Client et Date
                    st.markdown(f"**👤 Client :** {item['client_name']} | **📅 Date :** {item['date']}")
                    
                    # Ligne 3 : Commentaire (si existant)
                    if item['commentaire']:
                        st.markdown(f"*💬 {item['commentaire']}*")
                    else:
                        st.caption("Aucun commentaire ajouté.")
                
                with col_del:
                    # Centrage vertical du bouton de suppression
                    st.write("##") # Petit espace pour aligner le bouton au milieu
                    if st.button("🗑️", key=f"del_cart_{index}", help="Retirer cette intervention"):
                        st.session_state.multi_interventions.pop(index)
                        st.rerun()
        
        if st.button("🚀 TOUT ENREGISTRER", type="primary", use_container_width=True):
            conf = api.get_notion_config()
            for inter in st.session_state.multi_interventions:
                ph_list = []
                for f in inter['photos']:
                    u = api.upload_image_to_cloud(f)
                    if u: ph_list.append({"name": f.name, "external": {"url": u}})
                
                u_c = api.upload_image_to_cloud(api.convert_canvas_to_image(inter['canvas_client_data']))
                u_i = api.upload_image_to_cloud(api.convert_canvas_to_image(inter['canvas_inter_data']))
                
                props = {
                    "Date Intervention": {"date": {"start": inter['date']}},
                    "Client": {"relation": [{"id": inter['client_id']}]},
                    "Lien Prestation": {"relation": [{"id": inter['id_presta']}]},
                    "Commentaire": {"rich_text": [{"text": {"content": inter['commentaire']}}]},
                    "Intervenants": {"relation": [{"id": inter['intervenant_id']}]}
                }
                if ph_list: props["Preuves"] = {"files": ph_list}
                if u_c: props["Signature Client"] = {"files": [{"name": "sc.png", "external": {"url": u_c}}]}
                if u_i: props["Signature Intervenant"] = {"files": [{"name": "si.png", "external": {"url": u_i}}]}
                
                api.create_intervention_page({"parent": {"database_id": conf['db_interventions']}, "properties": props})
            
            count = len(st.session_state.multi_interventions)
            st.session_state.multi_interventions = []
            show_success_modal(count)