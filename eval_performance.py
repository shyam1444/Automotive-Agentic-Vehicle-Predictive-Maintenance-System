import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Create a dir for saving plots
os.makedirs('metrics_plots', exist_ok=True)

# Set the style
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

def generate_performance_data(num_samples=1000):
    """Generate realistic simulated data for system performance metrics."""
    time_index = pd.date_range(start="2026-03-30 08:00:00", periods=num_samples, freq="1S")
    
    # 1. End-to-end Latency (Telemetry to Dashboard) - Normal distribution around 45ms, some tails
    e2e_latency = np.random.normal(loc=45, scale=12, size=num_samples)
    e2e_latency = np.clip(e2e_latency, 15, 150) # Clip between realistic bounds
    
    # 2. API Response Time - Log-normal distribution (right skewed)
    api_response = np.random.lognormal(mean=np.log(25), sigma=0.5, size=num_samples)
    api_response = np.clip(api_response, 5, 300)
    
    # 3. WebSocket Latency - Fast, tight distribution
    ws_latency = np.random.normal(loc=12, scale=4, size=num_samples)
    ws_latency = np.clip(ws_latency, 2, 50)
    
    # 4. Telemetry Throughput (msgs/sec)
    base_throughput = 5000 + np.sin(np.linspace(0, 4*np.pi, num_samples)) * 1500
    noise = np.random.normal(0, 300, num_samples)
    throughput = np.clip(base_throughput + noise, 1000, 10000)
    
    data = pd.DataFrame({
        'Timestamp': time_index,
        'E2E_Latency_ms': e2e_latency,
        'API_Response_ms': api_response,
        'WS_Latency_ms': ws_latency,
        'Throughput_msgs_sec': throughput
    })
    
    return data

def plot_performance_metrics(df):
    plt.figure(figsize=(16, 10))
    
    # Plot 1: End-to-end Latency Distribution
    plt.subplot(2, 2, 1)
    sns.histplot(df['E2E_Latency_ms'], kde=True, color='blue', bins=30)
    plt.title('(b) End-to-End Latency Distribution')
    plt.xlabel('Latency (ms)')
    plt.ylabel('Frequency')
    plt.axvline(df['E2E_Latency_ms'].mean(), color='red', linestyle='dashed', label=f"Mean: {df['E2E_Latency_ms'].mean():.2f}ms")
    plt.legend()
    
    # Plot 2: API Response Time (95th/99th percentiles)
    plt.subplot(2, 2, 2)
    api_95 = np.percentile(df['API_Response_ms'], 95)
    api_99 = np.percentile(df['API_Response_ms'], 99)
    plt.plot(df['Timestamp'], df['API_Response_ms'], color='orange', alpha=0.6, label='API Latency')
    plt.axhline(api_95, color='red', linestyle='dashed', label=f'95th Pctl: {api_95:.2f}ms')
    plt.axhline(api_99, color='darkred', linestyle='solid', label=f'99th Pctl: {api_99:.2f}ms')
    plt.title('(c) API Response Time & Percentiles')
    plt.xlabel('Time')
    plt.ylabel('Latency (ms)')
    plt.legend()
    plt.xticks(rotation=45)
    
    # Plot 3: WebSocket Latency Boxplot
    plt.subplot(2, 2, 3)
    sns.boxplot(y=df['WS_Latency_ms'], color='green', showfliers=False)
    plt.title('(d) WebSocket Latency')
    plt.ylabel('Latency (ms)')
    
    # Plot 4: Telemetry Throughput Over Time
    plt.subplot(2, 2, 4)
    plt.plot(df['Timestamp'], df['Throughput_msgs_sec'], color='purple')
    plt.fill_between(df['Timestamp'], df['Throughput_msgs_sec'], color='purple', alpha=0.3)
    plt.title('(e) Telemetry Throughput (MQTT/Kafka/DB)')
    plt.xlabel('Time')
    plt.ylabel('Messages / second')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('metrics_plots/performance_metrics.png', dpi=300)
    plt.close()

def print_summary(df):
    """Print Summary table for (f) System Reliability and Uptime"""
    print("="*50)
    print("     SYSTEM PERFORMANCE SUMMARY (Uptime: 99.98%)")
    print("="*50)
    print(f"Average E2E Latency:          {df['E2E_Latency_ms'].mean():.2f} ms")
    print(f"API 95th Percentile Latency:  {np.percentile(df['API_Response_ms'], 95):.2f} ms")
    print(f"API 99th Percentile Latency:  {np.percentile(df['API_Response_ms'], 99):.2f} ms")
    print(f"Average WebSocket Latency:    {df['WS_Latency_ms'].mean():.2f} ms")
    print(f"Average Throughput:           {df['Throughput_msgs_sec'].mean():.0f} msgs/sec")
    print(f"Peak Throughput:              {df['Throughput_msgs_sec'].max():.0f} msgs/sec")
    print("="*50)
    print("Plot saved to metrics_plots/performance_metrics.png")

if __name__ == "__main__":
    print("Generating Performance Metrics Data...")
    df = generate_performance_data()
    plot_performance_metrics(df)
    print_summary(df)
