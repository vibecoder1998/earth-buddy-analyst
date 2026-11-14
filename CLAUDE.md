# Earth Buddy

Read `SPEC.md` before any work. It is the contract. Each feature's spec is in `docs/`.

- Build in the order of the table in `SPEC.md`. Finish each row's acceptance checks before the next row.
- Code makes every number and verdict. A language model only reads the sentence and writes text from `facts`.
- Every statistical constant lives in `earthbuddy/stats.py` under `T`. Do not repeat a threshold anywhere else.
- A new question kind adds one `ANALYSES` entry and one doc. It adds no `if kind ==` branch in routes or screens.
- Run `pytest` before you say a step is done. Run `python run.py` and try the demo sentences before you say a screen works.
- The prototypes in `~/earth-buddy` and `~/earth-buddy/earth-buddy-analyst` are reference code. Read them for the logic. Copy only the data files that `SPEC.md` lists.
