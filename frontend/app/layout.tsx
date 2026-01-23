import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bangkok Events - Discover Local Parties & Pop-ups",
  description: "Find rooftop parties, underground shows, pop-ups, and unique events in Bangkok that you won't find anywhere else.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-900 text-white min-h-screen">
        <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-900/95 backdrop-blur-sm border-b border-gray-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <a href="/" className="flex items-center space-x-2">
                <span className="text-2xl">🌃</span>
                <span className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
                  BKK Events
                </span>
              </a>
              <div className="flex items-center space-x-6">
                <a href="/" className="text-gray-300 hover:text-white transition-colors">
                  Discover
                </a>
                <a href="/map" className="text-gray-300 hover:text-white transition-colors">
                  Map
                </a>
                <a
                  href="/submit"
                  className="bg-primary-600 hover:bg-primary-700 px-4 py-2 rounded-lg font-medium transition-colors"
                >
                  Submit Event
                </a>
              </div>
            </div>
          </div>
        </nav>
        <main className="pt-16">
          {children}
        </main>
      </body>
    </html>
  );
}
