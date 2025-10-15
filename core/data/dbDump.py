"""
Database dump script for Crawl4AI RAG system
Dumps all URLs and content from the database to dbdump.md
"""

import sqlite3
import os
import sys

def main():
    # Database path
    db_path = '/home/robiloo/Documents/mcpragcrawl4ai/data/crawl4ai_rag.db'
    
    # Output file path
    output_path = 'dbdump.md'
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f'Error: Database file not found at {db_path}')
        sys.exit(1)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query all URLs and content from crawled_content table
    cursor.execute('SELECT url, content FROM crawled_content')
    results = cursor.fetchall()
    
    # Close connection
    conn.close()
    
    # Write to output file
    with open(output_path, 'w') as f:
        # Section 1: Full list of URLs
        f.write("# Full List of URLs\n")
        f.write("All URLs stored in the database\n")
        f.write("\n")
        for url, _ in results:
            f.write(f"{url}\n")
        
        # Section 2: URLs with first 200 chars of content
        f.write("\n")
        f.write("# URLs with First 200 Characters of Content\n")
        f.write("Each URL followed by the first 200 characters of its content\n")
        f.write("\n")
        for url, content in results:
            f.write(f"{url}\n")
            f.write(f"{content[:200]}\n")
            f.write("\n")
    
    print(f"Successfully wrote {len(results)} URLs and content snippets to {output_path}")

if __name__ == "__main__":
    main()
