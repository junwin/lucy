# Module Documentation for `src/tool_selection`

## YAML Front Matter
```yaml
tags:
  - src_tool_selection
  - lucyproject
  - ToolSelection
  - ToolSelectionPipeline
  - ToolSelectionError
  - ToolSelectionCode
  - VALID_CODES
```

## 1. Summary
The `tool_selection` module is responsible for orchestrating the selection of tools based on user-defined criteria and agent capabilities. It provides a structured pipeline that evaluates available tools, checks permissions, and validates requirements, ultimately returning a selection of tools that can be used in a given context. This module fits into a larger architecture where tools are dynamically selected based on user input and agent capabilities, solving the problem of efficiently managing and utilizing various tools in a flexible manner.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Pipeline Pattern**: The `ToolSelectionPipeline` class orchestrates the entire tool selection process, managing the flow of data through various stages.
- **Data Class**: The `ToolSelection` class is a frozen dataclass that encapsulates the results of the tool selection process, providing a clear and immutable structure for the output.
- **Error Handling**: Custom exceptions like `ToolSelectionError` are defined to handle specific error cases related to tool selection, enhancing robustness.

Classes within the module relate through composition and delegation. For instance, `ToolSelectionPipeline` uses helper functions and classes like `LLMResolver` to resolve tools based on agent capabilities. The module does not exhibit a legacy/v2 split, as it appears to be a cohesive implementation without backward compatibility concerns.

Important design decisions include the use of clear error codes in `ToolSelectionError`, which allows for precise error handling and messaging.

## 3. Key Classes
| Class                     | Base/Parent | Purpose                                                                 |
|---------------------------|--------------|-------------------------------------------------------------------------|
| ToolSelection             | N/A          | Represents the result of the tool selection process.                    |
| ToolSelectionPipeline      | N/A          | Orchestrates the tool selection process, managing various stages.       |
| ToolSelectionError        | Exception    | Custom exception for handling errors in tool selection.                 |
| LLMResolver               | N/A          | Resolves the LLM model and provider based on configuration and agent.   |

## 4. Source Files
| File                          | Responsibility                                               | Notable Exports                                   |
|-------------------------------|-------------------------------------------------------------|--------------------------------------------------|
| `__init__.py`                | Public API for the module, defining main exports.         | ToolSelection, ToolSelectionPipeline, ToolSelectionError |
| `errors.py`                  | Defines custom error handling for tool selection.          | ToolSelectionError, ToolSelectionCode, VALID_CODES |
| `pipeline.py`                | Implements the tool selection pipeline logic.              | ToolSelection, ToolSelectionPipeline, get_agent_allowed_tools, get_all_tools_from_registry, get_required_tools |
| `selection.py`               | Provides functionality for suggesting tools based on prompts. | suggest_tools                                     |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `re`
  - `typing`
- **Third-party packages**: None
- **Internal modules**:
  - `src.tool_selection.errors`
  - `src.tool_selection.selection`
- **Optional dependencies**: None

## 6. Configuration / Settings
| Key                          | Type   | Default | What it controls                                      |
|------------------------------|--------|---------|------------------------------------------------------|
| max_handler_schema_tokens     | int    | 8000    | Maximum allowed tokens for tool schemas.             |
| llm_model                     | str    | N/A     | The model used for LLM calls.                        |
| llm_provider                  | str    | N/A     | The provider for LLM calls.                          |
| llm_source                    | str    | "router"| Source of the LLM call (router or direct).          |
| prompt_style                  | str    | "verb_first" | Style of the prompt used for tool selection.     |

## 7. Exceptions
| Exception                  | Base      | When Raised                                           |
|----------------------------|-----------|------------------------------------------------------|
| ToolSelectionError         | Exception | Raised when there are issues with tool selection, such as permission or registration errors. |

## 8. Module-Level Constants
| Constant                          | Value                |
|-----------------------------------|----------------------|
| VALID_CODES                       | frozenset of error codes |
| DEFAULT_MAX_HANDLER_SCHEMA_TOKENS | 8000                 |
| _SELECTION_MODEL_FALLBACK         | "gpt-4o-mini"       |

## 9. Methods (by class)

### ToolSelectionPipeline
| Method                     | Type        | Signature                                                                 | Description                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, registry, storage, llm_adapter, config):`          | Initializes the pipeline with registry, storage, LLM adapter, and config.  |
| `resolve`                  | instance    | `def resolve(self, agent, account_name: str, context_name: str, prompt_text: str) -> ToolSelection:` | Resolves the tools based on agent and context, returning a ToolSelection object. |
| `get_tool_handler_defs`    | instance    | `def get_tool_handler_defs(self, agent, account_name: str, context_name: str, prompt_text: str) -> List[Dict[str, Any]]:` | Retrieves tool handler definitions based on the resolved tools.            |
| `_should_select_prompt_based` | instance  | `def _should_select_prompt_based(self, eligible: List[str]) -> Tuple[bool, Dict[str, Any]]:` | Determines if prompt-based selection should occur based on eligibility.    |
| `_select_prompt_based`     | instance    | `def _select_prompt_based(self, prompt_text: str, agent, eligible: List[str]) -> Tuple[List[str], Dict[str, Any]]:` | Selects tools based on a prompt using LLM.                                 |
| `_defs_by_name`           | instance    | `def _defs_by_name(self, names: List[str]) -> List[Dict[str, Any]]:` | Retrieves tool definitions by their names.                                 |

### LLMResolver
| Method                     | Type        | Signature                                                                 | Description                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config, agent, llm_adapter):`                       | Initializes the resolver with configuration, agent, and LLM adapter.       |
| `resolve`                  | instance    | `def resolve(self) -> Tuple[str, Optional[str]]:`                       | Resolves the LLM model and provider based on configuration and agent.      |
| `call_llm`                 | instance    | `def call_llm(self, messages: List[Dict[str, str]], model: str, provider: Optional[str]) -> str:` | Calls the LLM with the provided messages and returns the response.         |

## 10. Usage Examples
```python
from src.tool_selection import ToolSelectionPipeline

# Initialize the pipeline with necessary components
pipeline = ToolSelectionPipeline(registry, storage, llm_adapter, config)

# Resolve tools for a specific agent and context
tool_selection = pipeline.resolve(agent, "account_name", "context_name", "What tools do I need?")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising `ToolSelectionError` for specific issues like permission or registration failures.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources.
- **Validation Logic**: The `_validate_required` method ensures that required tools are both permissioned and registered, which may lead to exceptions if not handled properly.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |