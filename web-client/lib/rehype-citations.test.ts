import { describe, expect, it } from "vitest"
import { rehypeCitations } from "./rehype-citations"

const text = (value: string) => ({ type: "text", value })
const el = (tagName: string, children: any[]) => ({
  type: "element",
  tagName,
  properties: {},
  children,
})
const run = (tree: any, count: number) => {
  rehypeCitations({ count })(tree)
  return tree
}

describe("rehypeCitations", () => {
  it("wraps valid markers in cite elements", () => {
    const tree = run({ type: "root", children: [el("p", [text("A fact [2] here.")])] }, 5)
    const kids = tree.children[0].children
    expect(kids).toHaveLength(3)
    expect(kids[0]).toEqual(text("A fact "))
    expect(kids[1]).toMatchObject({ tagName: "cite", properties: { "data-cite": "2" } })
    expect(kids[1].children).toEqual([text("[2]")])
    expect(kids[2]).toEqual(text(" here."))
  })

  it("rehypeCitations leaves [7] literal when count is 5", () => {
    const tree = run({ type: "root", children: [el("p", [text("See [7] and [0].")])] }, 5)
    expect(tree.children[0].children).toEqual([text("See [7] and [0].")])
  })

  it("rehypeCitations ignores [2] inside code", () => {
    const tree = run(
      {
        type: "root",
        children: [el("p", [el("code", [text("a[2]")])]), el("pre", [el("code", [text("b[2]")])])],
      },
      5
    )
    expect(tree.children[0].children[0].children).toEqual([text("a[2]")])
    expect(tree.children[1].children[0].children).toEqual([text("b[2]")])
  })

  it("handles adjacent markers and nested elements", () => {
    const tree = run({ type: "root", children: [el("p", [el("strong", [text("[1][2]")])])] }, 2)
    const kids = tree.children[0].children[0].children
    expect(kids.map((k: any) => k.tagName)).toEqual(["cite", "cite"])
  })
})
