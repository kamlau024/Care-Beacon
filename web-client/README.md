# Care Beacon Web Client

A modern, responsive web interface for the Care Beacon medical AI assistant, built with Next.js and shadcn/ui.

## Features

- 🔍 **Natural Language Search** - Ask medical questions in plain language
- 📊 **Real-time Statistics** - Monitor API usage, costs, and cache performance
- ❤️ **Health Monitoring** - Check system status and service connectivity
- ⚙️ **Admin Controls** - Manage cache and reset statistics
- 🌓 **Dark Mode** - Beautiful light and dark themes
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile
- ⚡ **Fast Performance** - Built with Next.js 15 App Router

## Technology Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (Radix UI primitives)
- **Icons**: Lucide React
- **Theme**: next-themes

## Prerequisites

- Node.js 18+ and npm
- Care Beacon API running on `http://localhost:8000`

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

The default configuration connects to `http://localhost:8000`. To change this, create or edit `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
web-client/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout with theme provider
│   ├── page.tsx           # Main page with tabs
│   └── globals.css        # Global styles and theme variables
├── components/            # React components
│   ├── ui/               # shadcn/ui base components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── badge.tsx
│   │   └── tabs.tsx
│   ├── search-interface.tsx   # Main search UI
│   ├── stats-dashboard.tsx    # Statistics display
│   ├── health-check.tsx       # Health monitoring
│   ├── admin-controls.tsx     # Admin functions
│   ├── theme-provider.tsx     # Theme context
│   └── theme-toggle.tsx       # Dark/light mode toggle
├── lib/                   # Utilities and API client
│   ├── api.ts            # API client functions
│   ├── types.ts          # TypeScript type definitions
│   └── utils.ts          # Utility functions (cn)
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

## Available Scripts

- `npm run dev` - Start development server on port 3000
- `npm run build` - Build production bundle
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## Features Overview

### Search Tab
- Natural language question input
- Real-time answer generation
- Source citations with links
- Metadata display (tokens, cost, time)
- Cache status indicator
- System health check panel

### Statistics Tab
- Overview cards (total cost, cache hit rate, cost saved, embeddings)
- Detailed LLM statistics
- Cache performance metrics
- Vector database statistics
- Real-time data fetching

### Admin Tab
- Clear cache function
- Reset statistics function
- System health monitoring
- Warning indicators for destructive actions

## Theme Customization

The application uses CSS variables for theming. Edit `app/globals.css` to customize colors:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 0 0% 3.9%;
  --primary: 0 0% 9%;
  /* ... more variables */
}

.dark {
  --background: 0 0% 3.9%;
  --foreground: 0 0% 98%;
  /* ... dark mode variables */
}
```

## API Integration

The client connects to the Care Beacon API with these endpoints:

- `GET /health` - System health check
- `POST /api/v1/ask` - Ask a question
- `GET /api/v1/stats` - Get statistics
- `POST /api/v1/cache/clear` - Clear cache
- `POST /api/v1/stats/reset` - Reset statistics

See `lib/api.ts` for the full API client implementation.

## Responsive Design

The UI is fully responsive with breakpoints:

- Mobile: Single column layout
- Tablet (md): 2-column grid for some sections
- Desktop (lg): 3-column grid with optimized spacing

## Contributing

1. Follow TypeScript strict mode
2. Use shadcn/ui components for consistency
3. Maintain responsive design patterns
4. Test on both light and dark themes

## Deployment

### Vercel (Recommended)

1. Push to GitHub
2. Import project in Vercel
3. Set environment variable: `NEXT_PUBLIC_API_URL`
4. Deploy

### Docker

Create a `Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

Build and run:

```bash
docker build -t care-beacon-web .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://your-api-url care-beacon-web
```

## License

Same as Care Beacon main project.

## Support

For issues or questions, please refer to the main Care Beacon project documentation.
