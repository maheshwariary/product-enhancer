"""
Batch processor with row-level parallelism
This file preserves your battle-tested parallel processing logic
"""
import asyncio
import logging
from typing import List, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Process multiple rows in parallel with concurrency control
    
    This implements Layer 2 parallelism: across-row processing
    """
    
    def __init__(self, max_concurrent: int = 20, progress_bar: bool = False):
        """
        Args:
            max_concurrent: Maximum number of rows to process simultaneously
            progress_bar: Whether to show progress bar (disabled for Lambda)
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.progress_bar = progress_bar
    
    async def process_single_row_with_limit(
        self,
        row: Dict[str, Any],
        row_id: str
    ) -> Dict[str, Any]:
        """
        Process single row with concurrency limit
        
        The semaphore ensures max_concurrent rows are processed at once
        """
        async with self.semaphore:
            # Import here to avoid circular dependency
            from .orchestrator import run_pipeline_for_row
            return await run_pipeline_for_row(row, row_id)
    
    async def process_batch(
        self,
        df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Process entire DataFrame in parallel
        
        Creates tasks for all rows and executes them with concurrency control
        """
        rows = df.to_dict('records')
        
        # Create tasks for all rows
        tasks = [
            self.process_single_row_with_limit(row, f"row_{i}")
            for i, row in enumerate(rows)
        ]
        
        logger.info(f"Created {len(tasks)} tasks, executing with max_concurrent={self.max_concurrent}")
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Row {i} failed: {result}")
                processed_results.append({
                    "error": str(result),
                    "vendor_name": rows[i].get("vendor_name", ""),
                    "product_name": rows[i].get("product_name", "")
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def process_batch_sync(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Synchronous wrapper for async batch processing
        
        This allows the Lambda handler to call the async pipeline synchronously
        """
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async processing
        results = loop.run_until_complete(self.process_batch(df))
        
        # Convert to DataFrame
        return pd.DataFrame(results)