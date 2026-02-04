from core.graph import KnowledgeGraph

kg = KnowledgeGraph()

# Create 3 test expert personas
test_personas = [
    {
        "name": "Dr. Sarah Chen",
        "description": "Expert in distributed systems and Kubernetes orchestration. 10+ years experience with cloud-native architectures."
    },
    {
        "name": "Alex Rodriguez",
        "description": "Full-stack developer specializing in React, TypeScript, and modern web frameworks. Passionate about UI/UX design."
    },
    {
        "name": "Prof. Marcus Singh",
        "description": "Database architect with expertise in graph databases, Neo4j, and complex query optimization."
    }
]

query = """
UNWIND $personas AS persona
CREATE (c:Character {
    name: persona.name,
    description: persona.description
})
"""

with kg.driver.session() as session:
    session.run(query, personas=test_personas)
    print(f"✅ Created {len(test_personas)} test personas!")

# Verify
verify_query = "MATCH (c:Character) RETURN count(c) as count"
with kg.driver.session() as session:
    result = session.run(verify_query).single()
    print(f"📊 Total characters in database: {result['count']}")

kg.close()