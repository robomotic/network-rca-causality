import pandas as pd
import numpy as np
import os

def analyze_crash_precursors(input_path='output/causal_features.csv'):
    df = pd.read_csv(input_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Identify crash hours
    crash_indices = df[df['crash_occurred'] == 1].index
    print(f"Total crashes found: {len(crash_indices)}")
    
    precursor_data = []
    
    for idx in crash_indices:
        # Look back 12 hours
        start_idx = max(0, idx - 12)
        window = df.iloc[start_idx:idx+1]
        
        # Check if RSTP was throttled in this window
        was_throttled = window['RSTP_is_throttled'].any()
        max_rstp_vol = window['RSTP_vol'].max()
        
        precursor_data.append({
            'timestamp': df.loc[idx, 'timestamp'],
            'rstp_was_throttled': was_throttled,
            'max_rstp_vol_before_crash': max_rstp_vol,
            'hour_of_crash': df.loc[idx, 'hour']
        })
        
    pre_df = pd.DataFrame(precursor_data)
    print("\n--- Crash Precursor Analysis ---")
    print(pre_df)
    
    # Baseline comparison (random non-crash hours)
    non_crash_indices = df[df['crash_occurred'] == 0].sample(20).index
    non_crash_precursors = []
    for idx in non_crash_indices:
        start_idx = max(0, idx - 12)
        window = df.iloc[start_idx:idx+1]
        non_crash_precursors.append({
            'rstp_was_throttled': window['RSTP_is_throttled'].any(),
            'max_rstp_vol': window['RSTP_vol'].max()
        })
    
    nc_df = pd.DataFrame(non_crash_precursors)
    
    print("\n--- Summary Comparison ---")
    print(f"Crashes with RSTP throttling in prev 12h: {pre_df['rstp_was_throttled'].sum()}/{len(pre_df)}")
    print(f"Random hours with RSTP throttling in prev 12h: {nc_df['rstp_was_throttled'].sum()}/{len(nc_df)}")
    
    print(f"\nAvg RSTP volume before crash: {pre_df['max_rstp_vol_before_crash'].mean() / (1024*1024):.2f} MB")
    print(f"Avg RSTP volume in random hours: {nc_df['max_rstp_vol'].mean() / (1024*1024):.2f} MB")

if __name__ == "__main__":
    analyze_crash_precursors()
