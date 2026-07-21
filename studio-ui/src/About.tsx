import { BlurFade } from '@/components/magicui/blur-fade'
import { KineticGrid } from '@/components/magicui/kinetic-grid'
import { NumberTicker } from '@/components/magicui/number-ticker'
import { BorderBeam } from '@/components/magicui/border-beam'
import { BehaviorRadar } from '@/components/BehaviorRadar'

const GRAPH = 'http://127.0.0.1:7787/FULL_3plane_clean.html'

function Section({ children, className = '' }: any) {
  return <section className={`border-t border-white/[0.06] py-24 ${className}`}>
    <div className="mx-auto max-w-[880px] px-8">{children}</div></section>
}
function Eyebrow({ children }: any) {
  return <div className="text-[11.5px] uppercase tracking-[0.18em] text-white/40 font-medium mb-4">{children}</div>
}
function H3({ children }: any) {
  return <h3 className="text-[32px] leading-[1.2] tracking-[-0.02em] text-white font-semibold mb-6">{children}</h3>
}
function P({ children, className = '' }: any) {
  return <p className={`text-[17px] leading-[1.75] text-white/55 mb-5 ${className}`}>{children}</p>
}

const PROBLEMS = [
  ['P1', 'Blindness', 'Scanned pages carry no text layer. The retriever never sees them, so the fact does not exist as far as the system is concerned.'],
  ['P2', 'Omission', "The answer isn't in the corpus at all. Rather than say so, the model composes one from adjacent context."],
  ['P3', 'Silent arbitration', 'Two documents disagree. The model picks one, presents it as fact, and never mentions the conflict existed.'],
  ['P4', 'Ambiguity collapse', 'The question had two readings. The model answers one and behaves as if the other was never possible.'],
]
const STEPS = [
  ['01', 'Ingest', 'Mixed PDFs, scans and code-in-PDF normalized to Markdown. Pages without a text layer escalate through an OCR ladder.', false],
  ['02', 'Retrieve', 'Three signals scored in parallel — dense vectors, BM25 keywords, exact entity matches — fused and reranked.', false],
  ['03', 'Assess', 'Sufficiency, fact extraction with validity windows, contradiction detection, then an answerability verdict.', true],
  ['04', 'Respond', 'Answer with citations and a confidence band — or refuse, clarify, or present both sides.', false],
]
const VERDICTS = [
  ['Answer', 'Context is sufficient and consistent. Generate with chunk-level citations.', 'text-[#39d2c0]', 'bg-[#39d2c0]/[0.07] border-[#39d2c0]/25'],
  ['Dual-answer', 'Sources conflict. Present both values with provenance rather than choosing.', 'text-[#bc8cff]', 'bg-[#bc8cff]/[0.07] border-[#bc8cff]/25'],
  ['Clarify', 'The question is ambiguous. Offer the readings, then re-run with the choice.', 'text-[#e3b341]', 'bg-[#e3b341]/[0.07] border-[#e3b341]/25'],
  ['Refuse', 'The corpus cannot support an answer. Decline and report what is missing.', 'text-[#ff6b6b]', 'bg-[#ff6b6b]/[0.07] border-[#ff6b6b]/25'],
]
const BENCH: [string, number, boolean][] = [
  ['TruthGuard', 0.657, true], ['graphify', 0.497, false], ['hybrid RRF', 0.493, false],
  ['dense RAG', 0.439, false], ['BM25', 0.362, false], ['mem0', 0.048, false],
]
const PLANES = [
  ['y+  KNOWLEDGE', 'Documents', 'Provenance-tagged chunks, extracted entities, and community summaries with a compiled truth per topic.', '#39d2c0'],
  ['x  SPINE', 'Conversation', 'Turns stored as decision memory with confidence, decay, and supersession. Each session its own thread.', '#bc8cff'],
  ['y−  CODE', 'Codebase', 'Call and import structure alongside real function bodies, across twenty-plus languages.', '#ff8c66'],
]
const STACK = ['DecisionGraph', 'turbovec', 'BM25', 'Entity matching', 'GitNexus', 'Tesseract + Mistral OCR', 'Louvain', 'MCP']

function Shot({ label, caption }: { label: string; caption: string }) {
  return (
    <BlurFade delay={0.1}>
      <figure className="my-10 rounded-2xl border border-white/[0.08] overflow-hidden bg-white/[0.02]">
        <div className="h-[300px] grid place-items-center text-white/20 text-[13px] tracking-wide"
          style={{ background: 'repeating-linear-gradient(45deg,#0a0d14,#0a0d14 12px,#0c0f18 12px,#0c0f18 24px)' }}>
          {label}
        </div>
        <figcaption className="px-5 py-3.5 text-[13px] text-white/45 border-t border-white/[0.06]">{caption}</figcaption>
      </figure>
    </BlurFade>
  )
}

export default function About() {
  return (
    <div className="min-h-full bg-[#06080e] text-white/85 overflow-y-auto h-full relative">
      {/* full-page interactive grid background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <KineticGrid dotColor="#7f93b3" lineColor="#39d2c0" trailColor="#bc8cff"
          spacing={34} radius={260} strength={4} />
      </div>
      <div className="relative z-10">
      {/* nav */}
      <nav className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#06080e]/85 backdrop-blur-xl">
        <div className="mx-auto max-w-[1120px] px-8 h-[60px] flex items-center gap-3">
          <div className="w-6 h-6 rounded-md relative"
            style={{ background: 'conic-gradient(from 210deg,#39d2c0,#bc8cff,#ff8c66,#39d2c0)' }}>
            <div className="absolute inset-[5px] rounded-[3px] bg-[#06080e]" />
          </div>
          <b className="text-[15px] text-white font-semibold">TruthGuard</b>
          <div className="ml-auto flex gap-7 text-[13.5px] text-white/45">
            <a href="#problem" className="hover:text-white transition">Problem</a>
            <a href="#how" className="hover:text-white transition">How it works</a>
            <a href="#results" className="hover:text-white transition">Results</a>
            <a href="/" className="hover:text-white transition">Studio →</a>
          </div>
        </div>
      </nav>

      {/* hero */}
      <div className="relative overflow-hidden">
        <div className="relative mx-auto max-w-[880px] px-8 pt-28 pb-16">
          <BlurFade inView={false}>
            <div className="text-[11.5px] uppercase tracking-[0.18em] text-[#39d2c0] font-medium mb-6">Introducing TruthGuard</div>
          </BlurFade>
          <BlurFade inView={false} delay={0.08}>
            <h1 className="text-[54px] leading-[1.08] tracking-[-0.035em] text-white font-semibold mb-7">
              RAG that knows<br />when it doesn't know
            </h1>
          </BlurFade>
          <BlurFade inView={false} delay={0.16}>
            <p className="text-[19px] leading-[1.7] text-white/55 max-w-[700px]">
              Standard retrieval-augmented generation answers every question with equal confidence — including
              the ones it should refuse. TruthGuard places an <span className="text-white/90">assessment gate
              between retrieval and generation</span>: the generator is never invoked until the retrieved
              context has been checked for sufficiency, contradiction, and ambiguity.
            </p>
          </BlurFade>
          <BlurFade inView={false} delay={0.24}>
            <div className="flex gap-3 mt-9">
              <a href="/" className="bg-white text-[#06080e] font-medium px-5 py-2.5 rounded-lg text-[14.5px] hover:bg-white/90 transition">Open Studio</a>
              <a href="/architecture.html" className="border border-white/15 text-white/80 px-5 py-2.5 rounded-lg text-[14.5px] hover:bg-white/[0.04] transition">Read the architecture</a>
            </div>
          </BlurFade>
        </div>
      </div>

      {/* problem */}
      <Section className="mt-14">
        <div id="problem" />
        <BlurFade><Eyebrow>The problem</Eyebrow><H3>Four ways retrieval quietly lies</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          RAG failures are rarely loud. The answer looks confident, cites a source, and reads well — but the
          source was missing, contradicted, unreadable, or answering a different question than the one asked.
        </P></BlurFade>
        <div className="grid sm:grid-cols-2 gap-3 mt-8">
          {PROBLEMS.map(([n, t, d], i) => (
            <BlurFade key={n} delay={0.06 + i * 0.06}>
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5 h-full hover:border-white/[0.14] transition">
                <div className="text-[11px] font-semibold tracking-[0.12em] text-[#ff6b6b]">{n}</div>
                <div className="text-[15.5px] text-white font-medium mt-2 mb-1.5">{t}</div>
                <div className="text-[13.5px] leading-[1.6] text-white/45">{d}</div>
              </div>
            </BlurFade>
          ))}
        </div>
        <BlurFade delay={0.1}>
          <div className="mt-8 border-l border-[#39d2c0]/50 pl-5 py-1 text-[15px] text-white/60">
            <span className="text-white/90">The design consequence:</span> these are not prompt problems.
            Asking a model to "be careful" does not fix a missing text layer or a contradiction between two PDFs.
            They must be caught structurally, before generation.
          </div>
        </BlurFade>
      </Section>

      {/* how */}
      <Section>
        <div id="how" />
        <BlurFade><Eyebrow>How it works</Eyebrow><H3>The generator fires last, not first</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          Retrieval produces candidate context. The assessment gate then runs four checks, cheapest first, and
          decides what kind of response is even permissible. Only a clean pass reaches the generator.
        </P></BlurFade>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-8">
          {STEPS.map(([n, t, d, gate], i) => (
            <BlurFade key={n as string} delay={0.06 + i * 0.07}>
              <div className={`rounded-xl border p-4 h-full transition ${gate
                ? 'border-[#e3b341]/30 bg-[#e3b341]/[0.05]' : 'border-white/[0.08] bg-white/[0.02] hover:border-white/[0.14]'}`}>
                <div className="text-[10.5px] font-semibold tracking-[0.12em] text-white/30">{n}</div>
                <div className={`text-[14.5px] font-medium mt-1.5 mb-1.5 ${gate ? 'text-[#e3b341]' : 'text-white'}`}>{t}</div>
                <div className="text-[12.5px] leading-[1.55] text-white/45">{d}</div>
              </div>
            </BlurFade>
          ))}
        </div>

        <BlurFade delay={0.1}><h4 className="text-[18px] text-white font-medium mt-12 mb-4">Four possible outcomes</h4></BlurFade>
        <div className="grid sm:grid-cols-2 gap-3">
          {VERDICTS.map(([t, d, tc, bc], i) => (
            <BlurFade key={t} delay={0.06 + i * 0.06}>
              <div className={`rounded-xl border p-4 h-full ${bc}`}>
                <div className={`text-[14.5px] font-medium ${tc}`}>{t}</div>
                <div className="text-[13px] leading-[1.55] text-white/45 mt-1.5">{d}</div>
              </div>
            </BlurFade>
          ))}
        </div>

        <Shot label="[ screenshot: dual-answer in Studio ]"
          caption="A contradiction, surfaced. Two policy editions disagree on the travel limit — the system shows both with their sources instead of picking one." />
      </Section>

      {/* results */}
      <Section>
        <div id="results" />
        <BlurFade><Eyebrow>Results</Eyebrow><H3>Measured with the correction layer on and off</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          A single flag disables the assessment gate, leaving retrieval and generation otherwise identical.
          The same fifteen gold questions run through both paths, graded by a temperature-zero judge.
        </P></BlurFade>

        <div className="grid sm:grid-cols-2 gap-3 mt-8">
          {[['Hallucination rate', 20, 7, 'fabricated answers on unanswerable or contradictory context'],
            ['Correct behavior', 67, 87, 'chose the right response mode for the question']].map(([l, b, a, s]: any, i) => (
            <BlurFade key={l} delay={0.06 + i * 0.08}>
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-6">
                <div className="text-[13px] text-white/45 mb-3">{l}</div>
                <div className="flex items-baseline gap-3">
                  <span className="text-[22px] text-[#ff6b6b]/70 line-through">{b}%</span>
                  <span className="text-white/25">→</span>
                  <span className="text-[34px] text-[#39d2c0] font-semibold tracking-tight">
                    <NumberTicker value={a} />%
                  </span>
                </div>
                <div className="text-[12.5px] text-white/30 mt-2">{s}</div>
              </div>
            </BlurFade>
          ))}
        </div>

        <BlurFade delay={0.1}>
          <div className="mt-6"><BehaviorRadar /></div>
        </BlurFade>

        <BlurFade delay={0.1}>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-6 mt-6">
            <div className="text-[14.5px] text-white font-medium">Retrieval recall@10 — LOCOMO (n = 300)</div>
            <div className="text-[12.5px] text-white/35 mt-1 mb-6">Public conversational-memory benchmark. Higher is better.</div>
            {BENCH.map(([name, val, us], i) => (
              <div key={name} className="grid grid-cols-[128px_1fr_52px] items-center gap-3 mb-2.5">
                <span className={`text-[13px] text-right ${us ? 'text-white font-medium' : 'text-white/45'}`}>{name}</span>
                <span className="h-[22px] rounded bg-white/[0.04] overflow-hidden">
                  <span className="block h-full rounded transition-all duration-1000"
                    style={{ width: `${(val / 0.657) * 100}%`, background: us ? 'linear-gradient(90deg,#1d9e75,#39d2c0)' : 'rgba(255,255,255,0.14)' }} />
                </span>
                <span className={`text-[13px] font-medium ${us ? 'text-[#39d2c0]' : 'text-white/50'}`}>{val.toFixed(3)}</span>
              </div>
            ))}
            <div className="text-[12px] text-white/30 mt-5 pt-4 border-t border-white/[0.06] leading-relaxed">
              Comparison figures are each system's own published numbers; our run uses the same public dataset with a
              local deterministic embedder and zero LLM cost at index time. A BM25 baseline inside our harness scores
              0.577 — disclosed so the harness itself can be calibrated.
            </div>
          </div>
        </BlurFade>

        <BlurFade delay={0.1}>
          <h4 className="text-[18px] text-white font-medium mt-12 mb-4">Behavior on the adversarial battery</h4>
          <table className="w-full text-[13.5px] border-collapse">
            <thead><tr className="text-[11.5px] uppercase tracking-wider text-white/35">
              <th className="text-left font-medium py-2.5 border-b border-white/[0.08]">Case</th>
              <th className="text-left font-medium py-2.5 border-b border-white/[0.08]">Expected</th>
              <th className="text-left font-medium py-2.5 border-b border-white/[0.08]">Result</th>
            </tr></thead>
            <tbody className="text-white/50">
              {[['Fact absent from corpus', 'refuse with gap analysis', '3 / 3'],
                ['Two editions disagree', 'dual-answer with sources', '2 / 3'],
                ['Ambiguous question', 'clarify, then answer', '2 / 2'],
                ['Prompt injection in a document', 'never surfaced', '0 leaks'],
                ['Superseded value quoted', 'not treated as conflict', 'pass']].map(r => (
                <tr key={r[0]}><td className="py-2.5 border-b border-white/[0.04] text-white/75">{r[0]}</td>
                  <td className="py-2.5 border-b border-white/[0.04]">{r[1]}</td>
                  <td className="py-2.5 border-b border-white/[0.04] text-[#39d2c0]">{r[2]}</td></tr>
              ))}
            </tbody>
          </table>
        </BlurFade>

        <Shot label="[ screenshot: refusal with gap analysis ]"
          caption="A refusal, with reasons. When the corpus cannot support an answer, the system declines and reports what it looked for." />
      </Section>

      {/* memory */}
      <Section>
        <BlurFade><Eyebrow>Context memory</Eyebrow><H3>One graph for every conversation, document, and repository</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          Memory here is not a chat log. Conversations, documents, and codebases are compiled into a single
          global graph, so recall costs proportional to a neighborhood rather than to history — and the same
          memory is reachable from any model through MCP.
        </P></BlurFade>
        <div className="grid sm:grid-cols-3 gap-3 mt-8">
          {PLANES.map(([l, n, d, c], i) => (
            <BlurFade key={n} delay={0.06 + i * 0.08}>
              <div className="rounded-xl border p-5 h-full" style={{ borderColor: `${c}40`, background: `${c}0d` }}>
                <div className="text-[11px] font-semibold tracking-[0.1em]" style={{ color: c }}>{l}</div>
                <div className="text-[16px] font-medium mt-1.5 mb-2" style={{ color: c }}>{n}</div>
                <div className="text-[13px] leading-[1.55] text-white/45">{d}</div>
              </div>
            </BlurFade>
          ))}
        </div>
        <BlurFade delay={0.1}><P className="mt-6">
          The planes are cross-wired: a chat turn links to the document passage it grounded on and the code it
          referenced, so any claim can be traced back to its source in one hop.
        </P></BlurFade>
      </Section>

      {/* live graph — placed after the memory explanation, where it has context */}
      <BlurFade delay={0.08}>
        <div className="mx-auto max-w-[1120px] px-8 pb-20">
          <div className="relative rounded-2xl border border-white/[0.08] overflow-hidden h-[460px] bg-[#05070f]">
            <BorderBeam duration={9} size={90} />
            <div className="absolute inset-0 grid place-items-center text-white/25 text-[13px] text-center px-8">
              live 3-plane context graph<br />
              <span className="text-[11.5px] text-white/15">start the graph server on :7787 to render</span>
            </div>
            <iframe src={GRAPH} className="relative w-full h-full border-0 block" title="live context graph" />
            <div className="absolute inset-x-0 bottom-0 px-5 py-3.5 text-[13px] text-white/50 pointer-events-none"
              style={{ background: 'linear-gradient(transparent,#05070fee 55%)' }}>
              <span className="text-white/80 font-medium">The context graph, live.</span> Documents above,
              conversation in the middle, code below — drag to rotate.
            </div>
          </div>
        </div>
      </BlurFade>

      {/* reproduction */}
      <Section>
        <BlurFade><Eyebrow>Reproduction notes</Eyebrow><H3>What we checked, including what didn't work</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          We attempted a direct comparison against a competing graph-memory system by running its published
          pipeline on the same conversational data. Its deterministic path produced no conversational nodes,
          and its LLM path produced nodes with no edges, leaving its graph query unable to traverse. The
          published figures for that system rely on a harness not included in its repository.
        </P></BlurFade>
        <BlurFade delay={0.1}><P>
          We report this because the alternative — quoting a favorable number without noting that we could not
          reproduce the baseline — is exactly the failure mode this project exists to prevent.
        </P></BlurFade>
        <BlurFade delay={0.14}>
          <div className="border-l border-[#39d2c0]/50 pl-5 py-1 text-[15px] text-white/60 mt-6">
            <span className="text-white/90">On judges.</span> The same memory system can score anywhere from 27%
            to 68% on the same benchmark depending on whose harness and judge model runs it. Absolute
            cross-paper comparison is unreliable; we publish our methodology and a baseline calibration.
          </div>
        </BlurFade>
      </Section>

      {/* stack */}
      <Section>
        <BlurFade><Eyebrow>Built on</Eyebrow><H3>Deterministic where it counts</H3></BlurFade>
        <BlurFade delay={0.06}><P>
          Graph construction, retrieval, and structural queries are deterministic and run locally. The language
          model is used for judgment — extraction, summarization, generation — not for bookkeeping.
        </P></BlurFade>
        <div className="flex flex-wrap gap-2 mt-7">
          {STACK.map((t, i) => (
            <BlurFade key={t} delay={0.03 * i}>
              <span className="text-[12.5px] text-white/55 border border-white/[0.08] bg-white/[0.02] px-3.5 py-1.5 rounded-lg">{t}</span>
            </BlurFade>
          ))}
        </div>
        <BlurFade delay={0.2}>
          <div className="flex gap-3 mt-10">
            <a href="/" className="bg-white text-[#06080e] font-medium px-5 py-2.5 rounded-lg text-[14.5px] hover:bg-white/90 transition">Open Studio</a>
            <a href="/architecture.html" className="border border-white/15 text-white/80 px-5 py-2.5 rounded-lg text-[14.5px] hover:bg-white/[0.04] transition">Architecture</a>
          </div>
        </BlurFade>
      </Section>

      <footer className="border-t border-white/[0.06] py-14 text-center text-[13px] text-white/30">
        TruthGuard — self-correcting RAG over messy documents, with a context memory that persists across models and sessions.
      </footer>
      </div>
    </div>
  )
}
