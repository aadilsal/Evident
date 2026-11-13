import type { Metadata } from "next";
import { Suspense } from "react";
import { MapApp } from "@/components/map/MapApp";

export const metadata: Metadata = { title: "Map" };

export default function MapPage() {
  return (
    <Suspense fallback={<p className="p-xl text-on-surface-muted">Loading…</p>}>
      <MapApp />
    </Suspense>
  );
}
