import streamlit as st
import requests
import json
import uuid
import time
import websocket

# -- CONFIG --
BASE_URL = "http://localhost/api/v1"
WS_URL = "ws://localhost/api/v1/chat/ws"

st.set_page_config(page_title="CS AI Frontend Simulator", layout="wide")

# -- SESSION STATE --
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid.uuid4())
if "ws" not in st.session_state:
    st.session_state["ws"] = None

def get_headers():
    if st.session_state["token"]:
        return {"Authorization": f"Bearer {st.session_state['token']}"}
    return {}

# -- UTILS --
def init_websocket():
    if st.session_state["ws"] is None:
        try:
            url = f"{WS_URL}/{st.session_state['conversation_id']}"
            ws = websocket.create_connection(url)
            ws.settimeout(1.0)
            st.session_state["ws"] = ws
            return True
        except Exception as e:
            st.error(f"WebSocket Connection Failed: {e}")
            return False
    return True

def close_websocket():
    if st.session_state["ws"]:
        st.session_state["ws"].close()
        st.session_state["ws"] = None

# -- VIEWS --
def view_login():
    st.header("Login 🔐")
    email = st.text_input("Email", value="superadmin@example.com")
    password = st.text_input("Password", type="password", value="supersecret")
    
    if st.button("Login"):
        res = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
        if res.status_code == 200:
            data = res.json()["data"]
            token = data["access_token"]
            st.session_state["token"] = token
            
            # Fetch user profile using the new token
            me_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
            if me_res.status_code == 200:
                st.session_state["user"] = me_res.json()["data"]
            else:
                st.session_state["user"] = {"name": email} # Fallback
                
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error(f"Login failed: {res.text}")

def view_chat_simulator():
    st.header("Customer Chat Simulator 💬")
    st.write(f"**Conversation ID:** `{st.session_state['conversation_id']}`")
    
    if st.button("New Conversation"):
        close_websocket()
        st.session_state["conversation_id"] = str(uuid.uuid4())
        st.session_state["chat_messages"] = []
        st.rerun()
        
    connected = init_websocket()
    if not connected:
        return
        
    # Read pending messages from WS
    try:
        while True:
            msg = st.session_state["ws"].recv()
            st.session_state["chat_messages"].append({"role": "assistant", "content": msg})
    except websocket.WebSocketTimeoutException:
        pass
    except Exception as e:
        st.error(f"WS Error: {e}")
        close_websocket()
        
    # Render messages
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Chat Input
    if prompt := st.chat_input("Type your message..."):
        # Display user msg
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        # Send via WS
        try:
            st.session_state["ws"].send(prompt)
            # Wait for response
            with st.spinner("AI is thinking..."):
                time.sleep(1) # wait a bit for processing
                st.session_state["ws"].settimeout(30.0) # wait longer for AI
                while True:
                    ai_resp = st.session_state["ws"].recv()
                    st.session_state["chat_messages"].append({"role": "assistant", "content": ai_resp})
                    with st.chat_message("assistant"):
                        st.write(ai_resp)
                    break # exit loop after one response (simple simulation)
        except websocket.WebSocketTimeoutException:
            st.warning("AI took too long to respond.")
        finally:
            st.session_state["ws"].settimeout(1.0) # reset timeout
            st.rerun()

def view_inbox():
    st.header("Agent Inbox / Conversations 📥")
    if not st.session_state["token"]:
        st.warning("Please login first.")
        return
        
    res = requests.get(f"{BASE_URL}/conversations?limit=10", headers=get_headers())
    if res.status_code == 200:
        conversations = res.json()
        if not conversations:
            st.info("No conversations found.")
            return
            
        for conv in conversations:
            with st.expander(f"Conversation {conv['id'][:8]}... - Status: {conv['status']}"):
                st.write(f"**Customer ID:** {conv['anonymous_customer_id']}")
                st.write(f"**Created At:** {conv.get('created_at', 'N/A')}")
                if st.button("Load Messages", key=f"btn_{conv['id']}"):
                    msg_res = requests.get(f"{BASE_URL}/conversations/{conv['id']}/messages", headers=get_headers())
                    if msg_res.status_code == 200:
                        msgs = msg_res.json()
                        for m in msgs:
                            role = "user" if m["sender_type"] == "customer" else "assistant"
                            st.markdown(f"**{role}**: {m['content']}")
    else:
        st.error("Failed to load conversations.")

def view_config():
    st.header("System Config & Persona ⚙️")
    if not st.session_state["token"]:
        st.warning("Please login first.")
        return
        
    tab1, tab2 = st.tabs(["Persona Settings", "System Settings"])
    
    with tab1:
        res_persona = requests.get(f"{BASE_URL}/config/persona", headers=get_headers())
        if res_persona.status_code == 200:
            persona_data = res_persona.json()["data"] or {}
            
            with st.form("persona_form"):
                persona_name = st.text_input("Persona Name", value=persona_data.get("persona_name", ""))
                tone_of_voice = st.text_input("Tone of Voice", value=persona_data.get("tone_of_voice", ""))
                persona_rules = st.text_area("Persona Rules", value=persona_data.get("rules", ""), height=200)
                out_of_context = st.text_input("Out of Context Message", value=persona_data.get("out_of_context_message", ""))
                
                if st.form_submit_button("Save Persona"):
                    payload = {
                        "persona_name": persona_name,
                        "tone_of_voice": tone_of_voice,
                        "rules": persona_rules,
                        "out_of_context_message": out_of_context
                    }
                    update_res = requests.put(f"{BASE_URL}/config/persona", json=payload, headers=get_headers())
                    if update_res.status_code == 200:
                        st.success("Persona updated successfully!")
                    else:
                        st.error(f"Failed to update persona: {update_res.text}")
        else:
            st.error("Failed to load persona.")
            
    with tab2:
        res_system = requests.get(f"{BASE_URL}/config/system", headers=get_headers())
        if res_system.status_code == 200:
            system_data = res_system.json()["data"] or {}
            
            with st.form("system_form"):
                shopify_domain = st.text_input("Shopify Domain (e.g. my-store.myshopify.com)", value=system_data.get("shopify_domain", ""))
                admin_token = st.text_input("Shopify Admin API Token", type="password", help="Leave blank to keep existing token. Showing masked token: " + system_data.get("admin_api_token_masked", ""))
                webhook_secret = st.text_input("Shopify Webhook Secret", type="password", help="Leave blank to keep existing. Showing: " + system_data.get("webhook_secret_masked", ""))
                
                if st.form_submit_button("Save System Settings"):
                    payload = {"shopify_domain": shopify_domain}
                    
                    if admin_token:
                        payload["admin_api_token"] = admin_token
                        
                    if webhook_secret:
                        payload["webhook_secret"] = webhook_secret
                        
                    update_res = requests.put(f"{BASE_URL}/config/system", json=payload, headers=get_headers())
                    if update_res.status_code == 200:
                        st.success("System configuration updated successfully!")
                    else:
                        st.error(f"Failed to update system config: {update_res.text}")
        else:
            st.error("Failed to load system config.")

def view_kb():
    st.header("Knowledge Base 📚")
    if not st.session_state["token"]:
        st.warning("Please login first.")
        return
        
    tab1, tab2 = st.tabs(["View Documents", "Upload Document"])
    
    with tab1:
        res = requests.get(f"{BASE_URL}/kb/documents", headers=get_headers())
        if res.status_code == 200:
            docs = res.json()  # API returns a direct list, not wrapped in "data"
            if not docs:
                st.info("No documents in Knowledge Base.")
            else:
                for doc in docs:
                    with st.expander(f"📄 {doc['title']} ({doc.get('embedding_status', 'unknown')})"):
                        st.write(f"**ID:** {doc['id']}")
                        st.write(f"**Status:** {doc.get('embedding_status', 'N/A')}")
                        st.write(f"**Created At:** {doc.get('created_at', 'N/A')}")
                        if st.button("Delete", key=f"del_{doc['id']}"):
                            requests.delete(f"{BASE_URL}/kb/documents/{doc['id']}", headers=get_headers())
                            st.rerun()
                            
    with tab2:
        with st.form("kb_upload"):
            title = st.text_input("Title")
            content = st.text_area("Content")
            if st.form_submit_button("Upload"):
                payload = {"title": title, "content": content}
                res = requests.post(f"{BASE_URL}/kb/documents", json=payload, headers=get_headers())
                if res.status_code in [200, 201]:
                    st.success("Document added!")
                else:
                    st.error(f"Failed to add document: {res.text}")

def view_products():
    st.header("Products 🛍️")
    if not st.session_state["token"]:
        st.warning("Please login first.")
        return
        
    res = requests.get(f"{BASE_URL}/products?limit=50", headers=get_headers())
    if res.status_code == 200:
        products = res.json()["data"]
        if not products:
            st.info("No products found.")
        else:
            cols = st.columns(3)
            for i, prod in enumerate(products):
                with cols[i % 3]:
                    if prod.get('image_url'):
                        st.image(prod['image_url'], use_container_width=True)
                    st.subheader(prod.get("title", "Unknown Product"))
                    st.write(f"**Type:** {prod.get('product_type', 'N/A')}")
                    st.write(f"**Vendor:** {prod.get('vendor', 'N/A')}")
                    st.write(f"**Status:** {prod.get('embedding_status', 'N/A')}")
    else:
        st.error("Failed to load products.")

# -- MAIN APP ROUTING --
def main():
    st.sidebar.title("Navigation")
    
    # Navigation menu
    menu = ["Login / Auth", "Customer Chat Simulator", "Agent Inbox", "System Config", "Knowledge Base", "Products"]
    choice = st.sidebar.radio("Go to", menu)
    
    if st.session_state["user"]:
        st.sidebar.success(f"Logged in as: {st.session_state['user']['name']}")
        if st.sidebar.button("Logout"):
            st.session_state["token"] = None
            st.session_state["user"] = None
            close_websocket()
            st.rerun()
            
    if choice == "Login / Auth":
        view_login()
    elif choice == "Customer Chat Simulator":
        view_chat_simulator()
    elif choice == "Agent Inbox":
        view_inbox()
    elif choice == "System Config":
        view_config()
    elif choice == "Knowledge Base":
        view_kb()
    elif choice == "Products":
        view_products()

if __name__ == "__main__":
    main()
