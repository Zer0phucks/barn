import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { MapPin, Home, User, Mail, Phone, Send, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "@/hooks/use-toast";

const propertyReportSchema = z.object({
  address: z.string().trim().min(5, "Please enter a valid street address").max(200),
  city: z.string().trim().min(2, "Please enter a city").max(100),
  state: z.string().trim().length(2, "Please use 2-letter state code (e.g., CA)"),
  zip_code: z.string().trim().regex(/^\d{5}(-\d{4})?$/, "Please enter a valid ZIP code").optional().or(z.literal("")),
  description: z.string().trim().max(1000, "Description must be less than 1000 characters").optional(),
  reporter_name: z.string().trim().max(100).optional(),
  reporter_email: z.string().trim().email("Please enter a valid email").max(255).optional().or(z.literal("")),
  reporter_phone: z.string().trim().max(20).optional(),
});

type PropertyReportFormData = z.infer<typeof propertyReportSchema>;

interface PropertyReportFormProps {
  trigger?: React.ReactNode;
}

const PropertyReportForm = ({ trigger }: PropertyReportFormProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const form = useForm<PropertyReportFormData>({
    resolver: zodResolver(propertyReportSchema),
    defaultValues: {
      address: "",
      city: "Oakland",
      state: "CA",
      zip_code: "",
      description: "",
      reporter_name: "",
      reporter_email: "",
      reporter_phone: "",
    },
  });

  const onSubmit = async (data: PropertyReportFormData) => {
    setIsSubmitting(true);
    try {
      const { error } = await supabase.from("property_reports").insert({
        address: data.address,
        city: data.city,
        state: data.state,
        zip_code: data.zip_code || null,
        description: data.description || null,
        reporter_name: data.reporter_name || null,
        reporter_email: data.reporter_email || null,
        reporter_phone: data.reporter_phone || null,
      });

      if (error) throw error;

      setIsSuccess(true);
      toast({
        title: "Report Submitted",
        description: "Thank you for helping us identify properties in need of renewal.",
      });

      // Reset after showing success
      setTimeout(() => {
        setIsOpen(false);
        setIsSuccess(false);
        form.reset();
      }, 2000);
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error("Error submitting property report:", error);
      }
      toast({
        title: "Submission Failed",
        description: "There was an error submitting your report. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      setIsSuccess(false);
      form.reset();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="hero" size="lg">
            <Home className="w-5 h-5 mr-2" />
            Report a Property
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        {isSuccess ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <CheckCircle className="w-8 h-8 text-primary" />
            </div>
            <DialogTitle className="text-xl font-display mb-2">Report Submitted!</DialogTitle>
            <DialogDescription>
              Thank you for helping us identify properties in need of renewal. Our team will review your submission.
            </DialogDescription>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="font-display text-xl">Report an Abandoned Property</DialogTitle>
              <DialogDescription>
                Help us identify vacant or abandoned properties in the Bay Area that could be restored for housing.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 mt-4">
                {/* Property Address Section */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-primary" />
                    Property Location
                  </h3>
                  
                  <FormField
                    control={form.control}
                    name="address"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Street Address *</FormLabel>
                        <FormControl>
                          <Input placeholder="123 Main Street" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-3">
                    <FormField
                      control={form.control}
                      name="city"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>City *</FormLabel>
                          <FormControl>
                            <Input placeholder="Oakland" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <FormField
                        control={form.control}
                        name="state"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>State *</FormLabel>
                            <FormControl>
                              <Input placeholder="CA" maxLength={2} {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="zip_code"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>ZIP</FormLabel>
                            <FormControl>
                              <Input placeholder="94601" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                </div>

                {/* Description */}
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Property Description</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Describe the property condition, how long it appears abandoned, any safety concerns, etc."
                          className="resize-none"
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Reporter Contact Section */}
                <div className="space-y-3 pt-2">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <User className="w-4 h-4 text-primary" />
                    Your Contact Info (Optional)
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Provide your contact info if you'd like updates on this property.
                  </p>

                  <FormField
                    control={form.control}
                    name="reporter_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="flex items-center gap-1">
                          <User className="w-3 h-3" /> Name
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="Your name" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-3">
                    <FormField
                      control={form.control}
                      name="reporter_email"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="flex items-center gap-1">
                            <Mail className="w-3 h-3" /> Email
                          </FormLabel>
                          <FormControl>
                            <Input type="email" placeholder="email@example.com" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="reporter_phone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="flex items-center gap-1">
                            <Phone className="w-3 h-3" /> Phone
                          </FormLabel>
                          <FormControl>
                            <Input type="tel" placeholder="(510) 555-1234" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  variant="hero"
                  size="lg"
                  className="w-full mt-6"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    "Submitting..."
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-2" />
                      Submit Report
                    </>
                  )}
                </Button>
              </form>
            </Form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default PropertyReportForm;
