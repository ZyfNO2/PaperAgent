// Session 53: Button 单元测试 — loading/disabled/click
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("renders label", () => {
    render(<Button>点击</Button>);
    expect(screen.getByTestId("button")).toHaveTextContent("点击");
  });

  it("loading=true → disabled + aria-busy", () => {
    render(<Button loading>加载中</Button>);
    const btn = screen.getByTestId("button");
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });

  it("disabled=true → disabled", () => {
    render(<Button disabled>不可点</Button>);
    expect(screen.getByTestId("button")).toBeDisabled();
  });

  it("click triggers onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>点我</Button>);
    await userEvent.click(screen.getByTestId("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("loading 时点击不触发", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        加载
      </Button>,
    );
    await userEvent.click(screen.getByTestId("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("variant 切换 className", () => {
    const { rerender } = render(<Button variant="primary">P</Button>);
    expect(screen.getByTestId("button").className).toContain("pa-btn--primary");
    rerender(<Button variant="danger">D</Button>);
    expect(screen.getByTestId("button").className).toContain("pa-btn--danger");
  });
});
