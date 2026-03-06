import Header from "@/components/Header";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import Impact from "@/components/Impact";
import GetInvolved from "@/components/GetInvolved";
import Donate from "@/components/Donate";
import About from "@/components/About";
import Contact from "@/components/Contact";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <Impact />
        <GetInvolved />
        <Donate />
        <About />
        <Contact />
      </main>
      <Footer />
    </div>
  );
};

export default Index;
