// Session 53: WorkbenchShell 单元测试 — 三栏 + 中栏切换不 unmount 左右
import { describe, it, expect } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkbenchShell } from "./WorkbenchShell";

function Harness() {
  const [page, setPage] = useState("A");
  return (
    <>
      <button data-testid="switch" onClick={() => setPage(page === "A" ? "B" : "A")}>
        switch
      </button>
      <WorkbenchShell
        left={<span data-testid="left-static">L</span>}
        center={<span data-testid={`center-${page}`}>center {page}</span>}
        right={<span data-testid="right-static">R</span>}
      />
    </>
  );
}

describe("WorkbenchShell", () => {
  it("renders 三栏", () => {
    render(<Harness />);
    expect(screen.getByTestId("workbench-left")).toBeDefined();
    expect(screen.getByTestId("workbench-center")).toBeDefined();
    expect(screen.getByTestId("workbench-right")).toBeDefined();
  });

  it("中栏切换不 unmount 左右", async () => {
    render(<Harness />);
    const left = screen.getByTestId("left-static");
    const right = screen.getByTestId("right-static");

    expect(screen.getByTestId("center-A")).toBeDefined();
    await userEvent.click(screen.getByTestId("switch"));
    expect(screen.getByTestId("center-B")).toBeDefined();
    expect(screen.queryByTestId("center-A")).toBeNull();

    // 左右元素引用应保留 (说明未被 unmount 重建)
    expect(screen.getByTestId("left-static")).toBe(left);
    expect(screen.getByTestId("right-static")).toBe(right);
  });
});
