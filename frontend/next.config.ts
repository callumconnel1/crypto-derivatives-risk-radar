import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: [
    "192.168.0.138",
  ],
  reactCompiler: true,
};

export default nextConfig;
