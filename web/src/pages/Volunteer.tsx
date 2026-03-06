import { useState } from "react";
import { Users, Hammer, Heart, Clock, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import VolunteerSignupForm from "@/components/VolunteerSignupForm";

const roles = [
  {
    icon: Hammer,
    title: "Construction & Renovation",
    description: "Help with carpentry, painting, plumbing, electrical work, or general labor during property renovations.",
    skills: ["Carpentry", "Painting", "Plumbing", "Electrical", "General Labor"],
  },
  {
    icon: Heart,
    title: "Community Outreach",
    description: "Connect with community members, distribute information, and help identify families who could benefit from our program.",
    skills: ["Communication", "Networking", "Languages", "Social Work"],
  },
  {
    icon: Clock,
    title: "Administrative Support",
    description: "Assist with office tasks, data entry, scheduling, and coordination of volunteer activities.",
    skills: ["Organization", "Data Entry", "Scheduling", "Communication"],
  },
];

const expectations = [
  "Attend a brief orientation session before your first volunteer day",
  "Commit to at least 4 hours per month (flexible scheduling available)",
  "Follow all safety guidelines and instructions from team leaders",
  "Treat all community members, families, and fellow volunteers with respect",
  "Communicate in advance if you need to cancel or reschedule",
];

const Volunteer = () => {
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-20">
        {/* Hero Section */}
        <section className="section-padding bg-secondary text-primary-foreground">
          <div className="container-wide">
            <Link to="/#get-involved" className="inline-flex items-center gap-2 text-primary-foreground/80 hover:text-primary-foreground mb-6 transition-colors">
              <ArrowLeft size={18} />
              Back to Get Involved
            </Link>
            <div className="max-w-3xl">
              <div className="w-16 h-16 rounded-2xl bg-primary-foreground/20 flex items-center justify-center mb-6">
                <Users size={32} className="text-primary-foreground" />
              </div>
              <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Become a Volunteer
              </h1>
              <p className="text-lg md:text-xl text-primary-foreground/90 font-body">
                Join our crew of dedicated volunteers. Whether you have construction skills or just a willing heart, there's a place for you on our team.
              </p>
            </div>
          </div>
        </section>

        {/* Roles Section */}
        <section className="section-padding">
          <div className="container-wide">
            <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-12 text-center">
              Volunteer Opportunities
            </h2>
            <div className="grid md:grid-cols-3 gap-8 mb-16">
              {roles.map((role) => (
                <div key={role.title} className="bg-card rounded-2xl p-8 shadow-soft">
                  <div className="w-12 h-12 rounded-xl bg-secondary/10 flex items-center justify-center mb-4">
                    <role.icon size={24} className="text-secondary" />
                  </div>
                  <h3 className="font-display text-xl font-bold text-foreground mb-3">{role.title}</h3>
                  <p className="text-muted-foreground font-body mb-4">{role.description}</p>
                  <div className="flex flex-wrap gap-2">
                    {role.skills.map((skill) => (
                      <span key={skill} className="px-3 py-1 bg-muted rounded-full text-sm text-muted-foreground">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* What to Expect */}
            <div className="bg-muted rounded-3xl p-8 md:p-12 mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                What to Expect
              </h2>
              <div className="max-w-2xl mx-auto">
                <ul className="space-y-4">
                  {expectations.map((item, index) => (
                    <li key={index} className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-secondary text-primary-foreground font-bold text-sm flex items-center justify-center flex-shrink-0 mt-0.5">
                        ✓
                      </div>
                      <span className="text-muted-foreground font-body">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Benefits */}
            <div className="max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                Why Volunteer With Us?
              </h2>
              <div className="grid sm:grid-cols-2 gap-6">
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Make a Tangible Impact</h3>
                  <p className="text-muted-foreground font-body text-sm">See the direct results of your work as properties transform into homes.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Learn New Skills</h3>
                  <p className="text-muted-foreground font-body text-sm">Gain hands-on experience in construction, community organizing, and more.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Build Community</h3>
                  <p className="text-muted-foreground font-body text-sm">Connect with like-minded people who care about housing justice.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Flexible Scheduling</h3>
                  <p className="text-muted-foreground font-body text-sm">We offer weekday and weekend opportunities to fit your availability.</p>
                </div>
              </div>
            </div>

            {/* Form Section */}
            <div className="max-w-2xl mx-auto text-center">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-4">
                Ready to Join Our Team?
              </h2>
              <p className="text-muted-foreground font-body mb-8">
                Fill out our volunteer application and we'll reach out with upcoming opportunities that match your skills and availability.
              </p>
              <Button variant="hero" size="xl" onClick={() => setFormOpen(true)}>
                Sign Up to Volunteer
              </Button>
            </div>
          </div>
        </section>
      </main>
      <Footer />
      <VolunteerSignupForm open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
};

export default Volunteer;
