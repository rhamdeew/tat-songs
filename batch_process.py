#!/usr/bin/env python3
"""
Automatic batch processor for downloading Tatar songs
"""

import subprocess
import time
import sqlite3
import sys

def get_pending_count():
    """Get count of pending songs"""
    conn = sqlite3.connect('songs.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM songs WHERE status = "pending"')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def process_batch(batch_size=100, max_batches=None):
    """Process songs in batches"""
    batch_num = 0
    total_processed = 0
    
    while True:
        if max_batches and batch_num >= max_batches:
            break
            
        pending_count = get_pending_count()
        if pending_count == 0:
            print("All songs processed!")
            break
            
        print(f"\n=== Batch {batch_num + 1} ===")
        print(f"Pending songs: {pending_count}")
        
        # Run batch
        try:
            result = subprocess.run([
                sys.executable, 'download_songs.py', '--process', '--limit', str(batch_size)
            ], capture_output=True, text=True, timeout=600)  # 10 min timeout
            
            if result.returncode == 0:
                print(f"Batch {batch_num + 1} completed successfully")
                total_processed += batch_size
                batch_num += 1
            else:
                print(f"Batch {batch_num + 1} failed: {result.stderr}")
                break
                
        except subprocess.TimeoutExpired:
            print(f"Batch {batch_num + 1} timed out")
            break
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            break
        except Exception as e:
            print(f"Error running batch {batch_num + 1}: {e}")
            break
            
        # Small delay between batches
        time.sleep(2)
    
    print(f"\nTotal batches processed: {batch_num}")
    print(f"Final pending count: {get_pending_count()}")
    print(f"Total processed in this run: {total_processed}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch process Tatar songs')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size')
    parser.add_argument('--max-batches', type=int, help='Maximum number of batches')
    
    args = parser.parse_args()
    
    process_batch(args.batch_size, args.max_batches)