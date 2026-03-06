import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import type { Tables } from "@/integrations/supabase/types";
import { MapPin, User, Mail, Phone, Calendar, FileText } from "lucide-react";

type PropertyReport = Tables<"property_reports">;

interface PropertyReportDetailsProps {
  report: PropertyReport | null;
  onClose: () => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  reviewing: "bg-blue-100 text-blue-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const PropertyReportDetails = ({ report, onClose }: PropertyReportDetailsProps) => {
  if (!report) return null;

  return (
    <Dialog open={!!report} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-primary" />
            Property Report Details
          </DialogTitle>
          <DialogDescription>
            Submitted on {format(new Date(report.created_at), "MMMM d, yyyy 'at' h:mm a")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Status */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Status:</span>
            <Badge className={statusColors[report.status] || ""}>
              {report.status.charAt(0).toUpperCase() + report.status.slice(1)}
            </Badge>
          </div>

          {/* Property Address */}
          <div className="space-y-2">
            <h4 className="font-semibold flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              Property Address
            </h4>
            <div className="bg-muted/50 p-3 rounded-lg">
              <p className="font-medium">{report.address}</p>
              <p className="text-sm text-muted-foreground">
                {report.city}, {report.state} {report.zip_code || ""}
              </p>
            </div>
          </div>

          {/* Description */}
          {report.description && (
            <div className="space-y-2">
              <h4 className="font-semibold flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                Description
              </h4>
              <p className="text-sm bg-muted/50 p-3 rounded-lg whitespace-pre-wrap">
                {report.description}
              </p>
            </div>
          )}

          {/* Reporter Information */}
          <div className="space-y-2">
            <h4 className="font-semibold flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              Reporter Information
            </h4>
            <div className="bg-muted/50 p-3 rounded-lg space-y-2">
              {report.reporter_name ? (
                <p className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span>{report.reporter_name}</span>
                </p>
              ) : (
                <p className="text-muted-foreground italic">Anonymous submission</p>
              )}
              {report.reporter_email && (
                <p className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <a 
                    href={`mailto:${report.reporter_email}`}
                    className="text-primary hover:underline"
                  >
                    {report.reporter_email}
                  </a>
                </p>
              )}
              {report.reporter_phone && (
                <p className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <a 
                    href={`tel:${report.reporter_phone}`}
                    className="text-primary hover:underline"
                  >
                    {report.reporter_phone}
                  </a>
                </p>
              )}
            </div>
          </div>

          {/* Timestamps */}
          <div className="space-y-2 text-sm text-muted-foreground border-t pt-4">
            <p className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Created: {format(new Date(report.created_at), "MMM d, yyyy 'at' h:mm a")}
            </p>
            <p className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Updated: {format(new Date(report.updated_at), "MMM d, yyyy 'at' h:mm a")}
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PropertyReportDetails;
