import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'RSHub - Georgian Tax Assistant',
  description: 'AI-powered tax consultation for Individual Entrepreneurs and small businesses in Georgia',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ka">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Georgian:wght@300;400;500;600&family=Noto+Sans:wght@300;400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
