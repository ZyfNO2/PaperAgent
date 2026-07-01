// Session 54: StepWorkbenchPage — 主页面
// ponytail: 切到当前 step → 切回 → Trace/Thought/Chat 引用不丢
import { useWorkbench } from "./WorkbenchProvider";
import { STATUS, STEPS } from "./stepTypes";
import { StepNavigator } from "./components/StepNavigator";
import { StepCard } from "./components/StepCard";
import { StepGate } from "./components/StepGate";
import { EvidenceTrace } from "./components/EvidenceTrace";
import { ThoughtStream } from "./components/ThoughtStream";
import { WorkbenchChat } from "./components/WorkbenchChat";
import { MainStage } from "../../components/layout/MainStage";

interface Props {
  testId?: string;
}

export function StepWorkbenchPage({ testId }: Props) {
  const { state, dispatch } = useWorkbench();
  const idx = state.activeStepIndex;
  const step = state.steps[idx];
  const isPaused = state.streamPhase === "paused";

  return (
    <div data-testid={testId ?? "step-workbench-page"}>
      <MainStage
        title={`Step Workbench${state.demoLoaded ? " · Demo Case" : ""}`}
        stepper={STEPS.map((s) => ({
          key: s.key,
          title: s.title,
          state:
            idx === s.index
              ? "active"
              : state.steps[s.index]?.status === STATUS.COMPLETED
                ? "done"
                : "pending",
        }))}
        testId="wb-stage"
      >
        <StepNavigator
          steps={state.steps}
          activeIndex={idx}
          onSelect={(i) => dispatch({ type: "SET_ACTIVE_STEP", index: i })}
          testId="wb-step-nav"
        />
        <StepGate open={isPaused} stepTitle={step?.title ?? ""} testId="wb-step-gate" />
        <StepCard
          step={step}
          stepIndex={idx}
          isPaused={isPaused}
          onConfirm={() => {
            dispatch({ type: "SET_STEP_STATUS", index: idx, status: STATUS.APPROVED });
            dispatch({
              type: "APPEND_TRACE",
              kind: "user_confirm",
              text: `用户确认 Step ${idx + 1}: ${step?.title}`,
              step: idx,
            });
            dispatch({ type: "SET_STREAM_PHASE", phase: "done" });
          }}
          onRevise={() => {
            dispatch({ type: "SET_STEP_STATUS", index: idx, status: STATUS.NEEDS_REVISION });
            dispatch({
              type: "APPEND_TRACE",
              kind: "step_revise",
              text: `Step ${idx + 1} 需要重跑或修订`,
              step: idx,
            });
          }}
          testId="wb-step-card"
        />
        <WorkbenchChat
          draft={state.chatDraft}
          preview={state.commandPreview}
          messages={state.chat}
          onDraftChange={(v) => dispatch({ type: "SET_CHAT_DRAFT", draft: v })}
          onSubmit={(text) => {
            const t = text.trim();
            dispatch({ type: "ADD_CHAT", msg: { role: "user", text: t } });
            const intent = /^删除|remove/i.test(t)
              ? "remove"
              : /^修改|update/i.test(t)
                ? "modify"
                : /^增加|add/i.test(t)
                  ? "add"
                  : "query";
            dispatch({
              type: "SET_COMMAND_PREVIEW",
              preview: {
                intent,
                description: t,
              },
            });
            dispatch({ type: "APPEND_LLM", kind: "command_preview", text: `预览: ${intent} → ${t}`, step: idx });
            dispatch({ type: "SET_CHAT_DRAFT", draft: "" });
          }}
          onAcceptPreview={() => {
            if (!state.commandPreview) return;
            dispatch({ type: "ADD_CHAT", msg: { role: "system", text: `已应用: ${state.commandPreview.intent}` } });
            dispatch({
              type: "APPEND_TRACE",
              kind: "user_confirm",
              text: `应用 ${state.commandPreview.intent}: ${state.commandPreview.description}`,
              step: idx,
            });
            dispatch({ type: "SET_COMMAND_PREVIEW", preview: null });
          }}
          testId="wb-chat"
        />
      </MainStage>
      <EvidenceTrace events={state.trace} testId="wb-trace" />
      <ThoughtStream events={state.llm} streaming={state.streamPhase === "streaming"} testId="wb-thought" />
    </div>
  );
}
