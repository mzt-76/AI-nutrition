/**
 * Test Page for People Components (DYN-214)
 *
 * Displays all four people components with sample data for testing.
 */
import { ProfileCard } from '@/components/A2UI/People/ProfileCard';
import { CompanyCard } from '@/components/A2UI/People/CompanyCard';
import { QuoteCard } from '@/components/A2UI/People/QuoteCard';
import { ExpertTip } from '@/components/A2UI/People/ExpertTip';

export default function TestPeopleComponents() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">People Components Test - DYN-214</h1>
          <p className="text-muted-foreground">
            Testing ProfileCard, CompanyCard, QuoteCard, and ExpertTip components
          </p>
        </div>

        {/* ProfileCard Tests */}
        <section>
          <h2 className="text-2xl font-bold mb-4">ProfileCard Component</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">With Avatar & Social Links</h3>
              <ProfileCard
                name="Sarah Johnson"
                title="Senior Software Engineer"
                bio="Passionate about building scalable systems and mentoring developers. 10+ years experience in full-stack development."
                avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah"
                company="Tech Corp"
                location="San Francisco, CA"
                social_links={[
                  { platform: "Twitter", url: "https://twitter.com/sarah" },
                  { platform: "LinkedIn", url: "https://linkedin.com/in/sarah" },
                  { platform: "GitHub", url: "https://github.com/sarah" },
                  { platform: "Website", url: "https://sarahjohnson.dev" },
                ]}
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Without Avatar (Initials)</h3>
              <ProfileCard
                name="John Doe"
                title="Product Manager"
                bio="Building products that make a difference."
                company="Startup Inc"
                location="Austin, TX"
                social_links={[
                  { platform: "LinkedIn", url: "https://linkedin.com/in/john" },
                ]}
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Minimal (Name & Title Only)</h3>
              <ProfileCard
                name="Alice Smith"
                title="UX Designer"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Max Social Links (5)</h3>
              <ProfileCard
                name="Bob Wilson"
                title="DevOps Engineer"
                avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=Bob"
                social_links={[
                  { platform: "Twitter", url: "https://twitter.com/bob" },
                  { platform: "LinkedIn", url: "https://linkedin.com/in/bob" },
                  { platform: "GitHub", url: "https://github.com/bob" },
                  { platform: "YouTube", url: "https://youtube.com/@bob" },
                  { platform: "Blog", url: "https://bob.dev" },
                  { platform: "Extra", url: "https://example.com" }, // Should not display - max 5
                ]}
              />
            </div>
          </div>
        </section>

        {/* CompanyCard Tests */}
        <section>
          <h2 className="text-2xl font-bold mb-4">CompanyCard Component</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Full Details with Logo</h3>
              <CompanyCard
                name="TechVentures Inc."
                description="Leading innovation in AI and machine learning solutions for enterprise clients worldwide."
                industry="Technology"
                size="500-1000"
                logo_url="https://api.dicebear.com/7.x/identicon/svg?seed=TechVentures"
                founded={2015}
                location="Seattle, WA"
                url="https://techventures.example.com"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Without Logo (Text Fallback)</h3>
              <CompanyCard
                name="Innovate Labs"
                description="Research and development in quantum computing and advanced materials."
                industry="Research"
                size="50-100"
                founded="2020"
                location="Boston, MA"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Minimal Information</h3>
              <CompanyCard
                name="Startup Co"
                description="Early-stage startup building the next generation of productivity tools."
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Established Company</h3>
              <CompanyCard
                name="Global Enterprises"
                description="Fortune 500 company providing enterprise software solutions since 1985."
                industry="Enterprise Software"
                size="10,000+"
                logo_url="https://api.dicebear.com/7.x/identicon/svg?seed=Global"
                founded={1985}
                location="New York, NY"
                url="https://globalenterprises.example.com"
              />
            </div>
          </div>
        </section>

        {/* QuoteCard Tests */}
        <section>
          <h2 className="text-2xl font-bold mb-4">QuoteCard Component</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">With Avatar & Context</h3>
              <QuoteCard
                quote="The best way to predict the future is to invent it."
                author="Alan Kay"
                title="Computer Scientist"
                avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=Alan"
                context="From a keynote speech at Stanford University, 1971"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Without Avatar (Initial)</h3>
              <QuoteCard
                quote="Innovation distinguishes between a leader and a follower."
                author="Steve Jobs"
                title="Co-founder of Apple"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Long Quote</h3>
              <QuoteCard
                quote="Any sufficiently advanced technology is indistinguishable from magic. But when you're working on that technology, you realize it's just a bunch of if statements and for loops strung together."
                author="Arthur C. Clarke"
                title="Science Fiction Author"
                context="Adapted from Clarke's Third Law"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Minimal Quote</h3>
              <QuoteCard
                quote="Stay hungry, stay foolish."
                author="Steve Jobs"
              />
            </div>
          </div>
        </section>

        {/* ExpertTip Tests */}
        <section>
          <h2 className="text-2xl font-bold mb-4">ExpertTip Component</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Full Details with Custom Icon</h3>
              <ExpertTip
                title="Performance Optimization"
                tip="Always measure before optimizing. Use browser DevTools to identify actual bottlenecks rather than guessing what might be slow."
                expert="Jane Smith, Senior Performance Engineer"
                category="Web Performance"
                icon="⚡"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Default Icon (Lightbulb)</h3>
              <ExpertTip
                tip="Code reviews are not just about finding bugs - they're about sharing knowledge and improving team communication."
                expert="Michael Chen"
                category="Best Practices"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Custom Title</h3>
              <ExpertTip
                title="Security Pro Tip"
                tip="Never store sensitive data in localStorage. Use httpOnly cookies or secure session storage instead."
                expert="Sarah Security"
                icon="🔒"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Minimal Tip</h3>
              <ExpertTip
                tip="Write tests for your code before writing the implementation. It helps clarify requirements and catches edge cases early."
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Long Form Advice</h3>
              <ExpertTip
                title="Architecture Decision"
                tip="When choosing between microservices and monolith, consider your team size, deployment complexity, and operational maturity. Start simple and evolve as needed."
                expert="Alex Architect, Principal Engineer at Scale Corp"
                category="System Design"
                icon="🏗️"
              />
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Quick Tip</h3>
              <ExpertTip
                tip="Use semantic HTML. It improves accessibility and SEO."
                category="Accessibility"
              />
            </div>
          </div>
        </section>

        <div className="pt-8 border-t text-center text-muted-foreground">
          <p>All components support dark theme via Tailwind CSS</p>
        </div>
      </div>
    </div>
  );
}
