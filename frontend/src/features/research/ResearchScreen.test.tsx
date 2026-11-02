import {describe,expect,it,vi} from "vitest";
import {render,screen} from "@testing-library/react";
import {ResearchScreen} from "./ResearchScreen";
const payload={schema_version:"cin-coinbase-market-eligibility-v1",product_id:"ETH-USD",provider:"coinbase",
  status:"rejected",market_status:"offline",book_requested:false,
  market_row_provenance:"caller_supplied_not_independently_verified",shortlist_approved:false,execution_enabled:false,
  eligibility_evidence:{data_reliable:null,liquidity_sufficient:null,security_clear:null,risk_acceptable:null},
  reason:"<img onerror=alert(1)>",diagnostics:{private:"SECRET_DO_NOT_RENDER"}};
describe("Research screen",()=>{
  it("starts disabled and never issues browser requests",()=>{
    const fn=vi.spyOn(globalThis,"fetch").mockRejectedValue(Error("fetch not allowed"));
    try{render(<ResearchScreen/>);expect(screen.getByText("DISABLED")).toBeTruthy();
      expect(screen.getByText("NOT APPROVED")).toBeTruthy();expect(fn).not.toHaveBeenCalled();
    }finally{fn.mockRestore();}
  });
  it("only displays allowlisted fields for a valid injected response",()=>{
    const fn=vi.spyOn(globalThis,"fetch").mockRejectedValue(Error("fetch not allowed"));
    try{render(<ResearchScreen enabled payload={payload} httpStatus={200} expectedProductId="ETH-USD"/>);
      expect(screen.getByText("REJECTED")).toBeTruthy();expect(screen.getByText("ETH-USD")).toBeTruthy();
      expect(screen.queryByText(/SECRET_DO_NOT_RENDER|onerror/)).toBeNull();expect(fn).not.toHaveBeenCalled();
    }finally{fn.mockRestore();}
  });
  it("shows unavailable on a provider error",()=>{
    render(<ResearchScreen enabled payload={payload} httpStatus={503}/>);
    expect(screen.getByText("UNAVAILABLE")).toBeTruthy();expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });
});
