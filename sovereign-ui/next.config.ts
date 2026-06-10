import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["three"],
  experimental: {
    // needed for @react-three/fiber server component boundary
    esmExternals: "loose",
  },
};

export default nextConfig;
