# Care Beacon Web Client - Quick Start

## ✅ Your Web Application is Running!

The Next.js web client is now live and connected to your Care Beacon API.

- 🌐 **Web UI**: http://localhost:3000
- 🔌 **API Backend**: http://localhost:8000
- 🎨 **Framework**: Next.js 15 with shadcn/ui components
- 🌓 **Theme**: Vercel-inspired design with dark/light mode

## 🚀 Access the Application

Open your browser and navigate to:

```
http://localhost:3000
```

## 📋 Features Available

### 1. Search Tab (Main Interface)
- **Natural language question input** - Ask medical questions in plain English
- **Real-time answer generation** - Powered by OpenAI GPT-4o-mini
- **Source citations** - All answers include references to BC Cancer articles
- **Cache indicators** - See which answers are cached vs fresh
- **System health panel** - Monitor API and service status
- **Metadata display** - View tokens used, cost, and generation time

**Example Questions:**
```
- What are the symptoms of breast cancer?
- How is cancer diagnosed?
- What are the treatment options for lung cancer?
```

### 2. Statistics Tab
- **Overview metrics** - Total cost, cache hit rate, cost saved, embeddings
- **LLM statistics** - Token usage, API calls, costs
- **Cache performance** - Hit rate, misses, time saved
- **Vector database stats** - Embedding model, dimensions, costs

### 3. Admin Tab
- **Clear cache** - Remove all cached query results
- **Reset statistics** - Reset all usage metrics to zero
- **System health** - Monitor service connectivity

## 🎨 UI Features

### Theme Toggle
Click the sun/moon icon in the top-right to switch between light and dark modes.

### Responsive Design
The application works seamlessly on:
- 💻 Desktop browsers
- 📱 Mobile devices
- 📱 Tablets

## 🔧 Development Commands

### Start Development Server
```bash
npm run dev
```
Runs on http://localhost:3000

### Build for Production
```bash
npm run build
npm start
```

### Run Linter
```bash
npm run lint
```

## 📊 How It Works

1. **User asks a question** → Search interface
2. **Frontend sends request** → API client (`lib/api.ts`)
3. **Backend processes** → Care Beacon API at `localhost:8000`
4. **Cache check** → Redis checks for cached answer
5. **If cached** → Return immediately (fast, free)
6. **If not cached**:
   - Vector DB retrieves relevant chunks
   - LLM generates answer
   - Result is cached
7. **Response displayed** → UI shows answer + sources

## 🎯 Try These Examples

### Basic Search
1. Click on "Search" tab (default)
2. Type: "What are the symptoms of breast cancer?"
3. Click "Search" or press Enter
4. View the answer and source citations

### Check Statistics
1. Click on "Statistics" tab
2. View real-time metrics
3. Refresh to see updated numbers after queries

### Admin Functions
1. Click on "Admin" tab
2. Use "Clear Cache" to remove all cached results
3. Use "Reset Statistics" to zero out all metrics
4. Check system health status

## 🔍 Troubleshooting

### Web App Not Loading
```bash
# Check if dev server is running
curl http://localhost:3000

# Restart the server
npm run dev
```

### API Connection Errors
- Make sure Care Beacon API is running on port 8000
- Check Docker containers: `docker-compose ps`
- Both containers should show "Up (healthy)"

### Theme Not Switching
- Clear browser cache
- Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

### Slow Initial Load
- First page load compiles React components
- Subsequent loads are much faster
- Production build is optimized

## 📱 Mobile Testing

Test responsive design:
1. Open browser DevTools (F12)
2. Click device toolbar icon
3. Select mobile device
4. Test interface on different screen sizes

## 🚀 Next Steps

### Deployment Options

**1. Vercel (Recommended)**
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Follow prompts to deploy
```

**2. Docker**
```bash
# Build image
docker build -t care-beacon-web .

# Run container
docker run -p 3000:3000 care-beacon-web
```

**3. Traditional Hosting**
```bash
# Build static files
npm run build

# Start production server
npm start
```

### Environment Variables

For production, set:
```bash
NEXT_PUBLIC_API_URL=https://your-api-domain.com
```

## 💡 Tips

1. **Use cache efficiently** - Similar questions hit cache, saving cost
2. **Monitor statistics** - Track your API usage and costs
3. **Clear cache sparingly** - Only when needed for fresh data
4. **Try dark mode** - Easier on the eyes for extended use
5. **Bookmark common queries** - Faster access to frequent searches

## 📚 Additional Resources

- Main README: `web-client/README.md`
- API Documentation: `../DOCKER_QUICKSTART.md`
- Architecture: `../ARCHITECTURE.md`
- Full Deployment Guide: `../DOCKER_DEPLOYMENT.md`

## 🎉 Enjoy!

Your Care Beacon web application is ready to use. Ask medical questions and get evidence-based answers instantly!

---

**Current Status**: ✅ Running
**Web UI**: http://localhost:3000
**API**: http://localhost:8000
**Last Updated**: 2025-11-08
