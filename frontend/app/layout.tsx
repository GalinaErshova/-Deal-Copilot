import "./globals.css";
export const metadata = { title: "Deal Copilot", description: "AI tender analysis and pricing" };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="ru"><body>{children}</body></html>;
}
