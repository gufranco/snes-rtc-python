## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `python3 -m snesrtc.doctor` reports nothing on this machine
- [ ] `conformance/build.py` was run and every pinned state still agrees

## If this changes what the part does

The reference is the authority, and the host machine's clock is not. A change to
what a register reads has to name the model, the register, and the state the
clock was in.

## What it does not carry

- [ ] No cartridge, no save file, and no bytes from either
- [ ] Nothing that says where to obtain them
