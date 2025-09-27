#!/usr/bin/env python3
"""Test the MCP wrapper with an actual MCP client."""

import asyncio
import json
import subprocess
import sys
from typing import Dict, Any

class MCPClient:
    """Simple MCP client for testing the wrapper."""
    
    def __init__(self, server_command: list):
        self.server_command = server_command
        self.process = None
    
    async def start_server(self):
        """Start the MCP server process."""
        print(f"🚀 Starting MCP server: {' '.join(self.server_command)}")
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        print("✅ MCP server started")
    
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        if not self.process:
            raise RuntimeError("Server not started")
        
        request_json = json.dumps(request) + "\n"
        print(f"📤 Sending: {request_json.strip()}")
        
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        response_json = response_line.decode().strip()
        print(f"📥 Received: {response_json}")
        
        return json.loads(response_json)
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP session."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        response = await self.send_request(request)
        
        # Send initialized notification
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self.send_request(notification)
        
        return response
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        return await self.send_request(request)
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        return await self.send_request(request)
    
    async def close(self):
        """Close the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            print("✅ MCP server closed")

async def test_mcp_wrapper():
    """Test the MCP wrapper with a real MCP client."""
    print("🧪 Testing MCP wrapper with actual MCP client...")
    print("=" * 60)
    
    # Create MCP client
    client = MCPClient([
        sys.executable, "-m", "mcp_eval_server.mcp_wrapper",
        "--rest-url", "http://localhost:8080"
    ])
    
    try:
        # Start the server
        await client.start_server()
        
        # Initialize the session
        print("\n1️⃣ Initializing MCP session...")
        init_response = await client.initialize()
        print(f"✅ Initialization successful: {init_response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        
        # List tools
        print("\n2️⃣ Listing available tools...")
        tools_response = await client.list_tools()
        tools = tools_response.get('result', {}).get('tools', [])
        print(f"✅ Found {len(tools)} tools")
        
        # Show some tool names
        tool_names = [tool['name'] for tool in tools[:10]]
        print(f"   Sample tools: {', '.join(tool_names)}")
        if len(tools) > 10:
            print(f"   ... and {len(tools) - 10} more")
        
        # Test a simple tool call
        print("\n3️⃣ Testing tool call...")
        test_response = await client.call_tool("judge_evaluate", {
            "response": "Paris is the capital of France.",
            "criteria": [
                {
                    "name": "accuracy",
                    "description": "Factual accuracy",
                    "scale": "1-5",
                    "weight": 1.0
                }
            ],
            "rubric": {
                "criteria": [],
                "scale_description": {
                    "1": "Wrong",
                    "5": "Correct"
                }
            },
            "judge_model": "rule-based"
        })
        
        if 'result' in test_response:
            result = test_response['result']
            print(f"✅ Tool call successful!")
            print(f"   Overall score: {result.get('overall_score', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 'N/A')}")
            print(f"   Judge model: {result.get('judge_model', 'N/A')}")
        else:
            print(f"❌ Tool call failed: {test_response}")
        
        # Test server info tool
        print("\n4️⃣ Testing server info tool...")
        server_info = await client.call_tool("get_server_info", {})
        if 'result' in server_info:
            print(f"✅ Server info retrieved successfully")
            print(f"   Server: {server_info['result'].get('server_name', 'Unknown')}")
        else:
            print(f"❌ Server info failed: {server_info}")
        
        print("\n✅ MCP wrapper test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_wrapper())
