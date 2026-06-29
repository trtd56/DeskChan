import AppKit

let inputPath = "artifacts/demo_video/assets/generated_desk_ai_hero.png"
let outputPath = "artifacts/demo_video/cards/00_hackathon_hero.png"
let width: CGFloat = 1280
let height: CGFloat = 720

guard let source = NSImage(contentsOfFile: inputPath) else {
    fatalError("Could not open \(inputPath)")
}

guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: Int(width),
    pixelsHigh: Int(height),
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fatalError("Could not create output bitmap")
}

func drawText(_ text: String, rect: NSRect, size: CGFloat, weight: NSFont.Weight, color: NSColor, lineSpacing: CGFloat = 10) {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .left
    paragraph.lineSpacing = lineSpacing
    let attributed = NSAttributedString(
        string: text,
        attributes: [
            .font: NSFont.systemFont(ofSize: size, weight: weight),
            .foregroundColor: color,
            .paragraphStyle: paragraph,
        ]
    )
    attributed.draw(with: rect, options: [.usesLineFragmentOrigin, .usesFontLeading])
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

let outputRect = NSRect(x: 0, y: 0, width: width, height: height)
NSColor.black.setFill()
outputRect.fill()

source.draw(in: outputRect, from: NSRect(origin: .zero, size: source.size), operation: .copy, fraction: 1.0)

if let gradient = NSGradient(colors: [
    NSColor(calibratedWhite: 0.0, alpha: 0.78),
    NSColor(calibratedWhite: 0.0, alpha: 0.52),
    NSColor(calibratedWhite: 0.0, alpha: 0.10),
    NSColor(calibratedWhite: 0.0, alpha: 0.00),
]) {
    gradient.draw(in: outputRect, angle: 0)
}

NSColor(calibratedWhite: 0.0, alpha: 0.16).setFill()
outputRect.fill(using: .sourceOver)

drawText(
    "Gemma 4 × Cerebras Hackathon Demo",
    rect: NSRect(x: 88, y: 472, width: 680, height: 36),
    size: 24,
    weight: .medium,
    color: NSColor(calibratedRed: 0.64, green: 0.93, blue: 1.0, alpha: 1.0)
)

drawText(
    "卓上に、\n実況パートナーを。",
    rect: NSRect(x: 84, y: 292, width: 730, height: 170),
    size: 58,
    weight: .bold,
    color: .white,
    lineSpacing: 8
)

drawText(
    "低遅延マルチモーダルAIが、\nデスクの変化に即ツッコミ。",
    rect: NSRect(x: 90, y: 210, width: 680, height: 78),
    size: 29,
    weight: .semibold,
    color: NSColor(calibratedWhite: 0.94, alpha: 1.0),
    lineSpacing: 7
)

drawText(
    "Physical AI / Multiverse Agents",
    rect: NSRect(x: 90, y: 154, width: 560, height: 34),
    size: 22,
    weight: .regular,
    color: NSColor(calibratedWhite: 0.82, alpha: 0.92)
)

NSGraphicsContext.restoreGraphicsState()

try FileManager.default.createDirectory(
    atPath: (outputPath as NSString).deletingLastPathComponent,
    withIntermediateDirectories: true
)

guard let data = rep.representation(using: .png, properties: [:]) else {
    fatalError("Could not encode hero PNG")
}
try data.write(to: URL(fileURLWithPath: outputPath))
