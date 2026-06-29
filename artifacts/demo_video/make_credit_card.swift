import AppKit

let avatarInputPath = "artifacts/demo_video/assets/trtd6trtd_icon.png"
let outputPath = "artifacts/demo_video/cards/09_credits.png"
let width: CGFloat = 1280
let height: CGFloat = 720

guard let avatar = NSImage(contentsOfFile: avatarInputPath) else {
    fatalError("Could not open avatar image")
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
    fatalError("Could not create credit bitmap")
}

func drawText(_ text: String, rect: NSRect, size: CGFloat, weight: NSFont.Weight, color: NSColor, alignment: NSTextAlignment = .center, lineSpacing: CGFloat = 8) {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = alignment
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

let rect = NSRect(x: 0, y: 0, width: width, height: height)
NSColor(calibratedRed: 7.0 / 255.0, green: 16.0 / 255.0, blue: 22.0 / 255.0, alpha: 1.0).setFill()
rect.fill()

if let gradient = NSGradient(colors: [
    NSColor(calibratedRed: 0.02, green: 0.12, blue: 0.16, alpha: 1.0),
    NSColor(calibratedRed: 0.03, green: 0.06, blue: 0.08, alpha: 1.0),
]) {
    gradient.draw(in: rect, angle: 315)
}

let avatarSize: CGFloat = 158
let avatarRect = NSRect(x: (width - avatarSize) / 2, y: 438, width: avatarSize, height: avatarSize)
let ringRect = avatarRect.insetBy(dx: -5, dy: -5)

NSColor(calibratedRed: 0.55, green: 0.92, blue: 1.0, alpha: 0.85).setStroke()
let ring = NSBezierPath(ovalIn: ringRect)
ring.lineWidth = 3
ring.stroke()

NSGraphicsContext.saveGraphicsState()
NSBezierPath(ovalIn: avatarRect).addClip()
let cropSide = min(avatar.size.width, avatar.size.height)
let sourceRect = NSRect(
    x: (avatar.size.width - cropSide) / 2,
    y: (avatar.size.height - cropSide) / 2,
    width: cropSide,
    height: cropSide
)
avatar.draw(in: avatarRect, from: sourceRect, operation: .sourceOver, fraction: 1.0)
NSGraphicsContext.restoreGraphicsState()

drawText(
    "@Trtd6Trtd",
    rect: NSRect(x: 0, y: 372, width: width, height: 44),
    size: 32,
    weight: .semibold,
    color: .white
)

drawText(
    "Created with Cerebras × Gemma 4",
    rect: NSRect(x: 0, y: 294, width: width, height: 42),
    size: 34,
    weight: .bold,
    color: NSColor(calibratedWhite: 0.96, alpha: 1.0)
)

drawText(
    "Built during the Gemma 4 Hackathon",
    rect: NSRect(x: 0, y: 246, width: width, height: 36),
    size: 26,
    weight: .medium,
    color: NSColor(calibratedWhite: 0.82, alpha: 0.95)
)

drawText(
    "StackChan Desk Commentator",
    rect: NSRect(x: 0, y: 166, width: width, height: 34),
    size: 23,
    weight: .regular,
    color: NSColor(calibratedRed: 0.64, green: 0.93, blue: 1.0, alpha: 0.95)
)

NSGraphicsContext.restoreGraphicsState()

try FileManager.default.createDirectory(
    atPath: (outputPath as NSString).deletingLastPathComponent,
    withIntermediateDirectories: true
)

guard let data = rep.representation(using: .png, properties: [:]) else {
    fatalError("Could not encode credits PNG")
}
try data.write(to: URL(fileURLWithPath: outputPath))
