// Trip report template (LAA design system). Renders the document model in data.json and
// contains no trip content. Colours, type sizes, spacing and radii all come from the theme
// (design tokens) in data.json; edit the theme or the tokens rather than hard-coding values here.

#let data = json("data.json")
#let T = data.theme
#let C = T.colors
#let col(name) = rgb(C.at(name))
#let ink = col("ink")
#let muted = col("ink-muted")
#let brand = col("brand")
#let accent-text = col("accent-text")
#let line-col = col("line")
#let line-strong = col("line-strong")
#let surface = col("surface-000")
#let surface-well = col("surface-200")
#let inverse = col("surface-inverse")
#let on-inverse = col("ink-inverse")
#let sp(name) = T.space.at(name) * 1pt
#let TY(name) = T.type.at(name)

// Text in a token style: a family, size, weight and tracking from tokens.json.
#let sty(name, body, fill: ink, ..extra) = text(
  font: TY(name).typst_family, stretch: TY(name).stretch * 1%, size: TY(name).size * 1pt,
  weight: TY(name).weight, tracking: TY(name).tracking * 1pt, fill: fill, ..extra, body,
)
#let lead(name) = (TY(name).leading - 0.7 * TY(name).size) * 1pt

#let mx = T.page.margin_x_mm * 1mm
#let text-w = (T.page.width_mm - 2 * T.page.margin_x_mm) * 1mm
#let page-w = T.page.width_mm * 1mm
#let page-h = T.page.height_mm * 1mm

#set document(title: data.meta.title, author: data.meta.author)

// ---------------------------------------------------------------- components
// GradeBadge: system in small caps, then the grade exactly as the guidebook writes it.
#let grade-badge(b, inverse-ground: false) = {
  let key = b.key
  let fill = if key { col("action") } else { surface }
  let stroke = 0.75pt + (if key { col("action") } else { line-strong })
  let fg = if key { col("on-action") } else { ink }
  box(height: 18pt, inset: (x: 7.5pt), radius: T.radius.at("radius-pill") * 1pt, fill: fill, stroke: stroke,
    align(horizon, {
      if b.system != "" {
        sty("label", upper(b.system), fill: if key { col("on-action").transparentize(15%) } else { muted },
            size: 7.5pt)
        h(3pt)
      }
      sty("stat", b.grade, fill: fg, size: 9.75pt)
    }))
}

// StatGroup: the numbers that sum up the climb. At most one accent stat.
#let stat-group(items, on-dark: false) = {
  let label-fill = if on-dark { on-inverse.transparentize(30%) } else { muted }
  let value-fill = if on-dark { on-inverse } else { ink }
  let rule = 0.75pt + (if on-dark { on-inverse.transparentize(70%) } else { line-col })
  grid(
    columns: items.map(_ => auto),
    stroke: (x, y) => if x > 0 { (left: rule) } else { none },
    inset: (left: sp("space-6"), right: sp("space-6"), y: 0pt),
    ..items.enumerate().map(((i, it)) => {
      show: block.with(inset: (left: if i == 0 { -sp("space-6") } else { 0pt }))
      stack(spacing: sp("space-1"),
        sty("label", upper(it.label), fill: label-fill),
        {
          sty("stat-xl", it.value, fill: if it.accent { brand } else { value-fill }, features: ("tnum",))
          if it.unit != "" {
            h(2pt)
            sty("stat", it.unit, fill: if on-dark { on-inverse.transparentize(30%) } else { muted },
                size: 15pt, weight: 500)
          }
        },
      )
    }),
  )
}

// The Lithuanian tricolour as the three-band strip (covers only).
#let tricolour() = stack(dir: ttb, spacing: 0pt,
  rect(width: 48 * 0.75pt, height: 4.5pt, fill: col("flag-yellow"), stroke: none),
  rect(width: 48 * 0.75pt, height: 4.5pt, fill: col("flag-green"), stroke: none),
  rect(width: 48 * 0.75pt, height: 4.5pt, fill: col("flag-red"), stroke: none),
)

// ---------------------------------------------------------------- title page
// ReportHeader: photo above, one asphalt block below with the association band, the title,
// grades, outcome and the headline numbers. Nothing is set over the photo.
#page(paper: "a4", margin: 0pt, header: none, footer: none, fill: inverse)[
  #let photo-h = page-h * 0.55
  #box(width: page-w, height: photo-h, clip: true,
    image(data.cover.image, width: page-w, height: photo-h, fit: "cover"))
  #place(top + left, dx: mx, dy: photo-h + sp("space-8"), block(width: text-w, {
    grid(columns: (auto, 1fr), column-gutter: sp("space-4"), align: horizon,
      tricolour(),
      sty("label", upper(data.cover.association + " · " + data.cover.kind), fill: on-inverse))
    v(sp("space-6"))
    sty("label", upper(data.cover.label), fill: on-inverse.transparentize(30%))
    v(sp("space-1"))
    block(sty("display-xl", data.cover.title, fill: on-inverse))
    if data.cover.subtitle != "" {
      v(sp("space-2"))
      sty("subtitle", data.cover.subtitle, fill: on-inverse.transparentize(15%))
    }
    if data.cover.badges.len() > 0 or data.cover.outcome != "" {
      v(sp("space-4"))
      for b in data.cover.badges { grade-badge(b); h(sp("space-2")) }
      if data.cover.outcome != "" {
        sty("body-sm", data.cover.outcome, fill: on-inverse.transparentize(15%))
      }
    }
  }))
  #place(bottom + left, dx: mx, dy: -sp("space-12"), block(width: text-w, stat-group(data.cover.stats, on-dark: true)))
]

// ---------------------------------------------------------------- base styles
#set page(
  paper: "a4", fill: surface,
  margin: (x: mx, top: T.page.margin_top_mm * 1mm, bottom: T.page.margin_bottom_mm * 1mm),
  footer: context {
    grid(columns: (1fr, auto),
      sty("tick", data.meta.title, fill: muted),
      sty("tick", counter(page).display(), fill: muted, features: ("tnum",)))
  },
)
#set text(font: T.fonts.sans, size: TY("body").size * 1pt, weight: TY("body").weight, fill: ink, lang: data.lang,
  hyphenate: true)
#set par(justify: T.text.justify, leading: lead("body"), spacing: sp("space-3"))
#set list(
  marker: box(width: 3pt, height: 3pt, fill: muted, baseline: -0.2pt),
  indent: 0pt, body-indent: sp("space-3"), spacing: sp("space-2"),
)

// Headings: display-l, title, subtitle (sentence case, no numbering).
#show heading.where(level: 1): it => block(above: sp("space-8"), below: sp("space-4"), sticky: true,
  { set par(leading: lead("display-l")); sty("display-l", it.body) })
#show heading.where(level: 2): it => block(above: sp("space-8"), below: sp("space-2"), sticky: true,
  { set par(leading: lead("title")); sty("title", it.body) })

#show figure.caption: it => {
  set par(justify: false)
  sty("body-sm", it.body, fill: muted)
}
#show figure.where(kind: image): set block(breakable: false, above: sp("space-4"), below: sp("space-8"))
#show figure: set align(left)

// ---------------------------------------------------------------- helpers
#let runs(paras) = {
  for (i, para) in paras.enumerate() {
    if i > 0 { parbreak() }
    for r in para {
      let t = text(r.t)
      if r.b and r.i { strong(emph(t)) } else if r.b { strong(t) } else if r.i { emph(t) } else { t }
    }
  }
}

#let lines(s) = {
  for (i, p) in s.split("\n").enumerate() {
    if i > 0 { linebreak() }
    p
  }
}

#let cell-align(a) = if a == "right" { right } else { left }

#let render-table(b) = {
  let cols = b.columns
  let has-header = cols.any(c => c.header != "")
  let body = ()
  for row in b.rows {
    let ci = 0
    for cell in row {
      let is-dict = type(cell) == dictionary
      let span = if is-dict { cell.at("span", default: 1) } else { 1 }
      let is-key = b.at("key_first", default: false) and ci == 0
      if is-dict and cell.at("group", default: false) {
        // a group heading row: name, key grade badge and note
        body.push(table.cell(colspan: span, inset: (x: sp("space-2"), top: sp("space-4"), bottom: sp("space-2")), {
          strong(cell.text)
          if cell.badge != none { h(sp("space-2")); grade-badge(cell.badge) }
          if cell.note != "" { h(sp("space-2")); sty("body-sm", cell.note, fill: muted) }
        }))
      } else if is-dict and cell.at("badge", default: none) != none {
        body.push(table.cell(align: cell-align(cols.at(ci).align) + horizon, grade-badge(cell.badge)))
      } else {
        let txt = if is-dict { cell.text } else { cell }
        let bold = is-dict and cell.at("bold", default: false)
        let content = if is-key { text(fill: accent-text, weight: 600, lines(txt)) } else if bold { strong(lines(txt)) } else { lines(txt) }
        body.push(table.cell(colspan: span, align: cell-align(cols.at(ci).align) + top, content))
      }
      ci += span
    }
  }
  let header = cols.map(c => table.cell(fill: surface-well,
    align: cell-align(c.align) + bottom, sty("label", upper(c.header), fill: muted)))
  block(above: sp("space-3"), below: sp("space-6"), breakable: b.rows.len() > 14, {
    set text(size: TY("body-sm").size * 1pt, features: ("tnum",))
    set par(justify: false, leading: lead("body-sm"))
    table(
      columns: cols.map(c => c.width * 1fr),
      stroke: (x, y) => (bottom: 0.75pt + line-col),
      inset: (x: sp("space-2"), y: sp("space-2") * 0.8),
      column-gutter: 0pt,
      ..if has-header { (table.header(..header),) } else { () },
      ..body,
    )
  })
}

#let render-figure(b) = figure(
  kind: image,
  caption: if b.caption != "" [#b.caption] else { none },
  {
    block(width: 100%, {
      sty("subtitle", b.headline, size: 13.5pt)
      linebreak()
      sty("body-sm", b.subtitle, fill: muted)
    })
    v(sp("space-3"))
    image(b.image, width: 100%)
    v(2pt)
    sty("tick", b.source, fill: muted, font: T.fonts.sans, stretch: 100%, weight: 400)
  },
)

#let render-photo(it) = figure(
  kind: image,
  caption: [#it.caption],
  align(center, if it.h_mm != none {
    image(it.image, width: it.w_mm * 1mm, height: it.h_mm * 1mm, fit: "cover")
  } else {
    image(it.image, width: it.w_mm * 1mm)
  }),
)

// ---------------------------------------------------------------- body
#for b in data.blocks {
  if b.type == "h1" {
    if b.newpage { pagebreak(weak: true) }
    heading(level: 1, b.text)
  } else if b.type == "h2" {
    if b.prefix != "" {
      heading(level: 2, [#sty("label", upper(b.prefix), fill: accent-text) \ #b.text])
    } else {
      heading(level: 2, b.text)
    }
  } else if b.type == "paras" {
    runs(b.paras)
  } else if b.type == "labeled" {
    for item in b.items {
      let label = item.label
      let sep = if label.ends-with(".") or label.ends-with(":") { "" } else { "." }
      block(above: 0pt, below: sp("space-3"))[#strong(label + sep) #runs(item.paras)]
    }
  } else if b.type == "bullets" {
    if b.at("plain", default: false) {
      for item in b.items { par(text(item)) }
    } else {
      v(sp("space-1"))
      list(..b.items.map(i => text(i)))
    }
  } else if b.type == "table" {
    render-table(b)
  } else if b.type == "figure" {
    render-figure(b)
  } else if b.type == "contents" {
    if b.newpage { pagebreak(weak: true) } else { v(sp("space-8"), weak: true) }
    block(below: sp("space-4"), sticky: true, { set par(leading: lead("display-l")); sty("display-l", b.title) })
    show outline.entry: it => block(above: sp("space-3"), it)
    set outline.entry(fill: repeat(text(fill: line-strong)[ · ], gap: 0pt))
    outline(title: none, depth: 1)
  } else if b.type == "photo_pages" {
    for (i, pg) in b.pages.enumerate() {
      if i > 0 { pagebreak(weak: true) }
      for it in pg { render-photo(it) }
    }
  }
}
