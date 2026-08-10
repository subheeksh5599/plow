import HeroCanvas from "./HeroCanvas";
import ClientFx from "./ClientFx";

export default function Page() {
  return (
    <>
      <nav>
        <div className="nav-inner">
          <a className="logo" href="#top">
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
            <a className="btn btn-ghost btn-sm" href="https://github.com/subheeksh5599/plow" target="_blank" rel="noopener noreferrer">
              Source
            </a>
            <a className="btn btn-primary btn-sm" href="#demo">
              Live demo
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
            Policy-gated deposits.
            <br />
            <em>Sponsored. Verified. Audited.</em>
          </h1>
          <p className="hero-sub reveal">
            An autonomous agent that scans a wallet, ranks yield venues by live APY, and deposits through
            KeeperHub — policy-gated, gas-sponsored, and verified onchain. The last mile of the scan-to-automate
            funnel, executed.
          </p>
          <div className="hero-ctas reveal">
            <a className="btn btn-primary" href="#demo">
              Live demo
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
              <div className="big-number tnum">0%</div>
              <h3>Idle balances earn nothing</h3>
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
            <h2>Recorded run (Sepolia)</h2>
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
              <span className="dim">✓</span> <span className="purple">read</span> idle WETH&nbsp;&nbsp; <span className="green">0.01</span>{" "}
              @ 0xc558dbdd85…9a3c
              {"\n"}
              <span className="dim">→</span> <span className="purple">rank</span> venues (defillama yields, live)
              {"\n"}
              &nbsp;&nbsp;<span className="yellow">1.</span> Aave V3 (WETH supply)&nbsp;&nbsp;{" "}
              <span className="green">1.43%</span> apy
              {"\n"}
              <span className="dim">$</span> plow deposit --venue aave-v3-weth --amount 0.005
              {"\n"}
              <span className="dim">·</span> <span className="purple">gate</span>&nbsp; venue allowlisted ✓&nbsp; simulate: wouldRevert=false ✓
              {"\n"}
              <span className="dim">·</span> <span className="purple">supply</span> 0.005 → Aave V3&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→{" "}
              <span className="green">sponsored</span> 0x06d9288e…26f
              {"\n"}
              <span className="dim">·</span> <span className="purple">withdraw</span> 0.002&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→{" "}
              <span className="green">sponsored</span> 0x41d8900d…88f
              {"\n"}
              <span className="dim">✓</span> <span className="purple">verify</span> balanceOf = <span className="green">0.003</span> aWETH{" "}
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
            <h2>Execution guarantees</h2>
            <p className="lead">All execution goes through KeeperHub&apos;s direct-execution API; every decision is recorded in the audit trail.</p>
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
              <h4>Agent-callable tools</h4>
              <p>scan_positions, rank_venues, execute_deposit, verify_position — MCP-shaped tools any agent can call, BYOK per org.</p>
            </div>
            <div className="stack-item reveal reveal-d1">
              <div className="mono">idempotency</div>
              <h4>Idempotent retries</h4>
              <p>Stable semantic-intent keys, rotation on retry, chain-verify before re-firing — the sponsor&apos;s own reliability research applied.</p>
            </div>
            <div className="stack-item reveal reveal-d2">
              <div className="mono">defillama</div>
              <h4>Degrade-safe APY feed</h4>
              <p>Rankings come from live yield data with a cache and graceful degradation — a stale feed never produces a stale deposit.</p>
            </div>
          </div>
        </div>
      </section>

      <section id="evidence">
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">Evidence</div>
            <h2>Onchain evidence</h2>
            <p className="lead">Every run lands real sponsored transactions on Sepolia, each verified status 1 on the explorer.</p>
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
                  <td>Scan + rank — live Aave V3 WETH APY</td>
                  <td className="mono">onchain reads</td>
                  <td>
                    <span className="badge">1.43% live</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">02</td>
                  <td>Supply 0.005 WETH → Aave V3</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0x06d9288e821f98adc86128cfc99e941157f6350f59de80df24f0c5597b0f826f" target="_blank" rel="noopener noreferrer">
                      0x06d9288e…26f
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">03</td>
                  <td>Withdraw 0.002 WETH from Aave V3</td>
                  <td className="mono">
                    <a href="https://sepolia.etherscan.io/tx/0x41d8900d160bf3f8accd56c4ea04751de7393bd2df2fff3d22c0f5951d9288f1" target="_blank" rel="noopener noreferrer">
                      0x41d8900d…88f
                    </a>
                  </td>
                  <td>
                    <span className="badge">sponsored</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">04</td>
                  <td>Supply to unlisted venue</td>
                  <td className="mono">zero txs</td>
                  <td>
                    <span className="badge blocked">blocked</span>
                  </td>
                </tr>
                <tr>
                  <td className="mono">05</td>
                  <td>verify_position aWETH read-back</td>
                  <td className="mono">0.003 aWETH</td>
                  <td>
                    <span className="badge">verified</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="evidence-note reveal">All hashes verified status 1 on Blockscout; the sponsored flag is captured per run.</p>
        </div>
      </section>

      <section id="roadmap" style={{ background: "#fafbfe" }}>
        <div className="container">
          <div className="section-head reveal">
            <div className="kicker">Roadmap</div>
            <h2>Status &amp; roadmap</h2>
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
              <div className="phase">Engine</div>
              <div className="what">
                <h4>Multi-chain</h4>
                <p>Chain-abstracted execution (Base Sepolia config-ready); Base demo deposit pending testnet bridge relay.</p>
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
              <div className="logo">Plow</div>
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
