import streamlit as st
import websocket
import json
import threading
import time
from datetime import datetime
from pycognito import Cognito

# Configuration
USER_POOL_ID = 'us-east-1_bhnUjqcnZ'
CLIENT_ID = 'hk80qfivncg6ome7995htvhi9'
REGION = 'us-east-1'
WS_API_URL = "wss://d0j1b57ppi.execute-api.us-east-1.amazonaws.com/prod"

class WebSocketClient:
    def __init__(self):
        self.ws = None
        self.messages = []
        
    def on_message(self, ws, message):
        try:
            msg = json.loads(message)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.messages.append({"time": timestamp, "content": msg, "type": "received"})
            print(f"Message received: {msg}")
        except json.JSONDecodeError:
            print(f"Failed to parse message: {message}")
    
    def on_error(self, ws, error):
        print(f"Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed")
        
    def on_open(self, ws):
        print("WebSocket opened")
    
    def connect(self, url=WS_API_URL):
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
    
    def disconnect(self):
        if self.ws is not None:
            self.ws.close()
            self.ws = None
    
    def send_message(self, message):
        if self.ws is not None and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(message))
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.messages.append({"time": timestamp, "content": message, "type": "sent"})

def init_session_state():
    session_vars = {
        'authenticated': False,
        'token': None,
        'username': None,
        'page': 'auth',  # Add page state tracking
        'confirmation_required': False,
        'temp_username': None
    }
    
    for var, default in session_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default
            
    if 'client' not in st.session_state:
        st.session_state['client'] = WebSocketClient()

def reset_session_state():
    if 'client' in st.session_state:
        st.session_state.client.disconnect()
    st.session_state['authenticated'] = False
    st.session_state['token'] = None
    st.session_state['username'] = None
    st.session_state['page'] = 'auth'  # Reset to auth page

def authenticate_user(username, password):
    try:
        u = Cognito(USER_POOL_ID, CLIENT_ID, username=username)
        u.authenticate(password=password)
        return True, u.id_token
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return False, None

def register_user(username, password):
    try:
        u = Cognito(USER_POOL_ID, CLIENT_ID)
        u.set_base_attributes(email=username)
        u.register(username, password)
        return True
    except Exception as e:
        st.error(f"Registration failed: {str(e)}")
        return False

def confirm_user(username, confirmation_code):
    try:
        u = Cognito(USER_POOL_ID, CLIENT_ID, username=username)
        u.confirm_sign_up(confirmation_code)
        st.success("Confirmation successful! You can now log in.")
        return True
    except Exception as e:
        st.error(f"Confirmation failed: {str(e)}")
        return False

def auth_page():
    # Clear any existing content
    st.empty()
    
    st.title("Chat with YWR Intelligence")
    
    auth_mode = st.radio("Select Option", ['Login', 'Register'])

    if auth_mode == 'Login':
        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                success, token = authenticate_user(username, password)
                if success:
                    st.session_state['authenticated'] = True
                    st.session_state['token'] = token
                    st.session_state['username'] = username
                    st.session_state['page'] = 'chat'  # Set page to chat
                    st.session_state.client.connect()
                    st.success("Login successful!")
                    st.rerun()
    
    elif auth_mode == 'Register':
        st.subheader("Register")
        username = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            if register_user(username, password):
                st.success("Registration successful! Please check your email for the confirmation code.")
                st.session_state['confirmation_required'] = True
                st.session_state['temp_username'] = username
                
        if st.session_state.get('confirmation_required', False):
            st.subheader("Confirm Your Account")
            confirmation_code = st.text_input("Enter the confirmation code sent to your email")
            if st.button("Confirm"):
                if confirm_user(st.session_state['temp_username'], confirmation_code):
                    st.session_state['confirmation_required'] = False
                    st.session_state['temp_username'] = None
                    st.rerun()

def chat_page():
    # Clear any existing content
    st.empty()
    
    st.title("YWR Intelligence")
    
   # Initialize prompt in session state if not present
    if 'prompt' not in st.session_state:
        st.session_state.prompt = ""
    
    # Sidebar with user info and logout
    with st.sidebar:
        st.text(f"Logged in as: {st.session_state['username']}")
        
        if st.button("Logout"):
            reset_session_state()
            st.rerun()
        
        if st.button("Clear History"):
            st.session_state.client.messages = []
            st.rerun()
    
    # Message input
    with st.form(key='message_form', clear_on_submit=True):
        prompt = st.text_area("Enter your query", height=90, value=st.session_state.prompt, key="prompt_input")
        submit = st.form_submit_button("Send")
        if submit and prompt:
            st.session_state.client.send_message({
                "action": "sendmessage",
                "prompt": prompt.strip()
            })
    
    # Display messages
    message_container = st.container()
    with message_container:
        for msg in reversed(st.session_state.client.messages):
            if msg["type"] == "sent":
                st.info(f"You: {msg['content']['prompt']}")
            else:
                st.success(f"Assistant: {msg['content'].get('answer', '')}")

    # Auto-refresh for new messages
    if st.session_state.client.messages:
        time.sleep(0.5)
        st.rerun()

def main():
    st.set_page_config(layout="wide")
    init_session_state()
    
    # Clear the entire page before rendering
    st.empty()
    
    # Route to appropriate page based on state
    if not st.session_state['authenticated']:
        auth_page()
    else:
        chat_page()

if __name__ == "__main__":
    main()