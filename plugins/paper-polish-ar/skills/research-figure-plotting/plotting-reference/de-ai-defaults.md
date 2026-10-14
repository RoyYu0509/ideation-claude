# De-AI Defaults — remove unless it earns its place

The decorations a batch-generated plotting script ships by default and a researcher
strips. Each is **OFF by default**: remove it unless it *materially* serves the reader.

Two rules that make this list bite:

- **Apply it, don't wait for it.** These are defaults to enforce on every figure in
  code, not symptoms to notice in the render. Sweep all of them each round.
- **Shared ≠ sanctioned.** A trait present on *every* figure is not thereby a
  convention to preserve. If a rule below targets it, it is a shared **defect** to
  remove from all of them — it OVERRIDES any "stay consistent with the other figures"
  / baseline directive. Consistency never licenses a default-off decoration.

Run against every figure:

- [ ] **Grid on compact line/bar panels** — drop `ax.grid(...)` / the `axes.grid`
  rcParam unless it materially aids quantitative reading. (style-guide.md → Scientific
  communication; iteration-playbook.md → "Mesh grid in a scalar field / image")
- [ ] **Mesh grid / `ax.grid(True)` on images & heatmaps** — remove; contour lines are
  fine when they encode the field. (style-guide.md; iteration-playbook.md, same recipe)
- [ ] **Top & right spines** — hide them
  (`ax.spines[["top", "right"]].set_visible(False)`) unless a full box is needed; never
  leave data flush against the top spine (keep headroom). (style-guide.md → Color, lines,
  uncertainty: "Headroom above bars … never flush against the top spine")
- [ ] **Subplot titles in heterogeneous figures** — drop `ax.set_title(...)`; keep only
  when panels are similar enough that the title aids direct comparison. (style-guide.md →
  Typography; iteration-playbook.md → "Subplot titles in a heterogeneous figure")
- [ ] **Decorative gradients / shadows / 3-D effects** — remove anything that doesn't
  encode data. (style-guide.md → Color, lines, uncertainty)
- [ ] **Redundant double-encoding** — if x-position already identifies the method, don't
  also color by it; reserve color for the main comparison. (style-guide.md, same section)
- [ ] **Off-the-shelf default palette** (`tab10` / `viridis` straight out of the box) —
  pick a palette that encodes the comparison and survives grayscale / CVD. (style-guide.md)
- [ ] **Misleading colorbar `extend` triangles** — drop `extend=` unless clipping is
  intentional and applied to every compared panel. (iteration-playbook.md → "Cbar pointy
  when sibling is flat")

The per-item fix recipe lives in `iteration-playbook.md`; the rationale in `style-guide.md`.
