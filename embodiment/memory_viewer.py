import streamlit as st
import pandas as pd
import altair as alt
import json
import os
from streamlit_agraph import agraph, Node, Edge, Config
from core.graph import KnowledgeGraph

class MemoryViewer:
    def __init__(self):
        self.kg = KnowledgeGraph()

    def _get_novel_id_for_character(self, char_name: str):
        """Helper to find which novel a character belongs to."""
        query = "MATCH (c:Character {name: $name}) RETURN c.novel_id as nid LIMIT 1"
        with self.kg.driver.session() as session:
            res = session.run(query, name=char_name).single()
            return res['nid'] if res else None

    def _load_power_ranking(self, novel_id: str):
        """
        Loads the namespace.json to create a {RankName: OrderIndex} map.
        This allows us to plot 'Mortal Blood' as 1 and 'Divine Sea' as 3.
        """
        path = f"data/{novel_id}_namespace.json"
        rank_map = {}
        
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ranks = data.get("power_hierarchy", {}).get("ranks", [])
                    for r in ranks:
                        rank_map[r["name"]] = r["order_index"]
            except Exception as e:
                st.error(f"Failed to load namespace: {e}")
        
        return rank_map

    def render_character_evolution(self, char_name: str):
        """
        Visualizes the arc of the character: Power and Emotion over time.
        """
        # 1. Fetch Temporal States from Neo4j
        query = """
        MATCH (c:Character {name: $name})-[:HAS_STATE]->(cs:CharacterState)
        RETURN cs.chapter_number as chapter, 
               cs.power_rank as rank, 
               cs.emotion as emotion, 
               cs.personality_snapshot as snapshot
        ORDER BY cs.chapter_number ASC
        """
        
        data = []
        with self.kg.driver.session() as session:
            results = session.run(query, name=char_name)
            for record in results:
                data.append({
                    "Chapter": record["chapter"],
                    "Rank": record["rank"],
                    "Emotion": record["emotion"],
                    "Snapshot": record["snapshot"]
                })
        
        if not data:
            st.warning(f"No temporal states found for {char_name}. Run ingestion first.")
            return

        df = pd.DataFrame(data)

        # 2. Map Ranks to Numbers (for the Y-Axis)
        novel_id = self._get_novel_id_for_character(char_name)
        if novel_id:
            rank_map = self._load_power_ranking(novel_id)
            # Apply map; default to 0 if rank not found
            df["PowerIndex"] = df["Rank"].map(lambda x: rank_map.get(x, 0))
        else:
            df["PowerIndex"] = 0

        # 3. Render Charts using Altair
        st.subheader(f"📈 Evolution: {char_name}")
        
        # Chart A: Cultivation Progress
        power_chart = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X("Chapter", title="Chapter Number"),
            y=alt.Y("PowerIndex", title="Cultivation Level"),
            color=alt.value("#FF4B4B"),
            tooltip=["Chapter", "Rank", "Snapshot"]
        ).properties(
            title="Power Progression",
            height=300
        )
        
        st.altair_chart(power_chart, use_container_width=True)

        # Chart B: Emotional Timeline
        st.markdown("#### ❤️ Emotional State Log")
        
        # Simple color map for emotions
        emotion_colors = {
            "ANGER": "#FF0000", "JOY": "#00FF00", "SADNESS": "#0000FF", 
            "FEAR": "#800080", "NEUTRAL": "#808080", "DETERMINATION": "#FFA500",
            "MURDEROUS_INTENT": "#8B0000"
        }
        
        # Create a colored dataframe display
        # We transform it slightly for readability
        st.dataframe(
            df[["Chapter", "Emotion", "Rank", "Snapshot"]].style.apply(
                lambda x: [f"color: {emotion_colors.get(v, 'black')}" if i == 1 else "" for i, v in enumerate(x)], 
                axis=1
            ),
            use_container_width=True
        )

    def render_ego_graph(self, center_node_name: str, radius: int = 1):
        # [Existing render_ego_graph code remains unchanged]
        # Copy the previous render_ego_graph logic here...
        # ...
        
        # 1. Cypher Query: Get neighbors
        query = f"""
        MATCH (center {{name: $name}})-[r]-(neighbor)
        RETURN center, r, neighbor
        LIMIT 50
        """
        
        nodes = []
        edges = []
        node_ids = set()
        
        with self.kg.driver.session() as session:
            results = session.run(query, name=center_node_name)
            
            if results.peek() is None:
                st.warning(f"No connections found for '{center_node_name}'.")
                return

            for record in results:
                center = record['center']
                neighbor = record['neighbor']
                rel = record['r']
                
                # Center
                c_id = center.element_id
                c_label = center.get('name') or center.get('title') or "Unknown"
                c_type = list(center.labels)[0] if center.labels else "Entity"
                
                if c_id not in node_ids:
                    nodes.append(Node(
                        id=c_id, 
                        label=c_label, 
                        size=25, 
                        shape="circularImage" if c_type == "Character" else "dot",
                        image="https://ui-avatars.com/api/?name=" + c_label if c_type == "Character" else "",
                        color="#FF4B4B"
                    ))
                    node_ids.add(c_id)
                
                # Neighbor
                n_id = neighbor.element_id
                n_label = neighbor.get('name') or neighbor.get('title') or "Unknown"
                n_type = list(neighbor.labels)[0] if neighbor.labels else "Entity"
                
                if n_id not in node_ids:
                    color = "#00CC96" if n_type == "Scene" else "#636EFA"
                    nodes.append(Node(id=n_id, label=n_label, size=15, color=color))
                    node_ids.add(n_id)
                
                # Edge
                edges.append(Edge(source=c_id, target=n_id, label=rel.type, color="#888888"))

        config = Config(width=800, height=600, directed=True, physics=True, collapsible=True)
        return agraph(nodes=nodes, edges=edges, config=config)