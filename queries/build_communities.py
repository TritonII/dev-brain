"""
Graphiti Community Builder
==========================

Utility script that runs Graphiti's Leiden clustering algorithm to group related
nodes into high-level thematic "communities" and synthesize macro-summaries of
your project's modules (e.g., Caching sprint, DB optimization, Auth setup).

CLI:
    python -m queries.build_communities
"""

import asyncio
import logging
import time

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings

logger = logging.getLogger(__name__)


async def build_project_communities():
    """Triggers Leiden clustering and community generation over the knowledge graph."""
    settings = get_settings()
    logger.info("Initializing Graphiti client for community building...")
    graphiti = await get_graphiti()
    
    start_time = time.time()
    logger.info("Running community detection and summary synthesis (this may take a moment)...")
    
    try:
        # build_communities is a native method in Graphiti v0.28+
        await graphiti.build_communities()
        
        latency = time.time() - start_time
        logger.info("Successfully rebuilt communities! (took %.2fs)", latency)
        print("\n" + "="*50)
        print(f"SUCCESS: Dev Brain thematic communities rebuilt in {latency:.2f}s.")
        print("Your graph is now structured into high-level modular namespaces!")
        print("="*50 + "\n")
        
    except Exception as e:
        logger.error("Failed to build communities: %s", e)
        print(f"\nERROR: Community building failed: {e}\n")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        await build_project_communities()
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
