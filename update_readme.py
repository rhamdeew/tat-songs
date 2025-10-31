#!/usr/bin/env python3
import os
import re
from pathlib import Path

def parse_translated_file(filepath):
    """Parse a translated file and extract original and translated song names."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the original title (appears after "# Оригинал")
        original_title_match = re.search(r'# Оригинал\s*\n\s*###\s*([^\n]+)', content)
        # Extract the translated title (appears after "# Перевод")
        translated_title_match = re.search(r'# Перевод\s*\n\s*###\s*([^\n]+)', content)
        
        original_title = original_title_match.group(1).strip() if original_title_match else None
        translated_title = translated_title_match.group(1).strip() if translated_title_match else None
        
        return original_title, translated_title
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None, None

def update_readme(songs):
    """Update README.md with the list of songs."""
    readme_path = Path("README.md")
    
    # Sort songs alphabetically by original title
    songs_sorted = sorted(songs, key=lambda x: x['original_title'].lower())
    
    # Create song list content
    song_list = ["# Татарские песни и их перевод\n"]
    song_list.append("\n## Список песен\n")
    
    for song in songs_sorted:
        # Create markdown link: [Original / Translated](translated/filename)
        filename = song['filename']
        original_title = song['original_title']
        translated_title = song['translated_title']
        link_text = f"{original_title} / {translated_title}"
        link = f"[{link_text}](translated/{filename})"
        song_list.append(f"- {link}")
    
    # Write to README.md
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(song_list))

def main():
    translated_dir = Path("translated")
    
    if not translated_dir.exists():
        print(f"Error: {translated_dir} directory not found")
        return
    
    songs = []
    
    # Get all .md files in translated directory
    for filepath in sorted(translated_dir.glob("*.md")):
        original_title, translated_title = parse_translated_file(filepath)
        if original_title and translated_title:
            songs.append({
                'filename': filepath.name,
                'original_title': original_title,
                'translated_title': translated_title
            })
            print(f"Processed: {filepath.name} -> {original_title} / {translated_title}")
        else:
            print(f"Could not extract titles from: {filepath.name}")
    
    if songs:
        update_readme(songs)
        print(f"\nUpdated README.md with {len(songs)} songs")
    else:
        print("No songs found to update README.md")

if __name__ == "__main__":
    main()