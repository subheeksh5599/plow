import HeroCanvas from "./HeroCanvas";
import ClientFx from "./ClientFx";

const logo = (
  <span className="logo-mark">
    <svg viewBox="0 0 16 16" fill="none">
      <path d="M2 9.5 7.5 4l3 3L14 3.5" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 12.5h12" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  </span>
);

export default function Page() {
  return (
    <>
      <nav>
        <div className="nav-inner">
          <a className="logo" href="#top">
            {logo}
            Plow
          </a>
          <div className="nav-links">
            <a href="#gap">The gap</a>
            <a href="#how">How it works</a>
            <a href="#demo">Live flow</a>
            <a href="#evidence">Evidence</a>
            <a href="#roadmap">Roadmap</a>
          </div>
          <div className="nav-cta">
            <a className="btn btn-ghost btn-sm" href="#gap">
              Why now
            </a>
            <a className="btn btn-primary btn-sm" href="#how">
              See the flow
            </a>
          </div>
        </div>
      </nav>

      <header className="hero" id="top">
        <div className="hero-bg">
          <div className="orb orb-1" />
          <div className="orb orb-2" />
          <div className="orb orb-3" />
        </div>
        <div className="container hero-inner">
          <h1 className="hero-title reveal">
            Idle stablecoins shouldn&apos;t sit still.
            <br />
            <em>Plow moves them.</em>
          </h1>
          <p className="hero-sub reveal">
            An autonomous agent that scans your wallet, ranks yield venues by live APY, and deposits through
            KeeperHub — policy-gated, gas-sponsored, and verified onchain. The last mile of the scan-to-automate
            funnel, executed.
          </p>
          <div className="hero-ctas reveal">
            <a className="btn btn-primary" href="#demo">
              Watch it run
            </a>
            <a className="btn btn-ghost" href="#how">
              How it works
            </a>
          </div>
          <div className="hero-note reveal">
            Sepolia · sponsored gas · <code>contract-call</code> + <code>MCP</code> + <code>CLI</code>
          </div>
          <div className="reveal">
            <HeroCanvas />
          </div>
        </div>
      </header>

      <section className="quote-strip reveal">
        <div className="container">
          <div className="quote-mark">KeeperHub · specs/scan-apy-yield-suggestions.md</div>
          <div className="quote-text">
            &quot;<span className="hl">Read-only: Yes. No deposit/approve/write node is produced.</span> The
            auto-deposit write path is the deferred Phase 999.1 backlog item and is out of scope here.&quot;
          </div>
        </div>
      </section>

      <section id="gap">
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">The gap</div>
            <h2>Scanners recommend. Nothing executes.</h2>
            <p className="lead">
              Every automation funnel stops at the read. The suggestion engine ranks the venue, shows the APY — and
              then nothing happens. Plow is the write path.
            </p>
          </div>
          <div className="problem-grid">
            <div className="problem-card reveal">
              <div className="p-icon">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <circle cx="9" cy="9" r="7" stroke="#533afd" strokeWidth="1.4" />
                  <path d="M5.5 12.5 12.5 5.5" stroke="#533afd" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </div>
              <div className="big-number tnum">0</div>
              <h3>Write nodes produced</h3>
              <p>
                The sponsor&apos;s own spec defers the deposit path to a backlog item. Read-only by design, so idle
                balances stay idle.
              </p>
            </div>
            <div className="problem-card reveal reveal-d1">
              <div className="p-icon">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 2v14M4 6l5-4 5 4M4 12l5 4 5-4" stroke="#533afd" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div className="big-number tnum">~4%</div>
              <h3>Idle, while venues pay</h3>
              <p>
                Stablecoins parked in wallets earn nothing while the same assets in a supply venue earn live APY. The
                distance between them is one transaction.
              </p>
            </div>
            <div className="problem-card reveal reveal-d2">
              <div className="p-icon">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <rect x="3" y="6" width="12" height="9" rx="1.5" stroke="#533afd" strokeWidth="1.4" />
                  <path d="M6 6V5a3 3 0 0 1 6 0v1" stroke="#533afd" strokeWidth="1.4" />
                </svg>
              </div>
              <div className="big-number tnum">1</div>
              <h3>Decision, gated</h3>
              <p>
                No blind deposits. Every action passes a policy gate — venue allowlist, simulation, exact approvals —
                and every outcome lands in an audit trail.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="how" style={{ background: "#fafbfe" }}>
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">How it works</div>
            <h2>Scan. Rank. Gate. Execute. Verify.</h2>
            <p className="lead">One address in, a deployed yield position out — every step executed through KeeperHub and logged.</p>
          </div>
          <div className="steps">
            <div className="step reveal">
              <h3>Scan</h3>
              <p>Multicall3 reads resolve every stablecoin position across chains — the same methodology as KeeperHub&apos;s scanner.</p>
              <span className="tag">chain reads</span>
            </div>
            <div className="step reveal reveal-d1">
              <h3>Rank</h3>
              <p>Live APY from DefiLlama yields, cached and degrade-safe. No stale numbers — on lookup failure the suggestion degrades gracefully.</p>
              <span className="tag">defillama</span>
            </div>
            <div className="step reveal reveal-d2">
              <h3>Gate</h3>
              <p>The deposit is a proposal, not an order. Venue allowlist, simulate-first, exact approval per KeeperHub&apos;s PREFILL-07. Out of policy — zero transactions.</p>
              <span className="tag">policy gate</span>
            </div>
            <div className="step reveal reveal-d3">
              <h3>Execute · Verify</h3>
              <p>Gas-sponsored contract-call deposits, then balanceOf read-back as onchain proof. Idempotency-aware retries never double-deposit.</p>
              <span className="tag">sponsored + audited</span>
            </div>
          </div>
        </div>
      </section>

      <section id="demo" className="terminal-section">
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">Live flow</div>
            <h2>What a run looks like</h2>
            <p className="lead">The agent in the terminal — no dashboard, no click-through. MCP tools, one intent, executed.</p>
          </div>
          <div className="terminal reveal">
            <div className="term-bar">
              <span className="term-dot r" />
              <span className="term-dot y" />
              <span className="term-dot g" />
              <span className="term-title">plow — scan → rank → gate → deposit</span>
            </div>
            <div className="term-body">
              <span className="dim">$</span> plow scan 0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf --chain sepolia
              {"\n"}
              <span className="dim">✓</span> <span className="purple">read</span> idle USDC&nbsp;&nbsp; <span className="green">18,000.00</span>{" "}
              @ 0x032b4f81…8dd9
              {"\n"}
              <span className="dim">→</span> <span className="purple">rank</span> venues (defillama yields, live)
              {"\n"}
              &nbsp;&nbsp;<span className="yellow">1.</span> Mock Spark&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span className="green">4.03%</span>{" "}
              apy
              {"\n"}
              &nbsp;&nbsp;<span className="yellow">2.</span> Mock Sky Savings&nbsp;&nbsp;&nbsp;&nbsp;{" "}
              <span className="green">3.52%</span> apy
              {"\n"}
              &nbsp;&nbsp;<span className="yellow">3.</span> Mock Aave V3&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{" "}
              <span className="green">3.46%</span> apy
              {"\n"}
              <span className="dim">$</span> plow deposit --venue mock-sky --amount 1000
              {"\n"}
              <span className="dim">·</span> <span className="purple">gate</span>&nbsp; venue allowlisted ✓&nbsp; simulate: wouldRevert=false ✓
              {"\n"}
              <span className="dim">·</span> <span className="purple">approve</span> exact 1,000.00 (no max-uint)&nbsp; →{" "}
              <span className="green">sponsored</span> 0x6724cd07…5a2c
              {"\n"}
              <span className="dim">·</span> <span className="purple">deposit</span> 1,000.00 → mock-sky&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→{" "}
              <span className="green">sponsored</span> 0xc137e53f…e6c8
              {"\n"}
              <span className="dim">✓</span> <span className="purple">verify</span> balanceOf = <span className="green">2,000.00</span> sUSDS{" "}
              · onchain read
              {"\n"}
              <span className="dim">✓</span> <span className="purple">audit</span>&nbsp; {"{decision:ALLOW, gas:sponsored, outcome:landed, ts:…}"}
              {"\n"}
              <span className="green">$</span> <span className="term-cursor" />
            </div>
          </div>
          <p className="evidence-note reveal" style={{ textAlign: "center" }}>
            Illustrative run — same shape as the live demo, with the run&apos;s own hashes in the evidence table below.
          </p>
        </div>
      </section>

      <section className="stack-band">
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker" style={{ color: "#b9b9f9" }}>
              Built on KeeperHub
            </div>
            <h2>Execution with guarantees, not vibes</h2>
            <p className="lead">Every surface KeeperHub ships is used — and the audit trail is the product.</p>
          </div>
          <div className="stack-grid">
            <div className="stack-item reveal">
              <div className="mono">contract-call</div>
              <h4>Sponsored execution</h4>
              <p>Deposits and approvals execute via the direct-execution API with gas sponsorship on testnets — the agent never touches gas math.</p>
            </div>
            <div className="stack-item reveal reveal-d1">
              <div className="mono">policy gate</div>
              <h4>Fail closed</h4>
              <p>Venue allowlist, simulate-first, exact approvals per PREFILL-07. Unverifiable simulation means DENY — never a blind pass-through.</p>
            </div>
            <div className="stack-item reveal reveal-d2">
              <div className="mono">audit trail</div>
              <h4>Every decision logged</h4>
              <p>Trigger, simulation result, tx, gas, sponsored flag, outcome, timestamp — the full audit record behind each deposit.</p>
            </div>
            <div className="stack-item reveal">
              <div className="mono">MCP + CLI</div>
              <h4>Any framework drops in</h4>
              <p>scan_positions, rank_venues, execute_deposit, verify_position — MCP-shaped tools any agent can call, BYOK per org.</p>
            </div>
            <div className="stack-item reveal reveal-d1">
              <div className="mono">idempotency</div>
              <h4>Never double-deposit</h4>
              <p>Stable semantic-intent keys, rotation on retry, chain-verify before re-firing — the sponsor&apos;s own reliability research applied.</p>
            </div>
            <div className="stack-item reveal reveal-d2">
              <div className="mono">defillama</div>
              <h4>Live, degrade-safe APY</h4>
              <p>Rankings come from live yield data with a cache and graceful degradation — a stale feed never produces a stale deposit.</p>
            </div>
          </div>
        </div>
      </section>

      <section id="evidence">
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">Evidence</div>
            <h2>Transactions, not mockups</h2>
            <p className="lead">Every run lands real sponsored transactions on Sepolia, verified onchain. This table fills with the run&apos;s own hashes.</p>
          </div>
          <div className="reveal" style={{ overflowX: "auto" }}>
            <table className="evidence-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Action</th>
                  <th>Tx</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="mono">01</td>
                  <td>Mint 10,000 MockUSDC seed</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0x6bdf4521f682e5deddd93083dd6e8e5a69daa3e2762bf576ebfd2454ca7232b6" target="_blank" rel="noopener noreferrer">
                      0x6bdf4521…32b6
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">02</td>
                  <td>Approve exact 1,000 (PREFILL-07)</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0x6724cd07ffd27000e1c5fe01923c187b17f63215034427cb6703081b38595a2c" target="_blank" rel="noopener noreferrer">
                      0x6724cd07…5a2c
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">03</td>
                  <td>Deposit ALLOW → venue</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0x4fae07dda4e165e910d614456b7fe78a25125c0d71831a44faaa840367fcf326" target="_blank" rel="noopener noreferrer">
                      0x4fae07dd…f326
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">04</td>
                  <td>Deposit ALLOW → venue</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0xc137e53fb1abde2af4bebbd4f2874a6fb9f34872ac5898be4979f7a6e0f1e6c8" target="_blank" rel="noopener noreferrer">
                      0xc137e53f…e6c8
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">05</td>
                  <td>Deposit DENY (out-of-policy venue)</td>
                  <td className="mono">zero txs</td>
                  <td>
                    <span className="badge blocked">blocked</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">06</td>
                  <td>verify_position balanceOf read-back</td>
                  <td className="mono">2,000 sUSDS</td>
                  <td>
                    <span className="badge">verified</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="evidence-note reveal">Hashes land here after the live demo runs — every one Blockscout status 1, sponsored flag captured.</p>
        </div>
      </section>

      <section id="roadmap" style={{ background: "#fafbfe" }}>
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">Roadmap</div>
            <h2>From proof to pipeline</h2>
          </div>
          <ul className="roadmap reveal">
            <li>
              <div className="phase">P0–P3</div>
              <div className="what">
                <h4>Agent core</h4>
                <p>Policy gate, venue contracts on Sepolia, scan + rank engine, gated execution with verification.</p>
              </div>
            </li>
            <li>
              <div className="phase">P4</div>
              <div className="what">
                <h4>MCP + CLI surface</h4>
                <p>Agent-callable tools and a terminal demo path — no dashboard required.</p>
              </div>
            </li>
            <li>
              <div className="phase">P5–P6</div>
              <div className="what">
                <h4>Evidence + README</h4>
                <p>Sponsored demo runs, graph generation from run data, nendo-format README.</p>
              </div>
            </li>
            <li>
              <div className="phase">P7</div>
              <div className="what">
                <h4>Submission</h4>
                <p>Demo video, BUIDL, pitch — every artifact from real runs.</p>
              </div>
            </li>
            <li>
              <div className="phase">Done</div>
              <div className="what">
                <h4>Multi-chain</h4>
                <p>Base Sepolia (84532) scan + sponsored deposit — same policy gate, live evidence.</p>
              </div>
            </li>
            <li>
              <div className="phase">Done</div>
              <div className="what">
                <h4>Schedule + escalation</h4>
                <p>Recurring placement loop (plow_scheduler) and human-in-the-loop resolve (list/resolve_escalation).</p>
              </div>
            </li>
            <li>
              <div className="phase">Next</div>
              <div className="what">
                <h4>Mainnet path</h4>
                <p>Real venue adapters (Sky sUSDS, Ethena sUSDe, Aave V3) config-gated; audit before any real funds.</p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <footer>
        <div className="container">
          <div className="foot-grid">
            <div className="foot-brand">
              <div className="logo">
                {logo}
                Plow
              </div>
              <p>
                The write path for agent-executed yield. Built on KeeperHub&apos;s execution layer — every deposit
                sponsored, gated, and verified.
              </p>
            </div>
            <div className="foot-col">
              <h5>Product</h5>
              <a href="#gap">The gap</a>
              <a href="#how">How it works</a>
              <a href="#demo">Live flow</a>
              <a href="#evidence">Evidence</a>
            </div>
            <div className="foot-col">
              <h5>Built on</h5>
              <a href="https://keeperhub.com" target="_blank" rel="noopener noreferrer">
                KeeperHub
              </a>
              <a href="https://docs.keeperhub.com" target="_blank" rel="noopener noreferrer">
                Docs
              </a>
              <a href="https://github.com/KeeperHub/keeperhub" target="_blank" rel="noopener noreferrer">
                Open source
              </a>
            </div>
            <div className="foot-col">
              <h5>Source</h5>
              <a href="https://github.com/subheeksh5599/plow" target="_blank" rel="noopener noreferrer">
                github.com/subheeksh5599/plow
              </a>
            </div>
          </div>
          <div className="foot-bottom">
            <span>Sepolia testnet · sponsored gas · no real funds</span>
            <span>MIT</span>
          </div>
        </div>
      </footer>

      <ClientFx />
    </>
  );
}
