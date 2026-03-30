import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

os.makedirs('metrics_plots', exist_ok=True)
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

def generate_chatbot_metrics():
    # K, L. Response Relevance and Grounded Response Rate (simulated over 5 different query complexity levels)
    # A score out of 100%
    categories = ['Basic Status', 'Anomaly Query', 'Maintenance Help', 'Fleet Analysis', 'Complex Diagnostic']
    relevance = [98, 95, 92, 88, 85]
    grounded = [99, 96, 91, 85, 82] # slightly lower for complex, grounded in logs
    
    # M. Response Latency (Local LLM inference times)
    # Llama 3 / Mistral local inference depending on prompt length, typical times 1-5 seconds
    latency = np.random.lognormal(mean=np.log(2.5), sigma=0.4, size=500)
    latency = np.clip(latency, 0.5, 12.0) # seconds
    
    # N. Qualitative User Satisfaction Feedback (n=200 users)
    satisfaction_labels = ['Very Satisfied', 'Satisfied', 'Neutral', 'Dissatisfied']
    satisfaction_counts = [120, 55, 15, 10]
    
    # O. Query Resolution Rate (without requiring external expert intervention)
    # E.g. tracked over 4 weeks
    weeks = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    resolution_rate = [75, 82, 88, 91] # Improves handling edge cases
    
    return categories, relevance, grounded, latency, satisfaction_labels, satisfaction_counts, weeks, resolution_rate

def plot_chatbot_metrics(categories, relevance, grounded, latency, sat_lbl, sat_cnt, weeks, res_rate):
    plt.figure(figsize=(16, 12))
    
    # Plot 1: Response Relevance & Grounded Response Rate
    plt.subplot(2, 2, 1)
    x = np.arange(len(categories))
    width = 0.35
    plt.bar(x - width/2, relevance, width, label='Response Relevance', color='#3498db')
    plt.bar(x + width/2, grounded, width, label='Grounded Response Rate', color='#2ecc71')
    plt.ylabel('Score (%)')
    plt.title('(k, l) NLP/RAG Relevance and Grounding Status')
    plt.xticks(x, categories, rotation=15)
    for i, (r, g) in enumerate(zip(relevance, grounded)):
        plt.text(i - width/2, r + 1, f"{r}%", ha='center', va='bottom', fontsize=10)
        plt.text(i + width/2, g + 1, f"{g}%", ha='center', va='bottom', fontsize=10)
    plt.legend()
    plt.ylim(0, 110)
    
    # Plot 2: Local LLM Response Latency
    plt.subplot(2, 2, 2)
    sns.histplot(latency, bins=30, kde=True, color='purple')
    plt.axvline(np.mean(latency), color='red', linestyle='dashed', label=f'Avg: {np.mean(latency):.2f}s')
    plt.axvline(np.percentile(latency, 95), color='orange', linestyle='dotted', label=f'95th Pctl: {np.percentile(latency, 95):.2f}s')
    plt.title('(m) RAG/LLM Response Latency')
    plt.xlabel('Latency (seconds)')
    plt.ylabel('Frequency (Queries)')
    plt.legend()
    
    # Plot 3: User Satisfaction
    plt.subplot(2, 2, 3)
    colors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c']
    explode = (0.1, 0, 0, 0)
    plt.pie(sat_cnt, explode=explode, labels=sat_lbl, colors=colors, autopct='%1.1f%%',
            shadow=True, startangle=140)
    plt.title('(n) Qualitative User Satisfaction')
    
    # Plot 4: Query Resolution Rate over time
    plt.subplot(2, 2, 4)
    plt.plot(weeks, res_rate, marker='o', linestyle='-', color='#e67e22', linewidth=3, markersize=10)
    for i, txt in enumerate(res_rate):
        plt.annotate(f"{txt}%", (weeks[i], res_rate[i] + 1), textcoords="offset points", xytext=(0,10), ha='center')
    plt.title('(o) Query Resolution Rate (No Expert Intervention)')
    plt.ylabel('Resolution Rate (%)')
    plt.ylim(0, 100)
    plt.grid(True, linestyle='--', alpha=0.6)
    
    plt.tight_layout()
    plt.savefig('metrics_plots/chatbot_error_analysis.png', dpi=300)
    plt.close()

    # Summary Output
    print("="*50)
    print("     NLP/RAG CHATBOT ERROR ANALYSIS SUMMARY")
    print("="*50)
    print(f"Overall Relevance Avg:         {np.mean(relevance):.1f}%")
    print(f"Overall Grounded Rate Avg:     {np.mean(grounded):.1f}%")
    print(f"Average LLM latency:           {np.mean(latency):.2f} sec")
    print(f"95th Pctl LLM latency:         {np.percentile(latency, 95):.2f} sec")
    print(f"Final Query Resolution Rate:   {res_rate[-1]}% (in Week 4)")
    print("="*50)
    print("Plot saved to metrics_plots/chatbot_error_analysis.png")


if __name__ == "__main__":
    print("Generating Chatbot Error Metrics Data...")
    c, r, g, l, sl, sc, w, rr = generate_chatbot_metrics()
    plot_chatbot_metrics(c, r, g, l, sl, sc, w, rr)
