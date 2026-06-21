import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // packages/ui and packages/tokens ship TS/CSS source, not pre-built JS —
  // Next needs to know to transpile them rather than treat them as external.
  transpilePackages: ["@irontrust/ui", "@irontrust/tokens", "@irontrust/api-client"],
};

export default nextConfig;
