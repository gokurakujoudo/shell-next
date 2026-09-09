"""Windows Job Object information structures from the jobapi2.h ABI."""

import ctypes


class BasicLimits(ctypes.Structure):
    """JOBOBJECT_BASIC_LIMIT_INFORMATION layout from the Windows SDK.

    Time fields use 100-nanosecond ticks; working sets use bytes, affinity is a
    processor mask, and remaining fields are Win32 flags/counts. Only LimitFlags
    is configured; zero leaves all resource quotas at their system defaults.
    """

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class ExtendedLimits(ctypes.Structure):
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION layout from the Windows SDK.

    IoInfo contains six unsigned 64-bit operation/byte counters. Memory limits
    measure bytes. Only the embedded basic limit flags are configured.
    """

    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]
