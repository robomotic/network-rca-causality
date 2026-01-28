import pandas as pd
import numpy as np
import os
import datetime

def prepare_causal_data(output_dir='output', start_date='2025-01-28'):
    print("Loading data...")
    traffic_df = pd.read_csv(os.path.join(output_dir, 'traffic_flows.csv'))
    admin_df = pd.read_csv(os.path.join(output_dir, 'admin_events.csv'))
    system_df = pd.read_csv(os.path.join(output_dir, 'system_events.csv'))

    # Convert timestamps
    traffic_df['timestamp'] = pd.to_datetime(traffic_df['timestamp'])
    admin_df['timestamp'] = pd.to_datetime(admin_df['timestamp'])
    system_df['timestamp'] = pd.to_datetime(system_df['timestamp'])

    # Create hourly range
    start_dt = pd.to_datetime(start_date)
    end_dt = start_dt + pd.Timedelta(days=365)
    # Use 'h' instead of 'H' for pandas 2.0+
    hourly_range = pd.date_range(start=start_dt, end=end_dt, freq='h', inclusive='left')
    
    df = pd.DataFrame({'timestamp': hourly_range})
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.weekday
    
    # 1. Traffic Volumes (per-protocol bytes)
    print("Processing traffic volumes...")
    protocols = traffic_df['protocol'].unique()
    for proto in protocols:
        proto_data = traffic_df[traffic_df['protocol'] == proto]
        # Use 'h' for resample/floor frequency
        hourly_vol = proto_data.groupby(proto_data['timestamp'].dt.floor('h'))['bytes'].sum()
        df[f'{proto}_vol'] = df['timestamp'].map(hourly_vol).fillna(0)
        
        # Binary flag for "was throttled or denied"
        hourly_action = proto_data.groupby(proto_data['timestamp'].dt.floor('h'))['action'].apply(lambda x: x.mode()[0] if not x.empty else 'allow')
        df[f'{proto}_action'] = df['timestamp'].map(hourly_action).fillna('allow')
        df[f'{proto}_is_throttled'] = (df[f'{proto}_action'] == 'throttle').astype(int)
        df[f'{proto}_is_denied'] = (df[f'{proto}_action'] == 'deny').astype(int)

    # 2. System Crashes
    print("Processing system crashes...")
    df['crash_occurred'] = 0
    # Map crash to the hour it happened
    crash_hours = system_df['timestamp'].dt.floor('h')
    df.loc[df['timestamp'].isin(crash_hours), 'crash_occurred'] = 1

    # 3. Target variables for causal discovery at different lags
    # Next hour (lag 1)
    df['crash_next_hour'] = df['crash_occurred'].shift(-1).fillna(0).astype(int)
    
    # In 3 hours (lag 3) - matches our ground truth delay
    df['crash_in_3_hours'] = df['crash_occurred'].shift(-3).fillna(0).astype(int)
    
    # In 6 hours (lag 6) - for testing
    df['crash_in_6_hours'] = df['crash_occurred'].shift(-6).fillna(0).astype(int)

    # 4. Admin Activity
    print("Processing admin activity...")
    # Count admin changes per hour
    admin_counts = admin_df.groupby(admin_df['timestamp'].dt.floor('h')).size()
    df['admin_action_count'] = df['timestamp'].map(admin_counts).fillna(0)

    # Cleanup
    # Drop columns that are categorical but keep binary ones
    cols_to_drop = [c for c in df.columns if '_action' in c]
    df = df.drop(columns=cols_to_drop)

    output_path = os.path.join(output_dir, 'causal_features.csv')
    df.to_csv(output_path, index=False)
    print(f"Features saved to {output_path}")
    return df

if __name__ == "__main__":
    prepare_causal_data()
