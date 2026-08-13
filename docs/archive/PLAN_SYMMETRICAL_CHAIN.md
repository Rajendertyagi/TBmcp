# Symmetrical Option Chain Layout - Implementation Plan

## Current State vs. Desired State

### Current Table (14 columns)
```
CE Side: OI | OI% | Chg | LTP | LTP% | IV | Build
Center:  Strike  
PE Side: Build | LTP% | LTP | Chg | OI% | OI
```

### Desired Table (28 columns total)
```
CALLS (Left → Center):
  Buildup | Vega | Theta | Gamma | Delta | IV | Vol% | Volume | OI | LTP% | LTP | BidQty | BidPrice | AskPrice | AskQty

CENTER:
  STRIKE PRICE
  PCR (PE_OI / CE_OI)

PUTS (Center → Right):
  AskQty | AskPrice | BidPrice | BidQty | LTP | LTP% | OI | Volume | Vol% | IV | Delta | Gamma | Theta | Vega | Buildup
```

---

## Data Field Mapping (Verified from Upstox API)

| Column | API Field | Source Code | Status |
|--------|-----------|-------------|--------|
| Buildup | `buildTag` | `classify_buildup()` | ✅ Available |
| Vega | `vega` | `option_greeks.vega` | ✅ Available |
| Theta | `theta` | `option_greeks.theta` | ✅ Available |
| Gamma | `gamma` | `option_greeks.gamma` | ✅ Available |
| Delta | `delta` | `option_greeks.delta` | ✅ Available |
| IV | `impliedVolatility` | `option_greeks.iv` | ✅ Available |
| **Vol chg (%)** | ⚠️ **VERIFY** | `oiChangePct` (current) | ⚠️ Needs confirmation |
| Volume | `totalTradedVolume` | `market_data.volume / lot_size` | ✅ Available |
| OI | `openInterest` | `market_data.oi` | ✅ Available |
| LTP Chg (%) | `pChange` | `(ltp - prev_close) / prev_close` | ✅ Available |
| LTP | `lastPrice` | `market_data.ltp` | ✅ Available |
| Bid Qty | `bidQty` | `market_data.bid_qty` | ✅ Available |
| Bid Price | `bidPrice` | `market_data.bid_price` | ✅ Available |
| Ask Price | `askPrice` | `market_data.ask_price` | ✅ Available |
| Ask Qty | `askQty` | `market_data.ask_qty` | ✅ Available |

---

## Critical Question: Volume Change (%)

**User says:** "Upstox showing vol change in their option chain"

**Current code only extracts:**
- `volume_shares` → converted to contracts (`totalTradedVolume`)
- `oiChangePct` → OI change percentage

**Missing:** Volume change percentage field

### Possible Sources:
1. **Upstox API might return** a field like:
   - `volume_change`
   - `changeinVolume`
   - `vol_change`
   - `prev_volume`
   
2. **Or it's calculated** from historical data (not in option chain response)

3. **Or user is referring to** OI change % being displayed as "Vol chg" in Upstox UI

---

## Implementation Plan

### Phase 1: Verify Volume Change Field (30 min)

**Action:** Run a test to dump raw API response
```python
# In client.py, add debug output
raw = self._request(OPTION_CHAIN_PATH, {"instrument_key": key, "expiry_date": expiry_date})
import json
with open("debug_option_chain.json", "w") as f:
    json.dump(raw, f, indent=2)
```

**Goal:** Find actual field name for volume change

---

### Phase 2: Update Models (15 min)

**File:** `models.py`
```python
class OptionLeg(TypedDict):
    # ... existing fields ...
    volume_change_pct: Optional[float]  # NEW - add after verification
```

---

### Phase 3: Update Client (15 min)

**File:** `client.py` → `_map_leg()`
```python
# Extract volume change if field exists
volume_change_pct = md.get("volume_change_pct") or md.get("changeinVolume") or None
# Add to return dict
"volumeChangePct": volume_change_pct,
```

---

### Phase 4: Update Renderer (2 hours)

**File:** `render.py`

#### 4a. Update `_leg_cells()` for CALLS side
```python
def _leg_cells(leg: Optional[dict], side: str = "CE") -> str:
    """Generate 14 cells per leg."""
    if not leg:
        return "<td class='rtmcp-empty'>-</td>" * 14
    
    cells = []
    
    # Buildup
    cells.append(f"<td class='{_buildup_class(leg['buildTag'])}'>{leg['buildTag']}</td>")
    
    # Greeks
    cells.append(f"<td>{_fmt(leg.get('vega', 0), 4)}</td>")
    cells.append(f"<td>{_fmt(leg.get('theta', 0), 4)}</td>")
    cells.append(f"<td>{_fmt(leg.get('gamma', 0), 4)}</td>")
    cells.append(f"<td>{_fmt(leg.get('delta', 0), 4)}</td>")
    
    # IV
    cells.append(f"<td>{_fmt(leg['impliedVolatility'], 2)}</td>")
    
    # Volume Change %
    vol_chg = leg.get('volumeChangePct') or leg.get('oiChangePct') or 0
    cells.append(f"<td class='{_change_class(vol_chg)}'>{_fmt(vol_chg, 2)}%</td>")
    
    # Volume
    cells.append(f"<td>{_fmt(leg['totalTradedVolume'], 0)}</td>")
    
    # OI
    cells.append(f"<td>{_fmt(leg['openInterest'], 0)}</td>")
    
    # LTP %
    cells.append(f"<td class='{_change_class(leg['pChange'])}'>{_fmt(leg['pChange'], 2)}%</td>")
    
    # LTP
    cells.append(f"<td>{_fmt(leg['lastPrice'], 2)}</td>")
    
    # Bid/Ask (CALLS side: BidQty, BidPrice, AskPrice, AskQty)
    cells.append(f"<td>{leg.get('bidQty', 0)}</td>")
    cells.append(f"<td>{_fmt(leg.get('bidPrice', 0), 2)}</td>")
    cells.append(f"<td>{_fmt(leg.get('askPrice', 0), 2)}</td>")
    cells.append(f"<td>{leg.get('askQty', 0)}</td>")
    
    return "".join(cells)
```

#### 4b. Update Header
```python
header = (
    "<tr class='rtmcp-th'>"
    # CALLS side (14 cols)
    "<th>Buildup</th><th>Vega</th><th>Theta</th><th>Gamma</th><th>Delta</th>"
    "<th>IV</th><th>Vol%</th><th>Volume</th><th>OI</th><th>LTP%</th><th>LTP</th>"
    "<th>BidQty</th><th>BidPrice</th><th>AskPrice</th><th>AskQty</th>"
    # Center
    "<th rowspan='2' class='rtmcp-strike'>Strike</th>"
    "<th rowspan='2' class='rtmcp-pcr'>PCR</th>"
    # PUTS side (14 cols) - mirrored order
    "<th>AskQty</th><th>AskPrice</th><th>BidPrice</th><th>BidQty</th>"
    "<th>LTP</th><th>LTP%</th><th>OI</th><th>Volume</th><th>Vol%</th>"
    "<th>IV</th><th>Delta</th><th>Gamma</th><th>Theta</th><th>Vega</th>"
    "<th>Buildup</th>"
    "</tr>"
)
```

#### 4c. Update Row Generation
```python
for row in rows:
    strike = row.get("strikePrice", 0)
    ce = row.get("CE")
    pe = row.get("PE")
    
    # Calculate PCR for this strike
    ce_oi = ce.get("openInterest", 0) if ce else 0
    pe_oi = pe.get("openInterest", 0) if pe else 0
    pcr = (pe_oi / ce_oi) if ce_oi else 0
    
    rows_html.append(
        "<tr>"
        + _leg_cells(ce, "CE")
        + f"<td class='rtmcp-strike'>{_fmt(strike, 0)}</td>"
        + f"<td class='rtmcp-pcr'>{_fmt(pcr, 2)}</td>"
        + _leg_cells(pe, "PE")
        + "</tr>"
    )
```

---

### Phase 5: Update CSS (30 min)

**File:** `rtmcp.css`

Add/modify styles for:
- 28-column table layout
- Greek value formatting (4 decimal places)
- PCR styling
- Bid/Ask column widths

```css
/* New column widths for Greek values */
.rtmcp-table th:nth-child(2),
.rtmcp-table th:nth-child(3),
.rtmcp-table th:nth-child(4),
.rtmcp-table th:nth-child(5),
.rtmcp-table th:nth-child(10),
.rtmcp-table th:nth-child(11),
.rtmcp-table th:nth-child(12),
.rtmcp-table th:nth-child(13) {
  width: 70px;
}

/* PCR column */
.rtmcp-pcr {
  background: var(--bg-secondary);
  font-weight: 600;
}

/* Bid/Ask columns */
.rtmcp-table td:nth-child(12),
.rtmcp-table td:nth-child(13),
.rtmcp-table td:nth-child(14),
.rtmcp-table td:nth-child(15),
.rtmcp-table td:nth-child(29),
.rtmcp-table td:nth-child(30),
.rtmcp-table td:nth-child(31),
.rtmcp-table td:nth-child(32) {
  width: 80px;
  font-size: 12px;
}
```

---

### Phase 6: Update app.js (Optional - 1 hour)

If needed, update the frontend to handle the new column structure.

**Current:** `app.js` renders market page HTML with dropdowns
**Needed:** Minor adjustments if API response structure changes

---

## File Changes Summary

| File | Changes | Time |
|------|---------|------|
| `client.py` | Extract volume change field | 15 min |
| `models.py` | Add `volumeChangePct` field | 5 min |
| `render.py` | Rewrite `_leg_cells()` + header | 2 hours |
| `rtmcp.css` | Update column widths | 30 min |
| `app.js` | Minor updates (if needed) | 1 hour |
| **Total** | | **~4 hours** |

---

## Verification Checklist

- [ ] Run test to dump raw Upstox API response
- [ ] Confirm volume change field name (or calculate from available data)
- [ ] Update `models.py` with new field
- [ ] Update `client.py` to extract volume change
- [ ] Update `render.py` with new 28-column layout
- [ ] Update CSS for new column widths
- [ ] Test with sample data
- [ ] Verify all columns display correctly
- [ ] Check horizontal scrolling works
- [ ] Test with NIFTY and BANKNIFTY data

---

## Next Steps

1. **First:** Verify volume change field name from Upstox API
2. **Then:** Implement Phase 2-6 above
3. **Finally:** Test and refine

**Ready to start Phase 1 (API verification)?**
