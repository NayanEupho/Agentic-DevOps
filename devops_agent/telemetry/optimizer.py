
import os
from collections import Counter

LOG_FILE = "devops_agent/data/slow_queries.log"

def analyze_slow_queries():
    """
    Analyze the slow queries log and suggest new templates.
    """
    if not os.path.exists(LOG_FILE):
        print("✅ No slow queries logged yet.")
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        queries = [line.split(" | ", 1)[1].strip() for line in lines if " | " in line]
        counter = Counter(queries)
        
        print(f"\n📊 Performance Analysis ({len(queries)} slow queries logged)")
        print("="*60)
        
        print("\n🚀 Top Candidates for Optimization (Regex/Semantic):")
        for query, count in counter.most_common(10):
            print(f"   x{count}: {query}")
            
        print("\n💡 Tip: Add these to 'devops_agent/data/intents.json' to make them instant.")
        
    except Exception as e:
        print(f"❌ Error analyzing logs: {e}")

if __name__ == "__main__":
    analyze_slow_queries()
