"""Anthropic Claude provider implementation"""

import httpx
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude API provider"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"
    
    async def execute(self, task_type: str, input_json: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task via Anthropic API"""
        
        # Build prompt based on task type
        prompt = self._build_prompt(task_type, input_json)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        
        result = data["content"][0]["text"]
        tokens_used = data.get("usage", {}).get("input_tokens", 0)
        tokens_used += data.get("usage", {}).get("output_tokens", 0)
        
        # Calculate cost: Claude 3.5 Sonnet pricing
        cost_per_1k_input = 0.003
        cost_per_1k_output = 0.015
        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
        cost = (input_tokens / 1000 * cost_per_1k_input) + (output_tokens / 1000 * cost_per_1k_output)
        
        return {
            "output": {"result": result},
            "tokens_used": tokens_used,
            "cost_usd": cost,
        }
    
    def _build_prompt(self, task_type: str, input_json: Dict[str, Any]) -> str:
        """Build task-specific prompt"""
        if task_type == "summarize":
            text = input_json.get("text", "")
            return f"Please summarize the following text concisely:\n\n{text}"
        
        elif task_type == "classify":
            text = input_json.get("text", "")
            categories = input_json.get("categories", [])
            return f"Please classify this text into one of these categories: {', '.join(categories)}\n\nText: {text}"
        
        elif task_type == "extract":
            text = input_json.get("text", "")
            schema = input_json.get("schema", {})
            return f"Please extract data matching this schema from the text:\n\nSchema: {json.dumps(schema)}\n\nText: {text}"
        
        elif task_type == "analyze":
            text = input_json.get("text", "")
            return f"Please analyze and provide insights about the following text:\n\n{text}"
        
        else:
            return str(input_json)
