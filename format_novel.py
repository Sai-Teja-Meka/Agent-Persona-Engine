"""
Martial World Text Cleaner for Ingestion Engine
Prepares the text file for the Infinite Library project
"""

def clean_martial_world_text(input_file: str, output_file: str):
    r"""
    Cleans Martial World text to ensure compatibility with regex: r'(Chapter\s+\d+)'
    
    Actions:
    1. Normalizes chapter headers to "Chapter X" format
    2. Removes excessive separators (====)
    3. Ensures UTF-8 encoding
    4. Preserves all content
    """
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Normalize chapter headers
    # Convert "Chapter 0002" to "Chapter 2" format for consistency
    import re
    
    # STEP 1: Remove duplicate chapter headers
    # Pattern: "Chapter X – Title\n\nChapter X Title" becomes just "Chapter X Title"
    def remove_duplicate_headers(text):
        lines = text.split('\n')
        cleaned_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if current line is a chapter header
            if re.match(r'Chapter\s+\d+', line, re.IGNORECASE):
                # Look ahead to see if next non-empty line is also the same chapter
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                
                if j < len(lines):
                    next_line = lines[j].strip()
                    
                    # Extract chapter numbers
                    current_num = re.search(r'Chapter\s+(\d+)', line, re.IGNORECASE)
                    next_num = re.search(r'Chapter\s+(\d+)', next_line, re.IGNORECASE)
                    
                    if current_num and next_num and current_num.group(1) == next_num.group(1):
                        # Duplicate found! Skip the first one (with dash), keep the second
                        print(f"   Removing duplicate: {line}")
                        i = j  # Skip to the duplicate
                        continue
            
            cleaned_lines.append(lines[i])
            i += 1
        
        return '\n'.join(cleaned_lines)
    
    print("🔍 Checking for duplicate chapter headers...")
    content = remove_duplicate_headers(content)
    
    # STEP 2: Normalize remaining chapter headers
    # Pattern matches: "Chapter 1", "Chapter 0002", "Chapter 0003", etc.
    def normalize_chapter(match):
        chapter_num = int(match.group(1))  # Extract number, removes leading zeros
        chapter_title = match.group(2) if match.group(2) else ""
        # Remove the dash if present
        chapter_title = chapter_title.replace(' – ', ' ').replace(' - ', ' ')
        return f"Chapter {chapter_num}{chapter_title}"
    
    # Replace chapter headers
    content = re.sub(
        r'Chapter\s+(\d+)([^\n]*)', 
        normalize_chapter, 
        content, 
        flags=re.IGNORECASE
    )
    
    # Remove excessive separator lines (optional - keeps text cleaner)
    content = re.sub(r'={50,}', '', content)
    
    # Ensure consistent line breaks
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Write cleaned output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    
    print(f"✅ Cleaned text saved to: {output_file}")
    print(f"📊 File size: {len(content):,} characters")
    
    # Count chapters for verification
    chapter_count = len(re.findall(r'Chapter\s+\d+', content, re.IGNORECASE))
    print(f"📚 Detected chapters: {chapter_count}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python clean_martial_world.py <input_file> <output_file>")
        print("Example: python clean_martial_world.py Martial-World.txt data/martial_world.txt")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    try:
        clean_martial_world_text(input_path, output_path)
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_path}' not found")
    except Exception as e:
        print(f"❌ Error: {e}")