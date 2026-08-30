// How many tokens is a 200-word abstract? Measured, not divided (ticket 0140's rule).
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const PKG = '/home/haduong/data/projets/zoteus-bench/0263/tjs-check/';
const require = createRequire(`${PKG}package.json`);
const tjs = await import(pathToFileURL(require.resolve('@huggingface/transformers')).href);

const abstract = `Climate policy assessments increasingly rely on integrated models that couple
energy systems, land use, and macroeconomic feedbacks, yet the uncertainty
propagated through these couplings is rarely quantified in a way decision
makers can use. We develop a probabilistic framework that separates parametric
uncertainty from structural disagreement across fourteen models participating
in a coordinated scenario exercise. Applying the framework to mitigation
pathways consistent with limiting warming to two degrees, we find that
structural disagreement dominates parametric uncertainty for carbon price
trajectories after 2040, while the reverse holds for near-term investment
requirements in the power sector. Regional decomposition shows that the
largest divergences concentrate in projections for emerging economies, where
assumptions about capital costs and discount rates differ most across teams.
We further show that a simple ensemble weighting scheme, calibrated on
historical deployment rates for wind and solar capacity, narrows the projected
range of cumulative investment needs by roughly one third without discarding
any model. The results suggest that reporting conventions for model
intercomparison studies should routinely distinguish the two uncertainty
components, and that calibration against observed technology diffusion offers
a practical, transparent path toward decision-relevant uncertainty ranges in
long-term climate policy analysis and international assessment reports.`;

const words = abstract.split(/\s+/).filter(Boolean).length;
for (const repo of ['Xenova/all-MiniLM-L6-v2', 'Xenova/multilingual-e5-small']) {
  const tok = await tjs.AutoTokenizer.from_pretrained(repo);
  const n = tok(abstract).input_ids.dims.at(-1);
  const specials = tok('').input_ids.dims.at(-1);
  console.log(`${repo}: ${n} tokens incl ${specials} specials -> ${((n - specials) / words).toFixed(2)} tokens/word`);
}
console.log(`words: ${words}`);
