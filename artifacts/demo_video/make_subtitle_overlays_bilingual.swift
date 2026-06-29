import AppKit

struct Subtitle {
    let filename: String
    let ja: String
    let en: String
    let jaSize: CGFloat
    let enSize: CGFloat
}

let outputDir = "artifacts/demo_video/subtitles_bilingual"
try FileManager.default.createDirectory(atPath: outputDir, withIntermediateDirectories: true)

let subtitles = [
    Subtitle(
        filename: "01_start.png",
        ja: "お、来たな。今日も実況していくで！",
        en: "Oh, you're here. I'll be commentating today!",
        jaSize: 29,
        enSize: 24
    ),
    Subtitle(
        filename: "03_coding.png",
        ja: "コード書き始めたな、がんばれ。",
        en: "You started coding. Keep it up.",
        jaSize: 29,
        enSize: 24
    ),
    Subtitle(
        filename: "05_phone.png",
        ja: "触りすぎちゃう？Xばっか見とらんと、仕事仕事！",
        en: "Aren't you on your phone too much?\nStop scrolling X and get back to work!",
        jaSize: 27,
        enSize: 22
    ),
    Subtitle(
        filename: "07_danger.png",
        ja: "ストップストップ！それこぼすやつ！",
        en: "Stop, stop! You're going to spill that!",
        jaSize: 29,
        enSize: 24
    ),
]

let width = 1280
let height = 720
let boxWidth: CGFloat = 1040
let boxHeight: CGFloat = 154
let boxX = (CGFloat(width) - boxWidth) / 2
let boxY: CGFloat = 34

func makeText(_ text: String, size: CGFloat, weight: NSFont.Weight, color: NSColor, lineSpacing: CGFloat) -> NSAttributedString {
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

func drawSubtitle(_ subtitle: Subtitle) throws {
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
        fatalError("Could not create bitmap")
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()

    let boxRect = NSRect(x: boxX, y: boxY, width: boxWidth, height: boxHeight)
    let boxPath = NSBezierPath(roundedRect: boxRect, xRadius: 12, yRadius: 12)
    NSColor(calibratedWhite: 0.0, alpha: 0.70).setFill()
    boxPath.fill()
    NSColor(calibratedWhite: 1.0, alpha: 0.16).setStroke()
    boxPath.lineWidth = 1
    boxPath.stroke()

    let maxTextWidth = boxWidth - 86
    let jaText = makeText(subtitle.ja, size: subtitle.jaSize, weight: .bold, color: .white, lineSpacing: 5)
    let enText = makeText(
        subtitle.en,
        size: subtitle.enSize,
        weight: .semibold,
        color: NSColor(calibratedRed: 0.64, green: 0.93, blue: 1.0, alpha: 0.96),
        lineSpacing: 4
    )
    let jaBounds = jaText.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    let enBounds = enText.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )

    let gap: CGFloat = 13
    let totalHeight = ceil(jaBounds.height) + gap + ceil(enBounds.height)
    let startY = boxY + (boxHeight - totalHeight) / 2 - 2
    let x = boxX + 43
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
        fatalError("Could not encode subtitle PNG")
    }
    try data.write(to: URL(fileURLWithPath: "\(outputDir)/\(subtitle.filename)"))
}

for subtitle in subtitles {
    try drawSubtitle(subtitle)
}
