import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDiscoveries, acknowledgeDiscoveries, type VPTDiscovery } from "@/services/vptApi";

const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
};

export default function DiscoveriesPanel() {
  const [discoveries, setDiscoveries] = useState<VPTDiscovery[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [acking, setAcking] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const result = await getDiscoveries();
      setDiscoveries(result.discoveries);
      setTotal(result.total);
    } catch {
      // silently fail — panel is supplementary
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAck = async (apn: string) => {
    setAcking((prev) => new Set(prev).add(apn));
    try {
      await acknowledgeDiscoveries([apn]);
      await load();
    } finally {
      setAcking((prev) => {
        const next = new Set(prev);
        next.delete(apn);
        return next;
      });
    }
  };

  if (!isLoading && total === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          New Discoveries
          {total > 0 && (
            <Badge className="bg-blue-100 text-blue-800">{total}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : discoveries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No new discoveries</p>
        ) : (
          <div className="divide-y">
            {discoveries.map((d) => (
              <div
                key={d.apn}
                className="flex flex-wrap items-center gap-3 py-2 text-sm"
                data-testid={`discovery-row-${d.apn}`}
              >
                <span className="font-mono text-xs text-muted-foreground w-28 shrink-0">
                  {d.apn}
                </span>
                <span className="flex-1 min-w-0 truncate" title={d.location_of_property || ""}>
                  {d.location_of_property || "—"}
                </span>
                <span className="w-24 shrink-0 text-muted-foreground">
                  {d.city || "—"}
                </span>
                <span className="w-24 shrink-0 text-muted-foreground">
                  {formatDate(d.first_seen_at)}
                </span>
                {d.has_vpt === 1 ? (
                  <Badge className="bg-red-100 text-red-800 shrink-0">VPT</Badge>
                ) : (
                  <span className="w-8 shrink-0" />
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  disabled={acking.has(d.apn)}
                  onClick={() => handleAck(d.apn)}
                  data-testid={`ack-btn-${d.apn}`}
                >
                  Ack
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
