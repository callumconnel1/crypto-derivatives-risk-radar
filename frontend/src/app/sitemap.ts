import type { MetadataRoute } from "next";

const siteUrl = "https://cdrr.duckdns.org";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${siteUrl}/`,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${siteUrl}/dashboard`,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/markets`,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/models`,
      changeFrequency: "weekly",
      priority: 0.7,
    },
    {
      url: `${siteUrl}/methodology`,
      changeFrequency: "weekly",
      priority: 0.7,
    },
  ];
}