/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  
  // 環境變量
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api-production-b782.up.railway.app',
    NEXT_PUBLIC_APP_NAME: 'IB Portfolio Monitor',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
  },
  
  // 圖片優化
  images: {
    domains: ['localhost'],
    unoptimized: true, // Vercel 部署時可能需要
  },
  
  // 實驗性功能
  experimental: {
    // appDir is now stable in Next.js 13+
  },
  
  // API 路由配置
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api-production-b782.up.railway.app';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  
  // CORS 和安全頭
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;