"""
Phase 1: Exploratory (Non-Causal) Analysis
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.ensemble import IsolationForest
import os

def crash_proximity_heatmap(df, output_dir='experiments'):
    """Analyze correlations between protocol variables before and after system crashes."""
    print("\n=== Crash Proximity Correlation Analysis ===")
    
    from scipy.stats import pearsonr
    
    # Find crash times
    crash_times = df[df['crash_occurred'] == 1]['timestamp'].values
    
    if len(crash_times) == 0:
        print("No crashes found in data.")
        return None
    
    protocols = ['RSTP', 'HTTP', 'HTTPS', 'DNS', 'SMB']
    
    # Define time windows for before/after crash analysis
    before_window_hours = 6  # 6 hours before crash
    after_window_hours = 6   # 6 hours after crash
    
    # Collect data for before/after crash periods
    before_crash_data = []
    after_crash_data = []
    
    for crash_time in crash_times:
        crash_dt = pd.to_datetime(crash_time)
        
        # Before crash window
        before_start = crash_dt - pd.Timedelta(hours=before_window_hours)
        before_mask = (df['timestamp'] >= before_start) & (df['timestamp'] < crash_dt)
        before_df = df[before_mask]
        
        # After crash window  
        after_end = crash_dt + pd.Timedelta(hours=after_window_hours)
        after_mask = (df['timestamp'] >= crash_dt) & (df['timestamp'] < after_end)
        after_df = df[after_mask]
        
        if len(before_df) > 0:
            before_crash_data.append(before_df)
        if len(after_df) > 0:
            after_crash_data.append(after_df)
    
    if not before_crash_data:
        print("No proximity data found.")
        return None
    
    # Combine all before/after periods
    before_combined = pd.concat(before_crash_data, ignore_index=True)
    after_combined = pd.concat(after_crash_data, ignore_index=True) if after_crash_data else pd.DataFrame()
    
    # Compute correlations between all protocol measures
    correlation_results = {
        'before': [],
        'after': []
    }
    
    # Get all variable pairs
    variables = []
    for proto in protocols:
        variables.append(f'{proto}_is_throttled')
        variables.append(f'{proto}_vol')
    
    # Compute correlations for BEFORE crash period
    print(f"\nAnalyzing {len(before_combined)} hours before {len(crash_times)} crashes...")
    for i, var1 in enumerate(variables):
        for var2 in variables[i+1:]:
            if var1 in before_combined.columns and var2 in before_combined.columns:
                try:
                    corr, pval = pearsonr(before_combined[var1], before_combined[var2])
                    correlation_results['before'].append({
                        'var1': var1,
                        'var2': var2,
                        'correlation': corr,
                        'p_value': pval,
                        'significant': pval < 0.05
                    })
                except:
                    pass
    
    # Compute correlations for AFTER crash period
    if len(after_combined) > 0:
        print(f"Analyzing {len(after_combined)} hours after crashes...")
        for i, var1 in enumerate(variables):
            for var2 in variables[i+1:]:
                if var1 in after_combined.columns and var2 in after_combined.columns:
                    try:
                        corr, pval = pearsonr(after_combined[var1], after_combined[var2])
                        correlation_results['after'].append({
                            'var1': var1,
                            'var2': var2,
                            'correlation': corr,
                            'p_value': pval,
                            'significant': pval < 0.05
                        })
                    except:
                        pass
    
    # Summary statistics
    summary = {
        'total_crashes': len(crash_times),
        'before_hours': len(before_combined),
        'after_hours': len(after_combined),
        'correlations': correlation_results
    }
    
    # Print top correlations
    before_sorted = sorted(correlation_results['before'], key=lambda x: abs(x['correlation']), reverse=True)[:5]
    print("\nTop 5 correlations BEFORE crashes:")
    for corr in before_sorted:
        print(f"  {corr['var1']} <-> {corr['var2']}: r={corr['correlation']:.4f}, p={corr['p_value']:.4e}")
    
    if correlation_results['after']:
        after_sorted = sorted(correlation_results['after'], key=lambda x: abs(x['correlation']), reverse=True)[:5]
        print("\nTop 5 correlations AFTER crashes:")
        for corr in after_sorted:
            print(f"  {corr['var1']} <-> {corr['var2']}: r={corr['correlation']:.4f}, p={corr['p_value']:.4e}")
    
    return summary

def anomaly_detection(df, output_dir='experiments'):
    """Flag unusual traffic spikes per protocol using Isolation Forest."""
    print("\n=== Anomaly Detection ===")
    
    protocols = ['RSTP', 'HTTP', 'HTTPS', 'DNS', 'SMB']
    
    # Detect anomalies for each protocol
    anomaly_results = {}
    
    for proto in protocols:
        vol_col = f'{proto}_vol'
        if vol_col in df.columns:
            # Fit Isolation Forest
            iso_forest = IsolationForest(contamination=0.05, random_state=42)
            anomaly_col = f'{proto}_anomaly'
            df[anomaly_col] = iso_forest.fit_predict(df[[vol_col]].values)
            df[anomaly_col] = (df[anomaly_col] == -1).astype(int)  # 1 = anomaly
            
            # Find anomalies
            anomalies = df[df[anomaly_col] == 1].copy()
            anomalies_with_crash = anomalies[anomalies['crash_occurred'] == 1]
            
            anomaly_results[proto] = {
                'count': len(anomalies),
                'rate': len(anomalies) / len(df),
                'crashes': len(anomalies_with_crash)
            }
            
            print(f"{proto}: {len(anomalies)} anomalies ({100*len(anomalies)/len(df):.2f}%), {len(anomalies_with_crash)} coincide with crashes")
    
    total_crashes = df['crash_occurred'].sum()
    
    # Visualize all protocols
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, proto in enumerate(protocols):
        vol_col = f'{proto}_vol'
        anomaly_col = f'{proto}_anomaly'
        
        if vol_col in df.columns and anomaly_col in df.columns:
            anomalies = df[df[anomaly_col] == 1]
            
            # Time series with anomalies
            axes[idx].plot(df.index, df[vol_col], alpha=0.3, label=f'{proto} Volume', linewidth=0.5)
            axes[idx].scatter(anomalies.index, anomalies[vol_col], color='red', 
                            s=20, label='Anomalies', zorder=5, alpha=0.6)
            axes[idx].set_ylabel('Volume (bytes)')
            axes[idx].set_title(f'{proto} Traffic Anomalies')
            axes[idx].legend()
    
    # Last plot: Summary statistics
    axes[5].axis('off')
    summary_text = "Anomaly Detection Summary\n" + "="*30 + "\n\n"
    for proto, res in anomaly_results.items():
        summary_text += f"{proto}:\n"
        summary_text += f"  {res['count']} anomalies ({res['rate']*100:.1f}%)\n"
        summary_text += f"  {res['crashes']} during crashes\n\n"
    summary_text += f"Total Crashes: {total_crashes}"
    
    axes[5].text(0.1, 0.5, summary_text, fontsize=10, family='monospace',
                verticalalignment='center',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/anomaly_detection.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_dir}/anomaly_detection.png")
    
    return anomaly_results

def decision_tree_analysis(df, output_dir='experiments'):
    """Train decision tree to reveal interaction patterns."""
    print("\n=== Decision Tree Analysis ===")
    
    # Features: use all available protocol columns
    protocols = ['RSTP', 'HTTP', 'HTTPS', 'DNS', 'SMB']
    feature_cols = ['hour', 'day_of_week']
    
    # Add all protocol features
    for proto in protocols:
        vol_col = f'{proto}_vol'
        throttle_col = f'{proto}_is_throttled'
        if vol_col in df.columns:
            feature_cols.append(vol_col)
        if throttle_col in df.columns:
            feature_cols.append(throttle_col)
    
    X = df[feature_cols].fillna(0)
    y = df['crash_occurred']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    
    # Train shallow tree (for interpretability)
    dt = DecisionTreeClassifier(max_depth=4, min_samples_split=50, random_state=42)
    dt.fit(X_train, y_train)
    
    # Evaluate
    y_pred = dt.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Crash', 'Crash']))
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': dt.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nFeature Importance:")
    print(importance)
    
    # Visualize tree and importance
    fig, axes = plt.subplots(2, 1, figsize=(20, 14))
    
    # Tree structure
    plot_tree(dt, filled=True, feature_names=feature_cols, 
              class_names=['No Crash', 'Crash'], ax=axes[0], fontsize=7)
    axes[0].set_title('Decision Tree: Crash Prediction (Multi-Protocol Interaction Patterns)', fontsize=14)
    
    # Feature importance - only show top 10
    top_features = importance.head(10)
    axes[1].barh(top_features['feature'], top_features['importance'])
    axes[1].set_xlabel('Importance')
    axes[1].set_title('Top 10 Feature Importance for Crash Prediction')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/decision_tree.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_dir}/decision_tree.png")
    
    # Extract results
    report_dict = classification_report(y_test, y_pred, output_dict=True)
    
    return {
        'accuracy': (y_pred == y_test).mean(),
        'precision_crash': report_dict.get('1', {}).get('precision', 0.0),
        'recall_crash': report_dict.get('1', {}).get('recall', 0.0),
        'top_feature': importance.iloc[0]['feature'],
        'top_importance': importance.iloc[0]['importance']
    }

if __name__ == "__main__":
    from prepare_data import prepare_causal_data
    
    print("Loading data...")
    df = prepare_causal_data()
    
    # Run all exploratory analyses
    heatmap_res = crash_proximity_heatmap(df)
    anomaly_res = anomaly_detection(df)
    tree_res = decision_tree_analysis(df)
    
    print("\n=== Summary ===")
    print("Heatmap:", heatmap_res)
    print("Anomalies:", anomaly_res)
    print("Decision Tree:", tree_res)
