import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Crypto Derivatives Risk Radar",
    template: "%s | CDRR",
  },
  description:
    "Quantitative crypto derivatives stress monitoring across volatility, leverage, funding, liquidations, and venue concentration.",
  applicationName: "Crypto Derivatives Risk Radar",
  keywords: [
    "crypto",
    "derivatives",
    "risk",
    "volatility",
    "open interest",
    "funding",
    "liquidations",
    "CoinMarketCap",
  ],
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
