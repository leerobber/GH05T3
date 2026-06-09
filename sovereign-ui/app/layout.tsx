import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SOVEREIGN-PRIME — Mesh Podcast",
  description: "Live sovereign intelligence broadcast. Powered by GH05T3.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="scanlines bg-ghost-bg min-h-screen">
        {children}
      </body>
    </html>
  );
}
