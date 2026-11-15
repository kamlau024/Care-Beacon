/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    // The nav label is "Statistics" but the page lives at /stats; catch people typing the label.
    return [{ source: "/statistics", destination: "/stats", permanent: true }]
  },
}

module.exports = nextConfig
