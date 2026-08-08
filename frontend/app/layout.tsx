import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plow — Put idle capital to work, autonomously",
  description:
    "Plow is the agent that executes the write path: scan idle stablecoins, rank venues by live APY, deposit through KeeperHub — policy-gated, sponsored, verified.",
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
