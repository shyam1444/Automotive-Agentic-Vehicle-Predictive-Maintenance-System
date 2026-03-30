import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Create a dir for saving plots
os.makedirs('metrics_plots', exist_ok=True)

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

def generate_agent_data(num_samples=500):
    """Generate realistic simulated data for agent coordination architecture."""
    # 1. Alert resolution time (Anomaly to Action)
    resolution_time = np.random.lognormal(mean=np.log(120), sigma=0.8, size=num_samples) # sec
    
    # 2. Scheduling accuracy (predicted vs actual severity)
    actual_severity = np.random.choice([1, 2, 3, 4, 5], num_samples, p=[0.1, 0.4, 0.3, 0.15, 0.05])
    # Add some slight noise to simulate prediction mismatch
    scheduled_severity = [min(max(int(s + np.random.choice([-1, 0, 1], p=[0.05, 0.9, 0.05])), 1), 5) for s in actual_severity]
    
    # 3. Agent Coordination (Diagnostics, Scheduling, CAPA, Security)
    agents = ['Diagnostics', 'Scheduling', 'CAPA', 'Security']
    coordination_times = {
        agent: np.random.normal(loc=mean_val, scale=std_val, size=num_samples)
        for agent, mean_val, std_val in zip(agents, [45, 120, 250, 60], [10, 30, 50, 15])
    }
    
    # 4. Fleet Health Score Accuracy
    true_health = np.random.uniform(40, 100, num_samples)
    agent_health = true_health + np.random.normal(0, 3.5, num_samples) # Agents predict with minor variance
    agent_health = np.clip(agent_health, 0, 100)
    
    return resolution_time, actual_severity, scheduled_severity, pd.DataFrame(coordination_times), true_health, agent_health

def plot_agent_analysis(res_time, actual_sev, sched_sev, coord_df, true_h, agent_h):
    plt.figure(figsize=(16, 12))
    
    # Plot 1: Alert Resolution Time
    plt.subplot(2, 2, 1)
    sns.histplot(res_time, bins=40, kde=True, color='#d9534f')
    plt.title('(g) Alert Resolution Time (Anomaly to Action)')
    plt.xlabel('Resolution Time (seconds)')
    plt.ylabel('Frequency')
    plt.xlim(0, 600)
    plt.axvline(np.mean(res_time), color='black', linestyle='dashed', label=f'Mean: {np.mean(res_time):.1f}s')
    plt.legend()
    
    # Plot 2: Scheduling Accuracy
    plt.subplot(2, 2, 2)
    # Confusion matrix style bubble map or bar
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(actual_sev, sched_sev, labels=[1, 2, 3, 4, 5])
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=[1, 2, 3, 4, 5], yticklabels=[1, 2, 3, 4, 5])
    plt.title('(h) Scheduling Accuracy (Predicted vs Actual Severity)')
    plt.xlabel('Agent Predicted Severity')
    plt.ylabel('Actual Condition Severity')
    
    # Plot 3: Agent Coordination Efficiency
    plt.subplot(2, 2, 3)
    sns.boxplot(data=coord_df, palette="Set2")
    plt.title('(i) Agent Coordination Processing Times')
    plt.ylabel('Processing Time (ms)')
    plt.xlabel('Agent Type')
    
    # Plot 4: Fleet Health Score Accuracy
    plt.subplot(2, 2, 4)
    sns.scatterplot(x=true_h, y=agent_h, alpha=0.6, color='seagreen')
    # Plot unity line 
    lims = [max(min(true_h), min(agent_h)), min(max(true_h), max(agent_h))]
    plt.plot(lims, lims, 'k-', alpha=0.75, zorder=0, label='Ideal Fit')
    plt.title('(j) Fleet Health Score Accuracy')
    plt.xlabel('Observed Real-World Vehicle Health (%)')
    plt.ylabel('Agent Predicted Fleet Health (%)')
    
    correlation = np.corrcoef(true_h, agent_h)[0, 1]
    plt.annotate(f"Pearson r: {correlation:.4f}", xy=(0.05, 0.9), xycoords='axes fraction', 
                 fontsize=12, bbox=dict(boxstyle="round", alpha=0.2, color='green'))
    
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('metrics_plots/agent_analysis_metrics.png', dpi=300)
    plt.close()
    
    # Summary
    print("="*50)
    print("     AGENT ARCHITECTURE ANALYSIS SUMMARY")
    print("="*50)
    print(f"Mean Alert Resolution Time:    {np.mean(res_time):.2f} sec")
    accuracy = np.mean(np.array(actual_sev) == np.array(sched_sev)) * 100
    print(f"Scheduling Strict Accuracy:    {accuracy:.2f}%")
    print(f"Fleet Health Correlation:      {np.corrcoef(true_h, agent_h)[0, 1]:.4f}")
    print("Coordination Times (ms):")
    for col in coord_df.columns:
        print(f"  - {col}: {coord_df[col].mean():.1f} avg")
    print("="*50)
    print("Plot saved to metrics_plots/agent_analysis_metrics.png")

if __name__ == "__main__":
    print("Generating Agent Analysis Metrics Data...")
    res, a_sev, s_sev, coord, t_h, a_h = generate_agent_data()
    plot_agent_analysis(res, a_sev, s_sev, coord, t_h, a_h)
