#!/usr/bin/env python3
"""
Database Statistics Script for Crawl4AI RAG
Shows record counts, database size, and recent activity
"""

import sqlite3
import os
from datetime import datetime

def get_db_stats(db_path="crawl4ai_rag.db"):
    """Get comprehensive database statistics"""
    
    if not os.path.exists(db_path):
        print(f"❌ Database file '{db_path}' not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Try to load sqlite-vec extension
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            vec_available = True
            print("✅ sqlite-vec extension loaded successfully")
        except Exception as e:
            vec_available = False
            print(f"⚠️  sqlite-vec extension not available: {e}")
        
        print("=" * 50)
        print("📊 CRAWL4AI RAG DATABASE STATISTICS")
        print("=" * 50)
        
        # Basic counts
        pages = conn.execute('SELECT COUNT(*) FROM crawled_content').fetchone()[0]
        
        # Try to get embedding count, fallback if vec0 not available
        if vec_available:
            try:
                embeddings = conn.execute('SELECT COUNT(*) FROM content_vectors').fetchone()[0]
            except:
                embeddings = "N/A (vec0 error)"
        else:
            embeddings = "N/A (extension not loaded)"
            
        sessions = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
        
        print(f"📄 Total Pages: {pages:,}")
        print(f"🧠 Vector Embeddings: {embeddings}")
        print(f"👥 Sessions: {sessions:,}")
        
        # Database size
        size_result = conn.execute('SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()').fetchone()
        if size_result:
            size_bytes = size_result[0]
            size_mb = size_bytes / 1024 / 1024
            print(f"💾 Database Size: {size_mb:.2f} MB ({size_bytes:,} bytes)")
        
        # Records by retention policy
        print("\n📋 RECORDS BY RETENTION POLICY:")
        retention_stats = conn.execute('''
            SELECT retention_policy, COUNT(*) as count 
            FROM crawled_content 
            GROUP BY retention_policy 
            ORDER BY count DESC
        ''').fetchall()
        
        for policy, count in retention_stats:
            print(f"   {policy}: {count:,} pages")
        
        # Recent activity
        print("\n🕒 RECENT ACTIVITY (Last 10 pages):")
        recent = conn.execute('''
            SELECT url, title, timestamp, 
                   LENGTH(content) as content_size,
                   retention_policy
            FROM crawled_content 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''').fetchall()
        
        if recent:
            for url, title, timestamp, size, policy in recent:
                # Truncate long titles and URLs
                display_title = (title[:40] + "...") if title and len(title) > 40 else (title or "No title")
                display_url = (url[:50] + "...") if len(url) > 50 else url
                size_kb = size / 1024 if size else 0
                
                print(f"   📄 {display_title}")
                print(f"      🔗 {display_url}")
                print(f"      ⏰ {timestamp} | 📏 {size_kb:.1f}KB | 🏷️ {policy}")
                print()
        else:
            print("   No pages found")
        
        # Storage breakdown
        print("📊 STORAGE BREAKDOWN:")
        content_size = conn.execute('''
            SELECT SUM(LENGTH(content) + LENGTH(COALESCE(markdown, '')) + LENGTH(COALESCE(title, ''))) 
            FROM crawled_content
        ''').fetchone()[0] or 0
        
        # Approximate embedding size (384 dimensions * 4 bytes per float * number of embeddings)
        if isinstance(embeddings, int):
            embedding_size = embeddings * 384 * 4
        else:
            embedding_size = 0
        
        content_mb = content_size / 1024 / 1024
        embedding_mb = embedding_size / 1024 / 1024
        
        print(f"   📝 Content: {content_mb:.2f} MB")
        print(f"   🧠 Embeddings: {embedding_mb:.2f} MB")
        print(f"   🗂️ Metadata/Other: {(size_mb - content_mb - embedding_mb):.2f} MB")
        
        # Tags analysis if any pages have tags
        tags_result = conn.execute('''
            SELECT tags, COUNT(*) as count 
            FROM crawled_content 
            WHERE tags IS NOT NULL AND tags != ''
            GROUP BY tags 
            ORDER BY count DESC 
            LIMIT 5
        ''').fetchall()
        
        if tags_result:
            print("\n🏷️ MOST COMMON TAGS:")
            for tags, count in tags_result:
                print(f"   {tags}: {count:,} pages")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    # Try current directory first, then home directory
    db_paths = ["crawl4ai_rag.db", os.path.expanduser("~/crawl4ai_rag.db")]
    
    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"📍 Using database: {os.path.abspath(db_path)}")
            get_db_stats(db_path)
            break
    else:
        print("❌ Could not find crawl4ai_rag.db in current directory or home directory")
        print("💡 Run this script from the directory containing your database file")