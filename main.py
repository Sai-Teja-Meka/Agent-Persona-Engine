import argparse
from core.ingestion import IngestionEngine

def main():
    parser = argparse.ArgumentParser(description="The Infinite Library - Ingestion CLI")
    parser.add_argument("mode", choices=["ingest"], help="Operation mode")
    parser.add_argument("--file", help="Path to the novel text file")
    parser.add_argument("--id", help="Unique ID for the novel (e.g., reverend_insanity)")
    
    args = parser.parse_args()
    
    if args.mode == "ingest":
        if not args.file or not args.id:
            print("❌ Error: --file and --id are required for ingestion.")
            return
            
        engine = IngestionEngine(novel_id=args.id)
        engine.process_file(args.file)

if __name__ == "__main__":
    main()