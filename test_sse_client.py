#!/usr/bin/env python3
"""Test the MCP wrapper with proper SSE client."""

import asyncio
import httpx
import json
import re

class SSEClient:
    """Simple SSE client for testing streamable-http transport."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def send_request(self, request: dict) -> dict:
        """Send a JSON-RPC request and parse SSE response."""
        headers = {"Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        
        response = await self.client.post(
            self.base_url,
            json=request,
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code not in [200, 202]:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        # For notifications (202), return empty result
        if response.status_code == 202:
            return {}
        
        # Extract session ID from response headers
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
            print(f"Session ID: {self.session_id}")
        
        # Parse SSE response
        content = response.text
        print(f"Raw SSE response: {content}")
        
        # Extract JSON from SSE format
        # Look for "data: {json}" pattern
        data_match = re.search(r'data:\s*(\{.*\})', content)
        if data_match:
            json_str = data_match.group(1)
            return json.loads(json_str)
        else:
            raise Exception(f"Could not parse SSE response: {content}")

async def test_sse_wrapper():
    """Test the MCP wrapper with SSE client."""
    print("🧪 Testing MCP wrapper with SSE client...")
    print("=" * 60)
    
    async with SSEClient("http://localhost:9001/mcp/") as client:
        try:
            # Test 1: Initialize
            print("\n1️⃣ Testing initialization...")
            init_request = {
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
            
            result = await client.send_request(init_request)
            print(f"✅ Initialization successful: {result.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
            
            # Send initialized notification
            print("\n📢 Sending initialized notification...")
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await client.send_request(initialized_notification)
            print("✅ Initialized notification sent")
            
            # Test 2: List tools
            print("\n2️⃣ Testing tools list...")
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            result = await client.send_request(tools_request)
            tools = result.get('result', {}).get('tools', [])
            print(f"✅ Found {len(tools)} tools")
            if tools:
                print(f"   Sample tools: {', '.join([tool['name'] for tool in tools[:5]])}")
            
            # Test 3: Call a tool
            print("\n3️⃣ Testing tool call...")
            tool_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "judge_evaluate",
                    "arguments": {
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
                    }
                }
            }
            
            result = await client.send_request(tool_request)
            if 'result' in result:
                tool_result = result['result']
                print(f"✅ Tool call successful!")
                print(f"   Overall score: {tool_result.get('overall_score', 'N/A')}")
                print(f"   Confidence: {tool_result.get('confidence', 'N/A')}")
            else:
                print(f"❌ Tool call failed: {result}")
            
            print("\n✅ SSE wrapper test completed successfully!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sse_wrapper())