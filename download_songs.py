#!/usr/bin/env python3
"""
Tatar Songs Parser - Database Version
Downloads song lyrics from https://erlar.ru/asongs with SQLite database for tracking progress
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
import sqlite3
import argparse
from datetime import datetime


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


def init_database():
    """Initialize SQLite database for tracking songs"""
    conn = sqlite3.connect('songs.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            musician TEXT,
            songwriter TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            lyrics TEXT,
            filename TEXT
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON songs (status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON songs (url)')
    
    conn.commit()
    conn.close()


def get_db_connection():
    """Get database connection"""
    return sqlite3.connect('songs.db')


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
        artist_name = ""
    
    # Create header - only include artist name if we have one
    header = f"# Оригинал\n\n"
    if artist_name:
        header += f"### {artist_name} - {song_data['title']}\n"
    else:
        header += f"### {song_data['title']}\n"
    
    # Format lyrics with proper line breaks
    lyrics = song_data['lyrics'].strip()
    formatted_lyrics = f"\n```\n{lyrics}\n```\n"
    
    return header + formatted_lyrics


def generate_filename(song_data):
    """Generate filename without 'unknown' placeholder"""
    artist_name = ""
    if song_data['songwriter'] and song_data['musician']:
        artist_name = f"{song_data['songwriter']} {song_data['musician']}"
    elif song_data['songwriter']:
        artist_name = song_data['songwriter']
    elif song_data['musician']:
        artist_name = song_data['musician']
    
    if artist_name:
        filename_base = f"{artist_name} - {song_data['title']}"
    else:
        filename_base = song_data['title']
    
    filename = transliterate_tatar_to_latin(filename_base)
    filename = sanitize_filename(filename)
    return filename + ".md"


def collect_all_songs(base_url, session, start_page=0, max_pages=268):
    """Collect all song links from pagination pages"""
    if session is None:
        session = requests.Session()
        session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"Collecting songs from pages {start_page} to {max_pages-1}...")
    
    for page_num in range(start_page, max_pages):
        page_url = f"{base_url}?page={page_num}"
        print(f"Scraping page: {page_url}")
        
        page_content = get_page_content(page_url, session)
        if not page_content:
            print(f"Skipping page {page_num} due to errors")
            continue
        
        page_songs = extract_songs_from_page(page_content, base_url)
        print(f"Found {len(page_songs)} songs on page {page_num}")
        
        # Insert songs into database
        for song in page_songs:
            cursor.execute('''
                INSERT OR IGNORE INTO songs (url, title, musician, songwriter)
                VALUES (?, ?, ?, ?)
            ''', (song['url'], song['title'], song['musician'], song['songwriter']))
        
        conn.commit()
        
        # Small delay between pages to be respectful
        time.sleep(random.uniform(1.0, 3.0))
    
    total_songs = cursor.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    print(f"Total songs collected in database: {total_songs}")
    
    conn.close()


def process_songs(output_dir, limit=None, test_mode=False):
    """Process songs from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if test_mode:
        # Get 100 random songs for testing
        cursor.execute('SELECT * FROM songs WHERE status = "pending" ORDER BY RANDOM() LIMIT 100')
    else:
        # Get pending songs (with optional limit)
        if limit:
            cursor.execute('SELECT * FROM songs WHERE status = "pending" LIMIT ?', (limit,))
        else:
            cursor.execute('SELECT * FROM songs WHERE status = "pending"')
    
    pending_songs = cursor.fetchall()
    print(f"Found {len(pending_songs)} songs to process")
    
    # Configure session
    session = requests.Session()
    session.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    successful_downloads = 0
    failed_downloads = 0
    
    for i, song in enumerate(pending_songs, 1):
        song_id = song[0]
        song_url = song[1]
        song_title = song[2]
        
        print(f"Processing song {i}/{len(pending_songs)}: {song_title}")
        
        song_content = get_page_content(song_url, session)
        if not song_content:
            print(f"Failed to fetch song: {song_title}")
            cursor.execute('UPDATE songs SET status = "failed" WHERE id = ?', (song_id,))
            failed_downloads += 1
            conn.commit()
            continue
        
        song_data = extract_lyrics_from_song_page(song_content, song_url)
        
        if not song_data['lyrics']:
            print(f"No lyrics found for: {song_title}")
            cursor.execute('UPDATE songs SET status = "failed" WHERE id = ?', (song_id,))
            failed_downloads += 1
            conn.commit()
            continue
        
        # Generate filename
        filename = generate_filename(song_data)
        
        # Format and save
        markdown_content = format_lyrics_markdown(song_data)
        
        file_path = output_dir / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Update database with success
            cursor.execute('''
                UPDATE songs 
                SET status = "processed", 
                    processed_at = CURRENT_TIMESTAMP,
                    lyrics = ?,
                    filename = ?
                WHERE id = ?
            ''', (song_data['lyrics'], filename, song_id))
            
            successful_downloads += 1
            print(f"Saved: {filename}")
        except Exception as e:
            print(f"Failed to save {filename}: {e}")
            cursor.execute('UPDATE songs SET status = "failed" WHERE id = ?', (song_id,))
            failed_downloads += 1
        
        conn.commit()
        
        # Small delay between requests
        time.sleep(0.3)
    
    conn.close()
    
    print(f"Done! Successfully downloaded {successful_downloads} songs. Failed: {failed_downloads}")
    print(f"Total files in {output_dir}/: {len(list(output_dir.glob('*.md')))}")


def main():
    parser = argparse.ArgumentParser(description='Download Tatar songs from erlar.ru')
    parser.add_argument('--collect', action='store_true', help='Collect song links from all pages')
    parser.add_argument('--process', action='store_true', help='Process downloaded songs')
    parser.add_argument('--start-page', type=int, default=0, help='Start page for collection')
    parser.add_argument('--max-pages', type=int, default=268, help='Maximum pages to collect')
    parser.add_argument('--limit', type=int, help='Limit number of songs to process')
    parser.add_argument('--test', action='store_true', help='Process 100 random songs for testing')
    
    args = parser.parse_args()
    
    base_url = "https://erlar.ru/asongs"
    output_dir = Path("tat")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize database
    init_database()
    
    if args.collect or not any([args.collect, args.process]):
        # Collect songs by default
        collect_all_songs(base_url, None, args.start_page, args.max_pages)
    
    if args.process:
        process_songs(output_dir, args.limit, args.test)


if __name__ == "__main__":
    main()