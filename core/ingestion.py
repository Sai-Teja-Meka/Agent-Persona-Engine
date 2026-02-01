import os
import re
import time
import json
from typing import Generator, Tuple, List

from core.graph import KnowledgeGraph
from core.vector import VectorVault
from agents.archivist import ArchivistAgent
from core.models import NovelNamespace

class IngestionEngine:
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        
        # 1. Load World Truth (Namespace)
        self.namespace = self._load_namespace()
        self.power_ranks = [r.name for r in self.namespace.power_hierarchy.ranks] if self.namespace.power_hierarchy else []
        print(f"[Loaded] World Context: {len(self.power_ranks)} Cultivation Ranks found.")

        # 2. Initialize Components
        self.kg = KnowledgeGraph()
        self.kg.create_schema()
        self.vault = VectorVault()
        self.archivist = ArchivistAgent()

        # 3. Resume Logic
        self.start_chapter, self.current_state_vector = self._get_resume_state()

    def _load_namespace(self) -> NovelNamespace:
        """Loads the scraped namespace.json for this novel."""
        path = f"data/{self.novel_id}_namespace.json"
        if not os.path.exists(path):
            print(f"[WARNING] No namespace file found at {path}. Power scaling will be disabled.")
            # Return empty namespace to prevent crash
            return NovelNamespace(novel_id=self.novel_id, title="Unknown")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return NovelNamespace(**data)

    def _get_resume_state(self) -> Tuple[int, str]:
        # (Same as previous version...)
        query = """
        MATCH (c:Chapter {novel_id: $novel_id})
        RETURN c.chapter_number AS last_num, c.state_vector AS state
        ORDER BY c.chapter_number DESC
        LIMIT 1
        """
        with self.kg.driver.session() as session:
            result = session.run(query, novel_id=self.novel_id).single()

        if result:
            return result["last_num"] + 1, result["state"]
        return 1, "Story Start. No events yet."

    def process_file(self, file_path: str, limit: int = None):
        # ... [File Check Logic] ...
        
        chapter_iterator = self._read_and_split(file_path)
        processed_count = 0

        for chapter_num, raw_text in chapter_iterator:
            if chapter_num < self.start_chapter:
                continue
            if limit and processed_count >= limit:
                break

            print(f"[PROCESSING] Chapter {chapter_num}...")

            try:
                # 1. Analyze (Injecting Power Ranks!)
                chapter_data = self.archivist.analyze_chapter(
                    novel_id=self.novel_id,
                    chapter_num=chapter_num,
                    text=raw_text,
                    previous_state=self.current_state_vector,
                    power_ranks=self.power_ranks # <--- INJECTION
                )

                # 2. Persist Core Data
                self.current_state_vector = chapter_data.state_vector
                self.kg.add_chapter(chapter_data)
                self.vault.add_chapter(chapter_data)

                # 3. Persist Granular Graph Nodes
                # A. Scenes
                for scene in chapter_data.scenes:
                    self.kg.link_scene_to_chapter(self.novel_id, chapter_num, scene.order_index)
                    for char in scene.characters_present:
                        self.kg.link_character_to_scene(char, self.novel_id, chapter_num, scene.order_index)
                
                # B. Character States (The New Feature)
                for state in chapter_data.character_states:
                    self.kg.add_character_state(state) # <--- STORAGE

                processed_count += 1
                time.sleep(1)

            except Exception as e:
                print(f"[CRASH] Ch {chapter_num}: {e}")
                break

        self.kg.close()

    def _read_and_split(self, file_path: str):
        # (Same as previous regex logic)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(r"(Chapter\s+\d+)", re.IGNORECASE)
        parts = pattern.split(content)
        current_chapter_num = 1
        for i in range(1, len(parts), 2):
            yield current_chapter_num, f"{parts[i]}\n{parts[i+1]}".strip()
            current_chapter_num += 1