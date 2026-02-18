"""
Bit width constants for date components in Z3 bitvector operations.

This module defines the minimum bit widths needed for various date components
to avoid unnecessary overhead while ensuring all valid values can be represented.
"""
LEGACY_BITS = 21

# User-defined integer variable bit width
# Keep at 21 bits to match other date components, use bounds to prevent overflow
INT_VAR_BITS = LEGACY_BITS

# Date component bit widths
YEAR_BITS = 12     # 4096 > 2100
MONTH_BITS = 12    # Because in the implementation, we multiply YEAR by 12 and add to MONTH
DAY_BITS = 20      # Because we add Period.days to the date, and Period.days can be large

# Epoch-based bit widths
EPOCH_DAYS_BITS = 17  # -36525 to 36523 (~73k days) -> 2^17 = 131,072 > 73,000

# Absolute ordinal bit widths (for representing absolute day numbers since 0001-01-01)
ORD_BITS = max(20, DAY_BITS)  # 730179 needs 20 bits (2^19 < 730179 < 2^20)

# Alpha-beta bit widths
ALPHA_BITS = 12  # (2100-1900)*12 + (2-3) = 2399 -> 2^12 = 4096 > 2399
BETA_BITS = 5      # 0-30 (day within month) -> 2^5 = 32 > 30

# Validation ranges
YEAR_MIN = 1900
YEAR_MAX = 2100
MONTH_MIN = 1
MONTH_MAX = 12
DAY_MIN = 1
DAY_MAX = 31

# Epoch bounds (2000-03-01 as epoch)
EPOCH_DAYS_MIN = -36525  # 1900-03-01
EPOCH_DAYS_MAX = 36523   # 2100-02-28

# Months since epoch bounds
MONTHS_SINCE_EPOCH_MIN = (1900 - 2000) * 12 + (3 - 3)  # -1200
MONTHS_SINCE_EPOCH_MAX = (2100 - 2000) * 12 + (2 - 3)  # 2399

# Beta bounds
BETA_MIN = 0
BETA_MAX = 30  # 0-30 for day within month (0-based)
