import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, ExternalLink } from "lucide-react";
import {
  vptGetMarkers,
  vptToggleFavorite,
  vptGetStreetviewImageUrlFromMarker,
  type VPTMarker,
  type VPTFilters,
} from "@/services/vptApi";
import { useToast } from "@/hooks/use-toast";

export default function VPTMapView() {
  const [markers, setMarkers] = useState<VPTMarker[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<VPTFilters>({});
  const [selectedMarker, setSelectedMarker] = useState<VPTMarker | null>(null);
  const { toast } = useToast();

  const fetchMarkers = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await vptGetMarkers(filters);
      setMarkers(data);
      if (selectedMarker) {
        const refreshedSelection = data.find((marker) => marker.apn === selectedMarker.apn) || null;
        setSelectedMarker(refreshedSelection);
      }
    } catch {
      toast({
        title: "Error",
        description: "Failed to fetch map markers from Supabase.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [filters, selectedMarker, toast]);

  useEffect(() => {
    fetchMarkers();
  }, [fetchMarkers]);

  const updateFilter = (key: keyof VPTFilters, value: string | undefined) => {
    setFilters((prev) => ({ ...prev, [key]: value || undefined }));
  };

  const handleToggleFavorite = async (apn: string) => {
    try {
      const result = await vptToggleFavorite(apn);
      setMarkers((prev) =>
        prev.map((m) => (m.apn === apn ? { ...m, is_favorite: result.favorited } : m))
      );
      setSelectedMarker((prev) =>
        prev && prev.apn === apn ? { ...prev, is_favorite: result.favorited } : prev
      );
    } catch {
      toast({ title: "Error", description: "Failed to toggle favorite", variant: "destructive" });
    }
  };

  const getConditionColor = (score: number | null) => {
    if (score === null) return "bg-blue-100 text-blue-800";
    if (score <= 3) return "bg-green-100 text-green-800";
    if (score <= 6) return "bg-yellow-100 text-yellow-800";
    return "bg-red-100 text-red-800";
  };

  const selectedImageUrl = selectedMarker
    ? vptGetStreetviewImageUrlFromMarker({
        lat: selectedMarker.lat,
        lng: selectedMarker.lng,
        location: selectedMarker.location,
      })
    : "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center bg-muted/50 p-3 rounded-lg">
        <Input
          placeholder="Search..."
          className="w-36 bg-background"
          value={filters.q || ""}
          onChange={(e) => updateFilter("q", e.target.value)}
        />
        <Input
          placeholder="City"
          className="w-28 bg-background"
          value={filters.city || ""}
          onChange={(e) => updateFilter("city", e.target.value.toUpperCase())}
        />
        <Select
          value={filters.power || "all"}
          onValueChange={(v) => updateFilter("power", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="w-28 bg-background">
            <SelectValue placeholder="Power" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Power</SelectItem>
            <SelectItem value="on">ON</SelectItem>
            <SelectItem value="off">OFF</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Checkbox
            id="map-vpt"
            checked={filters.vpt === "1"}
            onCheckedChange={(checked) => updateFilter("vpt", checked ? "1" : undefined)}
          />
          <label htmlFor="map-vpt" className="text-sm">VPT Only</label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="map-fav"
            checked={filters.fav === "1"}
            onCheckedChange={(checked) => updateFilter("fav", checked ? "1" : undefined)}
          />
          <label htmlFor="map-fav" className="text-sm">Favorites</label>
        </div>
        <Button onClick={fetchMarkers} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
        <span className="text-sm text-muted-foreground ml-auto">
          {markers.length.toLocaleString()} properties
        </span>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="md:col-span-1 border rounded-lg">
          <div className="p-3 border-b bg-muted/50">
            <h3 className="font-medium">Properties</h3>
          </div>
          <div className="h-[500px] overflow-y-auto">
            {isLoading ? (
              <div className="p-3 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : markers.length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                No properties found
              </div>
            ) : (
              markers.map((marker) => (
                <button
                  key={marker.apn}
                  onClick={() => setSelectedMarker(marker)}
                  className={`w-full text-left p-3 border-b hover:bg-muted/50 transition-colors ${
                    selectedMarker?.apn === marker.apn ? "bg-muted" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">{marker.location}</span>
                    <Badge className={getConditionColor(marker.condition_score)}>
                      {marker.condition_score?.toFixed(1) || "?"}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {marker.city} • {marker.apn}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="md:col-span-2 border rounded-lg">
          {selectedMarker ? (
            <Card className="h-full border-0">
              <CardContent className="p-4 space-y-4">
                {selectedImageUrl && (
                  <img
                    src={selectedImageUrl}
                    alt="Street View"
                    className="w-full h-48 object-cover rounded-lg border"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                )}

                <div>
                  <h3 className="text-lg font-semibold">{selectedMarker.location}</h3>
                  <p className="text-sm text-muted-foreground">{selectedMarker.city}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">APN:</span>
                    <span className="ml-2 font-mono">{selectedMarker.apn}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">VPT:</span>
                    <span className={`ml-2 ${selectedMarker.has_vpt === "Yes" ? "text-red-600 font-medium" : ""}`}>
                      {selectedMarker.has_vpt}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Delinquent:</span>
                    <span className={`ml-2 ${selectedMarker.delinquent === "Yes" ? "text-red-600 font-medium" : ""}`}>
                      {selectedMarker.delinquent}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Power:</span>
                    <span className={`ml-2 ${
                      selectedMarker.power_status === "ON"
                        ? "text-green-600"
                        : selectedMarker.power_status === "OFF"
                          ? "text-red-600"
                          : ""
                    }`}>
                      {selectedMarker.power_status || "-"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Tax Year:</span>
                    <span className="ml-2">{selectedMarker.tax_year}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Last Payment:</span>
                    <span className="ml-2">{selectedMarker.last_payment || "None"}</span>
                  </div>
                </div>

                {selectedMarker.mailing_address && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Mailing:</span>
                    <span className="ml-2">{selectedMarker.mailing_address}</span>
                  </div>
                )}

                <div className="flex gap-2 pt-2 flex-wrap">
                  <Button
                    onClick={() => handleToggleFavorite(selectedMarker.apn)}
                    variant={selectedMarker.is_favorite ? "default" : "outline"}
                    size="sm"
                  >
                    {selectedMarker.is_favorite ? "★ Favorited" : "☆ Favorite"}
                  </Button>
                  {selectedMarker.maps_url && (
                    <Button asChild variant="outline" size="sm">
                      <a href={selectedMarker.maps_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4 mr-1" />
                        Google Maps
                      </a>
                    </Button>
                  )}
                  {selectedMarker.streetview_url && (
                    <Button asChild variant="outline" size="sm">
                      <a href={selectedMarker.streetview_url} target="_blank" rel="noopener noreferrer">
                        Street View
                      </a>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground p-6">
              <div className="text-center">
                <p className="text-lg">Select a property to view details</p>
                <p className="text-sm mt-2">Results are sourced directly from Supabase scanner tables.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
