#!/bin/bash
# Validation script for Care-Beacon vector database ingestion
# Wrapper around validate_ingestion.py for convenience

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Print usage
usage() {
    echo -e "${BLUE}Care-Beacon Ingestion Validation${NC}"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  stats                               Show database statistics"
    echo "  list [LIMIT]                        List all chunks (default limit: 100)"
    echo "  search QUERY [TOP_K] [SOURCE]       Semantic search for content"
    echo "                                        TOP_K: number of results (default: 5)"
    echo "                                        SOURCE: 'BC Cancer' or 'Canadian Cancer Society'"
    echo "  article TITLE                       Search for article by title"
    echo "  file PATH                           Check if specific file was ingested"
    echo "  source SOURCE                       Show all articles from a source"
    echo "  help                                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 stats"
    echo "  $0 list 50"
    echo "  $0 search \"What is a normal PSA level?\" 5"
    echo "  $0 search \"What is a normal PSA level?\" 5 \"BC Cancer\""
    echo "  $0 article \"Prostate\""
    echo "  $0 file scraped_data/bc-cancer/articles/health-info/types-of-cancer/pelvic-area/prostate.md"
    echo "  $0 source \"BC Cancer\""
    echo ""
}

# Check if Python script exists
if [ ! -f "$SCRIPT_DIR/validate_ingestion.py" ]; then
    echo -e "${YELLOW}Error: validate_ingestion.py not found${NC}"
    exit 1
fi

# Parse command
COMMAND="${1:-stats}"

case "$COMMAND" in
    stats)
        echo -e "${GREEN}Getting database statistics...${NC}"
        python "$SCRIPT_DIR/validate_ingestion.py" --stats
        ;;

    list)
        LIMIT="${2:-100}"
        echo -e "${GREEN}Listing chunks (limit: $LIMIT)...${NC}"
        python "$SCRIPT_DIR/validate_ingestion.py" --list --limit "$LIMIT"
        ;;

    search)
        if [ -z "$2" ]; then
            echo -e "${YELLOW}Error: Please provide a search query${NC}"
            echo "Usage: $0 search QUERY [TOP_K] [SOURCE]"
            echo "  QUERY   - Search query (required)"
            echo "  TOP_K   - Number of results (default: 5)"
            echo "  SOURCE  - Filter by source: 'BC Cancer' or 'Canadian Cancer Society'"
            exit 1
        fi
        QUERY="$2"
        TOP_K="${3:-5}"
        SOURCE="${4:-}"

        if [ -n "$SOURCE" ]; then
            echo -e "${GREEN}Searching for: '$QUERY' (top $TOP_K results, source: $SOURCE)...${NC}"
            python "$SCRIPT_DIR/validate_ingestion.py" --search "$QUERY" --top-k "$TOP_K" --source-filter "$SOURCE"
        else
            echo -e "${GREEN}Searching for: '$QUERY' (top $TOP_K results)...${NC}"
            python "$SCRIPT_DIR/validate_ingestion.py" --search "$QUERY" --top-k "$TOP_K"
        fi
        ;;

    article)
        if [ -z "$2" ]; then
            echo -e "${YELLOW}Error: Please provide an article title${NC}"
            echo "Usage: $0 article TITLE"
            exit 1
        fi
        TITLE="$2"
        echo -e "${GREEN}Searching for article: '$TITLE'...${NC}"
        python "$SCRIPT_DIR/validate_ingestion.py" --article "$TITLE"
        ;;

    file)
        if [ -z "$2" ]; then
            echo -e "${YELLOW}Error: Please provide a file path${NC}"
            echo "Usage: $0 file PATH"
            exit 1
        fi
        FILE_PATH="$2"
        echo -e "${GREEN}Checking if file was ingested: $FILE_PATH${NC}"
        python "$SCRIPT_DIR/validate_ingestion.py" --file "$FILE_PATH"
        ;;

    source)
        if [ -z "$2" ]; then
            echo -e "${YELLOW}Error: Please provide a source name${NC}"
            echo "Usage: $0 source SOURCE"
            echo "Available sources:"
            echo "  - BC Cancer"
            echo "  - Canadian Cancer Society"
            exit 1
        fi
        SOURCE="$2"
        echo -e "${GREEN}Filtering by source: '$SOURCE'...${NC}"
        python "$SCRIPT_DIR/validate_ingestion.py" --source "$SOURCE"
        ;;

    help|--help|-h)
        usage
        exit 0
        ;;

    *)
        echo -e "${YELLOW}Unknown command: $COMMAND${NC}"
        echo ""
        usage
        exit 1
        ;;
esac
