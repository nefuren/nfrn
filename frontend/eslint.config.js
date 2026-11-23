import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const NO_HTML = "外部データは必ずテキストとして表示する（XSS 対策）。HTML を挿入する API は禁止。";

// XSS につながる「文字列を HTML として解釈させる」API をすべて禁止する
const noHtmlInjection = {
  "no-restricted-properties": [
    "error",
    { property: "innerHTML", message: NO_HTML },
    { property: "outerHTML", message: NO_HTML },
    { object: "document", property: "write", message: NO_HTML },
    { object: "document", property: "writeln", message: NO_HTML },
  ],
  "no-restricted-syntax": [
    "error",
    { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: NO_HTML },
    { selector: "CallExpression[callee.property.name='insertAdjacentHTML']", message: NO_HTML },
    { selector: "CallExpression[callee.property.name='createContextualFragment']", message: NO_HTML },
    { selector: "CallExpression[callee.property.name='html']", message: `${NO_HTML}（d3 の .html() も含む。.text() を使う）` },
    { selector: "CallExpression[callee.property.name='parseFromString']", message: NO_HTML },
  ],
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-new-func": "error",
  "no-script-url": "error",
};

export default defineConfig(
  { ignores: ["dist", "node_modules", "coverage"] },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      ...noHtmlInjection,
    },
  },
);
