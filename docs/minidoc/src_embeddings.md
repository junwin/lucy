```markdown
---
tags:
  - src_embeddings
  - lucyproject
  - DistanceMetric
  - EmbeddingFacade
  - EmbeddingModelInfo
---

## 1. Summary
The `src.embeddings` module is responsible for generating and comparing embeddings, which are numerical representations of data (like text) that capture semantic meaning. This module serves as a crucial component in the overall architecture, enabling applications to perform similarity searches, ranking, and other operations based on vector representations. By providing utilities for both embedding generation and vector comparison, it addresses the need for efficient and effective similarity assessments in various machine learning and natural language processing tasks.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Facade Pattern**: The `EmbeddingFacade` class acts as a single entry point for embedding generation and comparison, simplifying interactions for consumers.
- **Enum for Constants**: The `DistanceMetric` enum provides a clear and type-safe way to specify different distance metrics for vector comparisons.

Classes within the module exhibit a composition relationship, where `EmbeddingFacade` utilizes the `EmbeddingApi` for generating embeddings and the comparison functions for evaluating similarity. The design also includes a registry pattern in `registry.py`, which maintains metadata about known embedding models, allowing for easy retrieval and management of model information.

There is no explicit legacy or v2 split in the current implementation, but the presence of a legacy model in the registry indicates a potential for backward compatibility. Important design decisions are reflected in the clear separation of concerns, with distinct files handling different aspects of embedding functionality.

## 3. Key Classes
| Class                | Base/Parent | Purpose                                                                 |
|----------------------|--------------|-------------------------------------------------------------------------|
| DistanceMetric       | Enum         | Defines various distance metrics for vector comparison.                 |
| EmbeddingFacade      | N/A          | Provides a unified interface for embedding generation and comparison.    |
| EmbeddingModelInfo   | N/A          | Holds metadata for known embedding models.                              |

## 4. Source Files
| File                          | Responsibility                                           | Notable Exports                                      |
|-------------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `src/embeddings/__init__.py`  | Initializes the module and exports key components.     | DistanceMetric, cosine_similarity, rank, top_k, EmbeddingFacade, EmbeddingModelInfo, get_model_info, known_models |
| `src/embeddings/comparison.py`| Provides vector comparison utilities and scoring.      | DistanceMetric, cosine_similarity, rank, top_k     |
| `src/embeddings/facade.py`    | Implements the EmbeddingFacade for embedding operations.| EmbeddingFacade                                     |
| `src/embeddings/registry.py`  | Manages known embedding models and their metadata.     | get_model_info, known_models                        |

## 5. Dependencies
- **Standard library**:
  - `enum`
  - `math`
  - `typing`
  - `dataclasses`
  
- **Third-party packages**:
  - `galet` (for embedding generation)

- **Internal modules**:
  - `src.embeddings.comparison`
  - `src.embeddings.registry`

- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls                      |
|--------------------|--------|---------|---------------------------------------|
| None               | N/A    | N/A     | None                                  |

## 7. Exceptions
| Exception          | Base         | When Raised                                      |
|--------------------|--------------|-------------------------------------------------|
| None               | N/A          | None                                            |

## 8. Module-Level Constants
| Constant           | Value        |
|--------------------|--------------|
| None               | N/A          |

## 9. Methods (by class)

### DistanceMetric
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    | N/A  | N/A       | N/A         |

### EmbeddingFacade
| Method            | Type         | Signature                                                                 | Description |
|-------------------|--------------|---------------------------------------------------------------------------|-------------|
| __init__          | Instance     | `def __init__(self, *, embedding_api: Optional[EmbeddingApi] = None)`  | Initializes the facade, optionally taking an embedding API. |
| embed             | Instance     | `def embed(self, texts: List[str], *, model: str) -> EmbeddingResponse`| Generates embeddings for given texts using the specified model. Returns an `EmbeddingResponse`. |
| cosine_similarity  | Instance     | `def cosine_similarity(self, a: List[float], b: List[float]) -> float` | Computes cosine similarity between two vectors. Returns a float in the range [-1, 1]. |
| rank              | Instance     | `def rank(self, query: List[float], candidates: List[List[float]], *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[float]` | Scores candidates against a query vector, returning a list of scores. |
| top_k             | Instance     | `def top_k(self, query: List[float], candidates: List[List[float], k: int, *, metric: DistanceMetric = DistanceMetric.COSINE) -> List[Tuple[int, float]]` | Returns the top-k candidates and their scores, sorted by similarity. |
| model_info        | Instance     | `def model_info(self, model: str) -> Optional[EmbeddingModelInfo]`    | Retrieves metadata for a specified embedding model. |

### EmbeddingModelInfo
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    | N/A  | N/A       | N/A         |

## 10. Usage Examples
```python
from src.embeddings import EmbeddingFacade, DistanceMetric

facade = EmbeddingFacade()
response = facade.embed(["hello world"], model="text-embedding-3-small")
vector = response.embeddings[0]

similarity_score = facade.cosine_similarity(vector_a, vector_b)
ranked_candidates = facade.top_k(query_vector, candidate_vectors, k=5, metric=DistanceMetric.COSINE)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module raises `ValueError` for dimension mismatches in vector comparisons, ensuring robustness against incorrect input.
- **Zero-Length Vectors**: The cosine similarity function returns 0.0 for zero-length vectors, which may lead to unexpected results if not handled properly.
- **Thread Safety**: The current implementation does not explicitly address thread safety, which may be a concern in multi-threaded environments.
- **Known Limitations**: The module assumes that input vectors are of the same dimension, which must be validated by the user.

## 12. Consumers
| Consumer            | What it uses                                      |
|---------------------|--------------------------------------------------|
| Unknown             | Unknown — trace imports to confirm.              |
```