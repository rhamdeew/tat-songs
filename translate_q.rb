#!/usr/bin/env ruby
# translate_songs.rb - Automated Tatar to Russian lyrics translation

require 'json'
require 'fileutils'
require 'open3'

class SongTranslator
  BATCH_SIZE = 1
  TAT_DIR = 'tat'
  TRANSLATED_DIR = 'translated'
  
  def initialize
    ensure_directories
    @processed_count = 0
    @locked_files = []
  end
  
  def run
    loop do
      files = get_next_batch
      break if files.empty?
      
      puts "\n#{'-' * 50}"
      puts "Processing batch of #{files.length} files..."
      puts "Files: #{files.map { |f| File.basename(f) }.join(', ')}"
      
      # Lock files for processing
      lock_files(files)
      
      begin
        # Prepare batch data
        batch_data = prepare_batch_data(files)
        
        # Get translations from Qwen
        translations = get_translations(batch_data)
        
        if translations
          # Process and save translations
          process_translations(translations, files)
          
          # Remove original files
          remove_processed_files(files)
          
          @processed_count += files.length
          puts "✓ Successfully processed #{files.length} files (Total: #{@processed_count})"
        else
          puts "✗ Translation failed for this batch, skipping..."
          break
        end
      rescue => e
        puts "✗ Error processing batch: #{e.message}"
        puts e.backtrace.first(5).join("\n")
        break
      ensure
        # Always unlock files, even if an error occurred
        unlock_files(files)
      end
      
      # Small delay to avoid rate limiting
      sleep(2)
    end
    
    puts "\n#{'-' * 50}"
    puts "Translation complete! Processed #{@processed_count} files total."
  end
  
  private
  
  def sanitize_json_string(text)
    # Replace problematic characters that break JSON
    text.gsub(/[\u201C\u201D]/, '"')  # Left and right double curly quotes
         .gsub(/[""''""‟]/, '"')
         .gsub(/[–—]/, '-')
         .gsub(/[…]/, '...')
         .gsub(/[\u202F\u00A0]/, ' ')
         .gsub(/[\u2000-\u200F\u2028-\u202F\u205F\u3000]/, '')
  end
  
  def sanitize_json_response(json_str)
    # Replace problematic characters in JSON response
    json_str.gsub(/[\u201C\u201D]/, '"')  # Left and right double curly quotes
            .gsub(/[""''""‟]/, '"')
            .gsub(/[–—]/, '-')
            .gsub(/[…]/, '...')
            .gsub(/[\u202F\u00A0]/, ' ')
            .gsub(/[\u2000-\u200F\u2028-\u202F\u205F\u3000]/, '')
  end
  
  def ensure_directories
    FileUtils.mkdir_p(TAT_DIR) unless Dir.exist?(TAT_DIR)
    FileUtils.mkdir_p(TRANSLATED_DIR) unless Dir.exist?(TRANSLATED_DIR)
  end
  
  def get_next_batch
    available_files = Dir.glob(File.join(TAT_DIR, '*.md'))
    
    # Try to find unlocked files
    available_files.shuffle.each_slice(BATCH_SIZE) do |batch|
      batch_fhs = {}
      can_lock = true
      
      batch.each do |file|
        begin
          fh = File.open(file, 'r')
          # Try non-blocking lock
          if fh.flock(File::LOCK_EX | File::LOCK_NB)
            batch_fhs[file] = fh
          else
            fh.close
            can_lock = false
            break
          end
        rescue Errno::ENOENT
          # File was deleted by another process
          can_lock = false
          break
        end
      end
      
      if can_lock
        # Keep the locks and return the files
        @locked_files.concat(batch_fhs.values)
        return batch
      else
        # Release any locks we acquired
        batch_fhs.values.each { |fh| fh.close }
        next
      end
    end
    
    []
  end
  
  def lock_files(files)
    # Files are already locked by get_next_batch
  end
  
  def unlock_files(files)
    files.each do |file|
      # Find and close the file handle for this file
      @locked_files.delete_if do |fh|
        begin
          if fh.path == file
            fh.flock(File::LOCK_UN)
            fh.close
            true
          else
            false
          end
        rescue
          true
        end
      end
    end
  end
  
  def prepare_batch_data(files)
    files.map do |file|
      content = File.read(file, encoding: 'utf-8')
      filename = File.basename(file, '.md')
      
      # Parse artist and song name from filename
      parts = filename.split('-', 2)
      artist = parts[0] || 'unknown'
      song = parts[1] || 'untitled'
      
      # Extract song title and lyrics from content
      title_match = content.match(/###\s*(.+)/)
      title = title_match ? title_match[1].strip : "#{artist} - #{song}"
      
      # Extract lyrics (between ``` blocks)
      lyrics_match = content.match(/```\n(.*?)```/m)
      lyrics = lyrics_match ? lyrics_match[1].strip : content.strip
      
      # Clean up problematic characters that break JSON
      title = sanitize_json_string(title)
      lyrics = sanitize_json_string(lyrics)
      
      {
        'filename' => filename,
        'artist' => artist,
        'song' => song,
        'title' => title,
        'lyrics' => lyrics
      }
    end
  end
  
  def get_translations(batch_data)
    max_attempts = 3

    max_attempts.times do |attempt|
      attempt_number = attempt + 1

      # Prepare Qwen command with JSON data directly in the prompt
      json_data = JSON.pretty_generate(batch_data)

      claude_input = <<~PROMPT
Translate the following Tatar song lyrics to Russian.
Return ONLY a valid JSON array with translations, no explanations or markdown.
You are a professional translator specializing in poetic translation of Tatar song lyrics to Russian.

## Task
Translate the provided Tatar song lyrics to Russian, maintaining:
- Poetic beauty and rhythm
- Emotional depth and meaning
- Cultural context where appropriate
- Natural Russian language flow

## Input Format
You will receive a JSON array directly in the prompt containing songs with:
- `filename`: Original filename
- `artist`: Artist name (romanized)
- `song`: Song name (romanized)
- `title`: Original Tatar title
- `lyrics`: Tatar lyrics to translate

## Output Format
Return ONLY a valid JSON array. Each element should have:
```json
{
  "filename": "original-filename",
  "original_title": "Artist - Original Song Title in Tatar",
  "original_lyrics": "Original Tatar lyrics",
  "translated_title": "Артист - Название песни по-русски",
  "translated_lyrics": "Translated Russian lyrics"
}
```

## Translation Guidelines
1. **Preserve meaning** - Capture the essence and emotions
2. **Use poetic language** - Apply literary devices natural to Russian poetry
3. **Maintain structure** - Keep verse/chorus structure when possible
4. **Cultural adaptation** - Adapt cultural references appropriately
5. **Natural flow** - Ensure the Russian text flows naturally

## Important Notes
- Return ONLY the JSON array, no explanations or markdown
- Translate artist names to Cyrillic if they're Tatar names
- Keep romanized names as-is if they're already in Latin script
- Ensure all JSON is properly escaped and valid

## Example Translation Quality
Tatar: "Э мин явыр идем ап-ак карлар булып кулларына"
Russian: "Ах, я бы выпала белым снегом на твои ладони"
(Note the poetic enhancement while preserving meaning)

Input JSON:
      #{json_data}
    PROMPT

      puts claude_input
      puts "\nAttempt #{attempt_number}/#{max_attempts}..." if attempt > 0

      begin
        # Execute Qwen command
        stdout, stderr, status = Open3.capture3('qwen', stdin_data: claude_input)

        if status.success?
          # Extract JSON from response
          json_match = stdout.match(/\[.*\]/m)
          if json_match
            json_str = json_match[0]
            # Clean up problematic characters before parsing
            json_str = sanitize_json_response(json_str)
            translations = JSON.parse(json_str)
            return translations
          else
            puts "Warning: Could not find JSON in Qwen response"
            puts "Response: #{stdout[0..500]}..." if stdout.length > 500
          end
        else
          puts "Error running Qwen: #{stderr}"
        end
      rescue JSON::ParserError => e
        puts "Error parsing JSON response: #{e.message}"
      rescue => e
        puts "Error: #{e.message}"
      end

      if attempt < max_attempts - 1
        puts "Retrying in 3 seconds..."
        sleep(3)
      end
    end

    puts "Failed after #{max_attempts} attempts. Giving up."
    nil
  end
  
  def process_translations(translations, files)
    translations.each_with_index do |translation, index|
      next unless translation && files[index]
      
      original_file = files[index]
      filename = File.basename(original_file, '.md')

      # Create translated content
      content = create_translated_content(translation)

      # Get first letter of filename for directory structure
      first_letter = filename[0].downcase
      letter_dir = File.join(TRANSLATED_DIR, first_letter)
      FileUtils.mkdir_p(letter_dir) unless Dir.exist?(letter_dir)

      # Save to translated directory with letter subdirectory
      output_file = File.join(letter_dir, "#{filename}.md")
      File.write(output_file, content, encoding: 'utf-8')
      
      puts "  ✓ Saved: #{output_file}"
    end
  end
  
  def create_translated_content(translation)
    <<~CONTENT
      # Оригинал
      
      ### #{translation['original_title']}
      
      ```
      #{translation['original_lyrics']}
      ```
      
      ------
      
      # Перевод
      
      ### #{translation['translated_title']}
      
      ```
      #{translation['translated_lyrics']}
      ```
    CONTENT
  end
  
  def remove_processed_files(files)
    files.each do |file|
      FileUtils.rm(file)
      puts "  ✓ Removed: #{file}"
    end
  end
end

# Main execution
if __FILE__ == $0
  translator = SongTranslator.new
  translator.run
end
