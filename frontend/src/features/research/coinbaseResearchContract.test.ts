import { describe, expect, it } from "vitest";
import { classifyCoinbaseResearch } from "./coinbaseResearchContract";
const valid={
  schema_version:"cin-coinbase-market-eligibility-v1",product_id:"BTC-USD",provider:"coinbase",status:"insufficient_data",
  market_status:"online",book_requested:true,market_row_provenance:"caller_supplied_not_independently_verified",
  shortlist_approved:false,execution_enabled:false,
  eligibility_evidence:{data_reliable:true,liquidity_sufficient:null,security_clear:null,risk_acceptable:null},
  reason:"SECRET_MUST_NOT_APPEAR",diagnostics:{private:"SECRET_TOO"},
};
describe("research response -> UI contract",()=>{
  it("is disabled by default regardless of payload",()=>{
    expect(classifyCoinbaseResearch({enabled:false,payload:valid}).state).toBe("disabled");
  });
  it("handles missing and unavailable responses without implied eligibility",()=>{
    expect(classifyCoinbaseResearch({enabled:true}).state).toBe("unavailable");
    for(const [code,state] of [[404,"disabled"],[429,"rate_limited"],[401,"unavailable"],[403,"unavailable"],[503,"unavailable"],[422,"unavailable"]] as const){
      const v=classifyCoinbaseResearch({enabled:true,payload:valid,httpStatus:code});
      expect(v.state).toBe(state);expect(v.shortlistApproved).toBe(false);expect(v.productId).toBeNull();
    }
  });
  it("maps v1 insufficient data to conservative evidence labels, not raw text",()=>{
    const v=classifyCoinbaseResearch({enabled:true,payload:valid,httpStatus:200,expectedProductId:"BTC-USD"});
    expect(v.state).toBe("insufficient_data");expect(v.evidence.data).toBe("Preliminary only");
    expect(v.evidence.security).toBe("Unknown");expect(v.shortlistApproved).toBe(false);
    expect(v.executionEnabled).toBe(false);expect(JSON.stringify(v)).not.toMatch(/SECRET_/);
  });
  it("renders a rejected market safely",()=>{
    const v=classifyCoinbaseResearch({enabled:true,payload:{...valid,status:"rejected",market_status:"offline"}});
    expect(v.state).toBe("rejected");expect(v.marketStatus).toBe("Reported offline");
  });
  it("fails closed on drift, identity mismatch and optimistic gates",()=>{
    const cases=[
      {schema_version:"v2"},{product_id:"SOL-USD"},{provider:"binance"},{status:"approved"},
      {market_row_provenance:"verified"},{shortlist_approved:true},{execution_enabled:true},
      {book_requested:"true"},{market_status:42},{eligibility_evidence:null},
      {eligibility_evidence:{...valid.eligibility_evidence,data_reliable:"true"}},
      {eligibility_evidence:{...valid.eligibility_evidence,liquidity_sufficient:true}},
      {eligibility_evidence:{...valid.eligibility_evidence,security_clear:true}},
      {eligibility_evidence:{...valid.eligibility_evidence,risk_acceptable:true}},
    ];
    for(const v of cases)expect(classifyCoinbaseResearch({enabled:true,payload:{...valid,...v}}).state).toBe("invalid_contract");
    expect(classifyCoinbaseResearch({enabled:true,payload:valid,expectedProductId:"ETH-USD"}).state).toBe("invalid_contract");
    expect(classifyCoinbaseResearch({enabled:true,payload:[]}).state).toBe("invalid_contract");
  });
});
