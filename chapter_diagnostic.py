"""
Chapter Detection Diagnostic Tool
Helps identify what the regex is actually matching in your file
"""

import re

def diagnose_chapters(file_path: str):
    """
    Shows exactly what chapter markers are being detected
    """
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # This is the pattern your ingestion engine uses
    pattern = r'Chapter\s+\d+'
    
    matches = re.finditer(pattern, content, re.IGNORECASE)
    
    print("=" * 60)
    print("CHAPTER DETECTION DIAGNOSTIC")
    print("=" * 60)
    print(f"File: {file_path}")
    print(f"Pattern: {pattern}")
    print("-" * 60)
    
    chapter_list = []
    for i, match in enumerate(matches, 1):
        # Get some context around the match
        start = max(0, match.start() - 20)
        end = min(len(content), match.end() + 50)
        context = content[start:end].replace('\n', ' ')
        
        chapter_list.append({
            'num': i,
            'text': match.group(),
            'position': match.start(),
            'context': context
        })
    
    # Print results
    for ch in chapter_list:
        print(f"\n{ch['num']:2d}. [{ch['position']:6d}] {ch['text']}")
        print(f"    Context: ...{ch['context']}...")
    
    print("\n" + "=" * 60)
    print(f"TOTAL CHAPTERS DETECTED: {len(chapter_list)}")
    print("=" * 60)
    
    # Additional analysis
    if len(chapter_list) > 0:
        print(f"\n📊 Analysis:")
        print(f"   First chapter: {chapter_list[0]['text']}")
        print(f"   Last chapter: {chapter_list[-1]['text']}")
        
        # Check for duplicates
        chapter_numbers = [int(re.search(r'\d+', ch['text']).group()) for ch in chapter_list]
        unique_numbers = set(chapter_numbers)
        
        if len(unique_numbers) < len(chapter_numbers):
            print(f"\n⚠️  WARNING: Duplicate chapter numbers detected!")
            from collections import Counter
            dupes = [num for num, count in Counter(chapter_numbers).items() if count > 1]
            print(f"   Duplicates: {dupes}")
        
        # Check for gaps
        expected_chapters = set(range(min(chapter_numbers), max(chapter_numbers) + 1))
        missing = expected_chapters - unique_numbers
        if missing:
            print(f"\n⚠️  WARNING: Missing chapter numbers!")
            print(f"   Missing: {sorted(missing)}")
    
    return chapter_list


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python chapter_diagnostic.py <file_path>")
        print("Example: python chapter_diagnostic.py data/Martial_World.txt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        diagnose_chapters(file_path)
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()