import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        source: "/output/:path*",
        destination: "http://localhost:8000/output/:path*",
      },
    ];
  },
};

export default nextConfig;
