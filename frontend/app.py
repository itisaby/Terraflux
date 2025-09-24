"""
Infrastructure Provisioning Agent
Main application entry point
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.main import InfraAgent
from security.auth import authenticate_user
from database.models import User, InfraRequest
import logging

app = FastAPI(title="Infrastructure Provisioning Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the agent
infra_agent = InfraAgent()

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    plan: dict = None
    requires_confirmation: bool = False
    estimated_cost: float = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint for infrastructure requests"""
    try:
        # Authenticate user
        user = await authenticate_user(request.user_id)
        
        # Process the request through the agent
        response = await infra_agent.process_request(
            message=request.message,
            user=user,
            session_id=request.session_id
        )
        
        return ChatResponse(**response)
    
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/confirm-action")
async def confirm_action(action_id: str, user_id: str):
    """Confirm and execute infrastructure changes"""
    try:
        user = await authenticate_user(user_id)
        result = await infra_agent.execute_action(action_id, user)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)