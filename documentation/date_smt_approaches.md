# Date-SMT Approaches: Design Summary

This document summarizes the four different approaches implemented and proposed for solving date-related SMT problems in the Date-SMT project.

## Approach 1: Symbolic Baseline (`symbolic_baseline.py`)

**Design Philosophy**: Component-based representation with exact calendar arithmetic

### Core Design
- **Date Representation**: Three separate Z3 integer variables (year, month, day)
- **Period Representation**: Three separate Z3 integer variables (years, months, days)
- **Arithmetic Strategy**: Direct component-wise operations with proper normalization

### Key Features
- **Exact Calendar Logic**: Implements complete Gregorian calendar rules
- **Month Normalization**: Uses `normalize_month()` and `canon_months()` for proper carry-over
- **End-of-Month Policy**: Clamps invalid days to the last day of the target month
- **Ordinal Conversion**: Uses 400-year cycle reduction for exact day arithmetic
- **Leap Year Handling**: Complete leap year calculation with Z3 constraints

### Implementation Details
```python
# Date representation
self.year_var = Int(f"{name}_year")
self.month_var = Int(f"{name}_month") 
self.day_var = Int(f"{name}_day")

# Period arithmetic: NormMonth → EOM clamp → ordinal day add
y1, m1 = normalize_month(y0, m0)
d1 = EOMClamp(y1, m1, self.day_var)
y2, m2, d2 = add_days_ordinal(y1, m1, d1, period.days)
```

### Strengths
- Mathematically exact calendar arithmetic
- Handles all edge cases correctly
- Clear separation of concerns
- Predictable behavior

### Trade-offs
- More complex constraint generation
- Potentially slower SMT solving due to complex calendar logic
- Higher constraint count

### Use Cases
- When mathematical accuracy is critical
- Applications requiring exact calendar compliance
- Research or validation scenarios

---

## Approach 2: Symbolic Advanced (`symbolic_advanced.py`)

**Design Philosophy**: Epoch-based storage with conversion-based exact arithmetic

### Core Design
- **Date Representation**: Single Z3 integer variable (days since epoch: March 1, 2000)
- **Period Arithmetic**: Converts to YMD, performs exact arithmetic, converts back to epoch
- **Storage Strategy**: Epoch-optimized for comparisons and day arithmetic

### Key Features
- **Epoch System**: Uses March 1, 2000 as day 0
- **Conversion Pipeline**: Epoch → YMD → exact arithmetic → Epoch
- **Exact Calendar Logic**: Full Gregorian calendar implementation in Z3
- **Efficient Comparisons**: O(1) date comparisons using epoch arithmetic
- **Exact Period Arithmetic**: Uses `add_period_exact_days()` with full calendar logic

### Implementation Details
```python
# Date representation
self.days_var = Int(f"{name}_days")  # days since epoch

# Period arithmetic: convert to YMD, do exact arithmetic, convert back
def add_period_exact_days(days_term, period):
    y, m, d = ymd_from_days_since_epoch(days_term)
    y2, m2 = normalize_month(y + period.years, m + period.months)
    d2 = eom_clamp(y2, m2, d)
    base_ord = to_ordinal(y2, m2, d2)
    new_ord = base_ord + period.days
    return new_ord - _ORD_EPOCH
```

### Strengths
- Fast comparisons and day arithmetic
- Exact calendar arithmetic when needed
- Simple storage model
- Good balance of performance and accuracy

### Trade-offs
- Conversion overhead for period arithmetic
- More complex implementation than pure epoch
- Requires maintaining conversion functions

### Use Cases
- Applications with many date comparisons
- Mixed workloads (some exact, some approximate)
- When storage efficiency matters

---

## Approach 3: Symbolic Hybrid (`symbolic_hybrid.py`)

**Design Philosophy**: Dual representation with epoch-primary, YMD-derived components

### Core Design
- **Date Representation**: Four Z3 integer variables (Y, M, D, E) with forward link E = to_ordinal(Y,M,D)
- **Dual System**: Epoch-primary for comparisons/day arithmetic, YMD components for month/year arithmetic
- **AMI Arithmetic**: Uses "Absolute Month Index" for efficient month/year operations

### Key Features
- **Forward Link**: Single constraint E = to_ordinal(Y,M,D) per date
- **Optimized Operations**: O(1) comparisons using epoch, exact month arithmetic using components
- **Solver Factory**: Centralized DateVar creation with automatic constraint registration
- **Mixed Arithmetic**: Uses most appropriate representation for each operation type

### Implementation Details
```python
# Date representation
self.year_var = Int(f"{name}_year")
self.month_var = Int(f"{name}_month")
self.day_var = Int(f"{name}_day")
self.epoch_var = Int(f"{name}_epoch")

# Forward link constraint (once per date)
E == to_ordinal_z3(Y, M, D)

# Day arithmetic: O(1) on epoch
result.epoch_var == self.epoch_var + k_term

# Month arithmetic: AMI on YMD components
ami = 12 * self.year_var + (self.month_var - 1)
ami_new = ami + k_term
Yp = ami_new / 12
Mp = (ami_new % 12) + 1
```

### Strengths
- Best of both worlds: fast comparisons + exact month arithmetic
- Maintains calendar accuracy for month/year operations
- Efficient for mixed date/period constraints
- Clear operation mapping

### Trade-offs
- More complex implementation
- Requires maintaining consistency between dual representations
- Higher memory usage (4 variables per date)
- More sophisticated constraint management

### Use Cases
- **Recommended approach** for most applications
- Complex date/period constraint systems
- When both performance and accuracy are important
- Production systems with mixed workloads

---

## Approach 4: Epoch-Only (Proposed, Not Implemented)

**Design Philosophy**: Pure epoch space with Z3-pure calendar reconstruction

### Core Design
- **Date Representation**: Single Z3 integer variable (days since epoch)
- **Calendar Reconstruction**: Reconstruct year/month/day from epoch using Z3-pure arithmetic
- **Month Arithmetic**: Perform all operations directly in epoch space

### Key Features
- **Single Variable**: Only E (days since epoch) per date
- **Z3-Pure Functions**: `year_of(E)`, `month_of(E)`, `dom_of(E)` built with `/`, `%`, and nested `If`s
- **AMI in Epoch Space**: `ami_of(E) = 12*year_of(E) + (month_of(E)-1)`
- **Direct Epoch Arithmetic**: All operations performed without conversion

### Implementation Concept
```python
# Date representation
self.days_var = Int(f"{name}_days")

# Calendar reconstruction (Z3-pure)
def year_of(E): # 400/100/4/1 year block decomposition
def month_of(E): # nested If chains for month calculation
def dom_of(E): # day-of-month calculation

# Month arithmetic in epoch space
def add_months_epoch(E, k):
    ami = ami_of(E)
    ami_new = ami + k
    first = first_day_of_ami(ami_new)
    dim = dim_of_ami(ami_new)
    day = clamp(dom_of(E), dim)  # EOM-aware
    return first + (day - 1)
```

### Why It Looked Attractive
- Single integer per date
- Ultra-simple comparisons and day arithmetic
- No separate (Y,M,D) variables
- Elegant mathematical approach

### Why It Underperformed
- **Constraint Bloat**: Reconstructing year/month/day creates big nested `If` chains
- **Performance Issues**: 4–5× larger SMT2, 3.6× slower solving
- **Boundary Bugs**: Off-by-one errors around leap years and EOM
- **Case Splitting**: Multiple `div/mod` by large constants overwhelms Z3

### Net Result
- Elegant on paper, but conditional arithmetic overwhelms Z3 for realistic workloads
- **Not recommended** for practical applications

---

## Comparison Summary

| Approach | Storage | Period Arithmetic | Accuracy | Performance | Complexity | Memory |
|----------|---------|-------------------|----------|-------------|------------|---------|
| **Baseline** | YMD components | Direct YMD | Exact | Slower | High | 3 vars/date |
| **Advanced** | Epoch days | Epoch→YMD→Epoch | Exact | Fast | Medium | 1 var/date |
| **Hybrid** | Dual (YMD + Epoch) | Mixed (AMI + Epoch) | Exact | Fast | High | 4 vars/date |
| **Epoch-Only** | Epoch days | Pure epoch | Exact | Slow | High | 1 var/date |

## Recommendations

### For Most Applications: **Hybrid Approach**
- Best balance of performance and accuracy
- Efficient for mixed workloads
- Maintains exact calendar arithmetic
- Recommended for production systems

### For Simple Cases: **Advanced Approach**
- When storage efficiency is critical
- Applications with many date comparisons
- Good performance with exact arithmetic

### For Research/Validation: **Baseline Approach**
- When mathematical correctness is paramount
- Educational or research contexts
- Validation of other approaches

### Avoid: **Epoch-Only Approach**
- Elegant but impractical
- Performance issues with realistic workloads
- Complex implementation with poor results

## Key Insights

1. **Calendar arithmetic is inherently complex** - there's no way to avoid the complexity entirely
2. **Dual representation can be efficient** - using the right representation for each operation
3. **SMT solvers prefer simple constraints** - complex conditional logic hurts performance
4. **Forward links work better than inverse conversions** - let the solver derive rather than compute
5. **Factory patterns help** - centralized creation with automatic constraint registration

The hybrid approach represents the current best practice, combining the efficiency of epoch-based operations with the accuracy of component-based month/year arithmetic.
