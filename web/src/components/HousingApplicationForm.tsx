import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Home, Loader2 } from "lucide-react";

const formSchema = z.object({
  applicant_name: z.string().min(2, "Name must be at least 2 characters").max(100),
  applicant_email: z.string().email("Please enter a valid email address").max(255),
  applicant_phone: z.string().max(20).optional(),
  family_size: z.coerce.number().min(1, "Family size must be at least 1").max(20),
  has_children: z.boolean().default(false),
  children_ages: z.string().max(200).optional(),
  current_situation: z.string().min(10, "Please describe your current situation").max(1000),
  employment_status: z.string().optional(),
  monthly_income: z.string().optional(),
  special_needs: z.string().max(500).optional(),
  preferred_location: z.string().max(200).optional(),
  maintenance_agreement: z.boolean().refine(val => val === true, {
    message: "You must agree to maintain the property",
  }),
  background_check_consent: z.boolean().refine(val => val === true, {
    message: "You must consent to a background check",
  }),
});

type FormData = z.infer<typeof formSchema>;

interface HousingApplicationFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const HousingApplicationForm = ({ open, onOpenChange }: HousingApplicationFormProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      applicant_name: "",
      applicant_email: "",
      applicant_phone: "",
      family_size: 1,
      has_children: false,
      children_ages: "",
      current_situation: "",
      employment_status: "",
      monthly_income: "",
      special_needs: "",
      preferred_location: "",
      maintenance_agreement: false,
      background_check_consent: false,
    },
  });

  const hasChildren = form.watch("has_children");

  const onSubmit = async (data: FormData) => {
    setIsSubmitting(true);

    try {
      const { error } = await supabase.from("housing_applications").insert({
        applicant_name: data.applicant_name,
        applicant_email: data.applicant_email,
        applicant_phone: data.applicant_phone || null,
        family_size: data.family_size,
        has_children: data.has_children,
        children_ages: data.has_children ? data.children_ages : null,
        current_situation: data.current_situation,
        employment_status: data.employment_status || null,
        monthly_income: data.monthly_income || null,
        special_needs: data.special_needs || null,
        preferred_location: data.preferred_location || null,
        maintenance_agreement: data.maintenance_agreement,
        background_check_consent: data.background_check_consent,
      });

      if (error) throw error;

      toast({
        title: "Application Submitted",
        description: "Thank you for applying. We will review your application and contact you soon.",
      });

      form.reset();
      onOpenChange(false);
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error("Error submitting application:", error);
      }
      toast({
        title: "Submission Error",
        description: "There was an error submitting your application. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-2xl">
            <Home className="h-6 w-6 text-primary" />
            Apply for Housing
          </DialogTitle>
          <DialogDescription>
            Complete this application to be considered for housing through Bay Area Renewal Network. 
            All information is kept confidential.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Personal Information */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Personal Information</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="applicant_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Full Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="Your full name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="applicant_email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address *</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="your@email.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="applicant_phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Phone Number</FormLabel>
                    <FormControl>
                      <Input type="tel" placeholder="(555) 123-4567" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Family Information */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Family Information</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="family_size"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Family Size *</FormLabel>
                      <FormControl>
                        <Input type="number" min={1} max={20} {...field} />
                      </FormControl>
                      <FormDescription>Total number of people in your household</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="has_children"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-start space-x-3 space-y-0 pt-6">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <div className="space-y-1 leading-none">
                        <FormLabel>Do you have children?</FormLabel>
                      </div>
                    </FormItem>
                  )}
                />
              </div>

              {hasChildren && (
                <FormField
                  control={form.control}
                  name="children_ages"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Ages of Children</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., 5, 8, 12" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            {/* Current Situation */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Current Situation</h3>
              
              <FormField
                control={form.control}
                name="current_situation"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Describe Your Current Housing Situation *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Please describe your current living situation and circumstances..."
                        className="min-h-[100px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="employment_status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Employment Status</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select status" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="employed_full">Employed Full-Time</SelectItem>
                          <SelectItem value="employed_part">Employed Part-Time</SelectItem>
                          <SelectItem value="self_employed">Self-Employed</SelectItem>
                          <SelectItem value="unemployed_seeking">Unemployed - Seeking Work</SelectItem>
                          <SelectItem value="unemployed_not_seeking">Unemployed - Not Seeking</SelectItem>
                          <SelectItem value="disabled">Disabled</SelectItem>
                          <SelectItem value="retired">Retired</SelectItem>
                          <SelectItem value="student">Student</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="monthly_income"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Monthly Household Income</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select range" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="0">No income</SelectItem>
                          <SelectItem value="1-500">$1 - $500</SelectItem>
                          <SelectItem value="501-1000">$501 - $1,000</SelectItem>
                          <SelectItem value="1001-2000">$1,001 - $2,000</SelectItem>
                          <SelectItem value="2001-3000">$2,001 - $3,000</SelectItem>
                          <SelectItem value="3001+">$3,001+</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>

            {/* Housing Needs */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Housing Needs</h3>
              
              <FormField
                control={form.control}
                name="special_needs"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Special Needs or Accommodations</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Accessibility requirements, medical needs, pet accommodations, etc."
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="preferred_location"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Preferred Location</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Oakland, East Bay, Near public transit" {...field} />
                    </FormControl>
                    <FormDescription>
                      We'll do our best to match you with properties in your preferred area
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Agreements */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Agreements</h3>
              
              <FormField
                control={form.control}
                name="maintenance_agreement"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 p-4 border rounded-lg bg-muted/50">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel className="font-medium">
                        Property Maintenance Agreement *
                      </FormLabel>
                      <FormDescription>
                        I agree to maintain the property in good condition, perform basic upkeep 
                        (lawn care, cleaning, minor repairs), and treat the home with respect. 
                        I understand this is a key requirement of the BARN program.
                      </FormDescription>
                      <FormMessage />
                    </div>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="background_check_consent"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 p-4 border rounded-lg bg-muted/50">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel className="font-medium">
                        Background Check Consent *
                      </FormLabel>
                      <FormDescription>
                        I consent to a background check as part of the application process. 
                        This helps ensure the safety of all participants in the program.
                      </FormDescription>
                      <FormMessage />
                    </div>
                  </FormItem>
                )}
              />
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  "Submit Application"
                )}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default HousingApplicationForm;
