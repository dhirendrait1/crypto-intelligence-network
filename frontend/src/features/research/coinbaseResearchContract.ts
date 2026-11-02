/** CIN staging research response -> read-only dashboard model. No network/credentials. */
export type ResearchState = "disabled"|"unavailable"|"rate_limited"|"invalid_contract"|"rejected"|"insufficient_data";
export interface ResearchView {
  state: ResearchState; label: string; message: string;
  productId: string | null; marketStatus: string; provenance: string;
  evidence: { data: string; liquidity: string; security: string; risk: string };
  shortlistApproved: false; executionEnabled: false;
}
interface Input { enabled: boolean; payload?: unknown; httpStatus?: number|null; expectedProductId?: "BTC-USD"|"ETH-USD" }
const unknownEvidence = () => ({ data:"Unknown",liquidity:"Unknown",security:"Unknown",risk:"Unknown" });
const provenance = "Caller-supplied market row; not independently verified.";
function empty(state: ResearchState, label: string, message: string): ResearchView {
  return { state,label,message,productId:null,marketStatus:"Unknown",provenance,
    evidence:unknownEvidence(),shortlistApproved:false,executionEnabled:false };
}
function object(v:unknown):v is Record<string,unknown> { return v !== null && typeof v==="object" && !Array.isArray(v); }
function tristate(v:unknown):v is boolean|null { return v===null || v===true || v===false; }
/** Raw reason/diagnostics are intentionally never exposed; no positive gate is accepted. */
export function classifyCoinbaseResearch({enabled,payload,httpStatus,expectedProductId}: Input): ResearchView {
  if (!enabled) return empty("disabled","DISABLED","Research display is disabled by default.");
  if (httpStatus!==null && httpStatus!==undefined && httpStatus!==200) {
    if (httpStatus===404) return empty("disabled","NOT MOUNTED","The research route is not mounted.");
    if (httpStatus===429) return empty("rate_limited","RATE LIMITED","Staging request budget exhausted; no automatic retry.");
    return empty("unavailable","UNAVAILABLE","Protected research data is unavailable.");
  }
  if (payload===undefined || payload===null) return empty("unavailable","NOT CONNECTED","No validated research response is connected.");
  if (!object(payload)) return empty("invalid_contract","INVALID CONTRACT","Malformed research response.");
  const p=payload, ev=p.eligibility_evidence;
  const valid=p.schema_version==="cin-coinbase-market-eligibility-v1"
    && p.provider==="coinbase" && (p.product_id==="BTC-USD"||p.product_id==="ETH-USD")
    && (expectedProductId===undefined||p.product_id===expectedProductId)
    && (p.status==="rejected"||p.status==="insufficient_data")
    && p.market_row_provenance==="caller_supplied_not_independently_verified"
    && p.shortlist_approved===false && p.execution_enabled===false
    && typeof p.book_requested==="boolean"
    && (p.market_status===null||typeof p.market_status==="string")
    && object(ev) && tristate(ev.data_reliable) && tristate(ev.liquidity_sufficient)
    && tristate(ev.security_clear) && tristate(ev.risk_acceptable)
    && ev.liquidity_sufficient!==true && ev.security_clear!==true && ev.risk_acceptable!==true;
  if (!valid) return empty("invalid_contract","INVALID CONTRACT","Research schema or safety invariants failed.");
  const e=ev as Record<string,boolean|null>;
  const status=p.status as "rejected"|"insufficient_data";
  return { state:status,label:status==="rejected"?"REJECTED":"INSUFFICIENT DATA",
    message:status==="rejected"?"Research eligibility was rejected.":"Independent evidence is insufficient to approve this market.",
    productId:p.product_id as string, marketStatus:p.market_status==="online"?"Reported online":p.market_status==="offline"?"Reported offline":"Unknown",
    provenance, evidence:{
      data:e.data_reliable===true?"Preliminary only":e.data_reliable===false?"Not met":"Unknown",
      liquidity:e.liquidity_sufficient===false?"Not met":"Unknown",
      security:e.security_clear===false?"Not met":"Unknown",
      risk:e.risk_acceptable===false?"Not met":"Unknown",
    },shortlistApproved:false,executionEnabled:false };
}
