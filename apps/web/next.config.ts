import type { NextConfig } from "next";

const config: NextConfig = {
  // Allow streaming responses without buffering
  experimental: {
    proxyTimeout: 120_000,
  },
  output: "standalone",
};

export default config;
