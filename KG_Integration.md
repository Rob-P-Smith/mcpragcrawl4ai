# Knowledge Graph Integration with Neo4j

## Overview

This document outlines the integration of Neo4j knowledge graph capabilities with the existing Crawl4AI RAG system, using a custom llama.cpp embedding model for entity extraction and relationship mapping.

## Architecture

```
┌─────────────────────────────────────────────┐
│        SQLite (crawl4ai_rag.db)            │
│  ✓ crawled_content (text/markdown)         │
│  ✓ content_vectors (embeddings)            │
│  ✓ sessions, metadata                      │
└─────────────────────────────────────────────┘
                    ↓
            content_id (shared)
                    ↓
┌─────────────────────────────────────────────┐
│           Neo4j Graph Database              │
│  • Entity nodes (concepts, tech, etc)       │
│  • Relationship edges                       │
│  • Content-Entity mappings                  │
└─────────────────────────────────────────────┘
                    ↑
┌─────────────────────────────────────────────┐
│    llama.cpp EmbedderModel (Port 8081)     │
│  • Entity extraction from content           │
│  • Relationship extraction                  │
│  • CPU-only inference                       │
└─────────────────────────────────────────────┘
```

## EmbedderModel Configuration

### Recommended Settings for Web Page RAG

**Context Size:**
- **8192 tokens** - Optimal for processing chunked web content
- Allows full context of most web page sections
- Balances memory usage on CPU-only systems

**Temperature:**
- **0.1** - Low temperature for consistent, deterministic entity extraction
- Reduces hallucination in entity/relationship identification
- Ensures repeatable results across similar content

**Max Response Length:**
- **1024 tokens** - Sufficient for structured JSON output
- Typical entity extraction returns 20-100 entities per chunk
- Relationship extraction typically 50-200 tokens

**Example Configuration:**
```bash
# llama.cpp server startup
./server -m models/embedder-model.gguf \
  --port 8081 \
  --ctx-size 8192 \
  --temp 0.1 \
  --n-predict 1024 \
  --threads 8 \
  --batch-size 512
```

## Neo4j Setup

### Docker Compose Integration

Add to `deployments/server/docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  neo4j:
    image: neo4j:5.15-community
    container_name: crawl4ai-neo4j
    ports:
      - "7474:7474"  # HTTP Browser
      - "7687:7687"  # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-crawl4ai123}
      - NEO4J_PLUGINS=["apoc","graph-data-science"]
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
    networks:
      - crawl4ai-network
    restart: unless-stopped

  embedder-model:
    image: ghcr.io/ggerganov/llama.cpp:server
    container_name: crawl4ai-embedder
    ports:
      - "8081:8081"
    volumes:
      - ./models:/models
    command: >
      -m /models/embedder-model.gguf
      --port 8081
      --ctx-size 8192
      --temp 0.1
      --n-predict 1024
      --threads 8
    networks:
      - crawl4ai-network
    restart: unless-stopped

volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_import:

networks:
  crawl4ai-network:
    driver: bridge
```

### Environment Variables

Add to `.env`:

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=crawl4ai123

# Embedder Model Configuration
EMBEDDER_MODEL_URL=http://localhost:8081
EMBEDDER_MODEL_TEMPERATURE=0.1
EMBEDDER_MODEL_MAX_TOKENS=1024
EMBEDDER_MODEL_CONTEXT_SIZE=8192
```

## Implementation

### 1. Neo4j Schema Setup

Create `core/knowledge_graph/schema.cypher`:

```cypher
// Create constraints for unique entities
CREATE CONSTRAINT entity_name IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT content_id IF NOT EXISTS
FOR (c:Content) REQUIRE c.id IS UNIQUE;

// Create indexes for performance
CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity) ON (e.type);

CREATE INDEX entity_normalized IF NOT EXISTS
FOR (e:Entity) ON (e.normalized_name);

CREATE INDEX content_url IF NOT EXISTS
FOR (c:Content) ON (c.url);

// Entity types: Technology, Concept, Framework, Library, Language, Tool, Person, Company
// Relationship types: USES, IMPLEMENTS, PART_OF, SIMILAR_TO, BUILT_ON, RELATES_TO, MENTIONED_IN
```

### 2. LLM Entity Extractor

Create `core/knowledge_graph/extractor.py`:

```python
import os
import json
import httpx
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

class LLMEntityExtractor:
    def __init__(self):
        self.url = os.getenv("EMBEDDER_MODEL_URL", "http://localhost:8081")
        self.temperature = float(os.getenv("EMBEDDER_MODEL_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("EMBEDDER_MODEL_MAX_TOKENS", "1024"))
        self.timeout = 60.0

    async def extract_entities_and_relationships(
        self,
        content: str,
        url: str = ""
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Extract entities and relationships from content using LLM

        Returns:
            (entities, relationships)
        """
        prompt = self._build_extraction_prompt(content, url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.url}/completion",
                json={
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "n_predict": self.max_tokens,
                    "stop": ["</output>", "\n\n\n"]
                }
            )
            response.raise_for_status()
            result = response.json()

        # Parse LLM output
        llm_output = result.get("content", "")
        return self._parse_extraction_output(llm_output)

    def _build_extraction_prompt(self, content: str, url: str) -> str:
        # Truncate content to fit context window (leave room for prompt)
        max_content_length = 6000  # ~6k tokens for content, rest for instructions
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        return f"""You are a knowledge graph extraction system. Extract entities and relationships from the following web content.

URL: {url}

CONTENT:
{content}

INSTRUCTIONS:
1. Extract key entities (technologies, frameworks, concepts, tools, libraries, languages, companies, people)
2. Identify relationships between entities (USES, IMPLEMENTS, BUILT_ON, PART_OF, SIMILAR_TO, etc.)
3. Output ONLY valid JSON in this exact format:

{{
  "entities": [
    {{"name": "React", "type": "Framework", "context": "React is a JavaScript library"}},
    {{"name": "JavaScript", "type": "Language", "context": "programming language"}}
  ],
  "relationships": [
    {{"source": "React", "target": "JavaScript", "type": "BUILT_ON", "context": "React is built with JavaScript"}}
  ]
}}

OUTPUT JSON:
"""

    def _parse_extraction_output(self, llm_output: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse LLM JSON output into entities and relationships"""
        try:
            # Extract JSON from output (handle markdown code blocks)
            if "```json" in llm_output:
                json_start = llm_output.find("```json") + 7
                json_end = llm_output.find("```", json_start)
                llm_output = llm_output[json_start:json_end].strip()
            elif "```" in llm_output:
                json_start = llm_output.find("```") + 3
                json_end = llm_output.find("```", json_start)
                llm_output = llm_output[json_start:json_end].strip()

            data = json.loads(llm_output)

            entities = data.get("entities", [])
            relationships = data.get("relationships", [])

            # Normalize entity names
            for entity in entities:
                entity["normalized_name"] = entity["name"].lower().strip()

            return entities, relationships

        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM output as JSON: {e}", flush=True)
            print(f"Output was: {llm_output[:500]}", flush=True)
            return [], []
        except Exception as e:
            print(f"Error parsing extraction output: {e}", flush=True)
            return [], []
```

### 3. Neo4j Knowledge Graph Manager

Create `core/knowledge_graph/neo4j_manager.py`:

```python
import os
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class Neo4jKnowledgeGraph:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "crawl4ai123")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()

    def close(self):
        if self.driver:
            self.driver.close()

    def _initialize_schema(self):
        """Create constraints and indexes"""
        with self.driver.session() as session:
            # Constraints
            session.run("""
                CREATE CONSTRAINT entity_name IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.normalized_name IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT content_id IF NOT EXISTS
                FOR (c:Content) REQUIRE c.id IS UNIQUE
            """)

            # Indexes
            session.run("CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)")
            session.run("CREATE INDEX content_url IF NOT EXISTS FOR (c:Content) ON (c.url)")

    def store_content_graph(
        self,
        content_id: int,
        url: str,
        entities: List[Dict],
        relationships: List[Dict]
    ):
        """Store extracted knowledge graph for a piece of content"""
        with self.driver.session() as session:
            # Create or update Content node
            session.run("""
                MERGE (c:Content {id: $content_id})
                SET c.url = $url, c.updated_at = datetime()
            """, content_id=content_id, url=url)

            # Create Entity nodes and MENTIONS relationships
            for entity in entities:
                session.run("""
                    MERGE (e:Entity {normalized_name: $normalized_name})
                    SET e.name = $name,
                        e.type = $type,
                        e.last_seen = datetime()
                    WITH e
                    MATCH (c:Content {id: $content_id})
                    MERGE (c)-[m:MENTIONS]->(e)
                    SET m.context = $context
                """,
                    normalized_name=entity.get("normalized_name", entity["name"].lower()),
                    name=entity["name"],
                    type=entity.get("type", "Concept"),
                    content_id=content_id,
                    context=entity.get("context", "")
                )

            # Create relationships between entities
            for rel in relationships:
                session.run("""
                    MATCH (source:Entity {normalized_name: $source_name})
                    MATCH (target:Entity {normalized_name: $target_name})
                    MERGE (source)-[r:RELATES_TO {type: $rel_type}]->(target)
                    SET r.context = $context,
                        r.last_seen = datetime()
                """,
                    source_name=rel["source"].lower().strip(),
                    target_name=rel["target"].lower().strip(),
                    rel_type=rel.get("type", "RELATES_TO"),
                    context=rel.get("context", "")
                )

    def traverse_graph(
        self,
        start_entities: List[str],
        depth: int = 2,
        limit: int = 20
    ) -> List[Dict]:
        """Find content related to entities via graph traversal"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (start:Entity)-[*1..$depth]-(related:Entity)
                WHERE start.normalized_name IN $entities
                WITH related, length(path) as distance
                ORDER BY distance
                LIMIT $limit
                MATCH (c:Content)-[:MENTIONS]->(related)
                RETURN DISTINCT
                    c.id as content_id,
                    c.url as url,
                    related.name as entity_name,
                    related.type as entity_type,
                    distance
                ORDER BY distance, content_id
            """,
                entities=[e.lower().strip() for e in start_entities],
                depth=depth,
                limit=limit
            )

            return [dict(record) for record in result]

    def find_shortest_path(self, from_entity: str, to_entity: str) -> Optional[Dict]:
        """Find shortest path between two entities"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = shortestPath(
                    (start:Entity {normalized_name: $from_entity})-[*]-(end:Entity {normalized_name: $to_entity})
                )
                RETURN
                    [node in nodes(path) | node.name] as path_nodes,
                    [rel in relationships(path) | type(rel)] as path_relationships,
                    length(path) as path_length
            """,
                from_entity=from_entity.lower().strip(),
                to_entity=to_entity.lower().strip()
            )

            record = result.single()
            return dict(record) if record else None

    def get_entity_neighbors(self, entity_name: str, limit: int = 10) -> List[Dict]:
        """Get direct neighbors of an entity"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {normalized_name: $entity_name})-[r:RELATES_TO]-(neighbor:Entity)
                RETURN
                    neighbor.name as name,
                    neighbor.type as type,
                    r.type as relationship_type,
                    r.context as context
                LIMIT $limit
            """,
                entity_name=entity_name.lower().strip(),
                limit=limit
            )

            return [dict(record) for record in result]

    def find_central_entities(self, limit: int = 20) -> List[Dict]:
        """Find most connected entities (hubs) using degree centrality"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)-[r:RELATES_TO]-()
                WITH e, count(r) as degree
                ORDER BY degree DESC
                LIMIT $limit
                RETURN e.name as name, e.type as type, degree
            """, limit=limit)

            return [dict(record) for record in result]

    def remove_content_graph(self, content_id: int):
        """Remove content node and orphaned entities"""
        with self.driver.session() as session:
            # Remove content node
            session.run("MATCH (c:Content {id: $content_id}) DETACH DELETE c", content_id=content_id)

            # Remove orphaned entities (not mentioned by any content)
            session.run("""
                MATCH (e:Entity)
                WHERE NOT (e)<-[:MENTIONS]-(:Content)
                DETACH DELETE e
            """)
```

### 4. Update Storage Layer

Modify `core/data/storage.py`:

```python
# Add to imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge_graph.extractor import LLMEntityExtractor
from knowledge_graph.neo4j_manager import Neo4jKnowledgeGraph

class RAGDatabase:
    def __init__(self, db_path: str = None):
        # ... existing initialization ...

        # Initialize Knowledge Graph components
        self.use_kg = os.getenv("ENABLE_KNOWLEDGE_GRAPH", "false").lower() == "true"
        if self.use_kg:
            try:
                self.kg_extractor = LLMEntityExtractor()
                self.kg_manager = Neo4jKnowledgeGraph()
                print("✓ Knowledge Graph enabled (Neo4j + LLM Extractor)", flush=True)
            except Exception as e:
                print(f"⚠ Knowledge Graph disabled: {e}", flush=True)
                self.use_kg = False

    def close(self):
        # ... existing close code ...
        if self.use_kg and hasattr(self, 'kg_manager'):
            self.kg_manager.close()

    async def store_content(self, url: str, title: str, content: str, markdown: str,
                           retention_policy: str = 'permanent', tags: str = '',
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # ... existing store_content code ...

        # After storing in SQLite, extract and store in knowledge graph
        if self.use_kg:
            try:
                entities, relationships = await self.kg_extractor.extract_entities_and_relationships(
                    content, url
                )
                self.kg_manager.store_content_graph(
                    content_id, url, entities, relationships
                )
                print(f"✓ Stored {len(entities)} entities, {len(relationships)} relationships for {url}", flush=True)
            except Exception as e:
                print(f"⚠ Knowledge graph extraction failed: {e}", flush=True)

        return result

    def hybrid_search(self, query: str, limit: int = 5) -> List[Dict]:
        """Combine vector search with graph traversal"""
        # 1. Vector search (existing)
        vector_results = self.search_similar(query, limit=limit*2)

        # 2. Graph traversal search
        graph_content_ids = set()
        if self.use_kg:
            try:
                # Extract entities from query
                import asyncio
                entities, _ = asyncio.run(
                    self.kg_extractor.extract_entities_and_relationships(query, "")
                )
                entity_names = [e["name"] for e in entities[:3]]  # Top 3 entities

                if entity_names:
                    graph_results = self.kg_manager.traverse_graph(entity_names, depth=2, limit=20)
                    graph_content_ids = {r["content_id"] for r in graph_results}
            except Exception as e:
                print(f"Graph search failed: {e}", flush=True)

        # 3. Merge results
        all_content_ids = set()
        for r in vector_results:
            # Extract content_id from vector results
            cursor = self.execute_with_retry(
                'SELECT id FROM crawled_content WHERE url = ?', (r['url'],)
            )
            row = cursor.fetchone()
            if row:
                all_content_ids.add(row[0])

        all_content_ids.update(graph_content_ids)

        # Fetch full content
        if not all_content_ids:
            return vector_results[:limit]

        results = self.execute_with_retry('''
            SELECT url, title, content, timestamp, tags
            FROM crawled_content
            WHERE id IN ({})
            LIMIT ?
        '''.format(','.join('?' * len(all_content_ids))),
            (*all_content_ids, limit)
        ).fetchall()

        return [
            {
                'url': row[0],
                'title': row[1],
                'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                'timestamp': row[3],
                'tags': row[4]
            }
            for row in results
        ]

    def remove_content(self, url: str = None, session_only: bool = False) -> int:
        # Get content_id before deletion
        if url and self.use_kg:
            cursor = self.execute_with_retry(
                'SELECT id FROM crawled_content WHERE url = ?', (url,)
            )
            row = cursor.fetchone()
            if row:
                self.kg_manager.remove_content_graph(row[0])

        # ... existing removal code ...
```

### 5. Add New MCP Tools

Add to `core/rag_processor.py`:

```python
# Add to tools list in MCPServer.__init__
{
    "name": "explore_knowledge_graph",
    "description": "Explore knowledge graph starting from an entity, finding related entities and content",
    "inputSchema": {
        "type": "object",
        "properties": {
            "entity": {"type": "string", "description": "Starting entity name"},
            "depth": {"type": "integer", "description": "Traversal depth (1-3, default 2)"}
        },
        "required": ["entity"]
    }
},
{
    "name": "find_entity_path",
    "description": "Find shortest path between two entities in knowledge graph",
    "inputSchema": {
        "type": "object",
        "properties": {
            "from_entity": {"type": "string", "description": "Source entity"},
            "to_entity": {"type": "string", "description": "Target entity"}
        },
        "required": ["from_entity", "to_entity"]
    }
},
{
    "name": "list_central_entities",
    "description": "List most connected entities (knowledge hubs) in the graph",
    "inputSchema": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of results (default 20)"}
        }
    }
},
{
    "name": "hybrid_search",
    "description": "Search using both vector similarity and knowledge graph relationships",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Number of results (default 5)"}
        },
        "required": ["query"]
    }
}

# Add to tools/call handler
elif tool_name == "explore_knowledge_graph":
    entity = arguments["entity"]
    depth = arguments.get("depth", 2)
    if GLOBAL_DB.use_kg:
        graph_results = GLOBAL_DB.kg_manager.traverse_graph([entity], depth=depth)
        neighbors = GLOBAL_DB.kg_manager.get_entity_neighbors(entity)
        result = {
            "success": True,
            "entity": entity,
            "neighbors": neighbors,
            "related_content": graph_results
        }
    else:
        result = {"success": False, "error": "Knowledge Graph not enabled"}

elif tool_name == "find_entity_path":
    from_entity = arguments["from_entity"]
    to_entity = arguments["to_entity"]
    if GLOBAL_DB.use_kg:
        path = GLOBAL_DB.kg_manager.find_shortest_path(from_entity, to_entity)
        result = {"success": True, "path": path} if path else {"success": False, "error": "No path found"}
    else:
        result = {"success": False, "error": "Knowledge Graph not enabled"}

elif tool_name == "list_central_entities":
    limit = arguments.get("limit", 20)
    if GLOBAL_DB.use_kg:
        central = GLOBAL_DB.kg_manager.find_central_entities(limit)
        result = {"success": True, "central_entities": central}
    else:
        result = {"success": False, "error": "Knowledge Graph not enabled"}

elif tool_name == "hybrid_search":
    query = arguments["query"]
    limit = arguments.get("limit", 5)
    if GLOBAL_DB.use_kg:
        results = GLOBAL_DB.hybrid_search(query, limit)
        result = {"success": True, "results": results}
    else:
        # Fall back to regular vector search
        results = await GLOBAL_DB.search_similar(query, limit)
        result = {"success": True, "results": results, "note": "KG disabled, using vector search only"}
```

## Usage Examples

### 1. Enable Knowledge Graph

```bash
# In .env
ENABLE_KNOWLEDGE_GRAPH=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=crawl4ai123
EMBEDDER_MODEL_URL=http://localhost:8081
```

### 2. Start Services

```bash
cd deployments/server
docker-compose up -d neo4j embedder-model
docker-compose up -d api
```

### 3. Use via MCP

```python
# Crawl and auto-extract knowledge graph
await crawl_and_remember("https://react.dev/learn", tags="react,docs")

# Explore what's related to React
await explore_knowledge_graph("React", depth=2)
# Returns: neighbors (hooks, JSX, components) + related content

# Find connection between technologies
await find_entity_path("React", "TypeScript")
# Returns: React -> JavaScript -> TypeScript

# Hybrid search (vector + graph)
await hybrid_search("how to use hooks in react", limit=5)
# Returns: Combines semantic similarity with graph relationships
```

### 4. Direct Neo4j Queries

Access Neo4j Browser at `http://localhost:7474`

```cypher
// Visualize React ecosystem
MATCH path = (react:Entity {name: "React"})-[:RELATES_TO*1..2]-(related)
RETURN path
LIMIT 50

// Find most important technologies
MATCH (e:Entity)-[r:RELATES_TO]-()
WITH e, count(r) as connections
ORDER BY connections DESC
LIMIT 10
RETURN e.name, e.type, connections
```

## Performance Considerations

### LLM Extraction Optimization

1. **Chunking Strategy**: Process content in 6000-character chunks to stay within context limits
2. **Batch Processing**: Extract entities for multiple chunks in parallel
3. **Caching**: Cache entity extraction results by content_hash to avoid re-processing

### Neo4j Optimization

1. **Connection Pooling**: Neo4j driver uses connection pooling automatically
2. **Batch Writes**: Use transactions for bulk entity/relationship creation
3. **Index Tuning**: Ensure all lookup properties are indexed

### Resource Usage

- **Neo4j Memory**: 2GB heap + 1GB page cache (configured in docker-compose)
- **llama.cpp CPU**: 8 threads, adjust based on CPU cores
- **Network**: All services on same Docker network for low latency

## Troubleshooting

### LLM Extraction Failures

```python
# Check embedder model health
curl http://localhost:8081/health

# Test extraction manually
curl -X POST http://localhost:8081/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Extract entities from: React is a JavaScript framework", "temperature": 0.1, "n_predict": 512}'
```

### Neo4j Connection Issues

```bash
# Check Neo4j logs
docker logs crawl4ai-neo4j

# Test connection
docker exec -it crawl4ai-neo4j cypher-shell -u neo4j -p crawl4ai123
```

### Hybrid Search Not Working

```python
# Verify KG is enabled
from core.data.storage import GLOBAL_DB
print(f"KG Enabled: {GLOBAL_DB.use_kg}")

# Check entity count
GLOBAL_DB.kg_manager.driver.execute_query("MATCH (e:Entity) RETURN count(e)")
```

## Migration Path

### Phase 1: Enable for New Content Only
- Set `ENABLE_KNOWLEDGE_GRAPH=true`
- New crawls will populate KG automatically
- Old content uses vector search only

### Phase 2: Backfill Historical Content
```python
# Backfill script
from core.data.storage import GLOBAL_DB
import asyncio

async def backfill_kg():
    contents = GLOBAL_DB.list_content()
    for item in contents:
        content_row = GLOBAL_DB.execute_with_retry(
            'SELECT id, content FROM crawled_content WHERE url = ?',
            (item['url'],)
        ).fetchone()

        if content_row:
            content_id, content_text = content_row
            entities, rels = await GLOBAL_DB.kg_extractor.extract_entities_and_relationships(
                content_text, item['url']
            )
            GLOBAL_DB.kg_manager.store_content_graph(
                content_id, item['url'], entities, rels
            )
            print(f"✓ Backfilled {item['url']}")

asyncio.run(backfill_kg())
```

### Phase 3: Full Hybrid Search
- Update `search_memory` MCP tool to use `hybrid_search()` by default
- Monitor performance and tune parameters

## Future Enhancements

1. **Graph Algorithms**: Implement PageRank for entity importance
2. **Community Detection**: Cluster related entities into topics
3. **Temporal Graphs**: Track entity relationships over time
4. **Multi-modal**: Extract entities from images/diagrams in web pages
5. **Graph Embeddings**: Combine node2vec embeddings with text embeddings

## References

- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [llama.cpp Server API](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md)
- [Graph Data Science Library](https://neo4j.com/docs/graph-data-science/current/)
