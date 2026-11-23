// @vitest-environment node
import { ESLint } from "eslint";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cwd = fileURLToPath(new URL("..", import.meta.url));

async function errors(code: string): Promise<string[]> {
  const eslint = new ESLint({ cwd });
  const [result] = await eslint.lintText(code, { filePath: "src/__probe__.tsx" });
  return (result?.messages ?? []).filter((m) => m.severity === 2).map((m) => m.ruleId ?? "");
}

describe("XSS 対策の lint ルール", () => {
  it.each([
    ["innerHTML", "export const f = (el: HTMLElement, s: string) => { el.innerHTML = s; };"],
    ["outerHTML", "export const f = (el: HTMLElement, s: string) => { el.outerHTML = s; };"],
    ["insertAdjacentHTML", "export const f = (el: HTMLElement, s: string) => el.insertAdjacentHTML('beforeend', s);"],
    ["document.write", "export const f = (s: string) => document.write(s);"],
    ["dangerouslySetInnerHTML", "export const C = ({ s }: { s: string }) => <div dangerouslySetInnerHTML={{ __html: s }} />;"],
    ["d3 .html()", "export const f = (sel: { html(s: string): void }, s: string) => sel.html(s);"],
    ["eval", "export const f = (s: string) => eval(s);"],
  ])("%s を禁止する", async (_name, code) => {
    expect((await errors(code)).length).toBeGreaterThan(0);
  });

  it("textContent と JSX テキストは許可する", async () => {
    const code =
      "export const f = (el: HTMLElement, s: string) => { el.textContent = s; };\n" +
      "export const C = ({ s }: { s: string }) => <div>{s}</div>;";
    expect(await errors(code)).toEqual([]);
  });
});
