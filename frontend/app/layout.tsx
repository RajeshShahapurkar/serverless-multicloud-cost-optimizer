import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Multi-Cloud Cost Optimizer",
  description: "Unified AWS, GCP and Azure cost visibility"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}