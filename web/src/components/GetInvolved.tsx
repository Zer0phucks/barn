import { useState } from "react";
import { Building, Users, Heart, ArrowRight, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import PropertyReportForm from "@/components/PropertyReportForm";
import VolunteerSignupForm from "@/components/VolunteerSignupForm";
import OwnerRegistrationForm from "@/components/OwnerRegistrationForm";
import HousingApplicationForm from "@/components/HousingApplicationForm";

const involvementCards = [
  {
    icon: Home,
    title: "Report a Property",
    description: "Know of an abandoned or neglected property in the Bay Area? Help us identify properties that could be restored to provide housing for families in need.",
    cta: "Report a Property",
    color: "bg-primary",
    action: "propertyReport",
    learnMoreLink: "/report-property",
  },
  {
    icon: Building,
    title: "Property Owners",
    description: "Our Master Lease model protects you from tenant complications. BARN handles maintenance while caretakers hold a revocable license—no eviction headaches.",
    cta: "Register Your Property",
    color: "bg-primary",
    action: "ownerRegister",
    learnMoreLink: "/register-property",
  },
  {
    icon: Users,
    title: "Volunteers",
    description: "Join our crew of dedicated volunteers. Whether you have construction skills or just a willing heart, there's a place for you on our team.",
    cta: "Become a Volunteer",
    color: "bg-secondary",
    action: "volunteer",
    learnMoreLink: "/volunteer",
  },
  {
    icon: Heart,
    title: "Become a Caretaker",
    description: "Need stable housing? Our Caretaker Program offers a home in exchange for property upkeep. Apply to join the program today.",
    cta: "Apply Now",
    color: "bg-accent",
    action: "housingApply",
    learnMoreLink: "/apply-housing",
  },
];

const GetInvolved = () => {
  const [volunteerOpen, setVolunteerOpen] = useState(false);
  const [ownerRegisterOpen, setOwnerRegisterOpen] = useState(false);
  const [housingApplyOpen, setHousingApplyOpen] = useState(false);

  const handleAction = (action: string) => {
    switch (action) {
      case "volunteer":
        setVolunteerOpen(true);
        break;
      case "ownerRegister":
        setOwnerRegisterOpen(true);
        break;
      case "housingApply":
        setHousingApplyOpen(true);
        break;
    }
  };

  return (
    <section id="get-involved" className="section-padding">
      <div className="container-wide">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-primary font-medium text-sm uppercase tracking-wider">Get Involved</span>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mt-4 mb-6">
            Be Part of the <span className="text-gradient">Solution</span>
          </h2>
          <p className="text-muted-foreground text-lg font-body">
            Everyone has a role to play in supporting those in need. Find out how you can contribute
            to our mission and make a lasting impact in the Bay Area.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {involvementCards.map((card) => (
            <div
              key={card.title}
              className="group bg-card rounded-3xl overflow-hidden shadow-soft hover:shadow-elevated transition-all duration-300"
            >
              {/* Header */}
              <div className={`${card.color} p-6`}>
                <div className="w-14 h-14 rounded-2xl bg-primary-foreground/20 backdrop-blur-sm flex items-center justify-center mb-4">
                  <card.icon size={28} className="text-primary-foreground" />
                </div>
                <h3 className="font-display text-xl font-bold text-primary-foreground">
                  {card.title}
                </h3>
              </div>

              {/* Content */}
              <div className="p-6">
                <p className="text-muted-foreground font-body text-sm mb-5">
                  {card.description}
                </p>
                <div className="space-y-3">
                  {card.action === "propertyReport" ? (
                    <PropertyReportForm
                      trigger={
                        <Button variant="outline" className="w-full group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                          {card.cta}
                          <ArrowRight size={18} className="ml-2" />
                        </Button>
                      }
                    />
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full group-hover:bg-primary group-hover:text-primary-foreground transition-colors"
                      onClick={() => handleAction(card.action)}
                    >
                      {card.cta}
                      <ArrowRight size={18} className="ml-2" />
                    </Button>
                  )}
                  <Link to={card.learnMoreLink} className="block">
                    <Button variant="ghost" className="w-full text-muted-foreground hover:text-foreground">
                      Learn More
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

      </div>

      <VolunteerSignupForm open={volunteerOpen} onOpenChange={setVolunteerOpen} />
      <OwnerRegistrationForm open={ownerRegisterOpen} onOpenChange={setOwnerRegisterOpen} />
      <HousingApplicationForm open={housingApplyOpen} onOpenChange={setHousingApplyOpen} />
    </section>
  );
};

export default GetInvolved;
