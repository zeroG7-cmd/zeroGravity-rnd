# Reflection: Fusion 360 Assemblies
 
## Comparison
 
| | Bottom-up | Top-down |
|---|---|---|
| Where parts are designed | Separate files | Inside the assembly |
| Best for | Off-the-shelf / existing parts | New custom parts |
| Where you edit a part | Its own file | In the assembly |
| How changes reach the assembly | Update the linked reference | Updates with the shared geometry |
| Reusability | High | Low |
| Main risk | Parts may not fit if not designed against each other | Tangled dependencies |
 
## Fusion how-to
 
**Bottom-up**
- Insert a design from another file: right-click it in the Data Panel > **Insert into Current Design**.
- Inserted parts are **linked references** (chain link icon in the browser).
- When the source file changes, the assembly flags it as out of date. Update it with **Get Latest**.
- To edit a linked part inside the assembly: **Edit in Place**, or **Break Link** to make it a local copy.
**Top-down**
- Browser > **New Component**, then **activate** it (radio button) so new geometry goes into it.
- Sketch on faces of other components, or **Project** their edges into the sketch to reference them.
- Everything lives in one design file and one timeline.
## General
- Every separate part should be its own **component**, not a loose body, or joints won't work.

## In practice: hybrid
 
Most real projects use **both**. Bottom-up for the bought parts, top-down for the custom parts that have to fit around them.
 
**For my digital twin:**
- Components I already have modelled (motors, electronics, other bought parts) → **bottom-up**: insert them into an assembly file.
- Custom parts (frame, mounts, brackets) → **top-down**: design them around the inserted parts.
**Next thing to learn:** **Joints** (and As-built Joints). Inserting components only places them; joints are what actually connect them, define how they move, and stop them floating around.