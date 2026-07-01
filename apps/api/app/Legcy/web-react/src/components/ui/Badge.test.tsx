// Session 53: Badge 单元测试
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("渲染内容", () => {
    render(<Badge>ok</Badge>);
    expect(screen.getByTestId("badge")).toHaveTextContent("ok");
  });

  it("tone 切换 className", () => {
    render(<Badge tone="err">err</Badge>);
    expect(screen.getByTestId("badge").className).toContain("pa-badge--err");
  });
});
