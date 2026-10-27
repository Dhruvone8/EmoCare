import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow local development hostnames/IPs for HMR
  allowedDevOrigins: ["localhost:3000", "127.0.0.1:3000", "172.16.248.224:3000", "10.216.185.45:3000"],
};

export default nextConfig;
