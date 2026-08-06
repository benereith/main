import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Erlaubt externe Bildquellen (z.B. Fotograf-Galerie). Bei Bedarf ergänzen.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default nextConfig;
