import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" output is for the self-hosted Docker build (Dockerfile.frontend
  // copies .next/standalone/server.js). Vercel does its own serverless bundling
  // and this setting breaks its build (missing next-server.js.nft.json), so skip
  // it when building on Vercel (VERCEL=1 is set automatically during their build).
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
