// Session 53: Collapse 单元测试
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Collapse } from "./Collapse";

describe("Collapse", () => {
  it("默认折叠 → body 不渲染", () => {
    render(
      <Collapse title="标题">
        <div data-testid="content">内容</div>
      </Collapse>,
    );
    expect(screen.queryByTestId("collapse-body")).toBeNull();
  });

  it("defaultOpen=true 展开", () => {
    render(
      <Collapse title="标题" defaultOpen>
        <div data-testid="content">内容</div>
      </Collapse>,
    );
    expect(screen.getByTestId("collapse-body")).toBeDefined();
  });

  it("点击切换展开/折叠", async () => {
    render(
      <Collapse title="标题">
        <div data-testid="content">内容</div>
      </Collapse>,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTestId("collapse-toggle-closed"));
    expect(screen.getByTestId("collapse-body")).toBeDefined();
    await user.click(screen.getByTestId("collapse-toggle-open"));
    expect(screen.queryByTestId("collapse-body")).toBeNull();
  });
});
