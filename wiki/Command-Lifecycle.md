# Command lifecycle

| Interface | Ownership |
| --- | --- |
| `run()` | Owns execution through finalized result and cleanup. |
| `command()` | Owns a live handle within an asynchronous context. |
| `submit()` | Returns immediately; the session retains command ownership. |

`wait(wait_timeout=...)` is observation only. Cancelling it or reaching its
deadline does not stop the command. Cancelling `run()`, leaving a command scope
exceptionally, or calling `stop()` requests cleanup. Execution deadlines are
independent from acquisition, preparation, stop, drain, and finalization budgets.

The default concurrency policy rejects a second command. `QUEUE` serializes
submissions in FIFO order. A scoped command owner cannot recursively acquire
the same session. Use separate sessions for independent concurrent execution.

Forced interruption invalidates the persistent shell. There is no automatic
restart because that would lose state silently. Inspect the finalized result's
outcome, backend status, output accounting, and cleanup report before proceeding.

See the [usage guide](https://gokurakujoudo.github.io/shell-next/usage/) for
manual/planned input, file capture, and result checking.
