import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Database, List, Map } from "lucide-react";
import VPTPropertiesTable from "./VPTPropertiesTable";
import VPTMapView from "./VPTMapView";
import { vptGetEnrichmentStatus, vptGetScanStatus } from "@/services/vptApi";

export function getAutopilotHeaderStatus({ reachable }: { reachable: boolean }) {
  if (reachable) {
    return { tone: "green", label: "Autopilot Online" } as const;
  }
  return { tone: "red", label: "Autopilot Offline" } as const;
}

export default function VPTDashboard() {
  const [reachable, setReachable] = useState(true);
  const [statusNote, setStatusNote] = useState("Scanner data source: Supabase");

  useEffect(() => {
    let active = true;

    const refreshStatus = async () => {
      try {
        const [scan, enrichment] = await Promise.all([
          vptGetScanStatus(),
          vptGetEnrichmentStatus(),
        ]);
        if (!active) return;

        setReachable(true);
        if (scan.is_running && scan.mode === "daily_intake") {
          setStatusNote(`Daily intake running${scan.current_apn ? ` on ${scan.current_apn}` : ""}`);
        } else if (enrichment.is_running) {
          setStatusNote(`Enrichment running${enrichment.current_apn ? ` on ${enrichment.current_apn}` : ""}`);
        } else {
          setStatusNote("Scanner data source: Supabase");
        }
      } catch {
        if (!active) return;
        setReachable(false);
        setStatusNote("Worker unreachable");
      }
    };

    refreshStatus();
    const interval = window.setInterval(refreshStatus, 15000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const autopilotStatus = getAutopilotHeaderStatus({ reachable });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                autopilotStatus.tone === "green" ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className={autopilotStatus.tone === "green" ? "text-green-700" : "text-red-700"}>
              {autopilotStatus.label}
            </span>
          </span>
          <span className="text-sm text-muted-foreground">
            {statusNote}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Database className="h-3.5 w-3.5" />
          Unified project mode
        </div>
      </div>

      <Tabs defaultValue="properties" className="space-y-4">
        <TabsList>
          <TabsTrigger value="properties" className="gap-2">
            <List className="h-4 w-4" />
            Properties
          </TabsTrigger>
          <TabsTrigger value="map" className="gap-2">
            <Map className="h-4 w-4" />
            Map View
          </TabsTrigger>
        </TabsList>

        <TabsContent value="properties">
          <VPTPropertiesTable />
        </TabsContent>

        <TabsContent value="map">
          <VPTMapView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
