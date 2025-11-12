#!/bin/bash
# Care-Beacon Test Runner Script
# This script runs tests in the Docker container

set -e  # Exit on error

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root to ensure docker-compose works correctly
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CONTAINER_NAME="care-beacon-api"
COVERAGE=false
VERBOSE=false
QUICK=false
SPECIFIC_TEST=""

# Print usage
usage() {
    echo -e "${BLUE}Care-Beacon Test Runner${NC}"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -c, --coverage     Run tests with coverage report"
    echo "  -v, --verbose      Run tests in verbose mode"
    echo "  -q, --quick        Run tests in quick mode (no coverage, minimal output)"
    echo "  -f, --file FILE    Run specific test file (e.g., test_api.py)"
    echo "  -t, --test TEST    Run specific test function (e.g., test_root_endpoint)"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run all tests"
    echo "  $0 -c                        # Run all tests with coverage"
    echo "  $0 -v                        # Run all tests in verbose mode"
    echo "  $0 -f test_api.py            # Run only API tests"
    echo "  $0 -t test_root_endpoint     # Run specific test"
    echo "  $0 -c -v                     # Run with coverage and verbose output"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quick)
            QUICK=true
            shift
            ;;
        -f|--file)
            SPECIFIC_TEST="tests/$2"
            shift 2
            ;;
        -t|--test)
            SPECIFIC_TEST="tests/ -k $2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Check if Docker container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}Error: Container '$CONTAINER_NAME' is not running${NC}"
    echo -e "${YELLOW}Start it with: docker-compose up -d${NC}"
    exit 1
fi

# Build pytest command
PYTEST_CMD="pytest /app/tests/"

if [ -n "$SPECIFIC_TEST" ]; then
    PYTEST_CMD="pytest /app/$SPECIFIC_TEST"
fi

# Add flags based on options
if [ "$QUICK" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -q"
elif [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing"
fi

# Print what we're running
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Care-Beacon Test Runner                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ -n "$SPECIFIC_TEST" ]; then
    echo -e "${YELLOW}Running specific test:${NC} $SPECIFIC_TEST"
elif [ "$QUICK" = true ]; then
    echo -e "${YELLOW}Running quick test suite${NC}"
elif [ "$COVERAGE" = true ]; then
    echo -e "${YELLOW}Running full test suite with coverage${NC}"
else
    echo -e "${YELLOW}Running full test suite${NC}"
fi
echo ""

# Run the tests
echo -e "${GREEN}Executing:${NC} docker exec $CONTAINER_NAME $PYTEST_CMD"
echo ""

if docker exec "$CONTAINER_NAME" $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ All tests passed successfully!                         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Some tests failed                                       ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
