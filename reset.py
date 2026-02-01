import logging
from neo4j import GraphDatabase
import chromadb
from chromadb.config import Settings
from config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def wipe_neo4j():
    """
    Connects to Neo4j and deletes all nodes and relationships.
    """
    logger.warning("💥 Initiating Neo4j wipe...")
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    
    query = "MATCH (n) DETACH DELETE n"
    
    try:
        with driver.session() as session:
            session.run(query)
            # Verify emptiness
            result = session.run("MATCH (n) RETURN count(n) as count").single()
            count = result["count"]
            if count == 0:
                logger.info("✅ Neo4j database is empty.")
            else:
                logger.error(f"❌ Neo4j wipe failed. {count} nodes remain.")
    except Exception as e:
        logger.error(f"❌ Neo4j Error: {e}")
    finally:
        driver.close()

def wipe_chroma():
    """
    Connects to ChromaDB and deletes the project collections.
    """
    logger.warning("💥 Initiating ChromaDB wipe...")
    try:
        client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # Target collections defined in your VectorVault
        target_cols = [
            f"{settings.CHROMA_COLLECTION}_chapters",
            f"{settings.CHROMA_COLLECTION}_scenes"
        ]
        
        existing_cols = [c.name for c in client.list_collections()]
        
        for target in target_cols:
            if target in existing_cols:
                client.delete_collection(target)
                logger.info(f"✅ Deleted collection: {target}")
            else:
                logger.info(f"⚠️ Collection not found (already empty): {target}")
                
    except Exception as e:
        logger.error(f"❌ ChromaDB Error: {e}")

def main():
    print("⚠️  WARNING: THIS WILL DELETE ALL DATA IN NEO4J AND CHROMA ⚠️")
    confirm = input(f"Type '{settings.PROJECT_NAME}' to confirm reset: ")
    
    if confirm == settings.PROJECT_NAME:
        wipe_neo4j()
        wipe_chroma()
        print("✨ System Reset Complete. The slate is clean.")
    else:
        print("🚫 Reset aborted.")

if __name__ == "__main__":
    main()