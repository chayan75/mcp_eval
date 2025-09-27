#!/usr/bin/env python3
"""
AWS App Runner Startup Script with Proxy
Runs both REST API and MCP wrapper, with proxy routing
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class MCPEvaluationServer:
    def __init__(self):
        self.rest_port = int(os.getenv("PORT", "8080"))
        self.mcp_port = int(os.getenv("MCP_PORT", "9001"))
        self.rest_process: Optional[subprocess.Popen] = None
        self.mcp_process: Optional[subprocess.Popen] = None
        self.proxy_app = FastAPI(title="MCP Evaluation Server Proxy")
        self.setup_proxy_routes()
        
    def setup_proxy_routes(self):
        """Setup proxy routes for both REST API and MCP wrapper"""
        
        @self.proxy_app.get("/")
        async def root():
            return {
                "service": "MCP Evaluation Server",
                "version": "0.1.0",
                "endpoints": {
                    "rest_api": f"http://localhost:{self.rest_port}",
                    "mcp_wrapper": f"http://localhost:{self.mcp_port}/mcp/",
                    "docs": f"http://localhost:{self.rest_port}/docs",
                    "health": f"http://localhost:{self.rest_port}/health"
                },
                "protocols": ["HTTP REST API", "MCP over HTTP/SSE"]
            }
        
        @self.proxy_app.get("/health")
        async def health():
            """Health check endpoint"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://localhost:{self.rest_port}/health", timeout=5.0)
                    return response.json()
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {"status": "unhealthy", "error": str(e)}
        
        @self.proxy_app.api_route("/mcp/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        async def mcp_proxy(request: Request, path: str):
            """Proxy MCP wrapper requests"""
            try:
                url = f"http://localhost:{self.mcp_port}/mcp/{path}"
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=request.method,
                        url=url,
                        headers=dict(request.headers),
                        content=await request.body(),
                        timeout=30.0
                    )
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )
            except Exception as e:
                logger.error(f"MCP proxy error: {e}")
                return Response(
                    content=f"Proxy error: {str(e)}",
                    status_code=500
                )
        
        @self.proxy_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        async def rest_proxy(request: Request, path: str):
            """Proxy REST API requests"""
            try:
                url = f"http://localhost:{self.rest_port}/{path}"
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=request.method,
                        url=url,
                        headers=dict(request.headers),
                        content=await request.body(),
                        timeout=30.0
                    )
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )
            except Exception as e:
                logger.error(f"REST proxy error: {e}")
                return Response(
                    content=f"Proxy error: {str(e)}",
                    status_code=500
                )
    
    def start_rest_api(self):
        """Start the REST API server"""
        logger.info(f"🌐 Starting REST API server on port {self.rest_port}...")
        self.rest_process = subprocess.Popen([
            sys.executable, "-m", "mcp_eval_server.rest_server",
            "--port", str(self.rest_port),
            "--host", "127.0.0.1"
        ])
        logger.info(f"✅ REST API server started (PID: {self.rest_process.pid})")
    
    def start_mcp_wrapper(self):
        """Start the MCP wrapper server"""
        logger.info(f"⏳ Waiting for REST API to be ready...")
        time.sleep(5)
        
        logger.info(f"🔗 Starting MCP wrapper server on port {self.mcp_port}...")
        self.mcp_process = subprocess.Popen([
            sys.executable, "-m", "mcp_eval_server.mcp_wrapper",
            "--rest-url", f"http://127.0.0.1:{self.rest_port}",
            "--host", "127.0.0.1",
            "--port", str(self.mcp_port)
        ])
        logger.info(f"✅ MCP wrapper server started (PID: {self.mcp_process.pid})")
    
    def cleanup(self):
        """Cleanup processes"""
        logger.info("🛑 Shutting down servers...")
        if self.rest_process:
            self.rest_process.terminate()
            self.rest_process.wait()
        if self.mcp_process:
            self.mcp_process.terminate()
            self.mcp_process.wait()
    
    def run(self):
        """Run the proxy server"""
        logger.info("🚀 Starting MCP Evaluation Server on AWS App Runner...")
        logger.info(f"📡 Protocols: HTTP REST API + MCP Wrapper (SSE)")
        logger.info(f"🌍 REST API Port: {self.rest_port}")
        logger.info(f"🌍 MCP Wrapper Port: {self.mcp_port}")
        logger.info(f"🔗 Proxy Port: {self.rest_port}")
        
        # Log available judges
        try:
            from mcp_eval_server.tools.judge_tools import JudgeTools
            jt = JudgeTools()
            judges = jt.get_available_judges()
            logger.info("⚖️  Available judges:")
            for judge in judges:
                logger.info(f"  - {judge}")
        except Exception as e:
            logger.warning(f"Could not load judges: {e}")
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start both servers
        self.start_rest_api()
        self.start_mcp_wrapper()
        
        logger.info("🎉 Both servers are running!")
        logger.info(f"📚 REST API: http://0.0.0.0:{self.rest_port}/docs")
        logger.info(f"🔗 MCP Wrapper: http://0.0.0.0:{self.rest_port}/mcp/")
        logger.info(f"🏥 Health Check: http://0.0.0.0:{self.rest_port}/health")
        
        # Start the proxy server
        try:
            uvicorn.run(
                self.proxy_app,
                host="0.0.0.0",
                port=self.rest_port,
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.cleanup()

if __name__ == "__main__":
    server = MCPEvaluationServer()
    server.run()
