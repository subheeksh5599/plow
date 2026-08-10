import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plow — policy-gated yield execution on KeeperHub",
  description:
    "Plow executes the write path: scan wallet positions, rank allowlisted venues by live DefiLlama APY, deposit through KeeperHub — policy-gated, sponsored, verified onchain, audited.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600&family=Source+Code+Pro:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
