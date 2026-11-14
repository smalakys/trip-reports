// Trip report template. Renders the document model in data.json; contains no trip content.
// Edit this file (or pass --template) for layout changes; edit the theme for colours and sizes.

#let data = json("data.json")
#let T = data.theme
#let C = T.colors
#let accent = rgb(C.accent)
#let ink = rgb(C.ink)
#let muted = rgb(C.muted)
#let rule-col = rgb(C.rule)
#let surface = rgb(C.surface)

#let mx = T.page.margin_x_mm * 1mm
#let body-pt = T.text.body_pt * 1pt
#let cap-pt = T.text.caption_pt * 1pt
#let small-pt = T.text.small_pt * 1pt
#let text-w = (T.page.width_mm - 2 * T.page.margin_x_mm) * 1mm

#set document(title: data.meta.title, author: data.meta.author)

// ---------------------------------------------------------------- cover
#page(
  paper: "a4", margin: 0pt, header: none, footer: none, fill: ink,
)[
  #image(data.cover.image, width: 100%, height: 100%, fit: "cover")
  #place(bottom, rect(
    width: 100%, height: 72%, stroke: none,
    fill: gradient.linear(
      (ink.transparentize(100%), 0%), (ink.transparentize(45%), 38%), (ink.transparentize(8%), 72%),
      (ink.transparentize(2%), 100%),
      angle: 90deg),
  ))
  #place(top + left, dx: mx, dy: 16mm, rect(width: 14mm, height: 2.2mm, fill: accent, stroke: none))
  #place(bottom + left, dx: mx, dy: -22mm, block(width: text-w, {
    set text(fill: white, font: T.fonts.family)
    if data.cover.kicker != "" {
      text(size: 9pt, weight: "semibold", tracking: 1.4pt, fill: accent, upper(data.cover.kicker))
      v(9pt)
    }
    text(size: 36pt, weight: "bold", tracking: -0.4pt, data.cover.title)
    if data.cover.subtitle != "" {
      v(2pt)
      text(size: 22pt, weight: "light", data.cover.subtitle)
    }
    v(22pt)
    grid(
      columns: (28mm, 1fr), row-gutter: 7pt,
      ..data.cover.meta.map(m => (
        text(size: 8pt, weight: "semibold", fill: white.transparentize(30%), m.k),
        text(size: 9pt, m.v),
      )).flatten(),
    )
  }))
]

// ---------------------------------------------------------------- base styles
#set page(
  paper: "a4",
  margin: (x: mx, top: T.page.margin_top_mm * 1mm, bottom: T.page.margin_bottom_mm * 1mm),
  footer: context {
    set text(size: small-pt, fill: muted)
    align(right)[#data.meta.title #h(14pt) #counter(page).display()]
  },
)
#set text(
  font: T.fonts.family, size: body-pt, fill: ink, lang: data.lang, hyphenate: true,
)
#set par(justify: T.text.justify, leading: T.text.leading_em * 1em, spacing: 0.95em)
#set heading(numbering: "1.1")
#set list(
  marker: box(width: 3pt, height: 3pt, fill: accent, baseline: -0.2pt),
  indent: 0pt, body-indent: 9pt, spacing: 0.55em,
)

#show heading.where(level: 1): it => {
  block(above: 0pt, below: 18pt, sticky: true, {
    if it.numbering != none {
      text(size: 10pt, weight: "semibold", fill: accent, context counter(heading).display(it.numbering))
    } else {
      rect(width: 9mm, height: 1.4pt, fill: accent, stroke: none)
    }
    v(6pt)
    text(size: 26pt, weight: "light", tracking: -0.3pt, it.body)
  })
}
#show heading.where(level: 2): it => block(above: 20pt, below: 9pt, sticky: true, {
  set text(size: 12.5pt, weight: "semibold")
  if it.numbering != none {
    text(fill: muted, weight: "regular", context counter(heading).display(it.numbering))
    h(8pt)
  }
  it.body
})

#show figure.caption: it => {
  set text(size: cap-pt)
  set par(justify: false)
  context [
    #text(weight: "semibold")[#it.supplement #it.counter.display(it.numbering):] #it.body
  ]
}
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set block(breakable: true, above: 14pt, below: 14pt)
#show figure.where(kind: image): set block(breakable: false, above: 8pt, below: 22pt)
#show figure: set align(left)
#show figure.where(kind: table): set figure(supplement: data.labels.table)
#show figure.where(kind: image): set figure(supplement: data.labels.figure)
#set figure.caption(separator: none)

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
  let parts = s.split("\n")
  for (i, p) in parts.enumerate() {
    if i > 0 { linebreak() }
    p
  }
}

#let cell-align(a) = if a == "right" { right } else { left }

#let render-table(b) = {
  let cols = b.columns
  let n = cols.len()
  let rule-stroke = 0.7pt + ink
  let header = cols.map(c => table.cell(align: cell-align(c.align) + bottom, strong(c.header)))
  let body = ()
  for (ri, row) in b.rows.enumerate() {
    let ci = 0
    for cell in row {
      let is-dict = type(cell) == dictionary
      let txt = if is-dict { cell.text } else { cell }
      let bold = (is-dict and cell.at("bold", default: false)) or (b.at("key_first", default: false) and ci == 0)
      let span = if is-dict { cell.at("span", default: 1) } else { 1 }
      let content = if bold { strong(lines(txt)) } else { lines(txt) }
      if is-dict and cell.at("group", default: false) {
        body.push(table.cell(colspan: span, inset: (x: 5pt, top: 11pt, bottom: 4pt), content))
      } else {
        body.push(table.cell(colspan: span, align: cell-align(cols.at(ci).align) + top, content))
      }
      ci += span
    }
    if b.at("total_row", default: false) and ri == b.rows.len() - 2 {
      // rule above the total row is added via hline below
    }
  }
  let tbl = table(
    columns: cols.map(c => c.width * 1fr),
    stroke: none,
    inset: (x: 5pt, y: 5.5pt),
    column-gutter: 4pt,
    table.header(..header, table.hline(stroke: rule-stroke)),
    ..body,
    table.hline(stroke: rule-stroke),
  )
  set text(size: cap-pt, hyphenate: false)
  set par(justify: false, leading: 0.5em)
  if b.caption != none and b.caption != "" {
    figure(kind: table, caption: [#b.caption], tbl)
  } else {
    block(above: 12pt, below: 16pt, breakable: true, tbl)
  }
}

#let render-figure(b) = figure(
  kind: image,
  caption: if b.caption != "" [#b.caption] else { none },
  {
    block(width: 100%, {
      text(size: 13pt, weight: "semibold", b.headline)
      linebreak()
      text(size: 9.5pt, weight: "regular", fill: muted, b.subtitle)
    })
    v(8pt)
    image(b.image, width: 100%)
    v(2pt)
    text(size: small-pt, style: "italic", fill: muted, b.source)
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
    if b.newpage { pagebreak(weak: true) } else { v(30pt, weak: true) }
    heading(level: 1, numbering: if b.numbered { "1.1" } else { none }, b.text)
  } else if b.type == "h2" {
    heading(level: 2, numbering: if b.numbered { "1.1" } else { none }, b.text)
  } else if b.type == "paras" {
    runs(b.paras)
  } else if b.type == "labeled" {
    for item in b.items {
      let label = item.label
      let sep = if label.ends-with(".") or label.ends-with(":") { "" } else { "." }
      block(above: 0pt, below: 0.95em)[#strong(label + sep) #runs(item.paras)]
    }
  } else if b.type == "bullets" {
    if b.at("plain", default: false) {
      for item in b.items { par(hanging-indent: 0pt, text(item)) }
    } else {
      v(4pt)
      list(..b.items.map(i => text(i)))
    }
  } else if b.type == "table" {
    render-table(b)
  } else if b.type == "figure" {
    render-figure(b)
  } else if b.type == "contents" {
    pagebreak(weak: true)
    block(below: 18pt, {
      rect(width: 9mm, height: 1.4pt, fill: accent, stroke: none)
      v(6pt)
      text(size: 26pt, weight: "light", tracking: -0.3pt, b.title)
    })
    show outline.entry.where(level: 1): it => {
      set text(weight: "semibold")
      set block(above: 11pt)
      it
    }
    show outline.entry.where(level: 2): set block(above: 6pt)
    set outline.entry(fill: none)
    outline(title: none, depth: 2, indent: 14pt)
  } else if b.type == "photo_pages" {
    for (i, pg) in b.pages.enumerate() {
      if i > 0 { pagebreak(weak: true) }
      for it in pg { render-photo(it) }
    }
  }
}
