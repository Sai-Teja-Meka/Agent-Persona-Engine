import argparse
import os
from core.ingestion import IngestionEngine

def main():
    parser = argparse.ArgumentParser(description="Sanity Check: Ingest First 3 Chapters")
    parser.add_argument("--file", required=True, help="Path to the real novel text file")
    parser.add_argument("--id", required=True, help="Unique ID for the novel")
    
    args = parser.parse_args()
    
    # 1. Verification
    if not os.path.exists(args.file):
        print(f"❌ Error: File '{args.file}' not found.")
        print("💡 Tip: Place your .txt file in a 'data/' folder.")
        return

    print(f"🧪 Running Sanity Check on: {args.file}")
    print(f"🎯 Target: First 3 Chapters of '{args.id}'")
    print("-" * 40)

    # 2. Initialize Engine
    try:
        engine = IngestionEngine(novel_id=args.id)
        
        # 3. Run with Limit
        # This uses the new safety brake we just added
        engine.process_file(args.file, limit=3)
        
        print("-" * 40)
        print("✅ Sanity Check Complete.")
        print("👉 Next Step: Run 'streamlit run app.py' to verify the data visually.")
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        print("🔍 Check your regex splitter in 'core/ingestion.py' or file encoding.")

if __name__ == "__main__":
    main()