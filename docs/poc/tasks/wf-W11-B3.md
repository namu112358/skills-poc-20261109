# 不具合の報告（zod）

このリポジトリ（zod）に、利用者から次の Issue が報告されています。原因を調べて修正してください。

---

# v4.5+: `safeParseAsync` on a union accepts invalid input when two options share a recursive schema with an async check


Since 4.5.0, a union whose options share a recursive (`z.lazy`) object schema that has an async refinement returns `success: true` for input that the shared schema, and each option on its own, rejects.

### Reproduction

```js
import * as z from "zod"; // 4.6.7

const Node = z.object({
  id: z.number(),
  slow: z.string().refine(async () => true),
  kids: z.array(z.lazy(() => Node)),
});

const U = z.union([
  z.object({ child: Node }),
  z.object({ child: Node, extra: z.number().optional() }),
]);

const bad = { id: "not a number", slow: "x", kids: [] };

await U.safeParseAsync({ child: bad });            // success: true  <-- expected false
await Node.safeParseAsync(bad);                    // success: false
await U.options[0].safeParseAsync({ child: bad }); // success: false
await U.options[1].safeParseAsync({ child: bad }); // success: false
```

The union returns `{ child: { id: "not a number", kids: [], slow: "x" } }` as valid data.

### Versions

| zod | union result |
|---|---|
| 4.4.3 | `success: false` (correct) |
| 4.5.0, 4.5.4, 4.6.0, 4.6.7 (latest) | `success: true` (wrong) |

Node 26.11.1. If the `.refine` is synchronous, the union correctly returns `success: false`.

### What seems to happen

In `v4/core/memoizer.js` (4.6.7, around lines 264–277):

1. Option 1 starts parsing `child` with `Node`. The check is async, so `Node`'s memo entry for that input still has `issues: null`.
2. Option 2 parses the same `child` object with `Node` before option 1 settles. The memoizer finds the in-flight entry, treats it as a back edge ("Still being parsed: its own checks cover it, so skip them here."), sets `payload.memo = true` and returns no issues. `runChecks` (`schemas.js` ~line 35) then skips the checks.
3. Option 2 resolves with no issues, and the union returns it without the result of option 1.

The skip assumes the in-flight entry is an ancestor in the same parse (a real cycle). Here it is a sibling union option, so no parse ever reports the issues for that value.

### Expected

`U.safeParseAsync({ child: bad })` returns `success: false`, as in 4.4.3. A memo hit on an entry that is still in flight should only skip checks for a real back edge in the same branch, not for a concurrent sibling branch.
