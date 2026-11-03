"""Power evidence for a paired timing block. Wall/CPU ratios are diagnostic only."""
from contextlib import contextmanager
import ctypes
import os
import sys
import subprocess
import time
from xml.etree import ElementTree


def windows_event():
    # Read the most recent matching System event via the native Windows Event Log.
    api = ctypes.WinDLL("wevtapi", use_last_error=True)
    handle = ctypes.c_void_p
    api.EvtQuery.restype = handle
    query = "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and (EventID=42 or EventID=107 or EventID=506 or EventID=507 or EventID=105)]]"
    result = api.EvtQuery(None, "System", query, 0x201)
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    event = handle()
    count = ctypes.c_ulong()
    try:
        if not api.EvtNext(handle(result), 1, ctypes.byref(event), 1000, 0, ctypes.byref(count)):
            if ctypes.get_last_error() == 259:
                return None
            raise ctypes.WinError(ctypes.get_last_error())
        size, fields = ctypes.c_ulong(), ctypes.c_ulong()
        api.EvtRender(None, event, 1, 0, None, ctypes.byref(size), ctypes.byref(fields))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buf = ctypes.create_unicode_buffer(size.value // 2)
        if not api.EvtRender(None, event, 1, size.value, buf, ctypes.byref(size), ctypes.byref(fields)):
            raise ctypes.WinError(ctypes.get_last_error())
        return ElementTree.fromstring(buf.value).findtext(".//{*}EventRecordID")
    finally:
        if event.value:
            api.EvtClose(event)
        api.EvtClose(handle(result))


def sample():
    if os.name == "nt":
        active = ctypes.c_ulonglong()
        if not ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(active)):
            raise ctypes.WinError()
        return {"sleep_offset_ns": time.perf_counter_ns() - active.value * 100,
                "event": windows_event()}
    if sys.platform == "darwin":
        lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        lib.mach_continuous_time.restype = lib.mach_absolute_time.restype = ctypes.c_uint64
        units = (ctypes.c_uint32 * 2)()
        if lib.mach_timebase_info(ctypes.byref(units)) or not units[1]:
            raise RuntimeError("mach_timebase_info failed")
        ticks = lib.mach_continuous_time() - lib.mach_absolute_time()
        return {"sleep_offset_ns": ticks * units[0] // units[1], "event": None}
    if hasattr(time, "CLOCK_BOOTTIME"):
        return {"sleep_offset_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME) - time.monotonic_ns(),
                "event": None}
    raise RuntimeError(f"Timing protection unavailable on {sys.platform}")


def interrupted(a, b):
    return a["event"] != b["event"] or abs(b["sleep_offset_ns"] - a["sleep_offset_ns"]) > 100_000_000


@contextmanager
def awake():
    previous = None
    helper = None
    if os.name == "nt":
        request = ctypes.windll.kernel32.SetThreadExecutionState
        request.restype = ctypes.c_uint32
        previous = request(ctypes.c_uint32(0x80000003))
        if not previous:
            raise RuntimeError("Windows awake request failed")
    elif sys.platform == "darwin":
        helper = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
    try:
        sample()
        yield
    finally:
        if helper:
            helper.terminate()
            helper.wait()
        if previous:
            request(ctypes.c_uint32(previous))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check awake request and suspend detection on this device")
    parser.add_argument("--seconds", type=int, default=360)
    duration = parser.parse_args().seconds
    if duration < 1:
        parser.error("Duration must be positive")
    with awake():
        initial = sample()
        print(f"Observing {duration} seconds. Initial evidence: {initial}", flush=True)
        until = time.monotonic() + duration
        while time.monotonic() < until:
            time.sleep(1)
            current = sample()
            if interrupted(initial, current):
                raise SystemExit(f"Interruption detected: {current}")
    print("Check completed without an observed interruption.")
