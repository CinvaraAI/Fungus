import time
import traceback
import tracemalloc
from functools import wraps

from fungus.blackbox_agent import record_event, get_ctx


EXCLUDE_ATTR = "__blackbox_exclude__"
WRAPPED_ATTR = "__blackbox_wrapped__"


def blackbox_exclude(func):
    """Marks a function to be excluded from blackbox wrapping."""
    setattr(func, EXCLUDE_ATTR, True)
    return func


def is_excluded(obj):
    """Checks if a function or method has been excluded from wrapping."""
    return getattr(obj, EXCLUDE_ATTR, False)


def is_already_wrapped(func):
    """Checks if the function has already been wrapped by Blackbox."""
    return getattr(func, WRAPPED_ATTR, False)


def blackbox_wrap(label=None, log_type="internal", include_return_value=False):
    EXCLUDED_MODULES = {
        "dynamics.resolver",
        "fungus.blackbox_tag_engine",
        "fungus.blackbox_writer",
        "fungus.blackbox_config"
    }

    def decorator(func):
        if is_excluded(func) or is_already_wrapped(func):
            return func

        module = getattr(func, "__module__", "")
        if module in EXCLUDED_MODULES:
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):
            name = label or func.__name__
            ctx = get_ctx()
            docstring = (func.__doc__ or "").strip()
            start_time = time.time()

            tracemalloc.start()
            start_mem, _ = tracemalloc.get_traced_memory()

            record_event(log_type, ctx, f"[Autolog] Enter: {name}", {
                "args": safe_preview(args),
                "kwargs": safe_preview(kwargs),
                "doc": docstring,
                "__func__": func
            })

            try:
                result = func(*args, **kwargs)

                elapsed = time.time() - start_time
                end_mem, peak_mem = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                preview = safe_preview(result) if include_return_value else safe_preview(result)[:300]

                record_event(log_type, ctx, f"[Autolog] Exit: {name}", {
                    "result_preview": preview,
                    "elapsed_time_sec": round(elapsed, 4),
                    "memory_kb": round((end_mem - start_mem) / 1024, 2),
                    "peak_memory_kb": round(peak_mem / 1024, 2),
                    "doc": docstring,
                    "__func__": func
                })

                return result

            except Exception as e:
                if tracemalloc.is_tracing():
                    tracemalloc.stop()

                record_event(log_type, ctx, f"[Autolog] Error in {name}", {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "doc": docstring,
                    "__func__": func
                }, level="error")

                raise

        setattr(wrapper, WRAPPED_ATTR, True)
        return wrapper

    return decorator


def safe_preview(obj, limit=300):
    """Safely stringifies objects for logging, guards against recursion and crashes."""
    try:
        result = repr(obj)
        return result if len(result) <= limit else result[:limit] + "..."
    except Exception as e:
        return f"<unprintable: {e}>"
