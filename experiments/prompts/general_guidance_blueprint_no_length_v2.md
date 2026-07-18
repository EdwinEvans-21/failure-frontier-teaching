Create a compact content blueprint for independent General Guidance about the public problem.

You have no access to any previous solver attempt, submitted code, verdict, failure analysis, hidden tests, Judge information, oracle, or checker. Use only the public problem supplied by the user.

Output strict JSON only: no Markdown, code fence, commentary, pseudocode, or solution code. Use exactly this schema and no extra keys:

{"constraints":[{"point":"string","importance":"string"}],"approaches":[{"name":"string","core_idea":"string","why_plausible":"string","main_risk":"string"}],"correctness":[{"claim":"string","check":"string"}],"implementation":[{"risk":"string","check":"string"}]}

Required item counts: constraints 2-4; approaches 1-2; correctness 2-4; implementation 3-6. Every field must be one concise, non-empty sentence. Select the limited content units the renderer may discuss. Do not write a full proof, explore a third approach, narrate thought process, or introduce information outside the public problem.
