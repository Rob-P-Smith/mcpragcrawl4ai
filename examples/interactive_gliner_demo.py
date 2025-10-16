"""
Interactive GLiNER Entity Extraction Demo

Type queries and see what entities GLiNER small-v2.1 extracts in real-time.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.search.query_parser import get_query_parser


def interactive_demo():
    """Interactive demo for testing GLiNER entity extraction"""

    print("\n" + "="*80)
    print("Interactive GLiNER Entity Extraction Demo")
    print("GLiNER Model: urchade/gliner_small-v2.1")
    print("="*80)

    # Load parser
    print("\nLoading GLiNER model...")
    parser = get_query_parser()

    print(f"\n✓ GLiNER Model: {parser.model_name}")
    print(f"✓ Entity Types: {len(parser.entity_types)} loaded")
    print(f"✓ Threshold: {parser.threshold}")

    print("\n" + "-"*80)
    print("Type your queries below. Type 'quit' or 'exit' to stop.")
    print("-"*80 + "\n")

    while True:
        try:
            # Get user input
            query = input("🔍 Query: ").strip()

            # Check for exit
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            # Skip empty queries
            if not query:
                continue

            # Parse query
            result = parser.parse(query)

            # Display results
            print("\n" + "─"*80)
            print(f"📝 Original Query: {result.original_query}")
            print(f"🔄 Normalized: {result.normalized_query}")
            print(f"🎯 Intent: {result.query_intent}")
            print(f"📊 Confidence: {result.confidence:.2f}")

            if result.extracted_entities:
                print(f"\n✨ Entities Found ({len(result.extracted_entities)}):")
                for i, entity in enumerate(result.extracted_entities, 1):
                    print(f"   {i}. {entity}")
            else:
                print("\n⚠️  No entities found (try lowering threshold or different query)")

            print("\n" + "─"*80 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            continue


if __name__ == "__main__":
    interactive_demo()
