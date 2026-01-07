# Why Bounds Are Still Needed with Linear Arithmetic

## Question

Even though we've restricted the constraint parser to **linear arithmetic only** (no `var * var` or `**`), why do we still need to constrain integer variables to be within 0 to 8000 to prevent bit overflows?

## Answer

**Linear arithmetic can still overflow bitvectors** because:

1. **Fixed bitvector width**: Integer variables use 21-bit bitvectors, which can only represent values from **-1,048,576 to 1,048,575** (signed 21-bit range)

2. **Linear multiplication can overflow**: Even though we only allow `const * var` (not `var * var`), if the variable is too large, the result can still overflow:
   - Example: `x * 125` where `x = 10,000` → `1,250,000` ❌ **Overflows 21 bits!**
   - Example: `x * 12` where `x = 100,000` → `1,200,000` ❌ **Overflows 21 bits!**

3. **Modular wraparound**: Bitvectors use **modular arithmetic** - when values overflow, they wrap around:
   - `4,864,692 % 2^21 = 670,388` ← This creates **incorrect results**!

## Real Example from Bug Report

From `legal-134` constraint:
```
(is_short_taxable_year == True) -> (annualized_weeks == ((weeks_presented * 12) / taxable_year_months))
```

**Before bounds were added:**
- `weeks_presented = 405,391` (unbounded, Z3 found this "solution")
- `405,391 * 12 = 4,864,692` → **Overflows 21 bits!**
- Due to modular wraparound: `4,864,692 % 2^21 = 670,388`
- Result: `annualized_weeks = 670,388` ❌ **WRONG!**

**After bounds (0 to 8000):**
- `weeks_presented ≤ 8,000` (bounded)
- `8,000 * 12 = 96,000` → ✅ **Within 21-bit range**
- Result: `annualized_weeks = 96,000` ✅ **CORRECT!**

## Why 8000?

The bound of **8000** is chosen to ensure that common linear arithmetic operations stay within the 21-bit signed range.

**Actual constants found in legal document constraints:**
- `12 * x` (found in `legal-134`)
- `100 * x` (found in `legal-48`)
- `125 * x` (found in `legal-48`)

| Operation | Max Value | Max Safe x | 21-bit Limit | Status |
|-----------|-----------|------------|--------------|--------|
| `x * 125` | `8,000 * 125 = 1,000,000` | 8,388 | ±1,048,575 | ✅ Safe |
| `x * 100` | `8,000 * 100 = 800,000` | 10,485 | ±1,048,575 | ✅ Safe |
| `x * 12` | `8,000 * 12 = 96,000` | 87,381 | ±1,048,575 | ✅ Safe |

**Calculation:**
- 21-bit signed range: `-2^20` to `2^20 - 1` = `-1,048,576` to `1,048,575`
- Largest constant in constraints: **125**
- To safely multiply by 125: `max_x = 1,048,575 / 125 ≈ 8,388`
- Conservative bound: **8,000** (leaves safety margin for the largest constant)

## Key Insight

**Linear arithmetic restriction prevents:**
- ❌ `x * y` (variable × variable)
- ❌ `x ** 2` (power operations)

**But it does NOT prevent:**
- ✅ `x * 125` (constant × variable) ← **Can still overflow!**
- ✅ `x * 12` (constant × variable) ← **Can still overflow!**

Therefore, **bounds are still essential** to ensure that even linear arithmetic operations stay within the bitvector's representable range.

## Summary

| Aspect | Without Bounds | With Bounds (0-8000) |
|--------|----------------|---------------------|
| Linear arithmetic | ✅ Allowed | ✅ Allowed |
| Overflow risk | ❌ High (unbounded vars) | ✅ Low (bounded vars) |
| Correctness | ❌ Spurious solutions | ✅ Valid solutions only |
| Example | `x=405391, x*12` overflows | `x≤8000, x*12` safe |

**Conclusion**: Even with linear arithmetic restrictions, we must bound integer variables to prevent bitvector overflow in expressions like `const * var`.

