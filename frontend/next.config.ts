import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for frontend/Dockerfile (node server.js). Dev is unaffected.
  output: "standalone",
  async rewrites() {
    // Production: nginx splits /api → backend, / → frontend. Do not bake
    // 127.0.0.1:8000 into the image (that is the container's own loopback).
    if (process.env.NODE_ENV === "production") {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
