import pandas as pd
import os
from typing import List, Dict

class CSVExporter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def export_traffic(self, traffic_data: List[Dict]):
        df = pd.DataFrame(traffic_data)
        path = os.path.join(self.output_dir, "traffic_flows.csv")
        df.to_csv(path, index=False)
        print(f"Traffic flows exported to {path}")

    def export_admin_events(self, admin_data: List[Dict]):
        df = pd.DataFrame(admin_data)
        path = os.path.join(self.output_dir, "admin_events.csv")
        df.to_csv(path, index=False)
        print(f"Admin events exported to {path}")

    def export_system_events(self, system_data: List[Dict]):
        df = pd.DataFrame(system_data)
        path = os.path.join(self.output_dir, "system_events.csv")
        df.to_csv(path, index=False)
        print(f"System events exported to {path}")

    def export_summary(self, summary_text: str):
        path = os.path.join(self.output_dir, "summary.md")
        with open(path, "w") as f:
            f.write(summary_text)
        print(f"Simulation summary exported to {path}")
