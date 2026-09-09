# Troubleshooting

| Symptom | Check |
| --- | --- |
| Shell does not start | Platform/backend selection, interpreter PATH, and startup timeout. |
| Second command rejected | Default `REJECT` policy or scoped reentrancy. |
| Prompt never matches | Program buffering, stream selection, literal bytes, and match-window size. |
| Wait timed out but command runs | Observation deadlines do not own execution. |
| Output incomplete | Tail truncation, file errors, forced cleanup, or drain deadline. |
| Session broken after stop | Forced interruption requires a new session. |
| Sudo authentication fails | Separate password provider, cached credentials, and sudo policy. |

The [troubleshooting guide](https://gokurakujoudo.github.io/shell-next/troubleshooting/)
explains each case. For an issue, include versions, OS/backend, a minimal
reproduction, and sanitized result fields. Remove secrets before posting to
the [issue tracker](https://github.com/gokurakujoudo/shell-next/issues).
