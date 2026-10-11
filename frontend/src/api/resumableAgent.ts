import { HttpAgent, runHttpRequest, transformHttpEventStream } from '@ag-ui/client'
import type { RunAgentInput } from '@ag-ui/core'

/**
 * HttpAgent that can re-attach to a reply the server is still producing (or has just finished).
 *
 * The server runs each reply as a run of its own (backend/api/runs.py), so a dropped connection - a phone sent
 * to the background, a network change - does not lose the reply. `connectAgent` fetches `<url>/resume` for the
 * same run id and replays the events from the start; the caller resets what it had drawn before replaying.
 */
export class ResumableAgent extends HttpAgent {
  override connectAgent(...args: Parameters<HttpAgent['connectAgent']>) {
    // runAgent() creates a fresh AbortController per call; connectAgent() does not, and the previous one has
    // usually been aborted already.
    this.abortController = new AbortController()
    return super.connectAgent(...args)
  }

  protected override connect(input: RunAgentInput): ReturnType<HttpAgent['run']> {
    const forwarded = (input.forwardedProps ?? {}) as { agent_id?: string }
    const query = new URLSearchParams({ agent_id: forwarded.agent_id ?? '', run_id: input.runId })
    return transformHttpEventStream(
      runHttpRequest(() =>
        this.fetch(`${this.url}/resume?${query}`, {
          method: 'GET',
          headers: { ...this.headers, Accept: 'text/event-stream' },
          credentials: 'include',
          signal: this.abortController.signal,
        }),
      ),
      this.debugLogger,
    )
  }
}
