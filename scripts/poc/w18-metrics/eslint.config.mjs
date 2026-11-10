// W18 の lint の警告の数え方（全系列で同じ設定）。typescript-eslint の recommended（型情報なし）と、複雑さの目安。
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/.next/**", "**/node_modules/**", "**/*.d.ts"] },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
    rules: {
      complexity: ["warn", 10],
      "max-depth": ["warn", 4],
      "max-lines-per-function": ["warn", { max: 80, skipBlankLines: true, skipComments: true }],
      "max-params": ["warn", 5],
      "no-console": "warn",
    },
  },
);
