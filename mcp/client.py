"""
MCP Client Implementation
Handles communication with MCP servers for infrastructure operations
"""
import json
import asyncio
import websockets
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response" 
    NOTIFICATION = "notification"
    ERROR = "error"

@dataclass
class MCPMessage:
    """MCP protocol message structure"""
    id: str
    type: MessageType
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class MCPClient:
    """
    MCP Client for communicating with Terraform MCP Server
    Handles tool calls, server discovery, and error handling
    """
    
    def __init__(self, server_url: str = "ws://localhost:8001/mcp"):
        self.server_url = server_url
        self.websocket = None
        self.available_tools = {}
        self.pending_requests = {}
        self.is_connected = False
        
    async def connect(self):
        """Establish connection to MCP server"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            
            # Initialize connection and discover tools
            await self._initialize_session()
            await self._discover_tools()
            
            logging.info(f"Connected to MCP server at {self.server_url}")
            
        except Exception as e:
            logging.error(f"Failed to connect to MCP server: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Close connection to MCP server"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logging.info("Disconnected from MCP server")
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters to pass to the tool
            
        Returns:
            Tool execution result
        """
        if not self.is_connected:
            await self.connect()
        
        if tool_name not in self.available_tools:
            raise ValueError(f"Tool '{tool_name}' not available. Available tools: {list(self.available_tools.keys())}")
        
        # Create request message
        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            type=MessageType.REQUEST,
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": parameters
            }
        )
        
        try:
            # Send request
            await self._send_message(message)
            
            # Wait for response
            response = await self._wait_for_response(request_id, timeout=60)
            
            if response.error:
                raise Exception(f"Tool call failed: {response.error}")
            
            return response.result
            
        except asyncio.TimeoutError:
            raise Exception(f"Tool call '{tool_name}' timed out")
        except Exception as e:
            logging.error(f"Error calling tool '{tool_name}': {e}")
            raise
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from server"""
        return list(self.available_tools.values())
    
    async def _initialize_session(self):
        """Initialize MCP session with handshake"""
        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            type=MessageType.REQUEST,
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "infrastructure-agent",
                    "version": "1.0.0"
                }
            }
        )
        
        await self._send_message(message)
        response = await self._wait_for_response(request_id)
        
        if response.error:
            raise Exception(f"Failed to initialize session: {response.error}")
        
        logging.info("MCP session initialized successfully")
    
    async def _discover_tools(self):
        """Discover available tools from the server"""
        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            type=MessageType.REQUEST,
            method="tools/list",
            params={}
        )
        
        await self._send_message(message)
        response = await self._wait_for_response(request_id)
        
        if response.error:
            raise Exception(f"Failed to discover tools: {response.error}")
        
        # Store available tools
        tools = response.result.get("tools", [])
        self.available_tools = {tool["name"]: tool for tool in tools}
        
        logging.info(f"Discovered {len(self.available_tools)} tools: {list(self.available_tools.keys())}")
    
    async def _send_message(self, message: MCPMessage):
        """Send message to MCP server"""
        if not self.websocket:
            raise Exception("Not connected to MCP server")
        
        message_data = {k: v for k, v in asdict(message).items() if v is not None}
        
        # Convert enum to string
        if message_data.get("type"):
            message_data["type"] = message_data["type"].value
        
        await self.websocket.send(json.dumps(message_data))
        logging.debug(f"Sent message: {message_data}")
    
    async def _wait_for_response(self, request_id: str, timeout: int = 30) -> MCPMessage:
        """Wait for response to a specific request"""
        
        async def receive_messages():
            """Receive and process messages from server"""
            while True:
                try:
                    raw_message = await self.websocket.recv()
                    message_data = json.loads(raw_message)
                    
                    logging.debug(f"Received message: {message_data}")
                    
                    # Convert to MCPMessage
                    message = MCPMessage(
                        id=message_data.get("id"),
                        type=MessageType(message_data.get("type", "response")),
                        method=message_data.get("method"),
                        params=message_data.get("params"),
                        result=message_data.get("result"),
                        error=message_data.get("error")
                    )
                    
                    if message.id == request_id:
                        return message
                        
                except websockets.exceptions.ConnectionClosed:
                    raise Exception("Connection to MCP server lost")
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON received: {e}")
                    continue
        
        try:
            return await asyncio.wait_for(receive_messages(), timeout=timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"No response received for request {request_id}")

class TerraformMCPToolCaller:
    """
    High-level wrapper for Terraform-specific MCP tool calls
    Provides convenient methods for common infrastructure operations
    """
    
    def __init__(self, mcp_client: MCPClient):
        self.client = mcp_client
    
    async def plan_infrastructure(self, resources: List[Dict], region: str = "us-east-1", 
                                 environment: str = "dev", user_id: str = None) -> Dict[str, Any]:
        """Create Terraform plan for infrastructure resources"""
        return await self.client.call_tool("plan_infrastructure", {
            "resources": resources,
            "region": region,
            "environment": environment,
            "user_id": user_id
        })
    
    async def apply_infrastructure(self, plan_id: str, user_id: str) -> Dict[str, Any]:
        """Apply Terraform plan"""
        return await self.client.call_tool("apply_infrastructure", {
            "plan_id": plan_id,
            "user_id": user_id
        })
    
    async def destroy_infrastructure(self, resource_filter: str = None, 
                                   user_id: str = None) -> Dict[str, Any]:
        """Destroy infrastructure resources"""
        return await self.client.call_tool("destroy_infrastructure", {
            "resource_filter": resource_filter,
            "user_id": user_id
        })
    
    async def list_infrastructure(self, user_id: str, environment: str = None) -> Dict[str, Any]:
        """List current infrastructure resources"""
        return await self.client.call_tool("list_infrastructure", {
            "user_id": user_id,
            "environment": environment
        })
    
    async def get_terraform_state(self, user_id: str, environment: str = "dev") -> Dict[str, Any]:
        """Get current Terraform state"""
        return await self.client.call_tool("get_terraform_state", {
            "user_id": user_id,
            "environment": environment
        })
    
    async def validate_terraform_config(self, resources: List[Dict]) -> Dict[str, Any]:
        """Validate Terraform configuration before planning"""
        return await self.client.call_tool("validate_terraform_config", {
            "resources": resources
        })
    
    async def estimate_cost(self, resources: List[Dict], region: str = "us-east-1") -> Dict[str, Any]:
        """Estimate cost for infrastructure resources"""
        return await self.client.call_tool("estimate_cost", {
            "resources": resources,
            "region": region
        })

# Example usage and testing
async def test_mcp_client():
    """Test the MCP client functionality"""
    client = MCPClient()
    terraform_client = TerraformMCPToolCaller(client)
    
    try:
        # Connect to server
        await client.connect()
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool['name'] for tool in tools]}")
        
        # Test infrastructure planning
        test_resources = [
            {
                "type": "aws_instance",
                "config": {
                    "instance_type": "t3.micro",
                    "ami": "ubuntu-20.04"
                }
            }
        ]
        
        # Plan infrastructure
        plan_result = await terraform_client.plan_infrastructure(
            resources=test_resources,
            region="us-east-1",
            environment="dev",
            user_id="test-user"
        )
        
        print(f"Plan result: {plan_result}")
        
        # If planning successful, we could apply it
        if plan_result.get("success"):
            print(f"Plan ID: {plan_result['plan']['id']}")
            print(f"Resources to create: {plan_result['plan']['resources_to_create']}")
            print(f"Estimated cost: ${plan_result['plan'].get('estimated_cost', 0):.2f}")
        
    except Exception as e:
        print(f"Test failed: {e}")
    
    finally:
        await client.disconnect()

# Connection pool for managing multiple MCP connections
class MCPConnectionPool:
    """Manage multiple MCP client connections"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.available_connections = []
        self.in_use_connections = set()
    
    async def get_client(self) -> MCPClient:
        """Get an available MCP client from the pool"""
        if self.available_connections:
            client = self.available_connections.pop()
            self.in_use_connections.add(client)
            return client
        
        if len(self.in_use_connections) < self.max_connections:
            client = MCPClient()
            await client.connect()
            self.in_use_connections.add(client)
            return client
        
        raise Exception("No available MCP connections")
    
    async def return_client(self, client: MCPClient):
        """Return a client to the pool"""
        if client in self.in_use_connections:
            self.in_use_connections.remove(client)
            if client.is_connected:
                self.available_connections.append(client)
            else:
                await client.disconnect()
    
    async def close_all(self):
        """Close all connections in the pool"""
        all_clients = list(self.available_connections) + list(self.in_use_connections)
        for client in all_clients:
            await client.disconnect()
        
        self.available_connections.clear()
        self.in_use_connections.clear()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_mcp_client())