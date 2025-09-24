"""
Main Agent Orchestrator
Coordinates between intent parsing, MCP calls, and response generation
"""
from typing import Dict, Any
import uuid
from .intent_parser import IntentParser
from .response_generator import ResponseGenerator
from mcp.client import MCPClient
from security.credentials import get_user_credentials
from database.models import InfraRequest, User
import logging

class InfraAgent:
    def __init__(self):
        self.intent_parser = IntentParser()
        self.response_generator = ResponseGenerator()
        self.mcp_client = MCPClient()
        self.pending_actions = {}  # Store actions awaiting confirmation
        
    async def process_request(self, message: str, user: User, session_id: str) -> Dict[str, Any]:
        """Process a user infrastructure request"""
        try:
            # Parse the user's intent
            intent = await self.intent_parser.parse(message)
            logging.info(f"Parsed intent: {intent}")
            
            # Generate action plan
            if intent.action == "provision":
                return await self._handle_provision_request(intent, user, session_id)
            elif intent.action == "list":
                return await self._handle_list_request(intent, user)
            elif intent.action == "destroy":
                return await self._handle_destroy_request(intent, user, session_id)
            else:
                return {
                    "response": "I'm not sure how to help with that. Try asking me to create, list, or destroy infrastructure resources.",
                    "requires_confirmation": False
                }
                
        except Exception as e:
            logging.error(f"Error in process_request: {e}")
            return {
                "response": f"Sorry, I encountered an error: {str(e)}",
                "requires_confirmation": False
            }
    
    async def _handle_provision_request(self, intent, user: User, session_id: str) -> Dict[str, Any]:
        """Handle infrastructure provisioning requests"""
        # Get user credentials (securely)
        credentials = await get_user_credentials(user.id)
        
        # Call MCP server to generate Terraform plan
        plan_result = await self.mcp_client.call_tool(
            "plan_infrastructure",
            {
                "resources": intent.resources,
                "region": intent.region or "us-east-1",
                "environment": intent.environment or "dev",
                "user_id": user.id
            }
        )
        
        if plan_result.get("success"):
            # Store pending action
            action_id = str(uuid.uuid4())
            self.pending_actions[action_id] = {
                "type": "provision",
                "plan": plan_result["plan"],
                "user_id": user.id,
                "session_id": session_id
            }
            
            # Generate human-readable response
            response = self.response_generator.generate_plan_response(
                plan_result["plan"], 
                intent.resources
            )
            
            return {
                "response": response,
                "plan": plan_result["plan"],
                "requires_confirmation": True,
                "estimated_cost": plan_result.get("estimated_cost", 0),
                "action_id": action_id
            }
        else:
            return {
                "response": f"I couldn't create a plan: {plan_result.get('error', 'Unknown error')}",
                "requires_confirmation": False
            }
    
    async def execute_action(self, action_id: str, user: User) -> Dict[str, Any]:
        """Execute a confirmed action"""
        if action_id not in self.pending_actions:
            raise ValueError("Invalid or expired action ID")
        
        action = self.pending_actions[action_id]
        
        if action["user_id"] != user.id:
            raise ValueError("Unauthorized action")
        
        # Execute via MCP
        result = await self.mcp_client.call_tool(
            "apply_infrastructure",
            {
                "plan_id": action["plan"]["id"],
                "user_id": user.id
            }
        )
        
        # Clean up pending action
        del self.pending_actions[action_id]
        
        return result