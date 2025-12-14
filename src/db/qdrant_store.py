import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
)

from db.vector_store import SearchResult, VectorRecord, VectorStore, UpsertResult
from qdrant_client.models import FieldCondition, MatchValue

from embedding_manager.embedding_backend import EmbeddingModel


# create Qdrant specific access filter
def build_access_filter(access_constraints: dict) -> Optional[Filter]:
    """
    Restrict read access to documents that belong to the provided constraints. (user_id only for now)
    """
    if not access_constraints or "user_id" not in access_constraints:
        raise PermissionError("No user_id in access constraints")  # will this break app execution? should be unreachable anyways...
    return Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=access_constraints["user_id"]),
            )
        ]
    )


class QdrantVectorStore(VectorStore):

    # IMPORTANT: make sure you have the Qdrant docker container up-and-running -> docker run -p 6333:6333 qdrant/qdrant (in terminal)
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = AsyncQdrantClient(host=host, port=port)

    async def get_or_create_collection(self, name: str, dim: int) -> None:
        # create_collection is idempotent; but might as well check existence first with get_collection
        try:
            await self.client.get_collection(name)
        except Exception:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert_records(
        self,
        collection: str,
        records: List[VectorRecord],
        ) -> UpsertResult:
        # create new database entries
        points: List[PointStruct] = []
        for record in records:

            if record.id is None:
                # no ID provided: generate a random unique ID fixme record cannot be overwritten, replaced, or updated since same doc (without identifier) would result in different 'point_id'
                point_id = (str(uuid.uuid4()))
            else:
                # convert whatever ID is given into UUIDv5 based on its string fixme upsert/overwrite semantics only when ID is unique
                point_id = (str(uuid.uuid5(uuid.NAMESPACE_DNS, str(record.id))))

            points.append(PointStruct(id=point_id, vector=record.vector, payload=record.metadata))

        # upload them to the database
        update_result = await self.client.upsert(
            collection_name=collection,
            points=points,
            wait=True,
        )

        # normalize qdrant status to a plain lowercase string
        status_raw = getattr(update_result, "status", None)
        if status_raw is None and isinstance(update_result, dict):
            status_raw = update_result.get("status")

        # enum-safe: UpdateStatus.COMPLETED → "completed"
        status_str = getattr(status_raw, "value", status_raw)
        status_str = str(status_str).lower()

        is_ok = status_str in ("completed", "acknowledged")

        return UpsertResult(
            status="ok" if is_ok else "error",
            indexed_count=len(records) if is_ok else 0,
            failed_ids=[] if is_ok else [str(r.id) for r in records if r.id is not None],
            raw=update_result,
        )

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        access_constraints: dict,
    ) -> List[SearchResult]:
        response = await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=k,
            query_filter=build_access_filter(access_constraints),  # create actual Qdrant filter implementation
            with_vectors=False,
            with_payload=True,
        )

        # obtain database entries that fulfill query (filtered due to attribute / within first k nearest / etc.)
        points = response.points

        # each p is a ScoredPoint
        results = []
        for p in points:
            results.append(
                SearchResult(
                    id=p.id,  # the unique UUID point ID
                    score=p.score,  # similarity score to query_vector
                    metadata=p.payload  # the created metadata incl. {text:"", idx:"", topic:"", user_id:""}
                )
            )

        return results

    #################################
    # ---- FOR DEMO PURPOSE ONLY ----
    #################################
    async def bootstrap_demo_corpus(
            self,
            embedding_model,
            user = "user",
            collection: str = "demo_corpus",
    ) -> None:
        """
        Creates a small demo corpus with pre-defined sentences.
        Is called once during 'middleware_application.py' startup to ingest some data into the Qdrant docker container.
        The resulting collection will only be available for queries with username: "user".
        """
        # dummy data to be stored in the database
        sentences = [
            "The red lighthouse stood at the edge of the harbor, blinking once every five seconds.",
            "A cargo ship entered the harbor just before sunrise on Tuesday morning.",
            "The lighthouse keeper logged the ship’s arrival in a handwritten notebook.",
            "Saltwater corrosion forced the lighthouse to undergo repairs last winter.",
            "Tourists often take photos of the lighthouse during summer afternoons.",

            "A small coffee shop opened across the street from the train station.",
            "The coffee shop serves espresso made from beans sourced in Ethiopia.",
            "Commuters stop at the coffee shop before boarding the 7:30 a.m. train.",
            "The train station was renovated to include digital departure boards.",
            "A delayed train caused a long line at the coffee shop counter.",

            "The software engineer deployed a new API endpoint on Friday night.",
            "A monitoring alert triggered after the API response time exceeded two seconds.",
            "The engineer rolled back the deployment to restore system stability.",
            "Logs showed a spike in database read latency during peak traffic.",
            "The incident report recommended adding better caching layers.",

            "A golden retriever slept under the kitchen table during the storm.",
            "Thunder rattled the windows as heavy rain fell outside the house.",
            "The dog woke up when a loud crack of thunder echoed nearby.",
            "Power briefly went out during the worst part of the storm.",
            "Candles were used to light the living room until electricity returned.",

            "The museum displayed a newly restored Renaissance painting.",
            "Art historians debated the painting’s true origin for decades.",
            "Infrared imaging revealed an earlier sketch beneath the visible paint.",
            "The museum curator organized a lecture about the restoration process.",
            "Visitors gathered quietly around the painting on opening day.",

            "A farmer checked soil moisture levels early in the morning.",
            "The wheat crop showed signs of drought stress in the southern field.",
            "An irrigation system was activated to compensate for low rainfall.",
            "Weather forecasts predicted continued dry conditions for the week.",
            "The farmer adjusted planting schedules based on climate data.",

            "A startup announced a seed funding round led by a venture capital firm.",
            "The founders pitched their idea at a technology conference last year.",
            "The product focuses on automating customer support workflows.",
            "Early users reported improved response times after adoption.",
            "The startup plans to hire three additional engineers.",

            "A mountain trail closed temporarily due to falling rocks.",
            "Park rangers placed warning signs at the trail entrance.",
            "Hikers were redirected to an alternate scenic route.",
            "Heavy snowfall earlier in the season contributed to unstable terrain.",
            "The trail is expected to reopen after safety inspections.",

            "A history book described the rise of trade routes across Asia.",
            "Silk and spices were transported along routes connecting distant empires.",
            "Merchants relied on caravans to cross vast deserts safely.",
            "Trade routes influenced cultural exchange between civilizations.",
            "Modern highways often follow paths similar to ancient routes.",

            "A student submitted a research paper on renewable energy storage.",
            "The paper analyzed lithium-ion battery degradation over time.",
            "Peer reviewers requested additional experimental data.",
            "The student revised the methodology section accordingly.",
            "The paper was accepted by an academic journal.",

            "A chef experimented with a new sourdough bread recipe.",
            "The dough fermented for thirty-six hours before baking.",
            "Higher hydration levels produced a more open crumb structure.",
            "The bread developed a dark, crispy crust in the oven.",
            "Customers praised the bread’s complex flavor.",

            "A city council meeting discussed new zoning regulations.",
            "Residents expressed concerns about increased building height limits.",
            "The proposal included incentives for green rooftops.",
            "Urban planners presented data on population growth.",
            "The vote was postponed until next month.",

            "A biologist tracked wolf populations using GPS collars.",
            "Migration patterns shifted after changes in prey availability.",
            "Data indicated improved survival rates among younger wolves.",
            "Conservation funding supported long-term monitoring efforts.",
            "The study was published in a wildlife journal.",

            "A novelist outlined the plot of a mystery thriller.",
            "The story takes place in a remote coastal town.",
            "A missing person case drives the central conflict.",
            "Clues are hidden in seemingly ordinary conversations.",
            "The final chapter reveals an unexpected connection.",

            "A fitness app released an update improving activity tracking accuracy.",
            "Users reported fewer GPS dropouts during outdoor runs.",
            "Battery consumption decreased after the update.",
            "The development team optimized background processes.",
            "App store ratings increased following the release.",

            "A teacher prepared lesson plans for the upcoming semester.",
            "The curriculum includes project-based learning activities.",
            "Students will collaborate in small groups.",
            "Assessment methods emphasize critical thinking skills.",
            "The school approved additional classroom resources.",

            "A space telescope detected unusual fluctuations in starlight.",
            "Astronomers suspected the presence of an exoplanet.",
            "Follow-up observations confirmed a periodic transit pattern.",
            "The planet orbits its star every twelve days.",
            "Findings were shared at an international astronomy conference.",

            "A supply chain disruption delayed electronic component shipments.",
            "Manufacturers adjusted production schedules accordingly.",
            "Alternative suppliers were evaluated for reliability.",
            "Logistics costs increased due to expedited shipping.",
            "Normal operations resumed after two weeks.",

            "A journalist interviewed residents after the flood.",
            "Many homes suffered water damage from the rising river.",
            "Emergency crews distributed food and clean water.",
            "Recovery efforts focused on infrastructure repair.",
            "The article highlighted community resilience.",

            "A data scientist trained a model on anonymized user data.",
            "Feature selection improved prediction accuracy.",
            "Cross-validation reduced the risk of overfitting.",
            "The model was deployed behind an internal API.",
            "Performance metrics were monitored in real time."
        ]
        vectors = await get_or_create_embeddings(sentences=sentences, embedding_model=embedding_model, name=embedding_model.name)

        # ensure collection exists
        dim = embedding_model.dim
        await self.get_or_create_collection(collection, dim)

        # create a new database-agnostic data transfer object for each document/text we want to upload
        records: List[VectorRecord] = []
        for idx, (sentence, vector) in enumerate(zip(sentences, vectors)):
            # data to store
            metadata: Dict[str, Any] = {
                "text": sentence,
                "user_id": user,
            }
            records.append(
                VectorRecord(
                    id=str(idx+1),  # needed to create unique point IDs (see upsert_points() above) fixme indexing from 0 is prone to accidental overwrites
                    vector=vector,
                    metadata=metadata,
                )
            )

        await self.upsert_records(
            collection=collection,
            records=records,
        )


async def get_or_create_embeddings(sentences: List[str], embedding_model: EmbeddingModel ,name: str) -> List[List[float]]:
    """
    Load cached embeddings if they exist, otherwise compute and save them.
    """
    # out_path = Path("demo_utils")
    BASE_DIR = Path(__file__).resolve().parent
    out_path = BASE_DIR / "demo_utils"
    out_path.mkdir(parents=True, exist_ok=True)

    file_path = out_path / f"embeddings_{name}.npy"

    # ----- load artifact if it already exists -----
    if file_path.exists():
        return np.load(file_path).tolist()

    # ----- create artifact -----
    vectors: List[List[float]] = embedding_model.embed(sentences)

    arr = np.asarray(vectors, dtype=np.float32)
    np.save(file_path, arr)

    return vectors

