#!/usr/bin/env ruby
# translate_songs.rb - Automated Tatar to Russian lyrics translation

require 'json'
require 'fileutils'
require 'open3'

class SongTranslator
  BATCH_SIZE = 2
  TAT_DIR = 'tat'
  TRANSLATED_DIR = 'translated'
  
  def initialize
    ensure_directories
    @processed_count = 0
  end
  
  def run
    loop do
      files = get_next_batch
      break if files.empty?
      
      puts "\n#{'-' * 50}"
      puts "Processing batch of #{files.length} files..."
      puts "Files: #{files.map { |f| File.basename(f) }.join(', ')}"
      
      # Prepare batch data
      batch_data = prepare_batch_data(files)
      
      # Get translations from Claude
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
    Dir.glob(File.join(TAT_DIR, '*.md'))
       .sort
       .first(BATCH_SIZE)
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
    # Prepare Claude command with JSON data directly in the prompt
    json_data = JSON.pretty_generate(batch_data)
    
    claude_input = <<~PROMPT
      Translate the following Tatar song lyrics to Russian.
      Return ONLY a valid JSON array with translations, no explanations or markdown.
      Follow the format specified in CLAUDE.md.
      
      Input JSON:
      #{json_data}
    PROMPT

    puts claude_input
    
    begin
      # Execute Claude command
      stdout, stderr, status = Open3.capture3('claude', stdin_data: claude_input)
      
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
          puts "Warning: Could not find JSON in Claude response"
          puts "Response: #{stdout[0..500]}..." if stdout.length > 500
        end
      else
        puts "Error running Claude: #{stderr}"
      end
    rescue JSON::ParserError => e
      puts "Error parsing JSON response: #{e.message}"
    rescue => e
      puts "Error: #{e.message}"
    end
    
    nil
  end
  
  def process_translations(translations, files)
    translations.each_with_index do |translation, index|
      next unless translation && files[index]
      
      original_file = files[index]
      filename = File.basename(original_file, '.md')
      
      # Create translated content
      content = create_translated_content(translation)
      
      # Save to translated directory
      output_file = File.join(TRANSLATED_DIR, "#{filename}.md")
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
