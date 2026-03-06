import { Heart, Users, Building, Sparkles } from "lucide-react";
import volunteersImage from "@/assets/volunteers-working.png";

const features = [
  {
    icon: Heart,
    label: "Family-Centered",
    description: "We prioritize the needs of families seeking stable housing",
  },
  {
    icon: Building,
    label: "Property Renewal",
    description: "Transforming abandoned homes into livable spaces",
  },
  {
    icon: Users,
    label: "Community Driven",
    description: "Volunteers and neighbors working together",
  },
  {
    icon: Sparkles,
    label: "Lasting Change",
    description: "Creating sustainable housing solutions",
  },
];

const Impact = () => {
  return (
    <section id="impact" className="section-padding bg-foreground text-primary-foreground relative overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-0 left-0 w-96 h-96 bg-primary rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-secondary rounded-full blur-3xl" />
      </div>

      <div className="container-wide relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Image */}
          <div className="relative">
            <div className="relative rounded-3xl overflow-hidden shadow-elevated">
              <img
                src={volunteersImage}
                alt="BARN volunteers cleaning up a neighborhood"
                className="w-full h-[500px] object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-foreground/60 to-transparent" />
            </div>
            
            {/* Floating Card */}
            <div className="absolute -bottom-6 -right-6 bg-card text-foreground rounded-2xl p-6 shadow-elevated max-w-xs">
              <p className="font-display text-2xl font-bold text-primary mb-2">Community First</p>
              <p className="text-muted-foreground text-sm">
                Every renovation brings neighbors together, building stronger communities.
              </p>
            </div>
          </div>

          {/* Content */}
          <div>
            <span className="text-golden font-medium text-sm uppercase tracking-wider">Our Approach</span>
            <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold mt-4 mb-6">
              Building a Better <span className="text-golden">Future Together</span>
            </h2>
            <p className="text-primary-foreground/80 text-lg mb-12 font-body">
              Bay Area Renewal Network connects abandoned properties with families 
              seeking stable housing, creating pathways to homeownership while 
              revitalizing neighborhoods.
            </p>

            <div className="grid sm:grid-cols-2 gap-8">
              {features.map((feature) => (
                <div key={feature.label} className="flex gap-4">
                  <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <feature.icon size={24} className="text-golden" />
                  </div>
                  <div>
                    <p className="font-medium text-primary-foreground/90">{feature.label}</p>
                    <p className="text-primary-foreground/60 text-sm mt-1">{feature.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Impact;
