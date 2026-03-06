import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Heart, ExternalLink, Search, RefreshCw, FileText, MapPin, ChevronLeft, ChevronRight } from "lucide-react";
import {
  vptGetProperties,
  vptToggleFavorite,
  vptStartResearch,
  vptStartConditionScan,
  type VPTProperty,
  type VPTMarker,
  type VPTFilters,
} from "@/services/vptApi";
import { useToast } from "@/hooks/use-toast";
import VPTPropertyModal from "./VPTPropertyModal";

const toMarker = (property: VPTProperty): VPTMarker => ({
  lat: property.lat,
  lng: property.lng,
  apn: property.apn,
  parcel_number: property.parcel_number,
  tracer_number: property.tracer_number,
  location: property.location_of_property,
  tax_year: property.tax_year,
  last_payment: property.last_payment,
  delinquent: property.delinquent,
  power_status: property.power_status,
  has_vpt: property.has_vpt,
  vpt_marker: property.vpt_marker,
  city: property.city,
  is_favorite: property.is_favorite,
  mailing_address: property.mailing_address,
  situs_address: property.situs_address,
  bill_url: property.bill_url,
  maps_url: property.maps_url,
  streetview_url: property.streetview_url,
  condition_score: property.condition_score,
  property_search_url: property.property_search_url,
  mailing_search_url: property.mailing_search_url,
});

export default function VPTPropertiesTable() {
  const [properties, setProperties] = useState<VPTProperty[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<VPTFilters>({
    page: 1,
    page_size: 25,
    sort: "location_of_property",
    order: "asc",
  });
  const [selectedProperty, setSelectedProperty] = useState<VPTMarker | null>(null);
  const [modalType, setModalType] = useState<"condition" | "research" | null>(null);
  const { toast } = useToast();

  const page = Math.max(1, filters.page || 1);
  const pageSize = Math.max(10, filters.page_size || 25);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const fetchProperties = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await vptGetProperties(filters);
      setProperties(data.rows);
      setTotal(data.total);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch properties from Supabase.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [filters, toast]);

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  const handleToggleFavorite = async (apn: string) => {
    try {
      const result = await vptToggleFavorite(apn);
      setProperties((prev) =>
        prev.map((p) =>
          p.apn === apn ? { ...p, is_favorite: result.favorited } : p
        )
      );
    } catch {
      toast({
        title: "Error",
        description: "Failed to toggle favorite",
        variant: "destructive",
      });
    }
  };

  const handleStartResearch = async (apn: string) => {
    try {
      const result = await vptStartResearch([apn]);
      toast({
        title: "Research Updated",
        description: result.message,
      });
      fetchProperties();
    } catch {
      toast({
        title: "Error",
        description: "Failed to queue research",
        variant: "destructive",
      });
    }
  };

  const handleStartConditionScan = async (apn: string) => {
    try {
      const result = await vptStartConditionScan([apn]);
      toast({
        title: "Condition Scanner",
        description: result.message,
      });
    } catch {
      toast({
        title: "Error",
        description: "Failed to request condition scan",
        variant: "destructive",
      });
    }
  };

  const updateFilter = (key: keyof VPTFilters, value: string | undefined) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
      page: 1,
    }));
  };

  const setPage = (nextPage: number) => {
    setFilters((prev) => ({
      ...prev,
      page: Math.min(Math.max(1, nextPage), totalPages),
    }));
  };

  const getConditionBadge = (score: number | null) => {
    if (score === null) {
      return <Badge variant="secondary">Not Scanned</Badge>;
    }
    if (score <= 3) {
      return <Badge className="bg-green-100 text-green-800">{score.toFixed(1)}</Badge>;
    }
    if (score <= 6) {
      return <Badge className="bg-yellow-100 text-yellow-800">{score.toFixed(1)}</Badge>;
    }
    return <Badge className="bg-red-100 text-red-800">{score.toFixed(1)}</Badge>;
  };

  const getPowerBadge = (status: string) => {
    if (status === "ON") {
      return <Badge className="bg-green-100 text-green-800">ON</Badge>;
    }
    if (status === "OFF") {
      return <Badge className="bg-red-100 text-red-800">OFF</Badge>;
    }
    return <Badge variant="secondary">-</Badge>;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <Input
          placeholder="Search..."
          className="w-40"
          value={filters.q || ""}
          onChange={(e) => updateFilter("q", e.target.value)}
        />
        <Input
          placeholder="City"
          className="w-32"
          value={filters.city || ""}
          onChange={(e) => updateFilter("city", e.target.value.toUpperCase())}
        />
        <Input
          placeholder="Zip"
          className="w-24"
          value={filters.zip || ""}
          onChange={(e) => updateFilter("zip", e.target.value)}
        />
        <Select
          value={filters.power || "all"}
          onValueChange={(v) => updateFilter("power", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="w-28">
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
            id="vpt-filter"
            checked={filters.vpt === "1"}
            onCheckedChange={(checked) => updateFilter("vpt", checked ? "1" : undefined)}
          />
          <label htmlFor="vpt-filter" className="text-sm">VPT Only</label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="delinquent-filter"
            checked={filters.delinquent === "1"}
            onCheckedChange={(checked) => updateFilter("delinquent", checked ? "1" : undefined)}
          />
          <label htmlFor="delinquent-filter" className="text-sm">Delinquent</label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fav-filter"
            checked={filters.fav === "1"}
            onCheckedChange={(checked) => updateFilter("fav", checked ? "1" : undefined)}
          />
          <label htmlFor="fav-filter" className="text-sm">Favorites</label>
        </div>
        <Button onClick={fetchProperties} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
        <span className="text-sm text-muted-foreground ml-auto">
          {total.toLocaleString()} properties
        </span>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10"></TableHead>
              <TableHead>City</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>APN</TableHead>
              <TableHead>VPT</TableHead>
              <TableHead>Delinquent</TableHead>
              <TableHead>Power</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Links</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 10 }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : properties.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                  No properties found
                </TableCell>
              </TableRow>
            ) : (
              properties.map((property) => (
                <TableRow key={property.apn}>
                  <TableCell>
                    <button
                      onClick={() => handleToggleFavorite(property.apn)}
                      className={`p-1 rounded hover:bg-muted ${
                        property.is_favorite ? "text-red-500" : "text-muted-foreground"
                      }`}
                    >
                      <Heart
                        className="h-4 w-4"
                        fill={property.is_favorite ? "currentColor" : "none"}
                      />
                    </button>
                  </TableCell>
                  <TableCell className="font-medium">{property.city}</TableCell>
                  <TableCell
                    className="max-w-[200px] truncate"
                    title={property.location_of_property}
                  >
                    {property.location_of_property}
                  </TableCell>
                  <TableCell className="text-xs font-mono">{property.apn}</TableCell>
                  <TableCell>
                    {property.has_vpt === "Yes" ? (
                      <Badge className="bg-red-100 text-red-800">Yes</Badge>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {property.delinquent === "Yes" ? (
                      <Badge className="bg-red-100 text-red-800">Yes</Badge>
                    ) : (
                      <span className="text-muted-foreground">No</span>
                    )}
                  </TableCell>
                  <TableCell>{getPowerBadge(property.power_status)}</TableCell>
                  <TableCell>
                    <button
                      onClick={() => {
                        setSelectedProperty(toMarker(property));
                        setModalType("condition");
                      }}
                    >
                      {getConditionBadge(property.condition_score)}
                    </button>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {property.maps_url && (
                        <a
                          href={property.maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 hover:bg-muted rounded"
                          title="Google Maps"
                        >
                          <MapPin className="h-4 w-4" />
                        </a>
                      )}
                      {property.bill_url && (
                        <a
                          href={property.bill_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 hover:bg-muted rounded"
                          title="View Bill"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStartResearch(property.apn)}
                        title="Queue Research"
                      >
                        <Search className="h-4 w-4" />
                      </Button>
                      {property.condition_score === null && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleStartConditionScan(property.apn)}
                          title="Request Condition Scan"
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1 || isLoading}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages || isLoading}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>

      {selectedProperty && modalType && (
        <VPTPropertyModal
          property={selectedProperty}
          type={modalType}
          open={!!selectedProperty}
          onClose={() => {
            setSelectedProperty(null);
            setModalType(null);
          }}
        />
      )}
    </div>
  );
}
