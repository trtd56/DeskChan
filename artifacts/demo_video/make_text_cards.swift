import AppKit

struct Card {
    let filename: String
    let text: String
    let fontSize: CGFloat
}

let outputDir = URL(fileURLWithPath: "artifacts/demo_video/cards")
try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

let cards: [Card] = [
    Card(filename: "00_title.png", text: "卓上に、実況パートナーを。", fontSize: 56),
    Card(filename: "02_work.png", text: "まずは、いつもの作業から。", fontSize: 52),
    Card(filename: "04_watch.png", text: "でも、AIはちゃんと見ています。", fontSize: 52),
    Card(filename: "06_risk.png", text: "気づくのは、サボりだけじゃない。", fontSize: 52),
    Card(filename: "08_end.png", text: "見守り、ツッコミ、ときどき警告。\n卓上実況、はじめませんか。", fontSize: 46),
]

let width = 1280
let height = 720
let bg = NSColor(calibratedRed: 7.0 / 255.0, green: 16.0 / 255.0, blue: 22.0 / 255.0, alpha: 1.0)
let fg = NSColor.white

for card in cards {
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        fatalError("Could not create bitmap for \(card.filename)")
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

    bg.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 18

    let font = NSFont.systemFont(ofSize: card.fontSize, weight: .semibold)
    let attributes: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: fg,
        .paragraphStyle: paragraph,
    ]

    let maxTextWidth: CGFloat = 1080
    let attributed = NSAttributedString(string: card.text, attributes: attributes)
    let bounds = attributed.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )

    let drawRect = NSRect(
        x: (CGFloat(width) - maxTextWidth) / 2,
        y: (CGFloat(height) - ceil(bounds.height)) / 2,
        width: maxTextWidth,
        height: ceil(bounds.height) + 8
    )
    attributed.draw(with: drawRect, options: [.usesLineFragmentOrigin, .usesFontLeading])

    NSGraphicsContext.restoreGraphicsState()

    guard let data = rep.representation(using: .png, properties: [:]) else {
        fatalError("Could not encode PNG for \(card.filename)")
    }
    try data.write(to: outputDir.appendingPathComponent(card.filename))
}
