import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Roast My Code - The AI That Roasts Your Codebase",
  description: "A brutally honest, funny AI-powered code quality roaster. Paste a GitHub URL and get roasted.",
  openGraph: {
    title: "Roast My Code",
    description: "The AI that roasts your codebase so your teammates don't have to.",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d1117",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
