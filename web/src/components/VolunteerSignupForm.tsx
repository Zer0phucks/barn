import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle, Users } from "lucide-react";

const volunteerSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters").max(100, "Name must be less than 100 characters"),
  email: z.string().trim().email("Please enter a valid email").max(255, "Email must be less than 255 characters"),
  phone: z.string().trim().max(20, "Phone must be less than 20 characters").optional().or(z.literal("")),
  skills: z.array(z.string()).min(1, "Please select at least one skill"),
  availability: z.array(z.string()).min(1, "Please select at least one availability option"),
  notes: z.string().trim().max(500, "Notes must be less than 500 characters").optional(),
});

type VolunteerFormData = z.infer<typeof volunteerSchema>;

const SKILLS_OPTIONS = [
  { id: "construction", label: "Construction/Renovation" },
  { id: "painting", label: "Painting" },
  { id: "landscaping", label: "Landscaping" },
  { id: "plumbing", label: "Plumbing" },
  { id: "electrical", label: "Electrical" },
  { id: "cleaning", label: "Cleaning" },
  { id: "admin", label: "Administrative" },
  { id: "fundraising", label: "Fundraising" },
  { id: "outreach", label: "Community Outreach" },
  { id: "other", label: "Other" },
];

const AVAILABILITY_OPTIONS = [
  { id: "weekday-morning", label: "Weekday Mornings" },
  { id: "weekday-afternoon", label: "Weekday Afternoons" },
  { id: "weekday-evening", label: "Weekday Evenings" },
  { id: "weekend-morning", label: "Weekend Mornings" },
  { id: "weekend-afternoon", label: "Weekend Afternoons" },
  { id: "flexible", label: "Flexible Schedule" },
];

interface VolunteerSignupFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const VolunteerSignupForm = ({ open, onOpenChange }: VolunteerSignupFormProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const { toast } = useToast();

  const form = useForm<VolunteerFormData>({
    resolver: zodResolver(volunteerSchema),
    defaultValues: {
      name: "",
      email: "",
      phone: "",
      skills: [],
      availability: [],
      notes: "",
    },
  });

  const onSubmit = async (data: VolunteerFormData) => {
    setIsSubmitting(true);

    try {
      const { error } = await supabase.from("volunteers").insert({
        name: data.name,
        email: data.email,
        phone: data.phone || null,
        skills: data.skills,
        availability: data.availability,
        notes: data.notes || null,
      });

      if (error) throw error;

      setIsSuccess(true);
      form.reset();
    } catch (error) {
      toast({
        title: "Submission Failed",
        description: "There was an error submitting your application. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    onOpenChange(false);
    setTimeout(() => {
      setIsSuccess(false);
      form.reset();
    }, 300);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        {isSuccess ? (
          <div className="py-8 text-center">
            <div className="mx-auto w-16 h-16 bg-secondary/20 rounded-full flex items-center justify-center mb-4">
              <CheckCircle className="h-8 w-8 text-secondary" />
            </div>
            <DialogHeader>
              <DialogTitle className="text-2xl">Thank You!</DialogTitle>
              <DialogDescription className="text-base mt-2">
                Your volunteer application has been submitted. We'll be in touch soon to discuss 
                how you can help transform lives in our community.
              </DialogDescription>
            </DialogHeader>
            <Button onClick={handleClose} className="mt-6">
              Close
            </Button>
          </div>
        ) : (
          <>
            <DialogHeader>
              <div className="mx-auto w-12 h-12 bg-secondary/20 rounded-full flex items-center justify-center mb-2">
                <Users className="h-6 w-6 text-secondary" />
              </div>
              <DialogTitle className="text-center text-2xl">Volunteer With Us</DialogTitle>
              <DialogDescription className="text-center">
                Join our team of dedicated volunteers making a difference in the Bay Area.
              </DialogDescription>
            </DialogHeader>

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 mt-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Full Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="John Smith" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email *</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="john@example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone (Optional)</FormLabel>
                      <FormControl>
                        <Input type="tel" placeholder="(555) 123-4567" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="skills"
                  render={() => (
                    <FormItem>
                      <FormLabel>Skills & Interests *</FormLabel>
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {SKILLS_OPTIONS.map((skill) => (
                          <FormField
                            key={skill.id}
                            control={form.control}
                            name="skills"
                            render={({ field }) => (
                              <FormItem className="flex items-center space-x-2 space-y-0">
                                <FormControl>
                                  <Checkbox
                                    checked={field.value?.includes(skill.id)}
                                    onCheckedChange={(checked) => {
                                      const updated = checked
                                        ? [...field.value, skill.id]
                                        : field.value.filter((v) => v !== skill.id);
                                      field.onChange(updated);
                                    }}
                                  />
                                </FormControl>
                                <FormLabel className="text-sm font-normal cursor-pointer">
                                  {skill.label}
                                </FormLabel>
                              </FormItem>
                            )}
                          />
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="availability"
                  render={() => (
                    <FormItem>
                      <FormLabel>Availability *</FormLabel>
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {AVAILABILITY_OPTIONS.map((option) => (
                          <FormField
                            key={option.id}
                            control={form.control}
                            name="availability"
                            render={({ field }) => (
                              <FormItem className="flex items-center space-x-2 space-y-0">
                                <FormControl>
                                  <Checkbox
                                    checked={field.value?.includes(option.id)}
                                    onCheckedChange={(checked) => {
                                      const updated = checked
                                        ? [...field.value, option.id]
                                        : field.value.filter((v) => v !== option.id);
                                      field.onChange(updated);
                                    }}
                                  />
                                </FormControl>
                                <FormLabel className="text-sm font-normal cursor-pointer">
                                  {option.label}
                                </FormLabel>
                              </FormItem>
                            )}
                          />
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Additional Notes (Optional)</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Tell us about your experience or any questions you have..."
                          className="resize-none"
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                  {isSubmitting ? "Submitting..." : "Submit Application"}
                </Button>
              </form>
            </Form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default VolunteerSignupForm;
