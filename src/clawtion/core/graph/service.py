"""GraphRAG service for entity extraction and graph traversal.

Provides a :class:`GraphService` that manages entities and relations
extracted from document chunks, supporting N-hop graph traversal via
recursive SQL CTEs.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING, Any

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.client import EmbeddingClient

logger = get_logger(__name__)

# -- Built-in NER keyword lists for heuristic extraction --------------------

_PERSON_PATTERNS: list[str] = [
    r"[A-Z][a-z]+ [A-Z][a-z]+",  # "John Smith"
    r"Mr\. [A-Z][a-z]+",
    r"Ms\. [A-Z][a-z]+",
    r"Dr\. [A-Z][a-z]+",
    r"[A-Z][a-z]+先生",
    r"[A-Z][a-z]+さん",
]

_ORGANIZATION_PATTERNS: list[str] = [
    r"[A-Z][a-z]+ (?:Corporation|Corp|Inc|LLC|Ltd|Company|Co|Group)",
    r"[A-Z][A-Z]+[a-z]* (?:大学|研究所|庁|省|協会|委員会)",
    r"University of [A-Z][a-z]+",
]

_CONCEPT_TRIGGERS: list[str] = [
    r"concept of ([A-Za-z]+)",
    r"idea of ([A-Za-z]+)",
    r"the notion of ([A-Za-z]+)",
    r"([A-Z][a-z]+) is a (?:key |critical |important |central )?concept",
    r"([A-Z][a-z]+) refers to",
    r"([A-Z][a-z]+) is defined as",
]

_TECHNOLOGY_PATTERNS: list[str] = [
    r"[A-Z][a-z]+(?:QL|ML|AI|OS|API|SDK|DB)",
    r"Python|JavaScript|TypeScript|Rust|Go|Kotlin|Swift",
    r"React|Vue|Angular|Django|Flask|FastAPI|Spring",
    r"PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch",
    r"Docker|Kubernetes|Terraform|Ansible",
    r"AWS|Azure|GCP|OpenAI|Anthropic|Google|Microsoft",
]

_KNOWN_ENTITIES: dict[str, str] = {
    "clawtion": "Project",
    "GraphRAG": "Technique",
    "RAG": "Technique",
    "vector search": "Technique",
    "semantic search": "Technique",
    "embedding": "Technique",
    "chunking": "Technique",
    "knowledge base": "Concept",
    "MCP": "Protocol",
}


class GraphService:
    """Manages entities and relations for GraphRAG traversal.

    Provides methods for extracting entities from chunk text, adding
    entities/relations to the graph, and performing N-hop graph searches
    via recursive SQL CTEs.

    Constructor DI:
        ``db``: Database connection manager.
        ``embedder``: Embedding client (used for entity vectorisation).
    """

    def __init__(
        self,
        db: DatabaseManager,
        embedder: EmbeddingClient,
    ) -> None:
        self._db = db
        self._embedder = embedder

    # ------------------------------------------------------------------
    # Entity extraction (heuristic / keyword-based)
    # ------------------------------------------------------------------

    async def extract_entities(self, chunk_id: str) -> list[dict[str, Any]]:
        """Extract entities from a chunk using heuristic keyword matching.

        In production this would use an LLM; the current implementation
        applies a set of regex patterns and known-entity lookups.

        Args:
            chunk_id: The chunk UUID whose content should be analysed.

        Returns:
            A list of entity dicts with keys ``name``, ``entity_type``,
            and ``description``.

        Raises:
            ClawtionError: If the chunk does not exist.
        """
        row = await self._db.execute_one(
            "SELECT content, document_id FROM document_chunks WHERE chunk_id = :chunk_id",
            {"chunk_id": chunk_id},
        )
        if row is None:
            raise ClawtionError(
                code="CHUNK_NOT_FOUND",
                message=f"Chunk {chunk_id} not found for entity extraction.",
            )

        content: str = row["content"]
        entities: dict[str, dict[str, Any]] = {}

        # 1. Known entity lookups
        for name, etype in _KNOWN_ENTITIES.items():
            if name.lower() in content.lower():
                key = f"{name}:{etype}"
                if key not in entities:
                    entities[key] = {
                        "name": name,
                        "entity_type": etype,
                        "description": "",
                    }

        # 2. Person patterns
        for pattern in _PERSON_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(0)
                key = f"{name}:person"
                if key not in entities:
                    entities[key] = {
                        "name": name,
                        "entity_type": "person",
                        "description": "",
                    }

        # 3. Organisation patterns
        for pattern in _ORGANIZATION_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(0)
                key = f"{name}:organization"
                if key not in entities:
                    entities[key] = {
                        "name": name,
                        "entity_type": "organization",
                        "description": "",
                    }

        # 4. Technology / product patterns
        for pattern in _TECHNOLOGY_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(0)
                key = f"{name}:technology"
                if key not in entities:
                    entities[key] = {
                        "name": name,
                        "entity_type": "technology",
                        "description": "",
                    }

        # 5. Concept triggers
        for pattern in _CONCEPT_TRIGGERS:
            for match in re.finditer(pattern, content):
                name = match.group(1) if match.lastindex else match.group(0)
                key = f"{name}:concept"
                if key not in entities:
                    entities[key] = {
                        "name": name,
                        "entity_type": "concept",
                        "description": "",
                    }

        logger.info(
            "Entity extraction complete",
            chunk_id=chunk_id,
            entity_count=len(entities),
        )
        return list(entities.values())

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    async def add_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
    ) -> str:
        """Add a new entity to the graph.

        If an entity with the same ``(name, entity_type)`` already exists,
        its existing ID is returned instead of creating a duplicate.

        Args:
            name: Entity display name.
            entity_type: Type classifier (e.g. ``"person"``, ``"technology"``).
            description: Optional human-readable description.

        Returns:
            The UUID of the created (or existing) entity.
        """
        entity_id = str(uuid.uuid4())

        # Check for existing entity with same name+type
        existing = await self._db.execute_one(
            "SELECT entity_id FROM entities WHERE name = :name AND entity_type = :entity_type",
            {"name": name, "entity_type": entity_type},
        )
        if existing is not None:
            logger.info(
                "Entity already exists, returning existing",
                entity_id=existing["entity_id"],
                name=name,
                entity_type=entity_type,
            )
            return str(existing["entity_id"])

        await self._db.execute(
            """
            INSERT INTO entities (entity_id, name, entity_type, description)
            VALUES (:entity_id, :name, :entity_type, :description)
            """,
            {
                "entity_id": entity_id,
                "name": name,
                "entity_type": entity_type,
                "description": description,
            },
        )

        # Generate and store embedding for the entity
        try:
            desc_text = f"{name}: {description}" if description else name
            embedding_result = await self._embedder.embed_document(desc_text)
            embedding_json = json.dumps(embedding_result.embedding)
            await self._db.execute(
                """
                UPDATE entities
                SET embedding = CAST(:embedding AS vector)
                WHERE entity_id = :entity_id
                """,
                {
                    "entity_id": entity_id,
                    "embedding": embedding_json,
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to generate entity embedding",
                entity_id=entity_id,
                error=str(exc),
            )

        logger.info(
            "Entity created",
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
        )
        return entity_id

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Retrieve an entity by its ID.

        Args:
            entity_id: The entity UUID.

        Returns:
            An entity dict or ``None`` if not found.
        """
        row = await self._db.execute_one(
            "SELECT entity_id, name, entity_type, description, created_at FROM entities WHERE entity_id = :entity_id",
            {"entity_id": entity_id},
        )
        if row is None:
            return None
        return {
            "entity_id": str(row["entity_id"]),
            "name": row["name"],
            "entity_type": row["entity_type"],
            "description": row["description"],
            "created_at": (
                row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])
            ),
        }

    async def find_entity_by_name(
        self,
        name: str,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find entities by name (case-insensitive partial match).

        Args:
            name: Entity name to search for.
            entity_type: Optional type filter.

        Returns:
            A list of matching entity dicts.
        """
        if entity_type:
            rows = await self._db.execute(
                """
                SELECT entity_id, name, entity_type, description, created_at
                FROM entities
                WHERE name ILIKE :name AND entity_type = :entity_type
                ORDER BY name
                """,
                {"name": f"%{name}%", "entity_type": entity_type},
            )
        else:
            rows = await self._db.execute(
                """
                SELECT entity_id, name, entity_type, description, created_at
                FROM entities
                WHERE name ILIKE :name
                ORDER BY name
                """,
                {"name": f"%{name}%"},
            )
        return [
            {
                "entity_id": str(r["entity_id"]),
                "name": r["name"],
                "entity_type": r["entity_type"],
                "description": r["description"],
                "created_at": (
                    r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"])
                ),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Relation CRUD
    # ------------------------------------------------------------------

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        chunk_id: str | None = None,
    ) -> str:
        """Add a directed relation between two entities.

        If an identical relation already exists, its ID is returned.

        Args:
            source_id: UUID of the source entity.
            target_id: UUID of the target entity.
            relation_type: Semantic relation label (e.g. ``"uses"``, ``"mentions"``).
            weight: Numeric weight for scoring (default 1.0).
            chunk_id: Optional chunk UUID where this relation was observed.

        Returns:
            The UUID of the created (or existing) relation.
        """
        relation_id = str(uuid.uuid4())

        # Check for existing identical relation
        existing = await self._db.execute_one(
            """
            SELECT relation_id FROM relations
            WHERE source_entity_id = :source_id
              AND target_entity_id = :target_id
              AND relation_type = :relation_type
            """,
            {
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
            },
        )
        if existing is not None:
            return str(existing["relation_id"])

        await self._db.execute(
            """
            INSERT INTO relations
                (relation_id, source_entity_id, target_entity_id,
                 relation_type, weight, source_chunk_id)
            VALUES
                (:relation_id, :source_id, :target_id,
                 :relation_type, :weight, :chunk_id)
            """,
            {
                "relation_id": relation_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "weight": weight,
                "chunk_id": chunk_id,
            },
        )

        logger.info(
            "Relation created",
            relation_id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
        )
        return relation_id

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    async def graph_search(
        self,
        starting_entity: str,
        max_hops: int = 2,
        relation_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Traverse the entity graph from a starting entity using a recursive CTE.

        Args:
            starting_entity: Entity name (or UUID) to start traversal from.
            max_hops: Maximum number of relation hops (default 2).
            relation_types: Optional list of relation types to restrict traversal.

        Returns:
            A dict with:
                - ``"entities"``: list of visited entity dicts
                - ``"relations"``: list of traversed relation dicts
                - ``"graph"``: adjacency list representation

        Raises:
            ClawtionError: If the starting entity is not found.
        """
        # Resolve starting entity
        entity = await self._db.execute_one(
            """
            SELECT entity_id, name, entity_type, description
            FROM entities
            WHERE entity_id = :entity_id OR name = :entity_id
            """,
            {"entity_id": starting_entity},
        )
        if entity is None:
            raise ClawtionError(
                code="ENTITY_NOT_FOUND",
                message=f"Starting entity not found: {starting_entity}",
            )

        start_id: str = str(entity["entity_id"])

        # Build relation type filter clause
        type_filter = ""
        params: dict[str, Any] = {
            "start_id": start_id,
            "max_hops": max_hops,
        }
        if relation_types:
            placeholders = [f":rt_{i}" for i in range(len(relation_types))]
            type_filter = f"AND r.relation_type IN ({', '.join(placeholders)})"
            for i, rt in enumerate(relation_types):
                params[f"rt_{i}"] = rt

        # Recursive CTE for N-hop traversal
        cte = f"""
            WITH RECURSIVE graph_traversal AS (
                -- Anchor: find all relations from the starting entity
                SELECT
                    r.relation_id,
                    r.source_entity_id,
                    r.target_entity_id,
                    r.relation_type,
                    r.weight,
                    1 AS hop
                FROM relations r
                WHERE r.source_entity_id = :start_id
                  {type_filter}

                UNION

                -- Recursive: expand from newly reached entities
                SELECT
                    r.relation_id,
                    r.source_entity_id,
                    r.target_entity_id,
                    r.relation_type,
                    r.weight,
                    gt.hop + 1
                FROM relations r
                INNER JOIN graph_traversal gt
                    ON r.source_entity_id = gt.target_entity_id
                WHERE gt.hop < :max_hops
                  {type_filter if not relation_types else "AND r.relation_type IN (" + ", ".join(f":rt_{i}" for i in range(len(relation_types))) + ")"}
            )
            SELECT DISTINCT
                gt.relation_id,
                gt.source_entity_id,
                gt.target_entity_id,
                gt.relation_type,
                gt.weight,
                gt.hop
            FROM graph_traversal gt
            ORDER BY gt.hop, gt.relation_type
        """

        rows = await self._db.execute(cte, params)

        # Collect visited entity IDs and relation data
        visited_entity_ids: set[str] = set()
        relations_list: list[dict[str, Any]] = []
        adjacency: dict[str, list[dict[str, Any]]] = {}

        for r in rows:
            src = str(r["source_entity_id"])
            tgt = str(r["target_entity_id"])
            visited_entity_ids.add(src)
            visited_entity_ids.add(tgt)

            rel: dict[str, Any] = {
                "relation_id": str(r["relation_id"]),
                "source_entity_id": src,
                "target_entity_id": tgt,
                "relation_type": r["relation_type"],
                "weight": float(r["weight"]),
                "hop": int(r["hop"]),
            }
            relations_list.append(rel)

            # Build adjacency
            adjacency.setdefault(src, []).append(
                {
                    "entity_id": tgt,
                    "relation_type": r["relation_type"],
                    "weight": float(r["weight"]),
                    "hop": int(r["hop"]),
                }
            )

        # Fetch entity details for all visited entities
        if visited_entity_ids:
            entity_ids_list = list(visited_entity_ids)
            placeholders = [f":eid_{i}" for i in range(len(entity_ids_list))]
            entity_params: dict[str, Any] = {}
            for i, eid in enumerate(entity_ids_list):
                entity_params[f"eid_{i}"] = eid

            entity_rows = await self._db.execute(
                f"""
                SELECT entity_id, name, entity_type, description
                FROM entities
                WHERE entity_id IN ({", ".join(placeholders)})
                """,
                entity_params,
            )
            entities_map: dict[str, dict[str, Any]] = {}
            for er in entity_rows:
                eid = str(er["entity_id"])
                entities_map[eid] = {
                    "entity_id": eid,
                    "name": er["name"],
                    "entity_type": er["entity_type"],
                    "description": er["description"],
                }
            # Include the starting entity even if no relations exist
            if start_id not in entities_map:
                entities_map[start_id] = {
                    "entity_id": start_id,
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "description": entity["description"],
                }
            entities_list = list(entities_map.values())
        else:
            entities_list = [
                {
                    "entity_id": start_id,
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "description": entity["description"],
                }
            ]

        return {
            "entities": entities_list,
            "relations": relations_list,
            "graph": adjacency,
            "start_entity_id": start_id,
            "total_entities": len(entities_list),
            "total_relations": len(relations_list),
            "max_hops_reached": max_hops,
        }

    async def find_related(self, chunk_id: str, max_hops: int = 1) -> list[dict[str, Any]]:
        """Find chunks related to a given chunk via shared entities.

        Traces the entity graph: finds entities mentioned in ``chunk_id``,
        then follows relations to discover other chunks that reference
        the same entities.

        Args:
            chunk_id: The anchor chunk UUID.
            max_hops: Entity graph traversal depth (default 1).

        Returns:
            A list of related chunk dicts with entity context.
        """
        # 1. Find entities associated with this chunk via relations
        entity_rows = await self._db.execute(
            """
            SELECT DISTINCT e.entity_id, e.name, e.entity_type
            FROM entities e
            JOIN relations r ON r.source_entity_id = e.entity_id
                OR r.target_entity_id = e.entity_id
            WHERE r.source_chunk_id = :chunk_id
            """,
            {"chunk_id": chunk_id},
        )

        if not entity_rows:
            return []

        entity_ids = [str(r["entity_id"]) for r in entity_rows]

        # 2. For each entity, find related chunks through relations
        entity_placeholders = [f":eid_{i}" for i in range(len(entity_ids))]
        entity_params: dict[str, Any] = {}
        for i, eid in enumerate(entity_ids):
            entity_params[f"eid_{i}"] = eid

        related_chunks = await self._db.execute(
            f"""
            SELECT DISTINCT
                dc.chunk_id,
                dc.document_id,
                dc.content,
                dc.chunk_level,
                dc.chunk_index,
                d.file_path,
                d.title,
                e.name AS entity_name,
                e.entity_type AS entity_type,
                r.relation_type
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            JOIN relations r ON r.source_chunk_id = dc.chunk_id
            JOIN entities e ON e.entity_id IN (
                CASE WHEN r.source_entity_id = e.entity_id
                     THEN r.source_entity_id
                     ELSE r.target_entity_id
                END
            )
            WHERE e.entity_id IN ({", ".join(entity_placeholders)})
              AND dc.chunk_id != :chunk_id
            ORDER BY dc.chunk_index
            """,
            {**entity_params, "chunk_id": chunk_id},
        )

        # 3. Group by chunk_id
        chunk_map: dict[str, dict[str, Any]] = {}
        for c in related_chunks:
            cid = str(c["chunk_id"])
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "chunk_id": cid,
                    "document_id": str(c["document_id"]),
                    "content_preview": c["content"][:200] if c["content"] else "",
                    "chunk_level": c["chunk_level"],
                    "chunk_index": c["chunk_index"],
                    "file_path": c["file_path"],
                    "title": c["title"],
                    "entities": [],
                }
            chunk_map[cid]["entities"].append(
                {
                    "name": c["entity_name"],
                    "entity_type": c["entity_type"],
                    "relation_type": c["relation_type"],
                }
            )

        logger.info(
            "Related chunks found",
            chunk_id=chunk_id,
            related_count=len(chunk_map),
        )
        return list(chunk_map.values())

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def extract_and_store(self, chunk_id: str) -> dict[str, Any]:
        """Extract entities from a chunk and store them along with relations.

        This is a convenience method that calls ``extract_entities``,
        then ``add_entity`` for each, and creates simple ``"co_occurs"``
        relations between entities found in the same chunk.

        Args:
            chunk_id: The chunk UUID to process.

        Returns:
            A dict with:
                - ``"entities_created"``: count of new entities
                - ``"relations_created"``: count of new relations
                - ``"entities"``: list of entity IDs
                - ``"relations"``: list of relation IDs
        """
        extracted = await self.extract_entities(chunk_id)

        entity_ids: list[str] = []
        for ent in extracted:
            eid = await self.add_entity(
                name=ent["name"],
                entity_type=ent["entity_type"],
                description=ent.get("description", ""),
            )
            entity_ids.append(eid)

        # Create co-occurrence relations between all entities found together
        relation_ids: list[str] = []
        for i in range(len(entity_ids)):
            for j in range(i + 1, len(entity_ids)):
                rid = await self.add_relation(
                    source_id=entity_ids[i],
                    target_id=entity_ids[j],
                    relation_type="co_occurs",
                    weight=1.0,
                    chunk_id=chunk_id,
                )
                relation_ids.append(rid)

        return {
            "entities_created": len(entity_ids),
            "relations_created": len(relation_ids),
            "entity_ids": entity_ids,
            "relation_ids": relation_ids,
        }
