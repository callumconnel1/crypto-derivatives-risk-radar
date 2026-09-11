import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Crypto Derivatives Risk Radar",
    short_name: "CDRR",

    description:
      "Quantitative crypto derivatives stress monitoring across volatility, leverage, funding, liquidations, and venue concentration.",

    start_url: "/",
    display: "standalone",

    background_color: "#000000",
    theme_color: "#000000",

    icons: [
      {
        src: "/favicon.ico",
        sizes: "256x256",
        type: "image/x-icon",
      },
    ],
  };
}