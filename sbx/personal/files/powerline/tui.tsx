import { Plugin, usePlugin } from "@opencode/plugin/tui"

const RIGHT = "\ue0b0"
const LEFT = "\ue0b2"
const BRANCH = "\ue0a0"
const RATE_URL = "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?lastNObservations=1&format=sdmx-json"
const RATE_MAX_AGE = 12 * 60 * 60 * 1000

const nok = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK", minimumFractionDigits: 2 })

type Rate = { value: number; date: string; fetched: number }

export default Plugin.define({
  id: "nilsml.powerline",
  setup(context) {
    const [rate, updateRate] = context.storage.store<Rate>("usd-nok", {
      initial: { value: 9.38, date: "reserve", fetched: 0 },
    })

    if (Date.now() - rate.fetched > RATE_MAX_AGE) {
      fetch(RATE_URL)
        .then((response) => response.json())
        .then((json: any) => {
          const series = json.data.dataSets[0].series
          const observations = series[Object.keys(series)[0]].observations
          const value = Number(observations[Object.keys(observations).pop()!][0])
          const date = json.data.structure.dimensions.observation[0].values.at(-1).id
          if (!Number.isFinite(value) || value <= 0) return
          return updateRate((draft) => {
            draft.value = value
            draft.date = date
            draft.fetched = Date.now()
          })
        })
        .catch(() => {})
    }

    const synced = new Set<string>()
    const ensure = (directory: string) => {
      if (synced.has(directory)) return
      synced.add(directory)
      queueMicrotask(() => {
        context.data.location.vcs.sync({ directory }).catch(() => synced.delete(directory))
      })
    }

    context.data.project.sync().catch(() => {})

    return context.ui.slot({
      replace: "prompt.footer",
      render: (input) => (
        <Powerline sessionID={input.sessionID} mode={input.mode} rate={() => rate.value} ensure={ensure} />
      ),
    })
  },
})

function Powerline(props: {
  sessionID?: string
  mode: "normal" | "shell"
  rate: () => number
  ensure: (directory: string) => void
}) {
  const context = usePlugin()
  const theme = () => context.theme

  const session = () => (props.sessionID ? context.data.session.get(props.sessionID) : undefined)
  const directory = () =>
    session()?.location.directory ?? context.location?.directory ?? context.data.location.default()?.directory

  const repo = () => {
    const dir = directory()
    if (!dir) return undefined
    props.ensure(dir)
    const project = session() ? context.data.project.get(session()!.projectID) : undefined
    const name = project?.name ?? (project?.canonical ?? dir).split("/").filter(Boolean).pop() ?? dir
    const branch = context.data.location.vcs.info({ directory: dir })?.branch.current
    return branch ? `${name} ${BRANCH} ${branch}` : name
  }

  const subagents = () => {
    if (!props.sessionID) return undefined
    const id = props.sessionID
    const running = context.data.session
      .family(id)
      .filter((child) => child !== id && context.data.session.status(child) === "running").length
    return running ? `${running} subagent${running === 1 ? "" : "er"}` : undefined
  }

  const tokens = () => {
    const info = session()
    if (!props.sessionID || !info) return undefined
    const messages = context.data.session.message.list(props.sessionID) as any[]
    const revert = info.revert?.messageID
    const end = revert ? messages.findIndex((message) => message.id === revert) : messages.length
    if (end === -1) return undefined
    const compacted = messages.findLastIndex(
      (message, index) => message.type === "compaction" && message.status === "completed" && index < end,
    )
    const last = messages.findLast(
      (message, index) => message.type === "assistant" && message.tokens && index > compacted && index < end,
    )
    if (!last) return undefined
    const t = last.tokens
    const total = t.input + t.output + t.reasoning + t.cache.read + t.cache.write
    if (total <= 0) return undefined
    const model = (context.data.location.model.list(info.location) ?? []).find(
      (item: any) => item.providerID === last.model.providerID && item.id === last.model.id,
    ) as any
    const size = total >= 1_000_000 ? `${(total / 1e6).toFixed(1)}M` : total >= 1000 ? `${(total / 1000).toFixed(1)}K` : `${total}`
    return model?.limit?.context ? `${size} (${Math.round((total / model.limit.context) * 100)}%)` : size
  }

  const cost = () => {
    if (!props.sessionID) return undefined
    const usd = context.data.session.cost(props.sessionID)
    return usd > 0 ? nok.format(usd * props.rate()) : undefined
  }

  const hint = () => {
    if (props.mode === "shell") return "esc avslutt shell"
    const key = context.keymap.shortcuts("command.palette.show")[0]
    return key ? `${key} kommandoer` : undefined
  }

  const accent = () => theme().hue.accent[300]
  const dark = () => theme().background.base
  const mid = () => theme().background.raised.max
  const low = () => theme().background.raised.high
  const text = () => theme().text.base
  const muted = () => theme().text.muted

  return (
    <box flexDirection="row" flexGrow={1} justifyContent="space-between">
      <text wrapMode="none" truncate>
        {repo() ? <span style={{ fg: dark(), bg: accent() }}>{` ${repo()} `}</span> : null}
        {repo() ? <span style={{ fg: accent(), bg: subagents() ? mid() : undefined }}>{RIGHT}</span> : null}
        {subagents() ? <span style={{ fg: text(), bg: mid() }}>{` ${subagents()} `}</span> : null}
        {subagents() ? <span style={{ fg: mid() }}>{RIGHT}</span> : null}
      </text>
      <text wrapMode="none" flexShrink={0}>
        {tokens() ? <span style={{ fg: low() }}>{LEFT}</span> : null}
        {tokens() ? <span style={{ fg: muted(), bg: low() }}>{` ${tokens()} `}</span> : null}
        {cost() ? <span style={{ fg: mid(), bg: tokens() ? low() : undefined }}>{LEFT}</span> : null}
        {cost() ? <span style={{ fg: text(), bg: mid() }}>{` ${cost()} `}</span> : null}
        {hint() ? <span style={{ fg: accent(), bg: cost() ? mid() : tokens() ? low() : undefined }}>{LEFT}</span> : null}
        {hint() ? <span style={{ fg: dark(), bg: accent() }}>{` ${hint()} `}</span> : null}
      </text>
    </box>
  )
}
