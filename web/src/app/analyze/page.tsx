import type { Metadata } from "next";
import { Suspense } from "react";
import { AnalyzeProgress } from "@/components/AnalyzeProgress";

export const metadata: Metadata = { title: "Analysing" };

export default function AnalyzePage() {
  return (
    <Suspense fallback={null}>
      <AnalyzeProgress />
    </Suspense>
  );
}
