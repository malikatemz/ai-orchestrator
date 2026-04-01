"""OpenAI provider implementation"""

import httpx
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI API provider (GPT-4, GPT-4o, etc.)"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"
    
    async def execute(self, task_type: str, input_json: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task via OpenAI API"""
        
        # Build prompt based on task type
        prompt = self._build_prompt(task_type, input_json)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        
        result = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens", 0)
        
        # Calculate cost: rough estimate
        cost_per_1k = 0.003  # GPT-4o approximate
        cost = (tokens_used / 1000) * cost_per_1k
        
        return {
            "output": {"result": result},
            "tokens_used": tokens_used,
            "cost_usd": cost,
        }
    
    def _build_prompt(self, task_type: str, input_json: Dict[str, Any]) -> str:
        """Build task-specific prompt"""
        if task_type == "summarize":
            text = input_json.get("text", "")
            return f"Summarize the following text concisely:\n\n{text}"
        
        elif task_type == "classify":
            text = input_json.get("text", "")
            categories = input_json.get("categories", [])
            return f"Classify this text into one of these categories: {', '.join(categories)}\n\nText: {text}"
        
        elif task_type == "extract":
            text = input_json.get("text", "")
            schema = input_json.get("schema", {})
            return f"Extract data matching this schema from the text:\n\nSchema: {json.dumps(schema)}\n\nText: {text}"
        
        elif task_type == "analyze":
            text = input_json.get("text", "")
            return f"Analyze and provide insights about the following text:\n\n{text}"
        
        else:
            return str(input_json)
