#!/usr/bin/env ruby
# reorganize_translated.rb - Reorganize existing translated files into letter subdirectories

require 'fileutils'

TRANSLATED_DIR = 'translated'

def reorganize_files
  # Get all .md files directly in the translated directory (not in subdirectories)
  files = Dir.glob(File.join(TRANSLATED_DIR, '*.md'))

  if files.empty?
    puts "No files found to reorganize in #{TRANSLATED_DIR}/"
    return
  end

  puts "Found #{files.length} files to reorganize"
  puts '-' * 50

  moved_count = 0

  files.each do |file|
    filename = File.basename(file)

    # Get first letter of filename for directory structure
    first_letter = filename[0].downcase
    letter_dir = File.join(TRANSLATED_DIR, first_letter)

    # Create letter subdirectory if it doesn't exist
    FileUtils.mkdir_p(letter_dir) unless Dir.exist?(letter_dir)

    # Move file to letter subdirectory
    new_path = File.join(letter_dir, filename)
    FileUtils.mv(file, new_path)

    puts "✓ Moved: #{filename} → #{first_letter}/#{filename}"
    moved_count += 1
  end

  puts '-' * 50
  puts "Successfully reorganized #{moved_count} files!"
end

# Main execution
if __FILE__ == $0
  reorganize_files
end
