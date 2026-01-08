#!/usr/bin/env python3
"""
Script to normalize person names in translated song files.
Finds similar names and offers to merge them.
Has automated mode for obvious cases (large difference in usage).
"""

import os
import re
import json
import subprocess
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple, Optional

# Similarity threshold for considering names as potential duplicates
SIMILARITY_THRESHOLD = 0.92

# Automation thresholds
AUTO_MERGE_MIN_DIFF_RATIO = 2.0  # One name used 2x more than other (was 5.0)
AUTO_MERGE_MIN_ABS_DIFF = 3  # At least 3 files difference (was 10)
AUTO_MERGE_VERY_HIGH_SIMILARITY = 0.95  # Auto-merge at 95%+ similarity regardless of count


def extract_names_from_file(filepath: str) -> Set[str]:
    """Extract all person names from a markdown file."""
    names = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all headers with pattern: ### Name1 / Name2 - Song Title
    # or ### Name - Song Title
    pattern = r'^###\s+(.+?)\s+-'
    matches = re.findall(pattern, content, re.MULTILINE)

    for match in matches:
        # Split by '/' and extract names
        parts = match.split('/')
        for part in parts:
            # Extract the name part (before dash if any)
            name = part.split('-')[0].strip()
            # Remove any trailing variants like "(первый вариант)"
            name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
            if name:
                names.add(name)

    return names


def collect_all_names(translated_dir: str) -> Dict[str, List[str]]:
    """
    Collect all names from all files.
    Returns dict: name -> list of files where it appears
    """
    all_names: Dict[str, List[str]] = {}

    for root, dirs, files in os.walk(translated_dir):
        for file in files:
            if file.endswith('.md'):
                filepath = os.path.join(root, file)
                names = extract_names_from_file(filepath)
                for name in names:
                    if name not in all_names:
                        all_names[name] = []
                    all_names[name].append(filepath)

    return all_names


def normalize_tatar_text(text: str) -> str:
    """
    Normalize Tatar text by replacing similar characters with canonical forms.
    This helps identify names that differ only in Tatar-specific character variations.
    """
    # Mapping of Tatar/Russian character variations to canonical form
    replacements = {
        'ә': 'е',  # Tatar schwa -> Russian e
        'э': 'е',  # э -> е
        'ө': 'о',  # Tatar ö -> Russian o
        'ү': 'у',  # Tatar ü -> Russian u
        'ң': 'н',  # Tatar ñ -> Russian n
        'җ': 'ж',  # Tatar j -> Russian zh
        'һ': 'х',  # Tatar h -> Russian kh
    }

    normalized = text.lower()
    for old_char, new_char in replacements.items():
        normalized = normalized.replace(old_char, new_char)

    return normalized


def similar(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, normalize_tatar_text(a), normalize_tatar_text(b)).ratio()


def find_similar_names(all_names: Dict[str, List[str]]) -> List[Tuple[str, str, float]]:
    """Find pairs of similar names."""
    names_list = sorted(all_names.keys())
    similar_pairs = []

    for i, name1 in enumerate(names_list):
        for name2 in names_list[i + 1:]:
            sim_ratio = similar(name1, name2)
            if sim_ratio >= SIMILARITY_THRESHOLD:
                similar_pairs.append((name1, name2, sim_ratio))

    # Sort by similarity (descending)
    similar_pairs.sort(key=lambda x: x[2], reverse=True)
    return similar_pairs


def merge_names(names_dict: Dict[str, List[str]], from_name: str, to_name: str) -> int:
    """
    Replace all occurrences of from_name with to_name in files.
    Returns number of files modified.
    """
    files_modified = 0
    from_name_escaped = re.escape(from_name)

    for filepath in names_dict.get(from_name, []):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the name in headers
        # Match name either after ### or after /
        # Pattern 1: ### [whitespace] name [whitespace] [/ or -]
        # Pattern 2: / [whitespace] name [whitespace] [- or end]
        pattern = rf'(###\s+|/\s*){re.escape(from_name)}(\s*(?:/|-|$))'
        new_content = re.sub(pattern, rf'\1{to_name}\2', content, flags=re.MULTILINE)

        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            files_modified += 1
            print(f"  Updated: {filepath}")

    return files_modified


def save_seen_pairs(seen_file: str, seen_pairs: Set[Tuple[str, str]]) -> None:
    """Save pairs that user has already reviewed."""
    with open(seen_file, 'w', encoding='utf-8') as f:
        json.dump(list(seen_pairs), f)


def load_seen_pairs(seen_file: str) -> Set[Tuple[str, str]]:
    """Load previously reviewed pairs."""
    if os.path.exists(seen_file):
        with open(seen_file, 'r', encoding='utf-8') as f:
            return set(tuple(x) for x in json.load(f))
    return set()


def get_staged_files() -> Set[str]:
    """Get set of staged markdown files in translated directory."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return set()

        staged = set()
        for line in result.stdout.strip().split('\n'):
            if line.startswith('translated/') and line.endswith('.md'):
                staged.add(line)
        return staged
    except Exception:
        return set()


def get_staged_names(staged_files: Set[str]) -> Set[str]:
    """Extract names from staged git files."""
    staged_names = set()
    for filepath in staged_files:
        if os.path.exists(filepath):
            names = extract_names_from_file(filepath)
            staged_names.update(names)
    return staged_names


def get_automated_decision(
    name1: str,
    name2: str,
    all_names: Dict[str, List[str]],
    staged_names: Set[str],
    sim_ratio: float
) -> Optional[Tuple[str, str]]:
    """
    Determine if a pair should be auto-merged.
    Returns (keep_name, replace_name) if auto-merge, None otherwise.
    """
    count1 = len(all_names[name1])
    count2 = len(all_names[name2])

    # Rule 1: Very high similarity (95%+) - always auto-merge to more popular version
    if sim_ratio >= AUTO_MERGE_VERY_HIGH_SIMILARITY:
        if count1 > count2:
            return (name1, name2)
        elif count2 > count1:
            return (name2, name1)
        # If equal counts, prefer the one in staged files or the first one
        if name1 in staged_names and name2 not in staged_names:
            return (name1, name2)
        if name2 in staged_names and name1 not in staged_names:
            return (name2, name1)
        # Both or none in staged, keep the shorter/more standard name
        return (name1, name2)

    # Check if one name is in staged files and other is not
    name1_in_staged = name1 in staged_names
    name2_in_staged = name2 in staged_names

    # Rule 2: Only one is in staged files - prioritize that one heavily
    if name1_in_staged and not name2_in_staged:
        if count1 >= count2:
            return (name1, name2)
    elif name2_in_staged and not name1_in_staged:
        if count2 >= count1:
            return (name2, name1)

    # Rule 3: Large usage difference
    if count1 > count2:
        ratio = count1 / count2 if count2 > 0 else float('inf')
        abs_diff = count1 - count2
        if ratio >= AUTO_MERGE_MIN_DIFF_RATIO and abs_diff >= AUTO_MERGE_MIN_ABS_DIFF:
            return (name1, name2)
    elif count2 > count1:
        ratio = count2 / count1 if count1 > 0 else float('inf')
        abs_diff = count2 - count1
        if ratio >= AUTO_MERGE_MIN_DIFF_RATIO and abs_diff >= AUTO_MERGE_MIN_ABS_DIFF:
            return (name2, name1)

    # Rule 4: Moderate difference but one is in staged files
    # If one has 1.5x more usage AND is in staged files
    if count1 > count2:
        ratio = count1 / count2 if count2 > 0 else float('inf')
        if ratio >= 1.5 and name1_in_staged and not name2_in_staged:
            return (name1, name2)
    elif count2 > count1:
        ratio = count2 / count1 if count1 > 0 else float('inf')
        if ratio >= 1.5 and name2_in_staged and not name1_in_staged:
            return (name2, name1)

    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Normalize person names in translated song files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually changing files')
    parser.add_argument('--auto-only', action='store_true',
                        help='Only show automated merges, skip manual review')
    args = parser.parse_args()

    translated_dir = 'translated'
    seen_file = '.normalize_names_seen.json'

    print("🔍 Collecting names from all files...")
    all_names = collect_all_names(translated_dir)

    print(f"📊 Found {len(all_names)} unique names\n")

    # Get staged files and extract names from them
    print("🔍 Checking git staged files...")
    staged_files = get_staged_files()
    staged_names = get_staged_names(staged_files)
    if staged_names:
        print(f"📊 Found {len(staged_names)} unique names in {len(staged_files)} staged file(s)\n")
    else:
        print("📊 No staged files found\n")

    # Load previously seen pairs
    seen_pairs = load_seen_pairs(seen_file)

    print("🔍 Finding similar names...")
    similar_pairs = find_similar_names(all_names)

    # Filter out already seen pairs
    new_pairs = [(n1, n2, sim) for n1, n2, sim in similar_pairs
                 if (n1, n2) not in seen_pairs and (n2, n1) not in seen_pairs]

    if not new_pairs:
        print("✅ No new similar names found!")
        return

    print(f"🔍 Found {len(new_pairs)} potential duplicates\n")

    auto_merged = 0
    manual_review = 0

    for name1, name2, sim_ratio in new_pairs:
        # Skip if either name was already merged in a previous iteration
        if name1 not in all_names or name2 not in all_names:
            seen_pairs.add((name1, name2))
            continue

        # Try automated decision first
        action = get_automated_decision(name1, name2, all_names, staged_names, sim_ratio)

        if action:
            # Automated merge
            keep_name, replace_name = action
            auto_merged += 1

            # Determine reason for auto-merge
            reason_parts = []
            if sim_ratio >= AUTO_MERGE_VERY_HIGH_SIMILARITY:
                reason_parts.append(f"very high similarity ({sim_ratio:.2%})")
            if keep_name in staged_names and replace_name not in staged_names:
                reason_parts.append("found in staged files")
            if len(all_names[keep_name]) > len(all_names[replace_name]):
                ratio = len(all_names[keep_name]) / len(all_names[replace_name]) if len(all_names[replace_name]) > 0 else float('inf')
                reason_parts.append(f"{ratio:.1f}x more usage")

            print(f"\n{'='*70}")
            print(f"🤖 Auto-merging ({sim_ratio:.2%} match):")
            print(f"  '{replace_name}' -> '{keep_name}'")
            print(f"  Reason: {', '.join(reason_parts)}")
            print(f"  Files: '{keep_name}' in {len(all_names[keep_name])}, '{replace_name}' in {len(all_names[replace_name])}")

            if not args.dry_run:
                print(f"\n  🔄 Replacing '{replace_name}' with '{keep_name}'...")
                count = merge_names(all_names, replace_name, keep_name)
                print(f"  ✅ Updated {count} file(s)")
            else:
                print(f"  [DRY RUN] Would update {len(all_names[replace_name])} file(s)")

            # Update the dictionary for future comparisons
            all_names[keep_name].extend(all_names[replace_name])
            del all_names[replace_name]

            seen_pairs.add((name1, name2))
            if not args.dry_run:
                save_seen_pairs(seen_file, seen_pairs)
            continue

        # Manual review required
        if args.auto_only:
            manual_review += 1
            continue

        manual_review += 1
        print(f"\n{'='*70}")
        print(f"🤔 Similar names found ({sim_ratio:.2%} match):")
        print(f"  1. '{name1}'")
        print(f"     Used in {len(all_names[name1])} file(s)")
        if name1 in staged_names:
            print(f"     ⭐ Found in staged files")
        print(f"  2. '{name2}'")
        print(f"     Used in {len(all_names[name2])} file(s)")
        if name2 in staged_names:
            print(f"     ⭐ Found in staged files")

        if args.dry_run:
            seen_pairs.add((name1, name2))
            continue

        while True:
            try:
                response = input("\nChoose action:\n  [s]kip - Skip this pair\n  [m]erge - Merge names\n  [q]uit - Quit script\n\nYour choice: ").strip().lower()
            except EOFError:
                print("\n\n👋 EOF detected, exiting...")
                save_seen_pairs(seen_file, seen_pairs)
                return

            if response in ('s', 'skip', ''):
                print("  ⏭️  Skipped")
                seen_pairs.add((name1, name2))
                break

            elif response in ('m', 'merge'):
                print("\nWhich name should be kept?")
                print(f"  [1] '{name1}'")
                print(f"  [2] '{name2}'")

                choice = input("\nYour choice (1 or 2): ").strip()
                if choice == '1':
                    keep_name = name1
                    replace_name = name2
                elif choice == '2':
                    keep_name = name2
                    replace_name = name1
                else:
                    print("  ❌ Invalid choice, skipping...")
                    seen_pairs.add((name1, name2))
                    break

                print(f"\n  🔄 Replacing '{replace_name}' with '{keep_name}'...")
                count = merge_names(all_names, replace_name, keep_name)
                print(f"  ✅ Updated {count} file(s)")

                # Update the dictionary for future comparisons
                all_names[keep_name].extend(all_names[replace_name])
                del all_names[replace_name]

                seen_pairs.add((name1, name2))
                break

            elif response in ('q', 'quit'):
                print("\n👋 Quitting...")
                save_seen_pairs(seen_file, seen_pairs)
                return

            else:
                print("  ❌ Invalid choice, please try again")

        # Save progress after each pair
        save_seen_pairs(seen_file, seen_pairs)

    print(f"\n{'='*70}")
    print("✅ Done! All pairs reviewed.")
    print(f"🤖 Auto-merged: {auto_merged} pair(s)")
    print(f"👤 Manual review: {manual_review} pair(s)")
    print(f"💾 Progress saved to {seen_file}")


if __name__ == '__main__':
    main()
