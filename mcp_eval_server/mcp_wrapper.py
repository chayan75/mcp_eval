#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Wrapper Server using FastMCP for SSE endpoint.

This module provides an MCP server that wraps the existing REST API endpoints
using FastMCP, allowing MCP clients to access all evaluation tools through
the MCP protocol via Server-Sent Events (SSE).
"""

# Standard
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Load .env file if it exists
try:
    # Third-Party
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Third-Party
import httpx
from fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("mcp-eval-wrapper")

# Configuration
REST_API_BASE_URL = os.getenv("REST_API_BASE_URL", "http://localhost:8080")
REST_API_TIMEOUT = 30.0


class RESTAPIClient:
    """Client for making requests to the REST API."""
    
    def __init__(self, base_url: str = REST_API_BASE_URL, timeout: float = REST_API_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request to the REST API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for GET {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error for GET {url}: {e}")
            raise
    
    async def post(self, endpoint: str, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Make a POST request to the REST API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self.client.post(url, json=data, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for POST {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error for POST {url}: {e}")
            raise


# Initialize REST API client
rest_client = RESTAPIClient()


@mcp.tool()
async def get_server_info() -> str:
    """Get server information and status."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        result = await client.get("/")
        return json.dumps(result, indent=2)


@mcp.tool()
async def get_health_status() -> str:
    """Get health check status."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        result = await client.get("/health")
        return json.dumps(result, indent=2)


@mcp.tool()
async def get_tool_categories() -> str:
    """Get list of available tool categories."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        result = await client.get("/tools/categories")
        return json.dumps(result, indent=2)


@mcp.tool()
async def get_all_tools() -> str:
    """Get detailed information about all available tools."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        result = await client.get("/tools")
        return json.dumps(result, indent=2)


# Judge evaluation tools
@mcp.tool()
async def judge_evaluate(
    response: str,
    criteria: List[Dict[str, Any]],
    rubric: Dict[str, Any],
    judge_model: str = "gpt-4o-mini",
    context: Optional[str] = None,
    use_cot: bool = True
) -> str:
    """Evaluate a single response using LLM-as-a-judge."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "response": response,
            "criteria": criteria,
            "rubric": rubric,
            "judge_model": judge_model,
            "context": context,
            "use_cot": use_cot
        }
        result = await client.post("/judge/evaluate", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def judge_compare(
    response_a: str,
    response_b: str,
    criteria: List[Dict[str, Any]],
    judge_model: str = "gpt-4o-mini",
    context: Optional[str] = None,
    position_bias_mitigation: bool = True
) -> str:
    """Compare two responses using LLM-as-a-judge."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "response_a": response_a,
            "response_b": response_b,
            "criteria": criteria,
            "judge_model": judge_model,
            "context": context,
            "position_bias_mitigation": position_bias_mitigation
        }
        result = await client.post("/judge/compare", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def judge_rank(
    responses: List[str],
    criteria: List[Dict[str, Any]],
    judge_model: str = "gpt-4o-mini",
    context: Optional[str] = None,
    ranking_method: str = "tournament"
) -> str:
    """Rank multiple responses using LLM-as-a-judge."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "responses": responses,
            "criteria": criteria,
            "judge_model": judge_model,
            "context": context,
            "ranking_method": ranking_method
        }
        result = await client.post("/judge/rank", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def judge_reference(
    response: str,
    reference: str,
    judge_model: str = "gpt-4o-mini",
    evaluation_type: str = "factuality",
    tolerance: str = "moderate"
) -> str:
    """Evaluate response against gold standard reference."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "response": response,
            "reference": reference,
            "judge_model": judge_model,
            "evaluation_type": evaluation_type,
            "tolerance": tolerance
        }
        result = await client.post("/judge/reference", data)
        return json.dumps(result, indent=2)


# Quality assessment tools
@mcp.tool()
async def quality_factuality(
    response: str,
    knowledge_base: Optional[Dict[str, Any]] = None,
    fact_checking_model: str = "gpt-4",
    confidence_threshold: float = 0.8,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Check factual accuracy of responses."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "response": response,
            "knowledge_base": knowledge_base,
            "fact_checking_model": fact_checking_model,
            "confidence_threshold": confidence_threshold,
            "judge_model": judge_model
        }
        result = await client.post("/quality/factuality", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def quality_coherence(
    text: str,
    context: Optional[str] = None,
    coherence_dimensions: List[str] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Analyze logical flow and consistency."""
    if coherence_dimensions is None:
        coherence_dimensions = ["logical_flow", "consistency", "topic_transitions"]
    
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "text": text,
            "context": context,
            "coherence_dimensions": coherence_dimensions,
            "judge_model": judge_model
        }
        result = await client.post("/quality/coherence", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def quality_toxicity(
    content: str,
    toxicity_categories: List[str] = None,
    sensitivity_level: str = "moderate",
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Detect harmful or biased content."""
    if toxicity_categories is None:
        toxicity_categories = ["profanity", "hate_speech", "threats", "discrimination"]
    
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "content": content,
            "toxicity_categories": toxicity_categories,
            "sensitivity_level": sensitivity_level,
            "judge_model": judge_model
        }
        result = await client.post("/quality/toxicity", data)
        return json.dumps(result, indent=2)


# Prompt evaluation tools
@mcp.tool()
async def prompt_clarity(
    prompt_text: str,
    target_model: str = "general",
    domain_context: Optional[str] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Assess prompt clarity."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "prompt_text": prompt_text,
            "target_model": target_model,
            "domain_context": domain_context,
            "judge_model": judge_model
        }
        result = await client.post("/prompt/clarity", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def prompt_consistency(
    prompt: str,
    test_inputs: List[str],
    num_runs: int = 3,
    temperature_range: List[float] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Test prompt consistency across runs."""
    if temperature_range is None:
        temperature_range = [0.1, 0.5, 0.9]
    
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "prompt": prompt,
            "test_inputs": test_inputs,
            "num_runs": num_runs,
            "temperature_range": temperature_range,
            "judge_model": judge_model
        }
        result = await client.post("/prompt/consistency", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def prompt_completeness(
    prompt: str,
    expected_components: List[str],
    test_samples: Optional[List[str]] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Measure prompt completeness."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "prompt": prompt,
            "expected_components": expected_components,
            "test_samples": test_samples,
            "judge_model": judge_model
        }
        result = await client.post("/prompt/completeness", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def prompt_relevance(
    prompt: str,
    outputs: List[str],
    embedding_model: str = "all-MiniLM-L6-v2",
    relevance_threshold: float = 0.7,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Assess prompt relevance."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "prompt": prompt,
            "outputs": outputs,
            "embedding_model": embedding_model,
            "relevance_threshold": relevance_threshold,
            "judge_model": judge_model
        }
        result = await client.post("/prompt/relevance", data)
        return json.dumps(result, indent=2)


# Agent evaluation tools
@mcp.tool()
async def agent_tool_use(
    agent_trace: Dict[str, Any],
    expected_tools: List[str],
    tool_sequence_matters: bool = False,
    allow_extra_tools: bool = True,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Evaluate agent tool usage."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "agent_trace": agent_trace,
            "expected_tools": expected_tools,
            "tool_sequence_matters": tool_sequence_matters,
            "allow_extra_tools": allow_extra_tools,
            "judge_model": judge_model
        }
        result = await client.post("/agent/tool-use", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def agent_task_completion(
    task_description: str,
    success_criteria: List[Dict[str, Any]],
    agent_trace: Dict[str, Any],
    final_state: Optional[Dict[str, Any]] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Evaluate agent task completion."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "task_description": task_description,
            "success_criteria": success_criteria,
            "agent_trace": agent_trace,
            "final_state": final_state,
            "judge_model": judge_model
        }
        result = await client.post("/agent/task-completion", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def agent_reasoning(
    reasoning_trace: List[Dict[str, Any]],
    decision_points: List[Dict[str, Any]],
    context: Dict[str, Any],
    optimal_path: Optional[List[str]] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Analyze agent reasoning quality."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "reasoning_trace": reasoning_trace,
            "decision_points": decision_points,
            "context": context,
            "optimal_path": optimal_path,
            "judge_model": judge_model
        }
        result = await client.post("/agent/reasoning", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def agent_benchmark(
    benchmark_suite: str,
    agent_config: Dict[str, Any],
    baseline_comparison: Optional[Dict[str, Any]] = None,
    metrics_focus: List[str] = None
) -> str:
    """Run agent performance benchmarks."""
    if metrics_focus is None:
        metrics_focus = ["accuracy", "efficiency", "reliability"]
    
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "benchmark_suite": benchmark_suite,
            "agent_config": agent_config,
            "baseline_comparison": baseline_comparison,
            "metrics_focus": metrics_focus
        }
        result = await client.post("/agent/benchmark", data)
        return json.dumps(result, indent=2)


# RAG evaluation tools
@mcp.tool()
async def rag_retrieval_relevance(
    query: str,
    retrieved_documents: List[Dict[str, Any]],
    relevance_threshold: float = 0.7,
    embedding_model: str = "text-embedding-ada-002",
    judge_model: str = "gpt-4o-mini",
    use_llm_judge: bool = True
) -> str:
    """Evaluate RAG retrieval relevance."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "query": query,
            "retrieved_documents": retrieved_documents,
            "relevance_threshold": relevance_threshold,
            "embedding_model": embedding_model,
            "judge_model": judge_model,
            "use_llm_judge": use_llm_judge
        }
        result = await client.post("/rag/retrieval-relevance", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def rag_context_utilization(
    query: str,
    retrieved_context: str,
    generated_answer: str,
    context_chunks: Optional[List[str]] = None,
    judge_model: str = "gpt-4o-mini"
) -> str:
    """Evaluate RAG context utilization."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "query": query,
            "retrieved_context": retrieved_context,
            "generated_answer": generated_answer,
            "context_chunks": context_chunks,
            "judge_model": judge_model
        }
        result = await client.post("/rag/context-utilization", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def rag_answer_groundedness(
    question: str,
    answer: str,
    supporting_context: str,
    judge_model: str = "gpt-4o-mini",
    strictness: str = "moderate"
) -> str:
    """Evaluate RAG answer groundedness."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "question": question,
            "answer": answer,
            "supporting_context": supporting_context,
            "judge_model": judge_model,
            "strictness": strictness
        }
        result = await client.post("/rag/answer-groundedness", data)
        return json.dumps(result, indent=2)


@mcp.tool()
async def rag_hallucination_detection(
    generated_text: str,
    source_context: str,
    judge_model: str = "gpt-4o-mini",
    detection_threshold: float = 0.8
) -> str:
    """Detect hallucinations in RAG responses."""
    async with RESTAPIClient(REST_API_BASE_URL) as client:
        data = {
            "generated_text": generated_text,
            "source_context": source_context,
            "judge_model": judge_model,
            "detection_threshold": detection_threshold
        }
        result = await client.post("/rag/hallucination-detection", data)
        return json.dumps(result, indent=2)


def main():
    """Main function to run the MCP wrapper server."""
    parser = argparse.ArgumentParser(description="MCP Evaluation Server Wrapper (SSE)")
    parser.add_argument("--rest-url", default="http://localhost:8080", help="REST API base URL")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9001, help="Port to bind to")
    
    args = parser.parse_args()
    
    # Update global configuration
    global REST_API_BASE_URL, REST_API_TIMEOUT
    REST_API_BASE_URL = args.rest_url
    REST_API_TIMEOUT = args.timeout
    
    logger.info("🚀 Starting MCP Evaluation Server Wrapper (SSE)...")
    logger.info(f"📡 Protocol: Model Context Protocol (MCP) via Server-Sent Events")
    logger.info(f"🌐 URL: http://{args.host}:{args.port}")
    logger.info(f"🔗 REST API URL: {REST_API_BASE_URL}")
    logger.info(f"⏱️  Timeout: {REST_API_TIMEOUT}s")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Run the FastMCP server with streamable-http
    mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
