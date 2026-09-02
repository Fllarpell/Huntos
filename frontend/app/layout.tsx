import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { IgnoreExtensionNoise } from "@/components/ignore-extension-noise";
import { AppFrame } from "@/components/app-frame";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: "Hunt — Job CRM",
  description: "Smart job-hunting CRM",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className={`${inter.variable} h-full dark`} suppressHydrationWarning>
      <body className="min-h-full bg-bg text-ink antialiased" suppressHydrationWarning>
        <IgnoreExtensionNoise />
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
