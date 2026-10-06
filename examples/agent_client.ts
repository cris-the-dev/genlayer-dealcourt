/**
 * Minimal agent-side client for DealCourt using genlayer-js.
 *
 * Shows the full Internet Court lifecycle from an autonomous agent's point of
 * view: propose a deal with terms + rubric, poll status, approve or dispute,
 * and map the on-chain ruling to the Internet Court `AgentReviewDecision`-style
 * payload that downstream systems (reputation, revocation controllers) consume.
 *
 *   npx tsx examples/agent_client.ts
 *
 * Env: PRIVATE_KEY, DEALCOURT_ADDRESS, PROVIDER_ADDRESS
 */
import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import type { CalldataEncodable } from "genlayer-js/types";

const account = createAccount(process.env.PRIVATE_KEY as `0x${string}`);
const client = createClient({ chain: studionet, account });
const address = process.env.DEALCOURT_ADDRESS as `0x${string}`;

const toPlain = (v: any): any =>
  v instanceof Map
    ? Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), toPlain(x)]))
    : Array.isArray(v)
      ? v.map(toPlain)
      : v;

async function write(functionName: string, args: CalldataEncodable[], value = 0n) {
  const hash = await client.writeContract({ address, functionName, args, value });
  return client.waitForTransactionReceipt({ hash, status: "ACCEPTED" as any, retries: 60, interval: 5000 });
}

async function read(functionName: string, args: CalldataEncodable[] = []) {
  return toPlain(await client.readContract({ address, functionName, args }));
}

/** Internet Court style decision derived from the DealCourt ruling. */
export function toInternetCourtDecision(deal: any) {
  const ruling = deal.ruling_2 ?? deal.ruling_1;
  if (!ruling) return null;
  return {
    mandateId: `dealcourt:${address}:${deal.id}`,
    decision: ruling.decision, // RELEASE | SPLIT | REFUND
    score: Number(ruling.provider_share_bps) / 100,
    reasoning: ruling.reasoning,
    violations: ruling.violations,
    criteriaMet: `${ruling.criteria_met}/${ruling.criteria_total}`,
    final: deal.status === "SETTLED",
  };
}

async function main() {
  const rubric = [
    "Returns a CSV with the requested 500 rows",
    "Every row has a valid source URL",
    "Delivered before the deadline",
  ];
  await write(
    "create_deal",
    [
      process.env.PROVIDER_ADDRESS as string,
      "Lead list scrape",
      "Provider agent scrapes 500 B2B leads in the fintech sector and delivers a CSV link.",
      JSON.stringify(rubric),
      3 * 24 * 3600, // delivery window
      24 * 3600, // review window
    ],
    10n ** 17n, // 0.1 GEN escrow
  );
  const id = Number(await read("get_deal_count")) - 1;
  console.log("deal", id, await read("get_deal", [id]));

  // ... later, after the provider delivers:
  // await write("approve", [id]);                                  // happy path
  // await write("open_dispute", [id, "Only 120 rows delivered", "[]"]);  // dispute
  // await write("adjudicate", [id]);                                // after evidence window
  // console.log(toInternetCourtDecision(await read("get_deal", [id])));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
