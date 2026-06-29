import AppKit

struct Subtitle {
    let filename: String
    let text: String
    let fontSize: CGFloat
}

let outputDir = "artifacts/demo_video/subtitles"
try FileManager.default.createDirectory(atPath: outputDir, withIntermediateDirectories: true)

let subtitles = [
    Subtitle(filename: "01_start.png", text: "お、来たな。今日も実況していくで！", fontSize: 34),
    Subtitle(filename: "03_coding.png", text: "コード書き始めたな、がんばれ。", fontSize: 34),
    Subtitle(filename: "05_phone.png", text: "触りすぎちゃう？Xばっか見とらんと、\n仕事仕事！", fontSize: 32),
    Subtitle(filename: "07_danger.png", text: "ストップストップ！それこぼすやつ！", fontSize: 34),
]

let width = 1280
let height = 720
let boxWidth: CGFloat = 1000
let boxHeight: CGFloat = 104
let boxX = (CGFloat(width) - boxWidth) / 2
let boxY: CGFloat = 58

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
    NSColor(calibratedWhite: 0.0, alpha: 0.68).setFill()
    boxPath.fill()
    NSColor(calibratedWhite: 1.0, alpha: 0.16).setStroke()
    boxPath.lineWidth = 1
    boxPath.stroke()

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 7

    let attributed = NSAttributedString(
        string: subtitle.text,
        attributes: [
            .font: NSFont.systemFont(ofSize: subtitle.fontSize, weight: .bold),
            .foregroundColor: NSColor.white,
            .paragraphStyle: paragraph,
        ]
    )
    let textBounds = attributed.boundingRect(
        with: NSSize(width: boxWidth - 80, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    let textRect = NSRect(
        x: boxX + 40,
        y: boxY + (boxHeight - ceil(textBounds.height)) / 2 - 2,
        width: boxWidth - 80,
        height: ceil(textBounds.height) + 8
    )
    attributed.draw(with: textRect, options: [.usesLineFragmentOrigin, .usesFontLeading])

    NSGraphicsContext.restoreGraphicsState()

    guard let data = rep.representation(using: .png, properties: [:]) else {
        fatalError("Could not encode subtitle PNG")
    }
    try data.write(to: URL(fileURLWithPath: "\(outputDir)/\(subtitle.filename)"))
}

for subtitle in subtitles {
    try drawSubtitle(subtitle)
}
