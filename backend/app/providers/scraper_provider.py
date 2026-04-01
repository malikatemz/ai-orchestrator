"""Web scraper provider implementation using httpx + BeautifulSoup"""

import httpx
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ScraperProvider:
    """HTTP + BeautifulSoup web scraper"""
    
    async def execute(self, task_type: str, input_json: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scraping task"""
        
        if task_type != "scrape":
            raise ValueError(f"Scraper only supports 'scrape' tasks, got: {task_type}")
        
        url = input_json.get("url")
        if not url:
            raise ValueError("Missing required 'url' in input_json")
        
        selector = input_json.get("selector", "body")  # CSS selector
        
        # Fetch page
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {url}: {str(e)}")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract based on selector
        elements = soup.select(selector)
        
        if not elements:
            content = ""
        elif len(elements) == 1:
            content = elements[0].get_text(strip=True)
        else:
            content = "\n".join([el.get_text(strip=True) for el in elements])
        
        return {
            "output": {
                "url": url,
                "content": content,
                "title": soup.title.string if soup.title else None,
            },
            "tokens_used": 0,
            "cost_usd": 0.0,
        }
