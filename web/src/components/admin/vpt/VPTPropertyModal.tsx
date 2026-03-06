import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useState, useEffect } from "react";
import {
  vptGetConditionScore,
  vptGetResearchReport,
  vptGetStreetviewImageUrlFromMarker,
  type VPTMarker,
} from "@/services/vptApi";

interface VPTPropertyModalProps {
  property: VPTMarker;
  type: "condition" | "research";
  open: boolean;
  onClose: () => void;
}

export default function VPTPropertyModal({ property, type, open, onClose }: VPTPropertyModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [conditionData, setConditionData] = useState<{
    score: number;
    notes: string;
    updated_at: string;
  } | null>(null);
  const [researchReport, setResearchReport] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (!open) return;

    setIsLoading(true);
    setImageError(false);

    if (type === "condition") {
      vptGetConditionScore(property.apn)
        .then((data) => {
          setConditionData({
            score: data.score,
            notes: data.notes,
            updated_at: data.updated_at,
          });
        })
        .catch(() => setConditionData(null))
        .finally(() => setIsLoading(false));
    } else {
      vptGetResearchReport(property.apn)
        .then((data) => {
          setResearchReport(data.report);
        })
        .catch(() => setResearchReport(null))
        .finally(() => setIsLoading(false));
    }
  }, [open, type, property.apn]);

  const getConditionBadge = (score: number) => {
    if (score <= 3) {
      return <Badge className="bg-green-100 text-green-800">Good ({score.toFixed(1)}/10)</Badge>;
    }
    if (score <= 6) {
      return <Badge className="bg-yellow-100 text-yellow-800">Fair ({score.toFixed(1)}/10)</Badge>;
    }
    return <Badge className="bg-red-100 text-red-800">Poor ({score.toFixed(1)}/10)</Badge>;
  };

  const streetviewImageUrl = vptGetStreetviewImageUrlFromMarker({
    lat: property.lat,
    lng: property.lng,
    location: property.location,
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {type === "condition" ? "Property Condition" : "Research Report"}: {property.location || property.apn}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {!imageError && streetviewImageUrl && (
            <img
              src={streetviewImageUrl}
              alt="Street View"
              className="w-full h-48 object-cover rounded-lg border"
              onError={() => setImageError(true)}
            />
          )}

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">City:</span>{" "}
              <span className="font-medium">{property.city}</span>
            </div>
            <div>
              <span className="text-muted-foreground">APN:</span>{" "}
              <span className="font-mono">{property.apn}</span>
            </div>
            <div>
              <span className="text-muted-foreground">VPT:</span>{" "}
              <span className={property.has_vpt === "Yes" ? "text-red-600 font-medium" : ""}>
                {property.has_vpt}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Delinquent:</span>{" "}
              <span className={property.delinquent === "Yes" ? "text-red-600 font-medium" : ""}>
                {property.delinquent}
              </span>
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : type === "condition" ? (
            <div className="space-y-4">
              {conditionData ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Condition Score:</span>
                    {getConditionBadge(conditionData.score)}
                  </div>
                  <div>
                    <span className="text-muted-foreground text-sm">Last Updated:</span>
                    <span className="ml-2 text-sm">{conditionData.updated_at || "N/A"}</span>
                  </div>
                  {conditionData.notes && (
                    <div>
                      <span className="text-muted-foreground text-sm block mb-1">Notes:</span>
                      <p className="text-sm whitespace-pre-wrap bg-muted p-3 rounded">
                        {conditionData.notes}
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground">No condition data available yet.</p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {researchReport ? (
                <div className="bg-muted p-4 rounded max-h-96 overflow-y-auto">
                  <pre className="text-sm whitespace-pre-wrap font-sans">{researchReport}</pre>
                </div>
              ) : (
                <p className="text-muted-foreground">No research report available yet.</p>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
