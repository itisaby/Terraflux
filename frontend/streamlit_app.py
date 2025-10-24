"""
Streamlit Frontend for Infrastructure Provisioning Agent
Modern web interface for conversational infrastructure management
"""
import streamlit as st
import requests
import json
import uuid
from datetime import datetime
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="Infrastructure Provisioning Agent",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left-color: #2196f3;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left-color: #4caf50;
    }
    .error-message {
        background-color: #ffebee;
        border-left-color: #f44336;
    }
    .cost-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        background-color: #4caf50;
        color: white;
        border-radius: 1rem;
        font-weight: bold;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .status-pending { background-color: #ff9800; color: white; }
    .status-executing { background-color: #2196f3; color: white; }
    .status-completed { background-color: #4caf50; color: white; }
    .status-failed { background-color: #f44336; color: white; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if 'pending_action' not in st.session_state:
    st.session_state.pending_action = None

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def authenticate(username: str, password: str) -> Dict[str, Any]:
    """Authenticate user and get token"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

def send_message(message: str) -> Dict[str, Any]:
    """Send message to the agent"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "user_id": st.session_state.user_id,
                "session_id": st.session_state.session_id
            }
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"response": f"Error: {response.text}", "requires_confirmation": False}
    except Exception as e:
        return {"response": f"Connection error: {e}", "requires_confirmation": False}

def confirm_action(action_id: str) -> Dict[str, Any]:
    """Confirm and execute infrastructure action"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/confirm-action",
            params={"action_id": action_id, "user_id": st.session_state.user_id}
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "result": {"error": response.text}}
    except Exception as e:
        return {"status": "error", "result": {"error": str(e)}}

def render_chat_message(role: str, content: str, metadata: Dict = None):
    """Render a chat message"""
    if role == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <strong>You:</strong><br/>
            {content}
        </div>
        """, unsafe_allow_html=True)
    elif role == "assistant":
        st.markdown(f"""
        <div class="chat-message assistant-message">
            <strong>🤖 Agent:</strong><br/>
            {content.replace(chr(10), '<br/>')}
        </div>
        """, unsafe_allow_html=True)

        if metadata and metadata.get('estimated_cost'):
            st.markdown(f"""
            <span class="cost-badge">
                💰 Estimated: ${metadata['estimated_cost']:.2f}/month
            </span>
            """, unsafe_allow_html=True)
    elif role == "error":
        st.markdown(f"""
        <div class="chat-message error-message">
            <strong>❌ Error:</strong><br/>
            {content}
        </div>
        """, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🏗️ Infrastructure Agent")
    st.markdown("---")

    # Authentication Section
    if not st.session_state.authenticated:
        st.markdown("### 🔐 Login")
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="admin123")

        if st.button("Login", type="primary"):
            with st.spinner("Authenticating..."):
                auth_result = authenticate(username, password)
                if auth_result:
                    st.session_state.authenticated = True
                    st.session_state.user_id = auth_result.get('user_id', username)
                    st.session_state.access_token = auth_result.get('access_token')
                    st.success("✅ Logged in successfully!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
    else:
        st.success(f"✅ Logged in as: {st.session_state.user_id}")

        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.messages = []
            st.rerun()

    st.markdown("---")

    # AWS Credentials Section (if authenticated)
    if st.session_state.authenticated:
        st.markdown("### ☁️ AWS Credentials")

        with st.expander("Configure AWS"):
            aws_access_key = st.text_input("AWS Access Key", type="password")
            aws_secret_key = st.text_input("AWS Secret Key", type="password")
            aws_region = st.selectbox(
                "Default Region",
                ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
            )

            if st.button("Save Credentials"):
                with st.spinner("Saving credentials..."):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/credentials/store",
                            json={
                                "user_id": st.session_state.user_id,
                                "provider": "aws",
                                "credentials": {
                                    "aws_access_key": aws_access_key,
                                    "aws_secret_key": aws_secret_key
                                },
                                "region": aws_region
                            }
                        )
                        if response.status_code == 200:
                            st.success("✅ Credentials saved!")
                        else:
                            st.error(f"❌ Error: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

        st.markdown("---")

    # Quick Actions
    if st.session_state.authenticated:
        st.markdown("### ⚡ Quick Actions")

        if st.button("📋 List Resources"):
            message = "Show me all my resources"
            st.session_state.messages.append({"role": "user", "content": message})
            response = send_message(message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

        if st.button("💰 Show Costs"):
            message = "Show me a cost breakdown"
            st.session_state.messages.append({"role": "user", "content": message})
            response = send_message(message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

        if st.button("❓ Help"):
            message = "help"
            st.session_state.messages.append({"role": "user", "content": message})
            response = send_message(message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response']
            })
            st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Session Info")
    st.caption(f"Session: {st.session_state.session_id[:8]}...")
    st.caption(f"Messages: {len(st.session_state.messages)}")

# Main content
st.markdown('<div class="main-header">🏗️ Infrastructure Provisioning Agent</div>', unsafe_allow_html=True)

if not st.session_state.authenticated:
    st.info("👈 Please login using the sidebar to get started")
    st.markdown("---")
    st.markdown("""
    ### Welcome to the Infrastructure Provisioning Agent!

    This AI-powered agent helps you provision and manage cloud infrastructure using natural language.

    **Features:**
    - 🗣️ Natural language interface
    - 🔒 Secure credential management
    - 🏗️ Terraform-backed provisioning
    - 💰 Cost estimation
    - 📊 Resource tracking

    **Example commands:**
    - "Create a VM in AWS"
    - "Deploy a database in us-west-2"
    - "Show me my resources"
    - "What's my infrastructure costing?"

    Get started by logging in with your credentials!
    """)
else:
    # Chat interface
    chat_container = st.container()

    with chat_container:
        # Display chat history
        for message in st.session_state.messages:
            render_chat_message(
                message["role"],
                message["content"],
                message.get("metadata")
            )

            # Handle pending confirmation
            if message.get("metadata", {}).get("requires_confirmation"):
                if st.session_state.pending_action == message["metadata"].get("action_id"):
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("✅ Confirm", key=f"confirm_{message['metadata']['action_id']}"):
                            with st.spinner("Provisioning infrastructure..."):
                                result = confirm_action(message["metadata"]["action_id"])
                                if result['status'] == 'success':
                                    st.session_state.messages.append({
                                        "role": "assistant",
                                        "content": result['result'].get('message', 'Infrastructure provisioned successfully!')
                                    })
                                    st.session_state.pending_action = None
                                    st.rerun()
                                else:
                                    st.session_state.messages.append({
                                        "role": "error",
                                        "content": f"Provisioning failed: {result['result'].get('error', 'Unknown error')}"
                                    })
                                    st.session_state.pending_action = None
                                    st.rerun()
                    with col2:
                        if st.button("❌ Cancel", key=f"cancel_{message['metadata']['action_id']}"):
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": "Action cancelled."
                            })
                            st.session_state.pending_action = None
                            st.rerun()
                else:
                    # Store pending action
                    st.session_state.pending_action = message["metadata"].get("action_id")

    # Chat input
    st.markdown("---")

    # Example prompts
    st.markdown("**💡 Try these:**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🖥️ Create VM"):
            user_message = "Create a VM in AWS"
            st.session_state.messages.append({"role": "user", "content": user_message})
            response = send_message(user_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

    with col2:
        if st.button("💾 Create Database"):
            user_message = "Create a MySQL database"
            st.session_state.messages.append({"role": "user", "content": user_message})
            response = send_message(user_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

    with col3:
        if st.button("🗂️ Create S3 Bucket"):
            user_message = "Create an S3 bucket"
            st.session_state.messages.append({"role": "user", "content": user_message})
            response = send_message(user_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

    with col4:
        if st.button("⚖️ Create Load Balancer"):
            user_message = "Create a load balancer"
            st.session_state.messages.append({"role": "user", "content": user_message})
            response = send_message(user_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response['response'],
                "metadata": response
            })
            st.rerun()

    # Text input
    user_input = st.chat_input("Ask me to provision infrastructure... (e.g., 'Create a VM in AWS')")

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Get agent response
        with st.spinner("🤖 Processing your request..."):
            response = send_message(user_input)

        # Add assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": response['response'],
            "metadata": response
        })

        st.rerun()

    # Clear chat button
    if st.session_state.messages:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.pending_action = None
            st.rerun()
