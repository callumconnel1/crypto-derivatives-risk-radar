import type { NextConfig } from "next";

const rawApiTarget =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "";

const apiTarget = rawApiTarget.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!apiTarget) {
      console.warn(
        "[CDRR] API_INTERNAL_URL is not configured; /api requests will not be proxied.",
      );

      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
