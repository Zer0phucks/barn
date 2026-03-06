import { Target, Eye } from "lucide-react";

const About = () => {
  return (
    <section id="about" className="section-padding bg-gradient-warm">
      <div className="container-wide">
        <div className="grid lg:grid-cols-2 gap-16">
          {/* Mission */}
          <div className="bg-card rounded-3xl p-8 lg:p-12 shadow-soft">
            <div className="w-16 h-16 rounded-2xl bg-barn-red-light flex items-center justify-center mb-6">
              <Target size={32} className="text-barn-red" />
            </div>
            <h3 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-6">
              Our Mission
            </h3>
            <p className="text-muted-foreground text-lg font-body mb-6">
              Bay Area Renewal Network bridges the gap between vacant properties
              and families in need through our innovative Master Lease model. Property owners grant us
              the right to use their properties, and we place vetted caretakers who maintain the home
              in exchange for stable housing.
            </p>
            <p className="text-muted-foreground font-body">
              Our Caretaker License approach protects owners from tenant rights complications
              while giving families a path to stability. Everyone wins—neighborhoods are revitalized,
              properties stay maintained, and families get the foundation they need to thrive.
            </p>
          </div>

          {/* Vision */}
          <div className="bg-card rounded-3xl p-8 lg:p-12 shadow-soft">
            <div className="w-16 h-16 rounded-2xl bg-barn-green-light flex items-center justify-center mb-6">
              <Eye size={32} className="text-barn-green" />
            </div>
            <h3 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-6">
              Our Vision
            </h3>
            <p className="text-muted-foreground text-lg font-body mb-6">
              We envision a Bay Area where no property sits abandoned while families sleep
              on the streets. A region where communities come together to address housing insecurity
              through practical, collaborative action.
            </p>
            <div className="space-y-4">
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-barn-green flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-primary-foreground text-xs">✓</span>
                </div>
                <p className="text-muted-foreground font-body">Zero abandoned properties in Bay Area neighborhoods</p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-barn-green flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-primary-foreground text-xs">✓</span>
                </div>
                <p className="text-muted-foreground font-body">Every family has access to safe, stable housing</p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-barn-green flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-primary-foreground text-xs">✓</span>
                </div>
                <p className="text-muted-foreground font-body">Strong, connected communities that support one another</p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
};

export default About;
