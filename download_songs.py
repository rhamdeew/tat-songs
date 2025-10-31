#!/usr/bin/env python3
"""
Tatar Songs Parser - Enhanced Version
Continues downloading songs with better error handling, random delays, and user agents
"""

import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin
import time
import json
from pathlib import Path
import sys
import random


def get_random_user_agent():
    """Get a random user agent to avoid blocking"""
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    ]
    return random.choice(user_agents)


def transliterate_tatar_to_latin(text):
    """Transliterate Tatar text from Cyrillic to Latin script"""
    mapping = {
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'Җ': 'C', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L',
        'М': 'M', 'Н': 'N', 'Ң': 'N', 'О': 'O', 'Ө': 'O', 'П': 'P', 'Р': 'R',
        'С': 'S', 'Т': 'T', 'У': 'U', 'Ү': 'U', 'Ф': 'F', 'Х': 'H', 'Һ': 'H',
        'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'I', 'Ә': 'A',
        'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'җ': 'c', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'ң': 'n', 'о': 'o', 'ө': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ү': 'u', 'ф': 'f', 'х': 'h', 'һ': 'h',
        'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'i', 'ә': 'a',
        'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    
    result = []
    for char in text:
        result.append(mapping.get(char, char))
    
    # Convert to lowercase and replace spaces with underscores
    latin_text = ''.join(result).lower()
    # Remove special characters and replace multiple spaces with single underscore
    latin_text = re.sub(r'[^\w\s-]', '', latin_text)
    latin_text = re.sub(r'\s+', '_', latin_text)
    return latin_text


def sanitize_filename(filename):
    """Create safe filename from song title"""
    # Remove any characters that aren't safe for filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single underscore
    filename = re.sub(r'\s+', '_', filename)
    # Remove leading/trailing underscores and spaces
    filename = filename.strip('_ ')
    return filename


def get_page_content(url, session, max_retries=3):
    """Get page content with error handling and retries"""
    for attempt in range(max_retries):
        try:
            # Random delay before each request
            delay = random.uniform(0.5, 2.0)
            time.sleep(delay)
            
            # Update user agent for each request
            session.headers.update({'User-Agent': get_random_user_agent()})
            
            response = session.get(url, timeout=8)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2, 5))  # Random backoff
            else:
                print(f"Failed to fetch {url} after {max_retries} attempts")
                return None


def extract_songs_from_page(html_content, base_url):
    """Extract song links from a page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    songs = []
    
    # Find all song links in table - looking for links in the title column
    song_links = soup.select('.views-field-title a')
    
    for link in song_links:
        href = link.get('href')
        if href and href.startswith('/node/'):
            full_url = urljoin(base_url, href)
            title = link.get_text(strip=True)
            if title:
                # Get the musician and songwriter from the same row
                row = link.find_parent('tr')
                musician = ""
                songwriter = ""
                
                if row:
                    # Get musician (music column)
                    music_cell = row.select_one('.views-field-tid a')
                    if music_cell:
                        musician = music_cell.get_text(strip=True)
                    
                    # Get songwriter (words column)
                    words_cell = row.select_one('.views-field-tid-1 a')
                    if words_cell:
                        songwriter = words_cell.get_text(strip=True)
                
                songs.append({
                    'url': full_url,
                    'title': title,
                    'musician': musician,
                    'songwriter': songwriter
                })
    
    return songs


def extract_lyrics_from_song_page(html_content, song_url):
    """Extract lyrics and metadata from individual song page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract title from h1
    title_element = soup.find('h1', class_='title')
    title = title_element.get_text(strip=True) if title_element else ""
    
    # Extract songwriter and musician from songinfo
    songwriter = ""
    musician = ""
    
    songinfo = soup.find('div', class_='songinfo')
    if songinfo:
        # Get musician (composer)
        composer_elem = songinfo.select_one('.composer a')
        if composer_elem:
            musician = composer_elem.get_text(strip=True)
        
        # Get songwriter (author)
        autor_elem = songinfo.select_one('.autor a')
        if autor_elem:
            songwriter = autor_elem.get_text(strip=True)
    
    # Extract lyrics from the song div
    lyrics_element = soup.select_one('.song')
    lyrics = ""
    
    if lyrics_element:
        # Remove the rating form and other unwanted elements
        for unwanted in lyrics_element.find_all(['form', 'div']):
            if 'fivestar' in unwanted.get('class', []):
                unwanted.decompose()
        
        # Get all text from p tags with line_one and line_two classes
        lyric_lines = []
        for p in lyrics_element.find_all('p', class_=['line_one', 'line_two']):
            # Get text and clean up line breaks
            text = p.get_text('\n', strip=True)
            lyric_lines.append(text)
        
        lyrics = '\n\n'.join(lyric_lines)
    
    return {
        'title': title,
        'songwriter': songwriter,
        'musician': musician,
        'lyrics': lyrics,
        'url': song_url
    }


def format_lyrics_markdown(song_data):
    """Format song data as markdown"""
    artist_name = ""
    if song_data['songwriter'] and song_data['musician']:
        artist_name = f"{song_data['songwriter']} / {song_data['musician']}"
    elif song_data['songwriter']:
        artist_name = song_data['songwriter']
    elif song_data['musician']:
        artist_name = song_data['musician']
    else:
        artist_name = "Unknown"
    
    # Create header
    header = f"# Оригинал\n\n### {artist_name} - {song_data['title']}\n"
    
    # Format lyrics with proper line breaks
    lyrics = song_data['lyrics'].strip()
    formatted_lyrics = f"\n```\n{lyrics}\n```\n"
    
    return header + formatted_lyrics


def load_existing_files(output_dir):
    """Load list of existing downloaded files"""
    existing_files = set()
    if output_dir.exists():
        for file_path in output_dir.glob("*.md"):
            existing_files.add(file_path.name)
    return existing_files


def save_progress(songs_processed, total_songs):
    """Save progress to resume later"""
    progress_file = Path("download_progress.json")
    progress_data = {
        'songs_processed': songs_processed,
        'total_songs': total_songs,
        'timestamp': time.time()
    }
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2)


def main():
    base_url = "https://erlar.ru/asongs"
    output_dir = Path("tat")
    output_dir.mkdir(exist_ok=True)
    
    # Load existing files to avoid re-downloading
    existing_files = load_existing_files(output_dir)
    print(f"Found {len(existing_files)} existing files")
    
    # Configure session with proxies (if needed) and headers
    session = requests.Session()
    session.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    all_songs = []
    
    # Determine where to start based on command line argument
    start_page = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    print("Starting to scrape Tatar songs (enhanced resume mode)...")
    
    # Process all pages
    max_pages = 268  # Download all pages (0-267)
    
    for page_num in range(start_page, max_pages):
        page_url = f"{base_url}?page={page_num}"
        print(f"Scraping page: {page_url}")
        
        page_content = get_page_content(page_url, session)
        if not page_content:
            print(f"Skipping page {page_num} due to errors")
            continue
        
        page_songs = extract_songs_from_page(page_content, base_url)
        all_songs.extend(page_songs)
        print(f"Found {len(page_songs)} songs on page {page_num}")
        
        # Small delay between pages to be respectful
        time.sleep(random.uniform(1.0, 3.0))
    
    # Remove duplicates
    unique_songs = []
    seen_urls = set()
    for song in all_songs:
        if song['url'] not in seen_urls:
            unique_songs.append(song)
            seen_urls.add(song['url'])
    
    print(f"Total unique songs found: {len(unique_songs)}")
    
    # Process each song
    successful_downloads = 0
    failed_downloads = 0
    songs_processed = 0
    
    for i, song in enumerate(unique_songs, 1):
        # Generate expected filename
        artist_name = ""
        if song['songwriter'] and song['musician']:
            artist_name = f"{song['songwriter']} {song['musician']}"
        elif song['songwriter']:
            artist_name = song['songwriter']
        elif song['musician']:
            artist_name = song['musician']
        else:
            artist_name = "unknown"
        
        filename_base = f"{artist_name} - {song['title']}"
        filename = transliterate_tatar_to_latin(filename_base)
        filename = sanitize_filename(filename)
        filename = filename + ".md"
        
        # Skip if already exists
        if filename in existing_files:
            continue
        
        print(f"Processing song {i}/{len(unique_songs)}: {song['title']}")
        
        song_content = get_page_content(song['url'], session)
        if not song_content:
            print(f"Failed to fetch song: {song['title']}")
            failed_downloads += 1
            continue
        
        song_data = extract_lyrics_from_song_page(song_content, song['url'])
        
        if not song_data['lyrics']:
            print(f"No lyrics found for: {song['title']}")
            failed_downloads += 1
            continue
        
        # Format and save
        markdown_content = format_lyrics_markdown(song_data)
        
        file_path = output_dir / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            successful_downloads += 1
            print(f"Saved: {filename}")
        except Exception as e:
            print(f"Failed to save {filename}: {e}")
            failed_downloads += 1
        
        songs_processed += 1
        
        # Save progress every 100 songs
        if songs_processed % 100 == 0:
            save_progress(songs_processed, len(unique_songs))
            print(f"Progress saved: {songs_processed}/{len(unique_songs)}")
    
    # Final progress save
    save_progress(successful_downloads, len(unique_songs))
    
    print(f"Done! Successfully downloaded {successful_downloads} new songs. Failed: {failed_downloads}")
    print(f"Total files in {output_dir}/: {len(list(output_dir.glob('*.md')))}")


if __name__ == "__main__":
    main()