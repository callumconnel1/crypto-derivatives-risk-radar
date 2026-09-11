import type { Metadata } from "next";
import "./globals.css";

const siteUrl = "https://cdrr.duckdns.org";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),

  title: {
    default: "Crypto Derivatives Risk Radar",
    template: "%s | CDRR",
  },

  description:
    "Quantitative crypto derivatives stress monitoring across volatility, leverage, funding, liquidations, and venue concentration.",

  applicationName: "Crypto Derivatives Risk Radar",

  keywords: [
    "crypto",
    "cryptocurrency",
    "derivatives",
    "risk",
    "systematic risk",
    "market stress",
    "volatility",
    "open interest",
    "funding",
    "liquidations",
    "venue concentration",
    "CoinMarketCap",
    "CDRR",
  ],

  alternates: {
    canonical: "/",
  },

  openGraph: {
    type: "website",
    locale: "en_GB",
    url: siteUrl,
    siteName: "Crypto Derivatives Risk Radar",
    title: "Crypto Derivatives Risk Radar",
    description:
      "Quantitative crypto derivatives stress monitoring across volatility, leverage, funding, liquidations, and venue concentration.",
  },

  twitter: {
    card: "summary",
    title: "Crypto Derivatives Risk Radar",
    description:
      "Quantitative crypto derivatives stress monitoring across volatility, leverage, funding, liquidations, and venue concentration.",
  },

  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
  },

  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },

  category: "finance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}