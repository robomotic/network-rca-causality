# Netflow Network Traffic Simulator

A Python-based simulator generating hourly traffic data for a private network with a Cisco router/switch connected to an ISP.

## Features

- **SCM/DAG Modeling**: Uses a Structural Causal Model to define dependencies between time, admin actions, usage, and faults.
- **Realistic Traffic Generation**: Simulates 10+ protocols (HTTP, HTTPS, DNS, SMTP, SSH, RDP, SMB, FTP, NTP, ICMP, RSTP, SNMP) based on time of day, day of week, and holidays.
- **Workstation Dynamics**: Endpoint count fluctuates daily.
- **Admin Simulation**: Simulated IT admin changes router configs (allow/deny, throttle) during business hours.
- **Fault Injection**: Simulates system crashes based on specific traffic conditions (e.g. RSTP + throttling + volume).
- **CSV Output**: produces `traffic_flows.csv`, `admin_events.csv`, and `system_events.csv`.

## Fault & Recovery Logic

### Causal Mechanism (Ground Truth)

The simulator implements a **deterministic causal chain** designed to be discoverable by causal inference methods while resisting naive correlation analysis:

```
RSTP Traffic Volume > 10KB  +  RSTP Throttled  →  [3-hour delay]  →  System Crash (80% probability)
```

**Interaction Effects** (all must be true for crash to trigger):
- RSTP protocol is currently throttled
- RSTP traffic volume exceeds 10KB threshold
- Active workstations > 70% of maximum (100)
- Current hour is during business hours (9 AM - 5 PM)

**Time-Delayed Causation**: When all conditions are met, a crash is scheduled for **3 hours later**. This lag defeats simple contemporaneous correlation analysis and requires time-series causal discovery methods (e.g., PCMCI with appropriate lag parameters).

**Zero Random Crashes**: There are NO random crashes. Every crash has a deterministic causal antecedent (RSTP throttling + volume threshold).

### Confounding Behavior

The admin actor introduces confounding correlations:

1. **Traffic-Reactive Throttling**: Admin is 3x more likely to throttle when traffic is high. This creates spurious correlation between high traffic and crashes (via the throttling path).

2. **RSTP Preference**: Admin has 4x bias toward throttling RSTP specifically, since RSTP generates the most traffic during business hours.

3. **Business Hours Correlation**: Both RSTP traffic AND admin activity peak during business hours, creating a confounding temporal pattern.

### Recovery Steps

When a system crash occurs:

1. **State Reset**: The appliance undergoes a simulated cold reboot. All **volatile configurations** (running-config) are wiped.
2. **Configuration Reversion**: The router reverts to its **default state** (all protocols allowed, all throttling removed). This mimics a real device returning to its startup-config.
3. **Boot Delay**: Traffic generation is paused for the remainder of the hour in which the crash occurred.
4. **Admin Blindness**: The simulated IT Admin does not know the specific cause of the crash (Kernel Panics are logged generically). Consequently, the admin may eventually re-apply the same problematic configuration (throttling) if the underlying SCM triggers another intervention, leading to potential recurring faults.
5. **Logging**: A generic crash event is recorded in `system_events.csv` without mentioning the specific causal trigger, preserving the mystery for downstream analysis.

### Causal Discovery Challenge

This simulation is designed as a benchmark for causal discovery algorithms:

| Method | Expected Outcome |
|--------|------------------|
| Simple Correlation | **Fails** - Traffic volume correlates with crashes but doesn't cause them directly |
| Granger Causality | **Partial** - May detect lag but misattributes cause |
| PCMCI (Tigramite) | **Should Succeed** - With lag=3, should identify throttle→crash link |
| DoWhy/Backdoor | **Should Succeed** - Conditioning on confounders should reveal true effect |

**Ground Truth File**: After simulation, check `output/ground_truth_faults.csv` for the actual causal triggers.

## Installation

1. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   (Or using `pip install .`)

## Usage

Run the simulator using the CLI:

```bash
python -m netflow_simulator.cli --days 365 --start-date 2025-01-01
```

Options:
- `--days`: Number of days to simulate (default: 365)
- `--start-date`: Start date in YYYY-MM-DD format.
- `--output-dir`: Directory to save CSV files.
- `--country`: Country code for holidays (default: US).

## Output

Inside the `output/` folder:
- `traffic_flows.csv`: Netflow records (hourly granularity).
- `admin_events.csv`: Log of admin configuration changes.
- `system_events.csv`: Log of system crashes/reboots.
- `ground_truth_faults.csv`: Causal triggers for each crash (for validation).
- `scm_dag.dot`: Graphviz DOT file of the causal model.
- `summary.md`: High-level statistics and crash timeline.


## Visualization

To view the causal model:
```bash
dot -Tpng output/scm_dag.dot -o output/scm_dag.png
```
