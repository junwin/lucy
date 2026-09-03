# src_metrics.md

## YAML Front Matter
```yaml
tags:
  - src_metrics
  - lucyproject
  - RunMetricsLogger
  - CorrelationLogHandler
  - MetricsRepository
```

## 1. Summary
The `src/metrics` module is responsible for logging and querying metrics related to FCP (First Contentful Paint) runs. It provides a structured way to record metrics in an append-only JSONL format and allows for querying these records based on various filters. This module fits into the overall architecture by serving as a metrics logging and retrieval system, addressing the need for performance monitoring and analysis in applications that utilize FCP metrics.

## 2. Architecture & Design
The module employs several design patterns:
- **Single Responsibility Principle**: Each class has a distinct responsibility, such as logging metrics, counting log records, or querying metrics.
- **Composition**: The `CorrelationLogHandler` uses `RequestContext` to manage correlation IDs, while `MetricsRepository` relies on `RunMetrics` for data representation.
- **Error Handling**: The module includes robust error handling, particularly in the `MetricsRepository`, where it tolerates missing files and malformed entries.

The design decisions are evident in the use of context management for thread safety in `CorrelationLogHandler` and the careful parsing of timestamps in `MetricsRepository`. The module does not appear to have a legacy/v2 split, indicating a relatively straightforward evolution of its design.

## 3. Key Classes
| Class                  | Base/Parent            | Purpose                                                                 |
|------------------------|------------------------|-------------------------------------------------------------------------|
| `RunMetricsLogger`     | None                   | Appends metrics records to a JSONL file.                               |
| `CorrelationLogHandler`| `logging.Handler`      | Counts ERROR/WARNING log records per correlation ID.                   |
| `MetricsRepository`     | None                   | Queries and filters metrics records from the JSONL log.                |

## 4. Source Files
| File                          | Responsibility                                           | Notable Exports                          |
|-------------------------------|---------------------------------------------------------|------------------------------------------|
| `__init__.py`                 | Public API for metrics logging and querying.            | `RunMetricsLogger`, `CorrelationLogHandler`, `MetricsRepository` |
| `correlation_log_handler.py`  | Handles counting of ERROR/WARNING logs per correlation ID.| `CorrelationLogHandler`                  |
| `metrics_repository.py`       | Provides a read-only interface for querying metrics logs.| `MetricsRepository`                       |
| `run_metrics_logger.py`       | Appends metrics records to a JSONL file.                | `RunMetricsLogger`                       |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `pathlib`
  - `threading`
  - `datetime`
  
- **Third-party packages**: None

- **Internal modules**:
  - `src.message_processors.run_metrics`
  - `src.message_processors.fcp_models`

- **Optional dependencies**: None

## 6. Configuration / Settings
| Key         | Type   | Default | What it controls |
|-------------|--------|---------|------------------|
| None        | None   | None    | None             |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      | None | None        |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     | None  | None        |

## 9. Methods (by class)

### RunMetricsLogger
| Method  | Type         | Signature                          | Description |
|---------|--------------|------------------------------------|-------------|
| `append`| instance     | `def append(self, record: RunMetrics) -> None:` | Appends a `RunMetrics` record to the JSONL file. Takes a `RunMetrics` object, serializes it to JSON, and writes it to the file. It ensures the directory exists and flushes the file after writing. |

### CorrelationLogHandler
| Method     | Type         | Signature                          | Description |
|------------|--------------|------------------------------------|-------------|
| `start_run`| instance     | `def start_run(self, correlation_id: str) -> RequestContext:` | Registers a new `RequestContext` for the given correlation ID and returns it. |
| `end_run`  | instance     | `def end_run(self, correlation_id: str) -> Optional[RequestContext]:` | Deregisters the accumulator for the correlation ID and returns it, or `None` if inactive. |
| `emit`     | instance     | `def emit(self, record: logging.LogRecord) -> None:` | Counts the log record against the active context for its correlation ID, incrementing the appropriate count based on the log level. |

### MetricsRepository
| Method     | Type         | Signature                          | Description |
|------------|--------------|------------------------------------|-------------|
| `__init__` | instance     | `def __init__(self, path: Union[str, Path]) -> None:` | Initializes the repository with the path to the metrics log file. |
| `query`    | instance     | `def query(self, correlation_id: Optional[str] = None, agent: Optional[str] = None, account: Optional[str] = None, started: Optional[Union[str, datetime]] = None, ended: Optional[Union[str, datetime]] = None, hit_iteration_cap: Optional[bool] = None, success: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]]:` | Returns matching run records based on provided filters. Validates input parameters and raises exceptions for invalid values. |
| `_read_entries` | instance | `def _read_entries(self) -> List[_Entry]:` | Reads the log file and returns a list of entries, skipping malformed lines. |
| `_parse_entry` | static   | `def _parse_entry(line: str, index: int) -> Optional[_Entry]:` | Parses a single line from the log file into a structured entry. |
| `_matches` | static       | `def _matches(entry: _Entry, correlation_id: Optional[str], agent: Optional[str], account: Optional[str], started_filter: Optional[datetime], ended_filter: Optional[datetime], hit_iteration_cap: Optional[bool], success: Optional[bool]) -> bool:` | Checks if a log entry matches the provided filters. |

## 10. Usage Examples
```python
from src.metrics import RunMetricsLogger, MetricsRepository

# Initialize the logger
logger = RunMetricsLogger('/path/to/metrics/runs.jsonl')

# Log a new metrics record
metrics_record = RunMetrics(...)  # Assume this is a valid RunMetrics object
logger.append(metrics_record)

# Query the metrics
repository = MetricsRepository('/path/to/metrics/runs.jsonl')
results = repository.query(correlation_id='some_id', limit=10)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The `MetricsRepository` is designed to be robust against missing files and malformed entries, which is crucial for maintaining stability in production environments.
- **Thread Safety**: The `CorrelationLogHandler` uses a lock to ensure that concurrent access to the context dictionary does not lead to race conditions.
- **Limitations**: The `query` method in `MetricsRepository` has a maximum limit of 500 records, which may need to be adjusted based on application requirements.

## 12. Consumers
| Consumer | What it uses |
|----------|--------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |