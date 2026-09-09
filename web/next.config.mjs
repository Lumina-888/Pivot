import { apiProxyRewrites } from "./lib/api/proxy.mjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return apiProxyRewrites(process.env.PIVOT_API_ORIGIN);
  },
};

export default nextConfig;
