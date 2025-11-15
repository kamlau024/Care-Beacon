#!/bin/bash
# Rebuild Docker Stack for Care-Beacon
# This script stops, cleans, rebuilds, and restarts all Docker services

set -e  # Exit on error

echo "========================================================================"
echo "Care-Beacon Docker Stack Rebuild"
echo "========================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Step 1: Stop all running containers
print_step "Stopping all running containers..."
if docker-compose ps -q 2>/dev/null | grep -q .; then
    docker-compose down
    print_success "Containers stopped"
else
    print_warning "No running containers to stop"
fi
echo ""

# Step 2: Remove all containers, networks, and images (optional)
read -p "Do you want to remove ALL containers and images? (y/n, default: n): " CLEAN_ALL
if [[ "$CLEAN_ALL" =~ ^[Yy]$ ]]; then
    print_step "Removing all containers, networks, and images..."
    docker-compose down --rmi all --volumes --remove-orphans
    print_success "All containers, images, and volumes removed"
else
    print_step "Removing containers and networks only..."
    docker-compose down --volumes --remove-orphans
    print_success "Containers and networks removed"
fi
echo ""

# Step 3: Clean up dangling images (optional)
print_step "Checking for dangling images..."
DANGLING=$(docker images -f "dangling=true" -q)
if [ -n "$DANGLING" ]; then
    read -p "Found dangling images. Remove them? (y/n, default: y): " CLEAN_DANGLING
    if [[ -z "$CLEAN_DANGLING" || "$CLEAN_DANGLING" =~ ^[Yy]$ ]]; then
        docker image prune -f
        print_success "Dangling images removed"
    else
        print_warning "Dangling images kept"
    fi
else
    print_success "No dangling images found"
fi
echo ""

# Step 4: Rebuild images
print_step "Rebuilding Docker images..."
echo ""
docker-compose build --no-cache
echo ""
print_success "Images rebuilt successfully"
echo ""

# Step 5: Start services
print_step "Starting services..."
echo ""
docker-compose up -d
echo ""
print_success "Services started"
echo ""

# Step 6: Wait for services to be healthy
print_step "Waiting for services to be healthy..."
echo ""

# Wait for API health check
MAX_WAIT=30
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker-compose ps api | grep -q "healthy"; then
        break
    fi
    echo -n "."
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done
echo ""

if [ $WAIT_COUNT -lt $MAX_WAIT ]; then
    print_success "API service is healthy"
else
    print_warning "API service may still be starting (waited ${MAX_WAIT}s)"
fi
echo ""

# Step 7: Show status
print_step "Service Status:"
echo ""
docker-compose ps
echo ""

# Step 8: Show recent logs
print_step "Recent logs (last 20 lines):"
echo ""
docker-compose logs --tail=20
echo ""

# Summary
echo "========================================================================"
echo "Docker Stack Rebuild Complete!"
echo "========================================================================"
echo ""
echo -e "${GREEN}Services:${NC}"
echo "  • API:     http://localhost:8000"
echo "  • Web UI:  http://localhost:3000"
echo "  • Redis:   localhost:6379"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  • View logs:        docker-compose logs -f"
echo "  • View API logs:    docker-compose logs -f api"
echo "  • View web logs:    docker-compose logs -f web"
echo "  • Restart service:  docker-compose restart <service>"
echo "  • Stop all:         docker-compose down"
echo ""
echo -e "${GREEN}✓${NC} Ready for testing!"
echo ""
