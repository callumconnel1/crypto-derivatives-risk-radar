import type { NextConfig } from "next";

const rawApiTarget =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "";

const apiTarget = rawApiTarget.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  poweredByHeader: false,

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

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;