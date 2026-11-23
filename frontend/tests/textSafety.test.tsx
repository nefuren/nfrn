import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Header } from "../src/components/Header";

afterEach(cleanup);

it("ホスト名などの外部データは HTML として解釈されずテキストで出る", () => {
  const evil = '<img src=x onerror="alert(1)">';
  const { container } = render(
    <Header hostname={evil} os={"<script>alert(2)</script>"} status="live" score={50} onLogout={vi.fn()} />,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
  expect(container.textContent).toContain(evil);
  expect(container.textContent).toContain("<script>alert(2)</script>");
});
