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

def create_song_pages(songs):
    """Create paginated song files (SONGS_1.md, SONGS_2.md, etc.) with 50 songs per file."""
    songs_per_page = 50
    songs_sorted = sorted(songs, key=lambda x: x['original_title'].lower())
    
    # Calculate number of pages needed
    total_songs = len(songs_sorted)
    num_pages = (total_songs + songs_per_page - 1) // songs_per_page
    
    page_files = []
    
    for page_num in range(1, num_pages + 1):
        start_idx = (page_num - 1) * songs_per_page
        end_idx = min(start_idx + songs_per_page, total_songs)
        page_songs = songs_sorted[start_idx:end_idx]
        
        # Create content for this page
        page_content = [f"# Татарские песни и их перевод - Страница {page_num}\n"]
        page_content.append(f"## Список песен (песни {start_idx + 1}-{end_idx} из {total_songs})\n")
        
        # Add navigation links
        if num_pages > 1:
            nav_links = []
            if page_num > 1:
                nav_links.append(f"[← Предыдущая страница](SONGS_{page_num-1}.md)")
            nav_links.append(f"[Главная страница](README.md)")
            if page_num < num_pages:
                nav_links.append(f"[Следующая страница →](SONGS_{page_num+1}.md)")
            page_content.append(" | ".join(nav_links) + "\n")
        
        page_content.append("")
        
        # Add songs for this page
        for song in page_songs:
            filename = song['filename']
            original_title = song['original_title']
            translated_title = song['translated_title']
            link_text = f"{original_title} / {translated_title}"
            link = f"[{link_text}](translated/{filename})"
            page_content.append(f"- {link}")
        
        page_content.append("")
        
        # Add navigation links at bottom
        if num_pages > 1:
            nav_links = []
            if page_num > 1:
                nav_links.append(f"[← Предыдущая страница](SONGS_{page_num-1}.md)")
            nav_links.append(f"[Главная страница](README.md)")
            if page_num < num_pages:
                nav_links.append(f"[Следующая страница →](SONGS_{page_num+1}.md)")
            page_content.append("---\n")
            page_content.append(" | ".join(nav_links))
        
        # Write page file
        page_filename = f"SONGS_{page_num}.md"
        with open(page_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(page_content))
        
        page_files.append(page_filename)
        print(f"Created {page_filename} with {len(page_songs)} songs")
    
    return page_files, num_pages

def update_readme(page_files, num_pages, total_songs):
    """Update README.md with links to song pages."""
    readme_path = Path("README.md")
    
    # Create README content
    readme_content = ["# Татарские песни и их перевод\n"]
    readme_content.append(f"Всего песен: {total_songs}\n")
    readme_content.append("## Список песен\n")
    
    if num_pages == 1:
        # If only one page, add a direct link
        readme_content.append(f"- [Все песни]({page_files[0]})\n")
    else:
        # Create links to each page
        for i, page_file in enumerate(page_files, 1):
            start_song = (i - 1) * 50 + 1
            end_song = min(i * 50, total_songs)
            readme_content.append(f"- [Песни {start_song}-{end_song}]({page_file})")
    
    readme_content.append("")
    readme_content.append("---")
    readme_content.append("")
    readme_content.append("*Эта страница автоматически генерируется скриптом `update_readme.py`*")
    
    # Write to README.md
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(readme_content))

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
        # Create paginated song files
        page_files, num_pages = create_song_pages(songs)
        
        # Update main README with links to pages
        update_readme(page_files, num_pages, len(songs))
        
        print(f"\nCreated {num_pages} page(s) with {len(songs)} total songs")
        print(f"Updated README.md with links to song pages")
    else:
        print("No songs found to update README.md")

if __name__ == "__main__":
    main()