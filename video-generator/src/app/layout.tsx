import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pabrik Video - Dashboard",
  description: "Automated Video Pipeline Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="bg-gray-950 text-white antialiased">{children}</body>
    </html>
  );
}
