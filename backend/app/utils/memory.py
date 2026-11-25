"""
Memory monitoring and management utilities to prevent OOM errors on memory-constrained platforms like Render (512MB RAM).
Cross-platform support: psutil -> Linux resource -> Windows ctypes kernel32/psapi.
"""
import gc
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Try psutil first if installed
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]


def get_memory_info() -> dict[str, float]:
    """
    Returns current process memory usage in MB.
    """
    if _HAS_PSUTIL:
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            return {
                "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            }
        except Exception as e:
            logger.debug(f"psutil failed to read memory: {e}")

    # Fallback for Windows using ctypes (standard library)
    if sys.platform == "win32":
        try:
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            fn = ctypes.windll.psapi.GetProcessMemoryInfo
            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            fn.restype = ctypes.c_int
            if fn(handle, ctypes.byref(counters), counters.cb):
                rss_mb = round(counters.WorkingSetSize / (1024 * 1024), 2)
                vms_mb = round(counters.PagefileUsage / (1024 * 1024), 2)
                return {"rss_mb": rss_mb, "vms_mb": vms_mb}
        except Exception as e:
            logger.debug(f"ctypes memory lookup failed on Windows: {e}")

    # Fallback for Linux / macOS via resource module
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        scale = 1024 * 1024 if sys.platform == "darwin" else 1024
        rss_mb = round(rusage.ru_maxrss / scale, 2)
        return {
            "rss_mb": rss_mb,
            "vms_mb": 0.0,
        }
    except Exception:
        pass

    return {
        "rss_mb": 0.0,
        "vms_mb": 0.0,
    }


def log_memory(stage: str) -> dict[str, float]:
    """
    Logs current memory usage with a contextual stage label.
    """
    mem = get_memory_info()
    rss = mem["rss_mb"]
    logger.info(f"--> [Memory Check] {stage} | RSS: {rss} MB")
    print(f"--> [Memory Check] {stage} | RSS: {rss} MB", flush=True)
    return mem


def force_garbage_collection(stage: str | None = None) -> dict[str, float]:
    """
    Forces Python garbage collection and PyTorch memory cleanup if available.
    """
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    if stage:
        return log_memory(f"After GC ({stage})")
    return get_memory_info()


class MemoryLimitExceeded(Exception):
    """Raised when process RSS memory exceeds the configured safety limit for Render (512MB)."""
    pass


def check_and_enforce_memory_limit(threshold_mb: float = 460.0, action: str = "operation") -> dict[str, float]:
    """
    Guards process memory below the 512MB hard limit on Render instances.
    - If RSS exceeds 400MB, proactively forces garbage collection.
    - If RSS remains above threshold_mb (e.g. 460MB), raises MemoryLimitExceeded to safely halt
      before the container is killed by Render's Linux kernel OOM killer.
    """
    mem = get_memory_info()
    rss = mem["rss_mb"]

    # Proactive cleanup if RAM is climbing towards the ceiling
    if rss > 400.0:
        mem = force_garbage_collection(f"Proactive memory recovery during {action}")
        rss = mem["rss_mb"]

    # If still above the hard safety threshold, halt gracefully
    if rss >= threshold_mb:
        msg = (
            f"Process memory ({rss} MB) reached safety ceiling ({threshold_mb} MB) "
            f"during {action}. Halting safely to prevent Render 512MB container OOM crash."
        )
        logger.warning(msg)
        print(f"--> [CRITICAL MEMORY GUARD] {msg}", flush=True)
        raise MemoryLimitExceeded(msg)

    return mem

