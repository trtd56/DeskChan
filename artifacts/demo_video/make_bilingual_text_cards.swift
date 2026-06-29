import AppKit

struct Card {
    let filename: String
    let ja: String
    let en: String
    let jaSize: CGFloat
    let enSize: CGFloat
}

let outputDir = URL(fileURLWithPath: "artifacts/demo_video/cards_bilingual")
try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

let cards: [Card] = [
    Card(
        filename: "02_work.png",
        ja: "まずは、いつもの作業から。",
        en: "First, just the usual work.",
        jaSize: 48,
        enSize: 28
    ),
    Card(
        filename: "04_watch.png",
        ja: "でも、AIはちゃんと見ています。",
        en: "But the AI is watching closely.",
        jaSize: 48,
        enSize: 28
    ),
    Card(
        filename: "06_risk.png",
        ja: "気づくのは、サボりだけじゃない。",
        en: "It notices more than just slacking off.",
        jaSize: 48,
        enSize: 28
    ),
    Card(
        filename: "08_end.png",
        ja: "見守り、ツッコミ、ときどき警告。\n卓上実況、はじめませんか。",
        en: "Watching, teasing, and sometimes warning.\nReady for desk-side commentary?",
        jaSize: 40,
        enSize: 25
    ),
]

let width = 1280
let height = 720
let bg = NSColor(calibratedRed: 7.0 / 255.0, green: 16.0 / 255.0, blue: 22.0 / 255.0, alpha: 1.0)
let jaColor = NSColor.white
let enColor = NSColor(calibratedRed: 0.64, green: 0.93, blue: 1.0, alpha: 0.95)

func attributed(_ text: String, size: CGFloat, weight: NSFont.Weight, color: NSColor, lineSpacing: CGFloat) -> NSAttributedString {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = lineSpacing
    return NSAttributedString(
        string: text,
        attributes: [
            .font: NSFont.systemFont(ofSize: size, weight: weight),
            .foregroundColor: color,
            .paragraphStyle: paragraph,
        ]
    )
}

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

    let maxTextWidth: CGFloat = 1080
    let jaText = attributed(card.ja, size: card.jaSize, weight: .semibold, color: jaColor, lineSpacing: 14)
    let enText = attributed(card.en, size: card.enSize, weight: .medium, color: enColor, lineSpacing: 7)
    let jaBounds = jaText.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    let enBounds = enText.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )

    let gap: CGFloat = 28
    let totalHeight = ceil(jaBounds.height) + gap + ceil(enBounds.height)
    let startY = (CGFloat(height) - totalHeight) / 2
    let x = (CGFloat(width) - maxTextWidth) / 2
    jaText.draw(
        with: NSRect(x: x, y: startY + ceil(enBounds.height) + gap, width: maxTextWidth, height: ceil(jaBounds.height) + 8),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    enText.draw(
        with: NSRect(x: x, y: startY, width: maxTextWidth, height: ceil(enBounds.height) + 8),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )

    NSGraphicsContext.restoreGraphicsState()

    guard let data = rep.representation(using: .png, properties: [:]) else {
        fatalError("Could not encode PNG for \(card.filename)")
    }
    try data.write(to: outputDir.appendingPathComponent(card.filename))
}
