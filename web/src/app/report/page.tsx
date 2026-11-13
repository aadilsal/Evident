import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportView } from "@/components/ReportView";

export const metadata: Metadata = { title: "Architecture report" };

export default function ReportPage() {
  return (
    <Suspense fallback={null}>
      <ReportView />
    </Suspense>
  );
}
