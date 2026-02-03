# Minimal shim for the 'injector' package used in tests.
# Provides a no-op `inject` decorator and a very small `Injector` class
# that can instantiate classes without constructor args. This keeps tests
# lightweight and avoids adding the actual dependency.

from typing import Any, Callable


def inject(fn: Callable) -> Callable:
    """No-op decorator compatible with 'injector.inject'."""
    return fn


class Injector:
    def __init__(self, modules: Any = None):
        # Very small provider-based resolver: if a list of module instances is
        # provided, call their provider methods (functions) and register the
        # returned instances by the annotated return type. This is sufficient
        # for the limited use in container_config in tests.
        self._bindings: dict[type, Any] = {}
        if modules:
            for mod in modules:
                # Inspect module attributes for callables with return annotations
                for name in dir(mod):
                    if name.startswith("_"):
                        continue
                    attr = getattr(mod, name)
                    if not callable(attr):
                        continue
                    ann = getattr(attr, "__annotations__", {})
                    ret = ann.get("return")
                    if ret is None:
                        continue
                    try:
                        # call provider (module methods expect 'self' bound)
                        instance = attr()
                        if isinstance(ret, type):
                            self._bindings[ret] = instance
                    except Exception:
                        # if a provider fails, keep going; real injector would
                        # surface the error during resolution.
                        pass

    def get(self, cls: Any) -> Any:
        # Prefer provided bindings
        if cls in self._bindings:
            return self._bindings[cls]

        # Fall back to naive construction
        try:
            return cls()
        except Exception as ex:
            raise RuntimeError(f"Injector shim failed to construct {cls}: {ex}")


# Minimal compatibility pieces referenced by container_config
class Module:
    pass


def provider(fn: Callable) -> Callable:
    return fn


def singleton(fn: Callable) -> Callable:
    return fn
