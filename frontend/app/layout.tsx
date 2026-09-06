import type { ReactNode } from "react";
import type { Metadata } from "next";
import { JetBrains_Mono, Onest } from "next/font/google";
import "./globals.css";
import { IgnoreExtensionNoise } from "@/components/ignore-extension-noise";
import { AppFrame } from "@/components/app-frame";

const onest = Onest({
  variable: "--font-onest",
  subsets: ["latin", "cyrillic"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: "HuntOS",
  description: "Воронка поиска работы",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="ru" className={`${onest.variable} ${jetbrains.variable} h-full dark`} suppressHydrationWarning>
      <body className="min-h-full bg-bg text-ink antialiased" suppressHydrationWarning>
        <IgnoreExtensionNoise />
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
