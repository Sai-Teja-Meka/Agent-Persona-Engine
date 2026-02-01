from core.graph import KnowledgeGraph
import logging

class SystemMonitor:
    def __init__(self):
        self.kg = KnowledgeGraph()

    def get_system_health(self):
        """
        Fetches vital statistics from the Graph for the Dashboard.
        """
        stats = {
            "ingestion_status": 0,
            "memory_raw": 0,
            "memory_summary": 0,
            "drift_score": "N/A"
        }

        try:
            with self.kg.driver.session() as session:
                # 1. Ingestion Status (Max Chapter)
                # We check the highest chapter number ingested
                query_ingest = "MATCH (c:Chapter) RETURN max(c.chapter_number) as max_ch"
                res_ingest = session.run(query_ingest).single()
                if res_ingest and res_ingest["max_ch"]:
                    stats["ingestion_status"] = res_ingest["max_ch"]

                # 2. Memory Load
                # Count raw memories vs compressed summaries
                query_mem = """
                MATCH (m:Memory) WITH count(m) as raw_count
                OPTIONAL MATCH (s:Summary) 
                RETURN raw_count, count(s) as sum_count
                """
                res_mem = session.run(query_mem).single()
                if res_mem:
                    stats["memory_raw"] = res_mem["raw_count"]
                    stats["memory_summary"] = res_mem["sum_count"]

                # 3. Drift Score (Placeholder for future logging)
                # If we saved (:DriftLog) nodes, we would fetch the latest here.
                # For now, we assume it's safe unless flagged.
                # query_drift = "MATCH (d:DriftLog) RETURN d.score ORDER BY d.timestamp DESC LIMIT 1"
                # res_drift = session.run(query_drift).single()
                # if res_drift: stats["drift_score"] = res_drift[0]
                
        except Exception as e:
            logging.error(f"Health Check Failed: {e}")
            stats["error"] = str(e)

        return stats