"""
AWS Bedrock LLM Client with connection pooling and caching
This file preserves your battle-tested Bedrock client implementation
"""
import boto3
import json
import logging
import asyncio
import os
from typing import Optional, Dict, Any
import hashlib

logger = logging.getLogger(__name__)


class BedrockLLMManager:
    """
    Optimized Bedrock client with connection pooling
    
    This implements Layer 3 parallelism: LLM connection pool (50 concurrent)
    """
    
    def __init__(
        self,
        region_name: str = None,
        max_concurrent: int = 50,
        cache_enabled: bool = True
    ):
        # Get region from environment
        if region_name is None:
            region_name = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
        
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region_name
        )
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, Any] = {}
        
        # Model configs optimized for speed and cost
        self.model_configs = {
            "sonnet": {
                "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "max_tokens": 4096,
                "temperature": 0.7,
            },
            "haiku": {
                "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
                "max_tokens": 4096,
                "temperature": 0.5,
            }
        }
        
        logger.info(f"Initialized Bedrock client in {region_name} with max_concurrent={max_concurrent}")
    
    def _get_cache_key(self, prompt: str, system_prompt: Optional[str], model: str) -> str:
        """Generate cache key from inputs"""
        content = f"{model}:{system_prompt or ''}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check cache for existing result"""
        if not self.cache_enabled:
            return None
        return self._cache.get(cache_key)
    
    def _set_cache(self, cache_key: str, result: str):
        """Store result in cache"""
        if self.cache_enabled:
            self._cache[cache_key] = result
            
            # Simple cache size management
            if len(self._cache) > 1000:
                # Remove oldest 100 entries (FIFO approximation)
                keys_to_remove = list(self._cache.keys())[:100]
                for key in keys_to_remove:
                    del self._cache[key]
    
    async def call_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "sonnet",
        use_cache: bool = True
    ) -> Optional[str]:
        """
        Async LLM call with caching and connection pooling
        
        Args:
            prompt: User prompt
            system_prompt: System instructions (optional)
            model: Model name ("sonnet" or "haiku")
            use_cache: Whether to use caching
            
        Returns:
            LLM response text
        """
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(prompt, system_prompt, model)
            cached = self._check_cache(cache_key)
            if cached:
                logger.debug(f"Cache hit for key: {cache_key[:16]}...")
                return cached
        
        # Acquire semaphore for connection pooling
        async with self.semaphore:
            try:
                config = self.model_configs.get(model, self.model_configs["sonnet"])
                
                # Build prompt
                if system_prompt:
                    combined_prompt = f"""[SYSTEM INSTRUCTIONS]
{system_prompt}

[USER QUERY]
{prompt}
"""
                else:
                    combined_prompt = prompt
                
                payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": config["max_tokens"],
                    "temperature": config["temperature"],
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": combined_prompt}],
                        }
                    ],
                }
                
                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.invoke_model(
                        modelId=config["model_id"],
                        contentType="application/json",
                        accept="application/json",
                        body=json.dumps(payload),
                    )
                )
                
                response_body = json.loads(response["body"].read().decode("utf-8"))
                result = response_body["content"][0]["text"].strip()
                
                # Cache result
                if use_cache:
                    self._set_cache(cache_key, result)
                
                return result
                
            except Exception as e:
                logger.error(f"Bedrock call failed: {str(e)}")
                return None
    
    def clear_cache(self):
        """Clear the LLM response cache"""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "cache_size": len(self._cache),
            "estimated_memory_mb": len(str(self._cache)) / (1024 * 1024)
        }


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON from LLM response, handling markdown code blocks
    
    Args:
        response: Raw LLM response
        
    Returns:
        Cleaned JSON string
    """
    import re
    
    # Remove markdown code fences
    response = re.sub(r'^```json\s*', '', response, flags=re.MULTILINE)
    response = re.sub(r'^```\s*$', '', response, flags=re.MULTILINE)
    
    # Try to find JSON object or array
    match = re.search(r'(\{.*\}|\[.*\])', response, re.DOTALL)
    if match:
        return match.group(1)
    
    return response.strip()


# Global instance
_llm_manager: Optional[BedrockLLMManager] = None


def get_llm_manager() -> BedrockLLMManager:
    """Get or create global LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = BedrockLLMManager(
            max_concurrent=50,
            cache_enabled=True
        )
    return _llm_manager