import Link from "next/link"
import {
  Activity,
  ArrowRight,
  BarChart3,
  MessageSquare,
  Search,
  SlidersHorizontal,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { SiteHeader } from "@/components/site-header"
import { getCitationNumberStyle, getSourceBadgeStyle } from "@/lib/source-colors"
import { cn } from "@/lib/utils"

export const GITHUB_URL = "https://github.com/kamlau024/Care-Beacon"

export const SOURCES = [
  {
    name: "BC Cancer",
    url: "https://www.bccancer.bc.ca/",
    blurb:
      "British Columbia’s provincial cancer agency: patient and family guides on diagnosis, treatment and managing side effects.",
  },
  {
    name: "Canadian Cancer Society",
    url: "https://cancer.ca/",
    blurb: "A national charity: plain-language information on cancer types, treatment, coping and support services.",
  },
  {
    name: "Cleveland Clinic",
    url: "https://my.clevelandclinic.org/",
    blurb: "A US academic medical centre: health library articles explaining conditions, tests and treatments.",
  },
] as const

const STEPS = [
  { title: "Ask in plain language", body: "Type your question the way you would ask a nurse or a friend." },
  {
    title: "We find the right passages",
    body: "Care Beacon searches its library of trusted pages for the paragraphs that best match your question.",
  },
  {
    title: "You get a cited answer",
    body: "Numbered citations sit next to each claim. Open one to read the original passage.",
  },
]

const FEATURES: { icon: LucideIcon; title: string; body: string; href?: string; cta?: string }[] = [
  {
    icon: MessageSquare,
    title: "Chat with follow-ups and History",
    body: "Ask a follow-up and it builds on what you already asked. Past conversations stay in History on this device.",
    href: "/chat",
    cta: "Open Chat",
  },
  {
    icon: Search,
    title: "Search with cited answers",
    body: "One question, one answer, with numbered citations that link to the exact source paragraph.",
    href: "/search",
    cta: "Open Search",
  },
  {
    icon: SlidersHorizontal,
    title: "Retrieval settings",
    body: "Choose which sources to draw from and how closely a passage must match before it is used.",
  },
  {
    icon: BarChart3,
    title: "Statistics",
    body: "See how big the library is, how many questions have been asked and what running Care Beacon costs.",
    href: "/stats",
    cta: "Open Statistics",
  },
]

const sourceLinkClass = "font-medium text-foreground underline underline-offset-[3px] hover:no-underline"

function CitationNumber({ n, source }: { n: number; source: string }) {
  return (
    <span className={cn(getCitationNumberStyle(source), "mx-0.5 align-[1px]")}>
      {n}
    </span>
  )
}

function SectionHeading({ title, intro }: { title: string; intro?: string }) {
  return (
    <div className="mb-8 space-y-2">
      <h2 className="text-2xl font-bold tracking-tight sm:text-[1.75rem]">{title}</h2>
      {intro && <p className="text-muted-foreground">{intro}</p>}
    </div>
  )
}

/** The page at "/": what Care Beacon is, its features and sources, how to start, and the disclaimer. */
export function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />

      <main className="container max-w-6xl mx-auto px-4 md:px-8 pt-4 pb-12">
        {/* Same line as on the app pages; scrolls away with the content. */}
        <p className="mb-6 text-center text-xs text-muted-foreground">
          ⚠️ For educational purposes only. Consult healthcare professionals for medical advice.
        </p>

        {/* Hero */}
        <section className="flex flex-wrap items-center gap-12 py-4 md:py-12">
          <div className="flex min-w-0 flex-[1_1_440px] flex-col gap-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border bg-muted">
              <Activity className="h-[26px] w-[26px]" aria-hidden="true" />
            </div>
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tight md:text-[3.5rem]">
              Cancer information you can trace to the source.
            </h1>
            <p className="max-w-xl text-lg text-muted-foreground">
              Care Beacon answers your questions using trusted patient-education pages from{" "}
              <a href={SOURCES[0].url} className={sourceLinkClass} target="_blank" rel="noopener noreferrer">
                BC Cancer
              </a>
              , the{" "}
              <a href={SOURCES[1].url} className={sourceLinkClass} target="_blank" rel="noopener noreferrer">
                Canadian Cancer Society
              </a>{" "}
              and{" "}
              <a href={SOURCES[2].url} className={sourceLinkClass} target="_blank" rel="noopener noreferrer">
                Cleveland Clinic
              </a>
              , and cites the passage behind every claim.
            </p>
            <div className="flex flex-col gap-3 pt-1 sm:flex-row">
              <Button asChild size="lg" className="h-11 px-5">
                <Link href="/chat">
                  Start a chat
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-11 px-5">
                <Link href="/search">Search the library</Link>
              </Button>
            </div>
          </div>

          {/* Illustrative answer: shows what a cited answer looks like. */}
          <figure
            aria-label="Example answer"
            className="flex min-w-0 flex-[1_1_380px] flex-col gap-4 rounded-xl border bg-card p-5 shadow-sm"
          >
            <figcaption className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Example answer
            </figcaption>
            <div className="max-w-[85%] self-end rounded-xl bg-muted px-3.5 py-2.5 text-sm">
              What are common side effects of chemotherapy?
            </div>
            <p className="text-sm leading-relaxed">
              Common side effects include tiredness, nausea and hair loss <CitationNumber n={1} source="BC Cancer" />.
              Many of these can be eased with help from your care team, so tell them early how you feel{" "}
              <CitationNumber n={2} source="Canadian Cancer Society" />.
            </p>
            <div className="flex flex-col gap-2 border-t pt-3 text-[13px] text-muted-foreground">
              {(["BC Cancer", "Canadian Cancer Society"] as const).map((source, i) => (
                <div key={source} className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">{i + 1}</span>
                  <span
                    className={cn(
                      "rounded-md border px-2 py-px text-xs font-medium",
                      getSourceBadgeStyle(source)
                    )}
                  >
                    {source}
                  </span>
                  <span>Patient-education page</span>
                </div>
              ))}
            </div>
          </figure>
        </section>

        {/* How it works */}
        <section className="border-t py-14">
          <SectionHeading title="How it works" intro="Every answer is built only from the passages it shows you." />
          <ol className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
            {STEPS.map((step, i) => (
              <li key={step.title} className="flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <h3 className="font-semibold">{step.title}</h3>
                </div>
                <p className="text-sm text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Features */}
        <section className="border-t py-14">
          <SectionHeading title="What you can do" />
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr))]">
            {FEATURES.map(({ icon: Icon, title, body, href, cta }) => (
              <div key={title} className="flex flex-col gap-2.5 rounded-xl border bg-card p-6">
                <Icon className="h-[22px] w-[22px]" aria-hidden="true" />
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="text-sm text-muted-foreground">{body}</p>
                {href && (
                  <Link href={href} className="mt-auto pt-1.5 text-sm font-medium underline-offset-4 hover:underline">
                    {cta} →
                  </Link>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Sources */}
        <section className="border-t py-14">
          <SectionHeading
            title="Where answers come from"
            intro="Care Beacon only answers from these three publishers' patient-education material. This collection is for educational purposes only and is not medical advice."
          />
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))]">
            {SOURCES.map((source) => (
              <div key={source.name} className="flex flex-col gap-2.5 rounded-xl border p-5">
                <span
                  className={cn(
                    "self-start rounded-md border px-2.5 py-0.5 text-[13px] font-semibold",
                    getSourceBadgeStyle(source.name)
                  )}
                >
                  {source.name}
                </span>
                <p className="text-sm text-muted-foreground">{source.blurb}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Get started */}
        <section className="flex flex-wrap items-start gap-10 border-t py-14">
          <div className="min-w-0 flex-[1_1_320px] space-y-2">
            <h2 className="text-2xl font-bold tracking-tight sm:text-[1.75rem]">Get started</h2>
            <p className="text-muted-foreground">No account needed. It takes about a minute.</p>
          </div>
          <ol className="flex min-w-0 flex-[2_1_480px] flex-col gap-3">
            {[
              <>
                Open <Link href="/chat" className="font-semibold underline-offset-4 hover:underline">Chat</Link> from
                the top of the page.
              </>,
              <>Type a question, for example “What are common side effects of chemotherapy?”</>,
              <>Tap a numbered citation to read the original passage.</>,
              <>
                Optional: open <strong>Retrieval settings</strong> to narrow the sources.
              </>,
            ].map((text, i) => (
              <li key={i} className="flex items-start gap-3.5 rounded-[10px] border px-4 py-3.5">
                <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-muted text-xs font-semibold">
                  {i + 1}
                </span>
                <span className="text-[15px]">{text}</span>
              </li>
            ))}
          </ol>
        </section>

        {/* Disclaimer */}
        <section aria-labelledby="disclaimer-heading" className="flex items-start gap-4 rounded-xl border bg-muted p-6">
          <TriangleAlert className="mt-0.5 h-[22px] w-[22px] flex-none" aria-hidden="true" />
          <div className="space-y-1.5">
            <h2 id="disclaimer-heading" className="font-semibold">
              For educational purposes only
            </h2>
            <p className="text-sm text-muted-foreground">
              Care Beacon shares general information from published patient-education material. It is not medical
              advice, cannot diagnose or treat any condition, and is not for emergencies. Talk to your doctor or care
              team about your own situation. In an emergency, call 911 or your local emergency number.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="container max-w-6xl mx-auto flex flex-wrap justify-between gap-2 px-4 py-5 text-[13px] text-muted-foreground md:px-8">
          <span>Care Beacon</span>
          <a href={GITHUB_URL} className="underline-offset-4 hover:underline" target="_blank" rel="noopener noreferrer">
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
