// Session 54: WorkbenchProvider + useWorkbench
// 跨组件共享 state; 切换 activeStep 不清空 trace/llm/chat
import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type ReactNode,
  type Dispatch,
} from "react";
import { initState, workbenchReducer, type WorkbenchState, type WorkbenchAction } from "./stepWorkbenchReducer";

interface WorkbenchCtx {
  state: WorkbenchState;
  dispatch: Dispatch<WorkbenchAction>;
}

const Ctx = createContext<WorkbenchCtx | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(workbenchReducer, undefined, initState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkbench(): WorkbenchCtx {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error("useWorkbench must be used within WorkbenchProvider");
  }
  return ctx;
}
