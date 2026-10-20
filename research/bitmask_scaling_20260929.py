"""Structural integer-storage probe. No planner or speed claim."""
import json
from pathlib import Path
import sys

from src.planning.bitmask import sensor_range_mask


def probe():
    records = []
    radius = 8
    side = 2 * radius + 1
    for size in (40, 80, 160, 320):
        positions = ((0, 0), (0, size - 1), (size // 2, size // 2),
                     (size - 1, 0), (size - 1, size - 1))
        for row, col in positions:
            global_mask = sensor_range_mask((row, col), (size, size), radius)
            local_mask, decoded = 0, 0
            remaining = global_mask
            while remaining:
                bit = remaining & -remaining
                index = bit.bit_length() - 1
                r, c = divmod(index, size)
                local_index = (r - row + radius) * side + c - col + radius
                assert 0 <= local_index < side * side
                local_mask |= 1 << local_index
                remaining ^= bit
            remaining = local_mask
            while remaining:
                bit = remaining & -remaining
                index = bit.bit_length() - 1
                dr, dc = divmod(index, side)
                decoded |= 1 << ((row + dr - radius) * size + col + dc - radius)
                remaining ^= bit
            assert decoded == global_mask
            records.append({"size": size, "candidate": [row, col], "radius": radius,
                            "memberships": global_mask.bit_count(), "global_bit_length": global_mask.bit_length(),
                            "local_bit_length": local_mask.bit_length(),
                            "global_integer_bytes": sys.getsizeof(global_mask),
                            "local_integer_bytes": sys.getsizeof(local_mask)})
    return {"python": sys.version, "int_bits_per_digit": sys.int_info.bits_per_digit,
            "records": records, "semantic_roundtrip_checks": len(records),
            "limitation": "Integer objects only; excludes containers, local UNKNOWN extraction, conversions and planner runtime. Local/tiled planner is unimplemented."}


if __name__ == "__main__":
    path = Path(sys.argv[1])
    with path.open("x", encoding="utf-8") as stream:
        json.dump(probe(), stream, indent=2)
        stream.write("\n")
