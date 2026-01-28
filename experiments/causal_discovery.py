import pandas as pd
import numpy as np
from tigramite import data_processing as pp
from tigramite.pcmci import PCMCI
from tigramite.independence_tests.parcorr import ParCorr
from dowhy import CausalModel
import os

def run_tigramite(df):
    print("\n=== Tigramite Time-Series Causal Discovery ===")
    
    # Include router configuration variables for multiple protocols
    variables = [
        'hour', 
        'day_of_week',
        # RSTP (primary suspect)
        'RSTP_vol', 
        'RSTP_is_throttled', 
        'RSTP_is_denied',
        # Other high-traffic protocols
        'HTTP_vol',
        'HTTP_is_throttled',
        'HTTPS_vol', 
        'HTTPS_is_throttled',
        'DNS_vol',
        'DNS_is_throttled',
        'SMB_vol',
        'SMB_is_throttled',
        # Target variable
        'crash_occurred'
    ]
    
    available_vars = [v for v in variables if v in df.columns]
    print(f"Using {len(available_vars)} variables: {available_vars}")
    
    data = df[available_vars].values
    dataframe = pp.DataFrame(data, var_names=available_vars)
    
    parcorr = ParCorr(significance='analytic')
    pcmci = PCMCI(dataframe=dataframe, cond_ind_test=parcorr, verbosity=0)
    
    # Test with tau_max=6 to capture the 3-hour delay
    print("\nRunning PCMCI with tau_max=6...")
    results = pcmci.run_pcmci(tau_max=6, pc_alpha=0.05)
    
    print("\nSignificant Causal Links (alpha=0.05):")
    pcmci.print_significant_links(
        p_matrix=results['p_matrix'], 
        val_matrix=results['val_matrix'], 
        alpha_level=0.05
    )
    
    # Check specific hypotheses for each protocol throttle -> crash
    crash_idx = available_vars.index('crash_occurred') if 'crash_occurred' in available_vars else None
    
    if crash_idx is not None:
        print(f"\n--- Checking Protocol Throttling -> Crash Hypotheses ---")
        
        for protocol in ['RSTP', 'HTTP', 'HTTPS', 'DNS', 'SMB']:
            throttle_var = f'{protocol}_is_throttled'
            if throttle_var in available_vars:
                throttle_idx = available_vars.index(throttle_var)
                print(f"\n{protocol}_is_throttled -> crash:")
                
                significant_lags = []
                for lag in range(1, 7):
                    p_val = results['p_matrix'][throttle_idx, crash_idx, lag]
                    val = results['val_matrix'][throttle_idx, crash_idx, lag]
                    sig = "***" if p_val < 0.05 else ""
                    print(f"  Lag {lag}: p={p_val:.4f}, val={val:.4f} {sig}")
                    if p_val < 0.05:
                        significant_lags.append((lag, val, p_val))
                
                if significant_lags:
                    best_lag = max(significant_lags, key=lambda x: abs(x[1]))
                    print(f"  → Strongest link at lag {best_lag[0]} (val={best_lag[1]:.4f})")
                else:
                    print(f"  → No significant causal link found")
    
    return results, available_vars

def run_dowhy(df):
    print("\n=== DoWhy Causal Effect Estimation ===")
    
    # Test RSTP specifically (primary hypothesis)
    causal_graph = """
    digraph {
        hour -> RSTP_is_throttled;
        day_of_week -> RSTP_is_throttled;
        RSTP_is_throttled -> RSTP_vol;
        RSTP_vol -> crash_occurred;
        RSTP_is_throttled -> crash_occurred;
        hour -> crash_occurred;
        day_of_week -> crash_occurred;
    }
    """
    
    model = CausalModel(
        data=df,
        treatment='RSTP_is_throttled',
        outcome='crash_occurred',
        graph=causal_graph.replace('\n', ' ')
    )
    
    # 2. Identify causal effect
    identified_estimand = model.identify_effect(proceed_when_unidentifiable=True)
    print("\n--- RSTP Throttling Effect ---")
    print("Identified Estimand:")
    print(identified_estimand)
    
    # 3. Estimate the causal effect
    print("\nEstimating causal effect using Propensity Score Matching...")
    estimate = model.estimate_effect(identified_estimand,
                                     method_name="backdoor.propensity_score_matching")
    
    print(f"Causal Effect (ATE): {estimate.value}")
    print(f"Interpretation: Throttling RSTP {'increases' if estimate.value > 0 else 'decreases'} crash probability by {abs(estimate.value):.4f}")
    
    # 4. Refute
    print("\nRefuting the estimate...")
    refute = model.refute_estimate(identified_estimand, estimate,
                                   method_name="random_common_cause", num_simulations=10)
    print(refute)
    
    # Test other protocols for comparison
    print("\n--- Testing Other Protocols for Comparison ---")
    for protocol in ['HTTP', 'HTTPS', 'DNS']:
        throttle_var = f'{protocol}_is_throttled'
        if throttle_var in df.columns and df[throttle_var].sum() > 0:
            try:
                print(f"\n{protocol} throttling effect:")
                simple_graph = f"""
                digraph {{
                    hour -> {throttle_var};
                    {throttle_var} -> crash_occurred;
                    hour -> crash_occurred;
                }}
                """
                model_test = CausalModel(
                    data=df,
                    treatment=throttle_var,
                    outcome='crash_occurred',
                    graph=simple_graph.replace('\n', ' ')
                )
                est_test = model_test.identify_effect(proceed_when_unidentifiable=True)
                effect_test = model_test.estimate_effect(est_test, method_name="backdoor.propensity_score_matching")
                print(f"  ATE: {effect_test.value:.4f}")
            except Exception as e:
                print(f"  Could not estimate: {e}")

if __name__ == "__main__":
    input_path = 'output/causal_features.csv'
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found. Run prepare_data.py first.")
    else:
        df = pd.read_csv(input_path)
        run_tigramite(df)
        run_dowhy(df)
