import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MoreHorizontal, Eye, Trash2, Mail, Phone, Users, DollarSign, MapPin } from "lucide-react";
import { format } from "date-fns";
import type { Tables } from "@/integrations/supabase/types";
import { useState } from "react";

type HousingApplication = Tables<"housing_applications">;

interface HousingApplicationsTableProps {
  applications: HousingApplication[];
  isLoading: boolean;
  onUpdateStatus: (id: string, status: string) => void;
  onDelete: (id: string) => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 hover:bg-amber-100",
  reviewing: "bg-blue-100 text-blue-800 hover:bg-blue-100",
  approved: "bg-green-100 text-green-800 hover:bg-green-100",
  rejected: "bg-red-100 text-red-800 hover:bg-red-100",
  waitlisted: "bg-purple-100 text-purple-800 hover:bg-purple-100",
};

const HousingApplicationsTable = ({
  applications,
  isLoading,
  onUpdateStatus,
  onDelete,
}: HousingApplicationsTableProps) => {
  const [selectedApplication, setSelectedApplication] = useState<HousingApplication | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading applications...</p>
      </div>
    );
  }

  if (applications.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground mb-2">No housing applications yet</p>
        <p className="text-sm text-muted-foreground">
          Family housing applications will appear here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Applicant</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Family Size</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Applied</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applications.map((application) => (
              <TableRow key={application.id}>
                <TableCell className="font-medium">{application.applicant_name}</TableCell>
                <TableCell>{application.applicant_email}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    {application.family_size}
                    {application.has_children && (
                      <Badge variant="outline" className="ml-1 text-xs">
                        w/ children
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge className={statusColors[application.status] || ""}>
                    {application.status.charAt(0).toUpperCase() + application.status.slice(1)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {format(new Date(application.created_at), "MMM d, yyyy")}
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuLabel>Actions</DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => setSelectedApplication(application)}>
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuLabel className="text-xs text-muted-foreground">
                        Update Status
                      </DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => onUpdateStatus(application.id, "pending")}>
                        Pending
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(application.id, "reviewing")}>
                        Reviewing
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(application.id, "approved")}>
                        Approved
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(application.id, "waitlisted")}>
                        Waitlisted
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(application.id, "rejected")}>
                        Rejected
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <DropdownMenuItem
                            onSelect={(e) => e.preventDefault()}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Application</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete this housing application? This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(application.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Application Details Dialog */}
      <Dialog open={!!selectedApplication} onOpenChange={() => setSelectedApplication(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Housing Application Details</DialogTitle>
            <DialogDescription>
              Application submitted {selectedApplication && format(new Date(selectedApplication.created_at), "MMMM d, yyyy")}
            </DialogDescription>
          </DialogHeader>
          {selectedApplication && (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-1">Applicant Name</h4>
                <p className="text-muted-foreground">{selectedApplication.applicant_name}</p>
              </div>
              
              <div className="flex gap-4">
                <div className="flex-1">
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <Mail className="h-4 w-4" /> Email
                  </h4>
                  <a href={`mailto:${selectedApplication.applicant_email}`} className="text-primary hover:underline">
                    {selectedApplication.applicant_email}
                  </a>
                </div>
                {selectedApplication.applicant_phone && (
                  <div className="flex-1">
                    <h4 className="font-medium mb-1 flex items-center gap-1">
                      <Phone className="h-4 w-4" /> Phone
                    </h4>
                    <a href={`tel:${selectedApplication.applicant_phone}`} className="text-primary hover:underline">
                      {selectedApplication.applicant_phone}
                    </a>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <Users className="h-4 w-4" /> Family Size
                  </h4>
                  <p className="text-muted-foreground">{selectedApplication.family_size} people</p>
                </div>
                <div>
                  <h4 className="font-medium mb-1">Children</h4>
                  <p className="text-muted-foreground">
                    {selectedApplication.has_children ? "Yes" : "No"}
                    {selectedApplication.children_ages && ` - Ages: ${selectedApplication.children_ages}`}
                  </p>
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-1">Current Living Situation</h4>
                <p className="text-muted-foreground whitespace-pre-wrap">{selectedApplication.current_situation}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <DollarSign className="h-4 w-4" /> Monthly Income
                  </h4>
                  <p className="text-muted-foreground">{selectedApplication.monthly_income || "Not provided"}</p>
                </div>
                <div>
                  <h4 className="font-medium mb-1">Employment Status</h4>
                  <p className="text-muted-foreground">{selectedApplication.employment_status || "Not provided"}</p>
                </div>
              </div>

              {selectedApplication.preferred_location && (
                <div>
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <MapPin className="h-4 w-4" /> Preferred Location
                  </h4>
                  <p className="text-muted-foreground">{selectedApplication.preferred_location}</p>
                </div>
              )}

              {selectedApplication.special_needs && (
                <div>
                  <h4 className="font-medium mb-1">Special Needs / Accommodations</h4>
                  <p className="text-muted-foreground whitespace-pre-wrap">{selectedApplication.special_needs}</p>
                </div>
              )}

              <div className="flex gap-4">
                <div>
                  <h4 className="font-medium mb-1">Maintenance Agreement</h4>
                  <Badge variant={selectedApplication.maintenance_agreement ? "default" : "secondary"}>
                    {selectedApplication.maintenance_agreement ? "Agreed" : "Not Agreed"}
                  </Badge>
                </div>
                <div>
                  <h4 className="font-medium mb-1">Background Check Consent</h4>
                  <Badge variant={selectedApplication.background_check_consent ? "default" : "secondary"}>
                    {selectedApplication.background_check_consent ? "Consented" : "Not Consented"}
                  </Badge>
                </div>
              </div>

              {selectedApplication.admin_notes && (
                <div>
                  <h4 className="font-medium mb-1">Admin Notes</h4>
                  <p className="text-muted-foreground text-sm whitespace-pre-wrap bg-muted p-2 rounded">
                    {selectedApplication.admin_notes}
                  </p>
                </div>
              )}

              <div>
                <h4 className="font-medium mb-1">Status</h4>
                <Badge className={statusColors[selectedApplication.status] || ""}>
                  {selectedApplication.status.charAt(0).toUpperCase() + selectedApplication.status.slice(1)}
                </Badge>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default HousingApplicationsTable;
