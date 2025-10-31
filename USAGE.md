# Tatar Songs Downloader - Usage Instructions

## Overview

This system downloads Tatar song lyrics from https://erlar.ru/asongs with full resume capability and database tracking.

## Files

- `download_songs.py` - Main script for collecting and processing songs
- `batch_process.py` - Automated batch processing tool
- `songs.db` - SQLite database tracking all songs and their status
- `tat/` - Directory containing downloaded song files (markdown format)

## Database Schema

The SQLite database (`songs.db`) contains:
- `songs` table with columns:
  - `id` - Primary key
  - `url` - Song page URL (unique)
  - `title` - Song title
  - `musician` - Composer/musician
  - `songwriter` - Lyricist/author
  - `status` - Status: 'pending', 'processed', 'failed'
  - `created_at` - Timestamp when song was added
  - `processed_at` - Timestamp when song was processed
  - `lyrics` - Full lyrics text
  - `filename` - Generated filename

## Commands

### 1. Collect Song Links
```bash
# Collect from specific page range
python download_songs.py --collect --start-page 0 --max-pages 268

# Collect from all pages (default)
python download_songs.py --collect
```

### 2. Process Songs
```bash
# Process specific number of songs
python download_songs.py --process --limit 100

# Process all pending songs
python download_songs.py --process

# Test mode: process 100 random songs
python download_songs.py --process --test
```

### 3. Batch Processing
```bash
# Automated batch processing
python batch_process.py --batch-size 50 --max-batches 100

# Run in background
nohup python batch_process.py --batch-size 100 >> batch.log 2>&1 &
```

### 4. Check Status
```bash
# View database status
sqlite3 songs.db "SELECT status, COUNT(*) FROM songs GROUP BY status;"

# View recent processed songs
sqlite3 songs.db "SELECT title, filename FROM songs WHERE status = 'processed' ORDER BY processed_at DESC LIMIT 10;"

# View failed songs
sqlite3 songs.db "SELECT title, url FROM songs WHERE status = 'failed' ORDER BY processed_at DESC LIMIT 10;"
```

## File Structure

### Output Files
Songs are saved as markdown files in the `tat/` directory:
```markdown
# Оригинал

### Artist Name - Song Title

```
Lyrics content here
```
```

### Filename Generation
- **Format**: `{artist} - {title}.md`
- **Transliteration**: Tatar names converted to Latin script
- **No 'unknown' placeholders**: Uses only title when artist info is missing
- **Safe characters**: Special characters removed for filesystem compatibility

## Workflow

### First Time Setup
```bash
# 1. Initialize database and collect all songs
python download_songs.py --collect

# 2. Test processing with small batch
python download_songs.py --process --test

# 3. Process all songs in batches
python batch_process.py --batch-size 50 --max-batches 200
```

### Resuming After Interruption
The system automatically tracks progress. Simply run:
```bash
# Resume processing remaining songs
python download_songs.py --process

# Or continue with batch processing
python batch_process.py --batch-size 100
```

### Monitoring Progress
```bash
# Check database status
sqlite3 songs.db "SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
  SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as processed,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM songs;"

# Check downloaded files count
ls tat/*.md | wc -l
```

## Error Handling

### Common Issues
1. **Server Timeouts**: Automatic retry with exponential backoff
2. **Rate Limiting**: Random delays between requests (0.5-3.0 seconds)
3. **Connection Errors**: 3 retry attempts per request
4. **Missing Lyrics**: Songs marked as 'failed' in database

### Recovery
```bash
# Reset failed songs to pending for retry
sqlite3 songs.db "UPDATE songs SET status = 'pending' WHERE status = 'failed';"

# Check specific errors
tail -f batch.log
```

## Configuration

### Script Settings
- **User Agents**: Rotates between 7 different browser user agents
- **Request Delays**: 0.5-3.0 seconds between requests
- **Timeout**: 8 seconds per request
- **Retries**: 3 attempts per request
- **Batch Size**: 50-100 songs recommended for stability

### Database Customization
```sql
-- Add custom queries for monitoring
CREATE VIEW song_progress AS 
SELECT 
  COUNT(*) as total_songs,
  ROUND(100.0 * SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_percent,
  SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
  SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as processed,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM songs;
```

## Command Line Options

### download_songs.py
- `--collect` - Collect song links from pagination pages
- `--process` - Process downloaded songs
- `--start-page` - Start page for collection (default: 0)
- `--max-pages` - Maximum pages to collect (default: 268)
- `--limit` - Limit number of songs to process
- `--test` - Process 100 random songs for testing

### batch_process.py
- `--batch-size` - Songs per batch (default: 100)
- `--max-batches` - Maximum number of batches to run

## Tips

1. **Start Small**: Test with `--test` flag first
2. **Use Batches**: Process 50-100 songs at a time for stability
3. **Background Processing**: Use `nohup` for long-running operations
4. **Monitor Logs**: Keep an eye on `batch.log` for errors
5. **Database Backup**: Periodically backup `songs.db`
6. **Check Disk Space**: Ensure enough space for downloaded files

## Troubleshooting

### Songs Not Downloading
```bash
# Check if pages are being scraped
python download_songs.py --collect --start-page 0 --max-pages 1

# Check individual song processing
sqlite3 songs.db "SELECT url FROM songs WHERE status = 'pending' LIMIT 1;"
# Test the URL manually
```

### Database Issues
```bash
# Check database integrity
sqlite3 songs.db "PRAGMA integrity_check;"

# Rebuild database if corrupted
rm songs.db
python download_songs.py --collect
```

### File System Issues
```bash
# Check permissions
ls -la tat/

# Clean up corrupted files
find tat/ -name "*.md" -size 0 -delete
```

## Statistics

Track your progress with:
```bash
# Completion percentage
sqlite3 songs.db "SELECT 
  ROUND(100.0 * COUNT(CASE WHEN status = 'processed' THEN 1 END) / COUNT(*), 2) || '%' as completion
FROM songs;"

# Recent activity
sqlite3 songs.db "SELECT 
  status, 
  COUNT(*) as count,
  datetime(MAX(processed_at), 'localtime') as last_activity
FROM songs 
GROUP BY status;"
```