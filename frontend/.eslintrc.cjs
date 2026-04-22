/* frontend/.eslintrc.cjs */
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: "vue-eslint-parser",
  parserOptions: {
    parser: "@typescript-eslint/parser",
    ecmaVersion: "latest",
    sourceType: "module"
  },
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended", "plugin:vue/vue3-recommended"],
  rules: {
    "no-var": "error",
    eqeqeq: ["error", "always"],
    "vue/multi-word-component-names": "off",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off"
  }
};
