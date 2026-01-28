# Network Traffic Simulator Experiment Configuration

## Overview

This document describes the optimized configuration for running the NetFlow simulator to generate data for Root Cause Analysis (RCA) experiments demonstrating causal discovery methods.

---

## Recommended Configuration

### Command

```bash
python -m netflow_simulator \
    --days 365 \
    --output-dir ./output \
    --start-date 2025-01-01 \
    --use-confounders \
    --confounder-level 1 \
    --confounder-level 2 \
    --confounder-level 3 \
    --confounder-level 4 \
    --confounder-level 5 \
    --confounder-multiplier 3.5
```

### Parameters Explained

| Parameter | Value | Description |
|-----------|-------|-------------|
| `--days` | 365 | Full year of data for robust statistical analysis |
| `--output-dir` | ./output | Directory for CSV exports |
| `--start-date` | 2025-01-01 | Simulation start date |
| `--use-confounders` | flag | Enable confounding mechanisms |
| `--confounder-level` | 1,2,3,4,5 | All confounding mechanisms active |
| `--confounder-multiplier` | 3.5 | Optimal strength (validated via tuning) |

---

## Confounding Mechanisms

The simulator implements 5 levels of confounding to create realistic, challenging scenarios for causal analysis:

### Level 1: Admin Reactive Behavior
**Mechanism:** Administrator throttles RSTP in response to high HTTP/HTTPS traffic

**Causal Path:**
```
High HTTP traffic → Admin investigates → Throttles RSTP → Crash (3h later)
```

**Effect:** Creates spurious correlation between HTTP and crashes (backdoor path)

**Why it matters:** This is the primary mechanism that creates misleading correlations. Simple correlation analysis will show HTTP as "causal" when it's actually just triggering admin behavior.

---

### Level 2: Cross-Protocol Traffic Correlation
**Mechanism:** DNS, HTTP, and HTTPS traffic spike together in coordinated "group bursts"

**Effect:** Creates contemporaneous correlations between infrastructure protocols

**Why it matters:** Real networks show correlated traffic patterns. DNS lookups precede HTTP requests, creating natural dependencies.

---

### Level 3: Workstation Common Cause
**Mechanism:** High workstation count amplifies both SMB and RSTP traffic

**Causal Path:**
```
High workstation count → More SMB traffic (file sharing)
                      → More RSTP traffic (topology changes)
```

**Effect:** SMB and RSTP become correlated through a common cause

**Why it matters:** Creates a classic "common cause" confounding scenario. SMB appears related to crashes but is actually driven by the same underlying factor (workstation count) as RSTP.

---

### Level 4: Post-Crash Recovery Surges
**Mechanism:** After a crash, DNS, HTTP, HTTPS, and NTP show traffic surges

**Causal Path:**
```
System crash → Reboot → Systems reconnect → DNS/HTTP/NTP surge
```

**Effect:** Reverse causation artifacts (protocol spikes follow crashes)

**Why it matters:** Naive temporal analysis might misinterpret these post-crash spikes as predictive, when they're actually consequences.

---

### Level 5: Lagged HTTP Confounder
**Mechanism:** HTTP traffic spikes during business hours (9-17), matching the timing window when RSTP-induced crashes can occur

**Effect:** HTTP spikes appear to "predict" crashes with the same 3-hour lag pattern as the true cause

**Why it matters:** This directly challenges temporal causal methods by mimicking the true causal lag structure. HTTP peaks at hours that are 3 hours before potential crash windows, creating a lag pattern similar to RSTP's causal link.

---

## Ground Truth Mechanism

**The actual cause of crashes:**

```
RSTP throttled
    AND
RSTP volume > 10KB
    AND
Workstation count ≥ 70
    AND
Business hours (9-17)
    ↓
80% probability
    ↓
Crash scheduled for T+3 hours
```

Only RSTP is causal. All other protocol correlations are spurious, created by the confounding mechanisms.

---

## Expected Outcomes

### Section 1.1: Non-Causal Analysis (Exploratory)

**Heatmaps and Correlation:**
- Will show HTTP throttling correlated with crashes (r≈0.30, p<0.001)
- Will show RSTP throttling correlated with crashes (r≈0.24, p<0.001)
- **Verdict:** Cannot distinguish true cause from confounder

**Anomaly Detection:**
- Will flag HTTP, RSTP, and other protocol spikes
- **Verdict:** Useful for outlier detection but not causal inference

**Decision Trees:**
- May discover interaction rules involving HTTP and RSTP
- **Verdict:** Reveals patterns but descriptive, not causal

---

### Section 2: Causal Discovery

**Simple Correlation (Pearson):**
- HTTP: r=0.299, p<0.001 ❌ (spurious)
- RSTP: r=0.243, p<0.001 ✅ (true cause)
- **Verdict:** ❌ FAILS - Cannot distinguish causation from correlation

**Granger Causality:**
- Will detect RSTP → crash predictive relationship
- May also flag HTTP as predictive
- **Verdict:** ⚠️ PARTIAL - Detects predictive precedence but struggles with confounders

**PCMCI (Tigramite):**
- Will identify RSTP → crash at lag 3 as primary causal link
- May show weak HTTP link but RSTP will dominate
- **Verdict:** ✅ SUCCESS - Correctly identifies RSTP at lag 3, conditional independence filters out most confounders

**DoWhy (Propensity Score Matching):**
- Will estimate treatment effect of RSTP throttling
- Handles confounders through backdoor adjustment
- **Verdict:** ✅ SUCCESS - Correctly estimates causal effect with confounder adjustment

---

## Validation Results

The configuration was validated through systematic tuning across multipliers 3.0-5.0:

| Multiplier | Crashes | Spurious Corr | RSTP Detected | PCMCI False Pos | Score |
|------------|---------|---------------|---------------|-----------------|-------|
| 3.0 | 8 | 0 | ✅ Yes | 1 (DNS) | 55/100 |
| **3.5** | **11** | **1 (HTTP)** | **✅ Yes** | **1 (HTTP)** | **65/100** |
| 4.0 | 5 | 0 | ✅ Yes | 0 | 60/100 |
| 4.5 | 9 | 0 | ✅ Yes | 0 | 60/100 |
| 5.0 | 1 | 0 | ✅ Yes | 0 | 60/100 |

**Multiplier 3.5 selected because:**
- ✅ Creates exactly 1 spurious correlation (HTTP) - demonstrates the challenge
- ✅ PCMCI still correctly identifies RSTP at lag 3 - demonstrates the solution
- ✅ Sufficient crash frequency (11 in 30 days) for statistical power
- ✅ Realistic complexity without overwhelming the analysis

---

## Output Files

After running the simulation, the following files will be generated in `./output/`:

### Data Files

1. **traffic_flows.csv**
   - Hourly NetFlow records
   - Columns: timestamp, protocol, src_ip, dst_ip, packets, bytes, action

2. **admin_events.csv**
   - Administrator configuration changes
   - Columns: timestamp, actor, action, details

3. **system_events.csv**
   - System crashes and reboots
   - Columns: timestamp, event

4. **ground_truth_faults.csv**
   - Hidden ground truth (for validation ONLY after analysis)
   - Columns: condition_met_time, scheduled_crash_time, rstp_throttled, rstp_volume_bytes, workstation_count, hour, delay_hours

### Metadata

5. **summary.md**
   - Simulation summary statistics
   - Monthly traffic and workstation counts

6. **scm_dag.dot**
   - Structural Causal Model graph
   - Visualizes the causal relationships (including confounders)

---

## Usage Workflow

### Step 1: Generate Data

```bash
# Full production run
python -m netflow_simulator \
    --days 365 \
    --output-dir ./output \
    --confounder-multiplier 3.5 \
    --confounder-level 1 \
    --confounder-level 2 \
    --confounder-level 3 \
    --confounder-level 4 \
    --confounder-level 5

# Expected runtime: ~3-5 minutes for 365 days
```

### Step 2: Prepare Features

```bash
python experiments/prepare_data.py

# Generates: output/causal_features.csv
# Aggregates hourly features for analysis
```

### Step 3: Run Exploratory Analysis

```bash
python experiments/exploratory_analysis.py

# Generates:
# - crash_proximity_heatmap.png
# - anomaly_detection.png
# - decision_tree.png
```

### Step 4: Run Causal Discovery

```bash
python experiments/causal_discovery.py

# Runs:
# - PCMCI temporal causal discovery
# - DoWhy propensity score matching
```

### Step 5: Generate Full Report

```bash
python experiments/run_experiments.py

# Generates: RCA_REPORT.html and RCA_REPORT.md
```

---

## Alternative Configurations

### Clean Baseline (No Confounders)

For validating PCMCI without confounders:

```bash
python -m netflow_simulator \
    --days 365 \
    --no-use-confounders
```

Expected: Only RSTP shows correlation and causal links.

---

### Maximum Confounding

For stress-testing causal methods:

```bash
python -m netflow_simulator \
    --days 365 \
    --confounder-multiplier 5.0 \
    --confounder-level 1 \
    --confounder-level 2 \
    --confounder-level 3 \
    --confounder-level 4 \
    --confounder-level 5
```

Expected: Very few crashes, but PCMCI should still identify RSTP.

---

### Minimal Confounding

For subtle confounding effects:

```bash
python -m netflow_simulator \
    --days 365 \
    --confounder-multiplier 2.0 \
    --confounder-level 2 \
    --confounder-level 3
```

Expected: No spurious correlations, clean PCMCI results.

---

## Key Insights

### Why This Configuration Matters

1. **Demonstrates Real-World Complexity**
   - Networks have correlated traffic patterns
   - Admins react to multiple signals
   - Common causes create spurious associations

2. **Validates Causal Methods**
   - Simple correlation fails (confounded)
   - PCMCI succeeds (conditional independence)
   - Shows why temporal + conditional methods are necessary

3. **Educational Value**
   - Clear ground truth for validation
   - Multiple confounding mechanisms to study
   - Realistic scenario for RCA training

### Interpretation Guidelines

**When analyzing results:**

1. **Don't peek at ground_truth_faults.csv until after causal analysis**
   - This defeats the purpose of blind validation

2. **Compare methods systematically**
   - Which methods flag HTTP as causal? (wrong)
   - Which methods flag RSTP at lag 3? (correct)

3. **Look for the lag-3 pattern**
   - Ground truth: RSTP conditions met → 3h → crash
   - PCMCI should recover this exact lag structure

4. **Assess robustness**
   - Do results hold with different lag ranges (tau_max)?
   - Do results hold with different alpha levels?

---

## References

### Tuning Reports

- `experiments/CONFOUNDER_TUNING_REPORT.md` - Initial tuning (levels 2-3)
- `experiments/CONFOUNDER_TUNING_FULL_REPORT.md` - Comprehensive tuning (levels 1-5)

### Code Documentation

- `src/netflow_simulator/faults/engine.py` - Crash mechanism
- `src/netflow_simulator/actors/admin.py` - Admin reactive behavior
- `src/netflow_simulator/generators/traffic.py` - Confounding logic
- `src/netflow_simulator/scm/graph.py` - Structural causal model

---

## Troubleshooting

### Issue: No crashes generated

**Cause:** RSTP throttling conditions not met frequently enough

**Solution:** Reduce `RSTP_VOLUME_THRESHOLD_BYTES` in `faults/engine.py` or increase simulation duration

---

### Issue: Too many crashes

**Cause:** Confounding multiplier too high or fault probability too high

**Solution:** Reduce `--confounder-multiplier` or decrease `FAULT_PROBABILITY` in `faults/engine.py`

---

### Issue: No spurious correlations

**Cause:** Confounder multiplier too low or Level 1 not enabled

**Solution:** Ensure `--confounder-level 1` is set and multiplier ≥ 3.5

---

### Issue: PCMCI very slow

**Cause:** Too many variables or too large tau_max

**Solution:** Reduce variable count or tau_max in `experiments/causal_discovery.py`

---

## Contact & Support

For questions about this configuration or the simulator:
- Review the tuning reports in `experiments/`
- Check the codebase documentation in `src/netflow_simulator/`
- Examine ground truth after analysis in `output/ground_truth_faults.csv`

---

**Generated:** 28 January 2026  
**Configuration Version:** 1.0 (Optimized)  
**Validated:** 30-day tuning runs across multipliers 3.0-5.0
