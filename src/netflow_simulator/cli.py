import click
import datetime
import holidays
import pandas as pd
import os
from typing import List, Dict
from tqdm import tqdm

from .scm.graph import SimulationSCM
from .core.network import WorkstationModel
from .core.appliance import RouterConfig
from .generators.traffic import TrafficGenerator
from .generators.protocols import PROTOCOLS
from .actors.admin import AdminActor
from .faults.engine import FaultEngine
from .exporters.csv_exporter import CSVExporter

@click.command()
@click.option('--start-date', default='2025-01-01', help='Start date YYYY-MM-DD')
@click.option('--days', default=365, help='Number of days to simulate')
@click.option('--output-dir', default='./output', help='Directory to save CSVs')
@click.option('--country', default='US', help='Country for holiday calendar')
@click.option('--use-confounders', is_flag=True, default=True, help='Enable confounding variables')
@click.option('--confounder-level', multiple=True, type=int, default=[2, 3], 
              help='Active confounding injections (1:Admin, 2:Traffic, 3:Network, 4:Recovery, 5:Lagged)')
@click.option('--confounder-multiplier', default=2.0, help='Strength of confounding effects')
def main(start_date, days, output_dir, country, use_confounders, confounder_level, confounder_multiplier):
    """
    Runs the Network Traffic Simulator.
    """
    # 1. Initialization
    click.echo(f"Initializing simulation for {days} days starting {start_date}...")
    if use_confounders:
        click.echo(f"Confounders enabled: {list(confounder_level)} (multiplier: {confounder_multiplier})")
    
    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + datetime.timedelta(days=days)
    
    conf_settings = {
        'enabled': use_confounders,
        'levels': list(confounder_level),
        'multiplier': confounder_multiplier
    }

    # Create output directory first
    os.makedirs(output_dir, exist_ok=True)

    scm = SimulationSCM(confounder_settings=conf_settings)
    # Export SCM for reference
    scm.export_graph(os.path.join(output_dir, "scm_dag.dot"))

    workstation_model = WorkstationModel()
    router_config = RouterConfig(supported_protocols=list(PROTOCOLS.keys()))
    
    traffic_generator = TrafficGenerator(router_config, workstation_model, confounder_settings=conf_settings)
    admin_actor = AdminActor(router_config, confounder_settings=conf_settings)
    fault_engine = FaultEngine(router_config, confounder_settings=conf_settings)
    exporter = CSVExporter(output_dir)
    
    holiday_cal = holidays.country_holidays(country)

    # Data Collectors
    all_traffic_records = []
    monthly_workstations = {} # { "YYYY-MM": [counts] }
    
    # 2. Simulation Loop
    current_dt = start_dt
    total_hours = days * 24
    
    # Track reboot state
    hours_since_reboot = 9999
    
    with tqdm(total=total_hours, desc="Simulating Hours") as pbar:
        while current_dt < end_dt:
            # -- Temporal Context --
            is_holiday = current_dt in holiday_cal
            is_weekend = current_dt.weekday() >= 5
            is_workday = not (is_holiday or is_weekend)
            
            # -- Daily Updates --
            if current_dt.hour == 0:
                count = workstation_model.next_day()
                month_key = current_dt.strftime("%Y-%m")
                if month_key not in monthly_workstations:
                    monthly_workstations[month_key] = []
                monthly_workstations[month_key].append(count)

            # -- System Status --
            if hours_since_reboot < 1: 
                # System is rebooting/down this hour
                current_traffic_flows = []  # No traffic
                hours_since_reboot += 1
            else:
                # -- Traffic Generation --
                current_traffic_flows = traffic_generator.generate_hourly_traffic(
                    current_dt, is_workday, hours_since_reboot=hours_since_reboot
                )
                
                # -- Admin Actions (AFTER traffic, so admin can react to traffic levels) --
                # This creates CONFOUNDING: admin throttles when traffic is high
                admin_actor.tick(current_dt, is_workday, current_traffic=current_traffic_flows)
                
                # Check for faults based on this traffic (with workstation count for interaction effect)
                if fault_engine.check_for_faults(current_dt, current_traffic_flows, 
                                                  workstation_count=workstation_model.get_count()):
                    # Crash!
                    hours_since_reboot = 0
                    # Reset router config after crash (volatile state lost)
                    router_config.reset_defaults(timestamp=current_dt)
                else:
                    hours_since_reboot += 1
                
                # Convert FlowRecords to dicts for storage
                for record in current_traffic_flows:
                    all_traffic_records.append({
                        "timestamp": record.timestamp.isoformat(),
                        "protocol": record.protocol,
                        "src_ip": record.src_ip,
                        "dst_ip": record.dst_ip,
                        "packets": record.packets,
                        "bytes": record.bytes,
                        "action": record.action
                    })

            current_dt += datetime.timedelta(hours=1)
            pbar.update(1)

    # 3. Export Data
    click.echo("Exporting data...")
    exporter.export_traffic(all_traffic_records)
    
    # Process admin logs
    admin_logs = admin_actor.admin_log + router_config.config_log
    # Sort by timestamp
    admin_logs.sort(key=lambda x: x['timestamp'])
    # formatting
    formatted_admin_logs = []
    for log in admin_logs:
        formatted_admin_logs.append({
            "timestamp": log['timestamp'].isoformat(),
            "actor": log.get('actor', 'System'),
            "action": log.get('action', ''),
            "details": str(log.get('details', '') or log.get('reason', ''))
        })
    exporter.export_admin_events(formatted_admin_logs)

    # Process system faults
    fault_logs = fault_engine.get_public_fault_logs()
    formatted_fault_logs = []
    for log in fault_logs:
        formatted_fault_logs.append({
            "timestamp": log['timestamp'].isoformat(),
            "event": log['event']
        })
    exporter.export_system_events(formatted_fault_logs)
    
    # Export ground truth (for validation AFTER causal analysis)
    ground_truth = fault_engine.get_ground_truth()
    if ground_truth:
        import csv
        from pathlib import Path
        gt_path = Path(exporter.output_dir) / "ground_truth_faults.csv"
        with open(gt_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=ground_truth[0].keys())
            writer.writeheader()
            writer.writerows(ground_truth)
        click.echo(f"Ground truth exported to {gt_path}")
    
    # 4. Generate Summary Markdown
    click.echo("Generating summary...")
    
    # Traffic per month
    traffic_df = pd.DataFrame(all_traffic_records)
    traffic_df['timestamp'] = pd.to_datetime(traffic_df['timestamp'])
    traffic_df['month'] = traffic_df['timestamp'].dt.strftime('%Y-%m')
    monthly_traffic = traffic_df.groupby('month')['bytes'].sum() / (1024 * 1024) # MB

    # Average Workstations per month
    avg_workstations = {m: sum(counts)/len(counts) for m, counts in monthly_workstations.items() if counts}

    summary_md = f"""# Simulation Summary
- **Period**: {start_date} to {current_dt.strftime('%Y-%m-%d')}
- **Total Protocols**: {len(PROTOCOLS)}
- **Total Crashes**: {len(fault_logs)}
- **Total System Changes**: {len(formatted_admin_logs)}

## Crash Timestamps
{chr(10).join([f"- {log['timestamp'].isoformat()}" for log in fault_logs]) if fault_logs else "None"}

## Monthly Traffic (MB)
| Month | Traffic (MB) |
|-------|--------------|
"""
    for month, vol in monthly_traffic.items():
        summary_md += f"| {month} | {vol:.2f} |\n"

    summary_md += """
## Monthly Workstation Count (Avg)
| Month | Avg Workstations |
|-------|------------------|
"""
    for month, avg in avg_workstations.items():
        summary_md += f"| {month} | {int(avg)} |\n"

    exporter.export_summary(summary_md)

    click.echo("Simulation complete.")


if __name__ == "__main__":
    main()
