import pandas as pd
df = pd.read_csv('output/causal_features.csv')
throttled = df[df['RSTP_is_throttled'] == 1]
print(f"Hours where RSTP was throttled: {len(throttled)}")
if len(throttled) > 0:
    print(f"Max RSTP volume during throttling: {throttled['RSTP_vol'].max() / (1024*1024):.2f} MB")
